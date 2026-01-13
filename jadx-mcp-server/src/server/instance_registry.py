"""
JADX Instance Registry

Manages connections, status, and health checks for multiple JADX instances.
All instances share a single authentication token.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


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
        }


class InstanceRegistry:
    """JADX Instance Registry (Singleton)"""
    
    _instances: Dict[str, JadxInstance] = {}
    _default_instance: Optional[str] = None
    _shared_auth_token: Optional[str] = None
    _lock = asyncio.Lock()
    
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
        name: str = None
    ) -> dict:
        """
        Add a new JADX instance
        
        Args:
            host: JADX instance IP address
            port: JADX instance port number
            name: Optional custom name. Leave empty to auto-use APK name+version
            
        Returns:
            {"success": bool, "instance": dict, "message": str}
        """
        async with cls._lock:
            try:
                # 1. Connect and fetch /apk-info
                apk_info = await cls._fetch_apk_info(host, port)
                
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
                )
                cls._instances[name] = instance
                
                # 5. If first instance, set as default
                if cls._default_instance is None:
                    cls._default_instance = name
                    logger.info(f"Set default instance: {name}")
                
                logger.info(f"Successfully added JADX instance: {name} ({host}:{port})")
                return {
                    "success": True,
                    "instance": instance.to_dict(),
                    "message": f"Successfully added instance '{name}'",
                }
                
            except Exception as e:
                error_msg = f"Failed to add instance: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "message": error_msg,
                }
    
    @classmethod
    async def _fetch_apk_info(cls, host: str, port: int) -> dict:
        """Fetch APK info from JADX instance"""
        url = f"http://{host}:{port}/apk-info"
        headers = {}
        if cls._shared_auth_token:
            headers["Authorization"] = f"Bearer {cls._shared_auth_token}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    
    @classmethod
    async def _check_health(cls, host: str, port: int) -> bool:
        """Check JADX instance health status"""
        url = f"http://{host}:{port}/health"
        headers = {}
        if cls._shared_auth_token:
            headers["Authorization"] = f"Bearer {cls._shared_auth_token}"
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers=headers)
                return response.status_code == 200
        except Exception:
            return False
    
    @classmethod
    def remove_instance(cls, name: str) -> dict:
        """
        Remove specified JADX instance
        
        Args:
            name: Instance name
            
        Returns:
            {"success": bool, "message": str}
        """
        if name not in cls._instances:
            return {
                "success": False,
                "message": f"Instance '{name}' not found",
            }
        
        del cls._instances[name]
        
        # If removed instance was default, select another
        if cls._default_instance == name:
            cls._default_instance = next(iter(cls._instances), None)
            if cls._default_instance:
                logger.info(f"Default instance changed to: {cls._default_instance}")
        
        logger.info(f"Removed instance: {name}")
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
    def set_default(cls, name: str) -> dict:
        """
        Set default instance
        
        Args:
            name: Instance name
            
        Returns:
            {"success": bool, "message": str}
        """
        if name not in cls._instances:
            return {
                "success": False,
                "message": f"Instance '{name}' not found",
            }
        
        cls._default_instance = name
        logger.info(f"Default instance set to: {name}")
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
        """Get instance by name"""
        return cls._instances.get(name)
    
    @classmethod
    async def health_check_all(cls) -> dict:
        """
        Check health status of all instances
        
        Returns:
            {"total": int, "healthy": int, "instances": [{"name": str, "status": str}]}
        """
        results = []
        healthy_count = 0
        
        for name, instance in cls._instances.items():
            try:
                is_healthy = await cls._check_health(instance.host, instance.port)
                instance.status = "connected" if is_healthy else "disconnected"
                instance.last_health_check = datetime.now()
                if is_healthy:
                    healthy_count += 1
                    instance.error_message = ""
                else:
                    instance.error_message = "Health check failed"
            except Exception as e:
                instance.status = "error"
                instance.error_message = str(e)
            
            results.append({
                "name": name,
                "status": instance.status,
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
