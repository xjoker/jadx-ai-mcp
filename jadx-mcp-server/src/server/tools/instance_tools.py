"""
JADX Instance Management MCP Tools

Provides 6 tools for managing multiple JADX instances:
- list_jadx_instances: List all instances
- add_jadx_instance: Add new instance
- remove_jadx_instance: Remove instance
- set_default_jadx_instance: Set default instance
- get_jadx_instance_info: Get instance details
- health_check_jadx_instances: Check health of all instances
"""

from ..instance_registry import InstanceRegistry


def register_instance_tools(mcp):
    """Register instance management tools to MCP Server"""
    
    @mcp.tool()
    async def list_jadx_instances() -> dict:
        """
        List all connected JADX instances.
        
        Returns name, address, status, and APK info for each instance.
        Use this to understand available analysis targets.
        
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
                        "apk_info": {...}
                    }
                ],
                "count": 1,
                "default_instance": "xhs-v8"
            }
        """
        instances = InstanceRegistry.list_instances()
        default = InstanceRegistry.get_default()
        return {
            "instances": instances,
            "count": len(instances),
            "default_instance": default.name if default else None,
        }
    
    @mcp.tool()
    async def add_jadx_instance(
        host: str,
        port: int,
        name: str = ""
    ) -> dict:
        """
        Dynamically add a new JADX instance connection.
        
        After adding, it will automatically try to connect and fetch APK info.
        If this is the first instance added, it will be set as default.
        
        Args:
            host: JADX instance IP address (e.g., "192.168.1.10" or "localhost")
            port: JADX instance port number (e.g., 8650)
            name: Optional custom name. Leave empty to auto-generate from APK name+version
            
        Returns:
            {
                "success": true,
                "instance": {...},
                "message": "Successfully added instance 'xhs-v8'"
            }
        """
        # Handle localhost
        if host.lower() == "localhost":
            host = "127.0.0.1"
        
        result = await InstanceRegistry.add_instance(host, port, name if name else None)
        return result
    
    @mcp.tool()
    async def remove_jadx_instance(name: str) -> dict:
        """
        Remove specified JADX instance connection.
        
        If removing the default instance, another available instance will be set as new default.
        
        Args:
            name: Name of the instance to remove
            
        Returns:
            {
                "success": true,
                "message": "Removed instance 'xhs-v8'"
            }
        """
        return InstanceRegistry.remove_instance(name)
    
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
        return InstanceRegistry.set_default(name)
    
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
        instance = InstanceRegistry.get_instance(name)
        if not instance:
            return {
                "success": False,
                "message": f"Instance '{name}' not found",
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
