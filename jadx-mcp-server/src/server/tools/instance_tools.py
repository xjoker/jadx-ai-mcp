"""
JADX Instance Management MCP Tools

Provides 7 tools for managing multiple JADX instances:
- list_jadx_instances: List all instances (filtered by user access)
- add_jadx_instance: Add new instance (with user ownership)
- remove_jadx_instance: Remove instance
- set_default_jadx_instance: Set default instance
- get_jadx_instance_info: Get instance details
- health_check_jadx_instances: Check health of all instances
- clear_class_cache: Clear ClassCacheManager cache (30s global cooldown)
"""

from ..instance_registry import InstanceRegistry
from ..user_auth import UserAuthManager
from ..config_loader import get_config_loader
from ..logging_config import get_logger

logger = get_logger("instance_tools")


def register_instance_tools(mcp):
    """Register instance management tools to MCP Server"""
    
    @mcp.tool()
    async def list_jadx_instances() -> dict:
        """
        List all connected JADX instances.
        
        Returns instances visible to the current user:
        - Shared/static instances (from config file)
        - Dynamic instances owned by the current user
        - Admin users can see ALL instances
        
        Returns:
            {
                "instances": [
                    {
                        "name": "xhs-v8",
                        "host": "192.168.1.10",
                        "port": 8650,
                        "url": "http://192.168.1.10:8650",
                        "status": "connected",
                        "is_default": true,
                        "owner": null,
                        "is_dynamic": false,
                        "apk_info": {...}
                    }
                ],
                "count": 1,
                "default_instance": "xhs-v8",
                "current_user": "alice"
            }
        """
        # Get current user from auth context
        user = UserAuthManager.get_current_user()
        username = user.name if user else "anonymous"
        is_admin = user.is_admin if user else False
        
        # Filter instances by user access
        instances = InstanceRegistry.list_instances_for_user(username, is_admin)
        default = InstanceRegistry.get_default()
        
        return {
            "instances": instances,
            "count": len(instances),
            "default_instance": default.name if default else None,
            "current_user": username,
        }
    
    @mcp.tool()
    async def add_jadx_instance(
        host: str,
        port: int,
        name: str = "",
        token: str = ""
    ) -> dict:
        """
        Dynamically add a new JADX instance connection.
        
        After adding, it will automatically try to connect and fetch APK info.
        If this is the first instance added, it will be set as default.
        
        The instance will be owned by the current user (dynamic instance).
        Other users will not see this instance (except admins).
        
        NOTE: This operation requires permission. Admin users can add instances by default.
        Regular users need `can_add_instances: true` in their config, and
        `security.allow_dynamic_instances` must be enabled globally.
        
        Args:
            host: JADX instance IP address (e.g., "192.168.1.10" or "localhost")
            port: JADX instance port number (e.g., 8650)
            name: Optional custom name. Leave empty to auto-generate from APK name+version
            token: Optional JADX plugin authentication token. Uses default if not provided.
            
        Returns:
            {
                "success": true,
                "instance": {...},
                "message": "Successfully added instance 'xhs-v8'"
            }
        """
        # Get current user from auth context
        user = UserAuthManager.get_current_user()
        username = user.name if user else "anonymous"
        
        # === PERMISSION CHECK ===
        # 1. Check global security setting
        config_loader = get_config_loader()
        if config_loader and config_loader.config:
            config = config_loader.config
            allow_global = config.security.allow_dynamic_instances
            
            # 2. Check user permission
            user_config = config.get_user_by_token(user.token) if user and user.token else None
            has_permission = False
            
            if user_config:
                has_permission = user_config.has_add_instances_permission
            elif user and user.is_admin:
                has_permission = True
            
            if not allow_global and not has_permission:
                logger.warning(f"User '{username}' denied add_jadx_instance: permission denied")
                return {
                    "error": "PERMISSION_DENIED",
                    "message": "Dynamic instance creation is disabled. Contact admin to enable 'security.allow_dynamic_instances' or grant 'can_add_instances' permission.",
                    "required_permission": "can_add_instances",
                }
        
        # Handle localhost
        if host.lower() == "localhost":
            host = "127.0.0.1"
        
        # Use default JADX token if not provided
        actual_token = token if token else UserAuthManager.get_default_jadx_token()
        
        logger.info(f"User '{username}' adding instance: {host}:{port}")
        
        result = await InstanceRegistry.add_instance(
            host=host,
            port=port,
            name=name if name else None,
            token=actual_token,
            owner=username,  # Owned by current user
            is_dynamic=True  # Dynamic instance (not from config file)
        )
        return result
    
    @mcp.tool()
    async def remove_jadx_instance(name: str) -> dict:
        """
        Remove specified JADX instance connection.
        
        If removing the default instance, another available instance will be set as new default.
        Users can only remove their own dynamic instances. Admins can remove any instance.
        
        Args:
            name: Name of the instance to remove
            
        Returns:
            {
                "success": true,
                "message": "Removed instance 'xhs-v8'"
            }
        """
        # Get current user from auth context
        user = UserAuthManager.get_current_user()
        username = user.name if user else "anonymous"
        is_admin = user.is_admin if user else False
        
        # Check if user has access to this instance
        instance = InstanceRegistry.get_instance_for_user(name, username, is_admin)
        if not instance:
            return {
                "success": False,
                "message": f"Instance '{name}' not found or you don't have access to it",
            }
        
        # Non-admin users can only remove their own dynamic instances
        if not is_admin and instance.owner != username:
            return {
                "success": False,
                "message": f"You can only remove your own dynamic instances",
            }
        
        return InstanceRegistry.remove_instance(name, username=username, is_admin=is_admin)
    
    @mcp.tool()
    async def set_default_jadx_instance(name: str) -> dict:
        """
        Set the default JADX instance.
        
        Subsequent tool calls without instance_id will use this instance.
        
        Args:
            name: Name of the instance to set as default
            
        Returns:
            {
                "success": true,
                "message": "Default instance set to 'xhs-v8'"
            }
        """
        # Get current user from auth context
        user = UserAuthManager.get_current_user()
        username = user.name if user else "anonymous"
        is_admin = user.is_admin if user else False
        
        return InstanceRegistry.set_default(name, username=username, is_admin=is_admin)
    
    @mcp.tool()
    async def get_jadx_instance_info(name: str) -> dict:
        """
        Get detailed information about a specific instance.
        
        Includes connection status, APK metadata (package, version, SDK, etc.), 
        and last health check time.
        
        Args:
            name: Instance name
            
        Returns:
            {
                "name": "xhs-v8",
                "host": "192.168.1.10",
                "port": 8650,
                "status": "connected",
                "apk_info": {
                    "apk_package": "com.xingin.xhs",
                    "version_name": "8.35.0",
                    "version_code": 8350100,
                    ...
                },
                "last_health_check": "2026-01-12T10:00:00"
            }
        """
        # Get current user from auth context
        user = UserAuthManager.get_current_user()
        username = user.name if user else "anonymous"
        is_admin = user.is_admin if user else False
        
        # Check user access
        instance = InstanceRegistry.get_instance_for_user(name, username, is_admin)
        if not instance:
            return {
                "success": False,
                "message": f"Instance '{name}' not found or you don't have access to it",
            }
        return {
            "success": True,
            **instance.to_dict(),
        }
    
    @mcp.tool()
    async def health_check_jadx_instances() -> dict:
        """
        Check health status of all JADX instances.
        
        Performs health check on each registered instance and updates connection status.
        
        Returns:
            {
                "total": 3,
                "healthy": 2,
                "instances": [
                    {"name": "xhs-v8", "status": "connected"},
                    {"name": "xhs-v9", "status": "disconnected"}
                ]
            }
        """
        return await InstanceRegistry.health_check_all()

    @mcp.tool()
    async def clear_class_cache(instance_id: str = None) -> dict:
        """
        Manually clear the ClassCacheManager cache on the JADX plugin.
        
        IMPORTANT: All cache clear operations share a global 30-second cooldown.
        This includes:
        - rename_class, rename_method, rename_field, rename_package (automatic)
        - This manual clear_class_cache tool
        
        If called within 30 seconds of the last cache clear, the request will be
        debounced and return the remaining cooldown time.
        
        Use this tool when:
        - You suspect stale cache data
        - After manually modifying the APK in JADX
        - After bulk operations that may have affected class data
        
        Args:
            instance_id: Optional. Target JADX instance name. Uses default if not specified.
            
        Returns:
            Success:
                {"success": true, "message": "Class cache cleared successfully", "cooldown_seconds": 30}
            Debounced:
                {"success": false, "message": "Cache clear debounced (30s global cooldown)", "cooldown_remaining_seconds": 25}
        """
        instance = InstanceRegistry.resolve_instance(instance_id)
        if not instance:
            return {"error": f"Instance '{instance_id}' not found or not connected"}
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{instance.url}/cache/clear",
                    headers=instance.get_auth_headers()
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"error": f"Failed to clear cache: {str(e)}"}

