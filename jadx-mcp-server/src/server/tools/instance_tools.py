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

import ipaddress

from ..instance_registry import InstanceRegistry
from ..user_auth import UserAuthManager
from ..config_loader import get_config_loader
from ..logging_config import get_logger
from ..types import ErrorCode, make_error

logger = get_logger("instance_tools")

_PRIVATE_IPV4_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
)


def _strip_ip_brackets(host: str) -> str:
    """Normalize bracketed IPv6 literals for address checks."""
    return host.strip().removeprefix("[").removesuffix("]")


def _is_local_address(host: str) -> bool:
    """Allow shared credentials only for localhost and loopback addresses."""
    normalized_host = _strip_ip_brackets(host).lower()
    if normalized_host == "localhost":
        return True

    try:
        return ipaddress.ip_address(normalized_host).is_loopback
    except ValueError:
        return False


def _is_private_network_address(host: str) -> bool:
    """Reject direct RFC1918/link-local IPv4 targets for non-admin users."""
    normalized_host = _strip_ip_brackets(host)
    if _is_local_address(normalized_host):
        return False

    try:
        ip_obj = ipaddress.ip_address(normalized_host)
    except ValueError:
        return False

    if isinstance(ip_obj, ipaddress.IPv4Address):
        return any(ip_obj in network for network in _PRIVATE_IPV4_NETWORKS)

    return False


def register_instance_tools(mcp):
    """Register instance management tools to MCP Server"""
    
    @mcp.tool()
    async def list_jadx_instances() -> dict:
        """List all registered JADX instances with connection status. Does not require a connected instance.

        Returns:
            dict: {instances: [{name, host, port, status, is_default, apk_info}], count, default_instance}
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
        """Dynamically register a new JADX instance. Requires can_add_instances permission for non-admin users.

        Args:
            host: IP address (e.g., "192.168.1.10"). port: Port number (e.g., 8650).
            name: Custom name (auto-generated if empty). token: Auth token (required for non-local hosts).
        Returns:
            dict: {success: bool, instance: {...}, message: str}
        """
        # Get current user from auth context
        user = UserAuthManager.get_current_user()
        username = user.name if user else "anonymous"
        is_admin = user.is_admin if user else False
        host = host.strip()
        
        # === PERMISSION CHECK ===
        config_loader = get_config_loader()
        if config_loader and config_loader.config:
            config = config_loader.config
            allow_global = config.security.allow_dynamic_instances

            user_config = config.get_user_by_token(user.token) if user and user.token else None
            has_permission = user_config.has_add_instances_permission if user_config else False

            if not is_admin:
                if not allow_global:
                    logger.warning(f"User '{username}' denied add_jadx_instance: globally disabled")
                    return make_error(
                        ErrorCode.PERMISSION_DENIED,
                        "Dynamic instance addition is globally disabled",
                    )
                if not has_permission:
                    logger.warning(f"User '{username}' denied add_jadx_instance: missing permission")
                    return make_error(
                        ErrorCode.PERMISSION_DENIED,
                        "User does not have can_add_instances permission",
                        required_permission="can_add_instances",
                    )
        else:
            # No config file — only admin users may add instances
            if not is_admin:
                logger.warning(f"User '{username}' denied add_jadx_instance: no config, non-admin")
                return make_error(
                    ErrorCode.PERMISSION_DENIED,
                    "Dynamic instance creation requires admin privileges when no config file is loaded.",
                )

        if _is_private_network_address(host) and not is_admin:
            logger.warning(f"User '{username}' denied add_jadx_instance: private network target {host}:{port}")
            return make_error(
                ErrorCode.PERMISSION_DENIED,
                "Private network JADX instances can only be added by administrators",
            )

        if not _is_local_address(host) and not token:
            logger.warning(f"User '{username}' denied add_jadx_instance: explicit token required for {host}:{port}")
            return make_error(
                ErrorCode.INVALID_INPUT,
                "Non-local JADX instances require an explicit token; shared default tokens are only used for localhost",
            )
        
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
            is_dynamic=True,  # Dynamic instance (not from config file)
            registration_source="ai_dynamic"
        )
        return result
    
    @mcp.tool()
    async def remove_jadx_instance(name: str) -> dict:
        """Remove a JADX instance. Users may only remove their own dynamic instances; admins can remove any.

        Args:
            name: Instance name to remove.
        Returns:
            dict: {success: bool, message: str}
        """
        # Get current user from auth context
        user = UserAuthManager.get_current_user()
        username = user.name if user else "anonymous"
        is_admin = user.is_admin if user else False
        
        # Check if user has access to this instance
        instance = InstanceRegistry.get_instance_for_user(name, username, is_admin)
        if not instance:
            return make_error(
                ErrorCode.INSTANCE_NOT_FOUND,
                f"Instance '{name}' not found or you don't have access to it",
            )

        # Non-admin users can only remove their own dynamic instances
        if not is_admin and instance.owner != username:
            return make_error(
                ErrorCode.PERMISSION_DENIED,
                "You can only remove your own dynamic instances",
            )
        
        return InstanceRegistry.remove_instance(name, username=username, is_admin=is_admin)
    
    @mcp.tool()
    async def set_default_jadx_instance(name: str) -> dict:
        """Set the default JADX instance for tool calls that omit instance_id.

        Args:
            name: Instance name to set as default.
        Returns:
            dict: {success: bool, message: str}
        """
        # Get current user from auth context
        user = UserAuthManager.get_current_user()
        username = user.name if user else "anonymous"
        is_admin = user.is_admin if user else False
        
        return InstanceRegistry.set_default(name, username=username, is_admin=is_admin)
    
    @mcp.tool()
    async def get_jadx_instance_info(name: str) -> dict:
        """Get detailed info about a specific JADX instance: status, APK metadata, last health check.

        Args:
            name: Instance name.
        Returns:
            dict: {name, host, port, status, apk_info: {apk_package, version_name, ...}, last_health_check}
        """
        # Get current user from auth context
        user = UserAuthManager.get_current_user()
        username = user.name if user else "anonymous"
        is_admin = user.is_admin if user else False
        
        # Check user access
        instance = InstanceRegistry.get_instance_for_user(name, username, is_admin)
        if not instance:
            return make_error(
                ErrorCode.INSTANCE_NOT_FOUND,
                f"Instance '{name}' not found or you don't have access to it",
            )
        return {
            "success": True,
            **instance.to_dict(),
        }
    
    @mcp.tool()
    async def health_check_jadx_instances() -> dict:
        """Perform health checks on all registered JADX instances and update their connection status.

        Returns:
            dict: {total: int, healthy: int, instances: [{name, status}]}
        """
        return await InstanceRegistry.health_check_all()

    @mcp.tool()
    async def clear_class_cache(instance_id: str = None) -> dict:
        """Manually clear the JADX class cache. Subject to 30s global cooldown shared with all rename operations.

        Args:
            instance_id: Target JADX instance name (uses default if omitted).
        Returns:
            dict: {success: bool, message: str, cooldown_remaining_seconds: int if debounced}
        """
        if instance_id:
            instance = InstanceRegistry.get_instance(instance_id)
        else:
            instance = InstanceRegistry.get_default()
            
        if not instance:
            return make_error(ErrorCode.INSTANCE_NOT_FOUND, f"Instance '{instance_id or 'default'}' not found or not connected")

        if instance.status != "connected":
            return make_error(ErrorCode.CONNECTION_FAILED, f"Instance '{instance.name}' is not connected (status: {instance.status})")
        
        try:
            import httpx
            # Get auth token - use instance token or global token
            auth_token = instance.token or InstanceRegistry.get_auth_token()
            headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{instance.url}/cache/clear",
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            # Security: log keeps full details, external returns generic message
            logger.error(f"Failed to clear cache: {type(e).__name__}: {e}")
            return {"error": f"Failed to clear cache: {type(e).__name__}"}
