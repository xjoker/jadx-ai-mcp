"""
JADX Instance Registry

Manages connections, status, and health checks for multiple JADX instances.
Supports multi-user isolation with owner-based access control.
"""

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from .logging_config import get_logger

logger = get_logger("registry")

# Timeout configuration (in seconds)
CONNECT_TIMEOUT = 10.0   # Timeout for initial connection/add instance
HEALTH_TIMEOUT = 5.0     # Timeout for health checks (should be fast)


@dataclass
class JadxInstance:
    """JADX instance information"""
    name: str                 # Instance name (user-defined or auto-generated)
    host: str                 # IP address
    port: int                 # Port number
    status: str = "unknown"   # "connected" | "disconnected" | "error"
    apk_info: dict = field(default_factory=dict)  # Info from /apk-info endpoint
    last_health_check: Optional[datetime] = None
    error_message: str = ""   # Most recent error message
    token: str = ""           # Instance-specific JADX plugin token
    owner: Optional[str] = None  # Owner username (None = shared/static)
    is_dynamic: bool = False  # True if added via AI conversation
    registration_source: str = "runtime"  # config | cli | default | ai_dynamic | runtime
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "url": self.url,
            "status": self.status,
            "apk_info": self.apk_info,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "error_message": self.error_message,
            "owner": self.owner,
            "is_dynamic": self.is_dynamic,
            "registration_source": self.registration_source,
        }


class InstanceRegistry:
    """
    JADX Instance Registry (Singleton)

    Thread-safe implementation supporting concurrent access from:
    - Main async event loop (MCP tool calls)
    - Background health monitor thread
    """

    HEALTH_TIMEOUT = HEALTH_TIMEOUT  # Expose for external callers (e.g., HealthMonitor)
    _instances: Dict[str, JadxInstance] = {}
    _default_instance: Optional[str] = None
    _shared_auth_token: Optional[str] = None
    _async_lock = asyncio.Lock()  # For async operations
    _thread_lock = threading.RLock()  # For cross-thread safety
    
    @classmethod
    def set_auth_token(cls, token: str) -> None:
        """Set the shared authentication token for all instances"""
        cls._shared_auth_token = token
        logger.info("Authentication token has been set")
    
    @classmethod
    def get_auth_token(cls) -> Optional[str]:
        """Get the shared authentication token"""
        return cls._shared_auth_token
    
    @classmethod
    async def add_instance(
        cls, 
        host: str, 
        port: int, 
        name: str = None,
        token: str = None,
        owner: str = None,
        is_dynamic: bool = False,
        registration_source: str = "runtime"
    ) -> dict:
        """
        Add a new JADX instance
        
        Args:
            host: JADX instance IP address
            port: JADX instance port number
            name: Optional custom name. Leave empty to auto-use APK name+version
            token: Instance-specific JADX plugin token (uses default if not provided)
            owner: Owner username (None = shared/static instance)
            is_dynamic: True if added via AI conversation
            registration_source: How the instance was added (config/cli/default/ai_dynamic/runtime)
            
        Returns:
            {"success": bool, "instance": dict, "message": str}
        """
        async with cls._async_lock:
            try:
                # Determine the token to use for connection
                actual_token = token or cls._shared_auth_token
                
                # 1. Connect and fetch /apk-info
                apk_info = await cls._fetch_apk_info(host, port, actual_token)
                
                # 2. Determine instance name
                if not name:
                    name = apk_info.get("instance_name") or f"jadx-{port}"
                
                # 3. Check if name already exists
                if name in cls._instances:
                    return {
                        "success": False,
                        "message": f"Instance name '{name}' already exists. Please use a different name",
                    }
                
                # 4. Create and register instance
                instance = JadxInstance(
                    name=name,
                    host=host,
                    port=port,
                    status="connected",
                    apk_info=apk_info,
                    last_health_check=datetime.now(),
                    token=actual_token or "",
                    owner=owner,
                    is_dynamic=is_dynamic,
                    registration_source=registration_source,
                )
                cls._instances[name] = instance
                
                # 5. If first instance, set as default
                if cls._default_instance is None:
                    cls._default_instance = name
                    logger.info(f"Set default instance: {name}")
                
                owner_info = f" (owner: {owner})" if owner else " (shared)"
                logger.info(f"Successfully added JADX instance: {name} ({host}:{port}){owner_info}")
                
                # 6. Version compatibility check
                result = {
                    "success": True,
                    "instance": instance.to_dict(),
                    "message": f"Successfully added instance '{name}'",
                }
                
                plugin_version = apk_info.get("plugin_version", "unknown")
                from src.banner import SERVER_VERSION
                if plugin_version != SERVER_VERSION:
                    version_warning = (
                        f"Version mismatch detected: "
                        f"Plugin={plugin_version}, Server={SERVER_VERSION}. "
                        f"This may cause compatibility issues."
                    )
                    logger.warning(version_warning)
                    result["version_warning"] = version_warning
                
                return result
                
            except Exception as e:
                # Security: log keeps full details, external returns only exception type
                logger.error(f"Failed to add instance: {type(e).__name__}: {e}")
                return {
                    "success": False,
                    "message": f"Failed to add instance: {type(e).__name__}",
                }
    
    @classmethod
    def register_pending_instance(
        cls, 
        name: str,
        host: str, 
        port: int, 
        token: str = None,
        owner: str = None,
        is_dynamic: bool = False,
        registration_source: str = "config"
    ) -> dict:
        """
        Register a JADX instance from config file without requiring immediate connection.
        
        The instance is added with 'pending' status and will be connected
        by the background health monitor when JADX becomes available.
        
        Thread-safe: Uses threading.RLock for cross-thread safety.
        
        Args:
            name: Instance name (required for config instances)
            host: JADX instance IP address
            port: JADX instance port number
            token: Instance-specific JADX plugin token
            owner: Owner username (None = shared/static instance)
            is_dynamic: True if added via AI conversation
            registration_source: How the instance was registered (typically config)
            
        Returns:
            {"success": bool, "message": str}
        """
        with cls._thread_lock:
            if name in cls._instances:
                return {
                    "success": False,
                    "message": f"Instance '{name}' already registered",
                }
            
            actual_token = token or cls._shared_auth_token
            
            instance = JadxInstance(
                name=name,
                host=host,
                port=port,
                status="pending",  # Not yet connected
                apk_info={},
                last_health_check=None,
                token=actual_token or "",
                owner=owner,
                is_dynamic=is_dynamic,
                registration_source=registration_source,
            )
            cls._instances[name] = instance
            
            # If first instance, set as default
            if cls._default_instance is None:
                cls._default_instance = name
            
            owner_info = f" (owner: {owner})" if owner else " (shared)"
            logger.info(f"Registered pending instance: {name} ({host}:{port}){owner_info}")
            
            return {
                "success": True,
                "message": f"Registered instance '{name}' (pending connection)",
            }
    
    @classmethod
    async def _fetch_apk_info(cls, host: str, port: int, token: str = None, timeout: float = None) -> dict:
        """Fetch APK info from JADX instance"""
        url = f"http://{host}:{port}/apk-info"
        headers = {}
        actual_token = token or cls._shared_auth_token
        if actual_token:
            headers["Authorization"] = f"Bearer {actual_token}"

        actual_timeout = timeout if timeout is not None else CONNECT_TIMEOUT
        logger.info(f"Connecting to JADX instance: {url}")
        async with httpx.AsyncClient(timeout=actual_timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Connected to JADX: {data.get('apk_package', 'unknown')} v{data.get('version_name', 'unknown')}")
            return data
    
    @classmethod
    async def _check_health(cls, host: str, port: int) -> bool:
        """Check JADX instance health status"""
        url = f"http://{host}:{port}/health"
        headers = {}
        if cls._shared_auth_token:
            headers["Authorization"] = f"Bearer {cls._shared_auth_token}"

        try:
            async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT) as client:
                response = await client.get(url, headers=headers)
                is_healthy = response.status_code == 200
                logger.debug(f"Health check {host}:{port}: {'OK' if is_healthy else 'FAILED'}")
                return is_healthy
        except Exception as e:
            logger.debug(f"Health check {host}:{port} failed: {e}")
            return False

    @classmethod
    async def _fetch_health_info(cls, host: str, port: int, token: str = None) -> dict:
        """
        Fetch full health info from JADX /health endpoint.

        Returns dict with memory stats, OOM flag, etc.
        Raises on connection failure.
        """
        url = f"http://{host}:{port}/health"
        headers = {}
        actual_token = token or cls._shared_auth_token
        if actual_token:
            headers["Authorization"] = f"Bearer {actual_token}"

        async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    
    @classmethod
    def remove_instance(cls, name: str, username: str = None, is_admin: bool = False) -> dict:
        """
        Remove specified JADX instance (with permission check)
        
        Args:
            name: Instance name
            username: Current user's name (required for permission check)
            is_admin: Whether user is admin
            
        Returns:
            {"success": bool, "message": str}
        """
        if name not in cls._instances:
            return {
                "success": False,
                "message": f"Instance '{name}' not found",
            }
        
        instance = cls._instances[name]
        
        # Permission check: admin can remove any, user can only remove their own dynamic instances
        if not is_admin:
            if instance.owner is None:
                return {
                    "success": False,
                    "message": f"Cannot remove shared instance '{name}'. Only admins can remove shared instances.",
                }
            if instance.owner != username:
                return {
                    "success": False,
                    "message": f"Cannot remove instance '{name}'. You can only remove your own instances.",
                }
        
        # Thread-safe modification
        with cls._thread_lock:
            del cls._instances[name]
            
            # If removed instance was default, select another
            if cls._default_instance == name:
                cls._default_instance = next(iter(cls._instances), None)
                if cls._default_instance:
                    logger.info(f"Default instance changed to: {cls._default_instance}")
        
        owner_info = f" (owner: {instance.owner})" if instance.owner else " (shared)"
        logger.info(f"Removed instance: {name}{owner_info} by user: {username or 'system'}")
        return {
            "success": True,
            "message": f"Removed instance '{name}'",
        }
    
    @classmethod
    def list_instances(cls) -> List[dict]:
        """List all registered instances"""
        instances = [inst.to_dict() for inst in cls._instances.values()]
        for inst in instances:
            inst["is_default"] = inst["name"] == cls._default_instance
        return instances
    
    @classmethod
    def list_instances_for_user(cls, username: str, is_admin: bool = False) -> List[dict]:
        """
        List instances visible to a specific user.
        
        User can see:
        - All shared/static instances (owner=None)
        - Their own dynamic instances (owner=username)
        - Admin can see ALL instances
        
        Args:
            username: Current user's name
            is_admin: Whether user is admin
            
        Returns:
            List of instance dicts the user can access
        """
        result = []
        for inst in cls._instances.values():
            # Admin sees everything
            if is_admin:
                result.append(inst.to_dict())
            # User sees shared instances + their own
            elif inst.owner is None or inst.owner == username:
                result.append(inst.to_dict())
        
        # Mark default instance
        for inst in result:
            inst["is_default"] = inst["name"] == cls._default_instance
        
        return result
    
    @classmethod
    def get_instance_for_user(cls, name: str, username: str, is_admin: bool = False) -> Optional[JadxInstance]:
        """
        Get an instance if the user has access to it.
        
        Args:
            name: Instance name
            username: Current user's name
            is_admin: Whether user is admin
            
        Returns:
            JadxInstance if accessible, None otherwise
        """
        instance = cls._instances.get(name)
        if not instance:
            return None
        
        # Admin can access all
        if is_admin:
            return instance
        
        # User can access shared or their own
        if instance.owner is None or instance.owner == username:
            return instance
        
        return None
    
    @classmethod
    def set_default(cls, name: str, username: str = None, is_admin: bool = False) -> dict:
        """
        Set default instance (with permission check)
        
        Args:
            name: Instance name
            username: Current user's name (required for permission check)
            is_admin: Whether user is admin
            
        Returns:
            {"success": bool, "message": str}
        """
        if name not in cls._instances:
            return {
                "success": False,
                "message": f"Instance '{name}' not found",
            }
        
        instance = cls._instances[name]
        
        # Permission check: user can only set accessible instances as default
        if not is_admin:
            if instance.owner is not None and instance.owner != username:
                return {
                    "success": False,
                    "message": f"Cannot set '{name}' as default. You don't have access to this instance.",
                }
        
        # Thread-safe modification
        with cls._thread_lock:
            cls._default_instance = name
        logger.info(f"Default instance set to: {name} by user: {username or 'system'}")
        return {
            "success": True,
            "message": f"Default instance set to '{name}'",
        }
    
    @classmethod
    def get_default(cls) -> Optional[JadxInstance]:
        """Get default instance"""
        if cls._default_instance and cls._default_instance in cls._instances:
            return cls._instances[cls._default_instance]
        # If no default instance, return first one
        if cls._instances:
            return next(iter(cls._instances.values()))
        return None
    
    @classmethod
    def get_instance(cls, name: str) -> Optional[JadxInstance]:
        """Get instance by name (thread-safe)"""
        with cls._thread_lock:
            return cls._instances.get(name)
    
    @classmethod
    def get_all_instances(cls) -> Dict[str, JadxInstance]:
        """
        Get all registered instances (thread-safe copy for health monitoring).
        
        Returns a copy to prevent modification during iteration.
        """
        with cls._thread_lock:
            return cls._instances.copy()
    
    @classmethod
    def update_instance_status(
        cls, 
        name: str, 
        status: str, 
        apk_info: Optional[dict] = None,
        last_check: Optional[str] = None
    ) -> bool:
        """
        Update instance status (thread-safe).
        
        Used by HealthMonitor from background thread to update instance state.
        
        Args:
            name: Instance name
            status: New status ("connected", "disconnected", "pending")
            apk_info: Optional APK info to update (for newly connected instances)
            last_check: Optional ISO timestamp of health check
        
        Returns:
            True if updated successfully, False if instance not found
        """
        with cls._thread_lock:
            instance = cls._instances.get(name)
            if not instance:
                return False
            
            old_status = instance.status
            instance.status = status
            
            if apk_info is not None:
                instance.apk_info = apk_info
            
            if last_check is not None:
                instance.last_health_check = datetime.fromisoformat(last_check)
            
            if old_status != status:
                logger.info(f"Instance '{name}' status: {old_status} -> {status}")
            
            return True
    
    @classmethod
    async def health_check_all(cls) -> dict:
        """
        Check health status of all instances
        
        Returns:
            {"total": int, "healthy": int, "instances": [{"name": str, "status": str}]}
        """
        results = []
        healthy_count = 0
        
        # Iterate over a copy to avoid RuntimeError if dict changes during iteration
        instances_snapshot = list(cls._instances.items())
        
        for name, instance in instances_snapshot:
            new_status = "unknown"
            error_msg = ""
            old_status = instance.status
            try:
                # Fetch apk_info to also refresh metadata (detect file changes)
                apk_info = await cls._fetch_apk_info(
                    instance.host, instance.port, instance.token,
                    timeout=HEALTH_TIMEOUT
                )
                new_status = "connected"
                error_msg = ""

                # Check OOM/memory via /health (preserve degraded if OOM persists)
                try:
                    health_info = await cls._fetch_health_info(
                        instance.host, instance.port, instance.token
                    )
                    memory = health_info.get("memory", {})
                    if memory.get("oom_detected", False) or memory.get("percent", 0) >= 95:
                        new_status = "degraded"
                        error_msg = "Out of memory"
                except Exception:
                    # /health failed; if previously degraded, keep degraded
                    if old_status == "degraded":
                        new_status = "degraded"

                if new_status != "degraded":
                    healthy_count += 1

                with cls._thread_lock:
                    if name in cls._instances:
                        inst = cls._instances[name]
                        inst.status = new_status
                        inst.apk_info = apk_info
                        inst.last_health_check = datetime.now()
                        inst.error_message = error_msg
            except Exception as e:
                # apk-info failed, fall back to lightweight health check
                try:
                    is_healthy = await cls._check_health(instance.host, instance.port)
                    if is_healthy:
                        # Preserve degraded if previously degraded
                        new_status = "degraded" if old_status == "degraded" else "connected"
                        healthy_count += 1
                        error_msg = ""
                    else:
                        new_status = "disconnected"
                        error_msg = "Health check failed"
                except Exception as he:
                    new_status = "error"
                    error_msg = f"{type(he).__name__}: {str(he) or '(no details)'}"

                with cls._thread_lock:
                    if name in cls._instances:
                        inst = cls._instances[name]
                        inst.status = new_status
                        inst.last_health_check = datetime.now()
                        inst.error_message = error_msg

            results.append({
                "name": name,
                "status": new_status,
            })
        
        return {
            "total": len(cls._instances),
            "healthy": healthy_count,
            "instances": results,
        }
    
    @classmethod
    def get_instance_count(cls) -> int:
        """Get number of registered instances"""
        return len(cls._instances)
    
    @classmethod
    def clear_all(cls) -> None:
        """Clear all instances (for testing)"""
        cls._instances.clear()
        cls._default_instance = None
