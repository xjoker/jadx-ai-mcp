"""
Transfer Tools - MCP tool wrappers.
Provides MCP tools for creating, querying, and revoking transfer tokens.
"""

from typing import Optional
from datetime import datetime, timezone

from ..transfer_store import (
    TransferStoreCapacityError,
    get_token_store,
    Operation,
    ResourceType,
)
from ..logging_config import get_logger
from ..rate_limiter import get_token_limiter
from ..param_validator import ValidationError
from ..mcp_server_config import get_mcp_server_url
from ..types import ErrorCode, make_error

logger = get_logger("transfer_tools")


async def create_transfer_token(
    operation: str = "download",
    resource_type: str = "batch_classes",
    timeout_seconds: int = 120,
    params: Optional[dict] = None,
    instance_id: Optional[str] = None
) -> dict:
    """
    Create a large file transfer token.

    Bypasses MCP message size limits (~16KB) by enabling data download
    via a dedicated HTTP endpoint.

    Args:
        operation: "download" (only download is currently supported)
        resource_type: "batch_classes" | "batch_methods" | "project_export"
        timeout_seconds: Token validity period in seconds (default: 120)
        params: Optional request parameters
        instance_id: JADX instance ID

    Returns:
        {
            "success": true,
            "token": "<token string>",
            "transfer_url": "http://localhost:8765/transfer",
            "expires_in": 120,
            "expires_at": "2024-01-20T10:00:00Z",
            "resource_type": "batch_classes",
            "usage_hint": "<usage hint>"
        }

    Workflow:
        1. token_result = create_transfer_token("download", "batch_classes")
        2. Download directly using an HTTP client:
           GET {transfer_url}/download/batch-classes?classes=A,B,C&token={token}
        3. revoke_transfer_token(token)  # optional; token auto-expires

    Supported 'format' query parameter:
        - json: Returns JSON data (default)
        - zip: Returns a ZIP archive with one .java file per class

    Supported 'compression' query parameter:
        - auto: Automatically selected based on Accept-Encoding (default)
        - br: Brotli compression (best ratio)
        - gzip: GZIP compression
        - none: No compression

    Examples:
        # JSON format + Brotli compression
        GET /transfer/download/batch-classes?classes=com.A,com.B&token=xxx&format=json

        # ZIP format
        GET /transfer/download/batch-classes?classes=com.A,com.B&token=xxx&format=zip
    """
    # Rate limit check (use instance_id or "default" as client identifier)
    client_id = instance_id or "default"
    rate_limiter = get_token_limiter()
    
    if not rate_limiter.check(client_id):
        remaining_time = rate_limiter.get_reset_time(client_id)
        logger.warning(f"Token creation rate limit exceeded for {client_id}")
        return make_error(
            ErrorCode.RATE_LIMITED,
            f"Maximum token creation requests exceeded. Please try again in {remaining_time} seconds.",
            retry_after=remaining_time,
        )
    
    try:
        op = Operation(operation)
        rt = ResourceType(resource_type)
    except ValueError as e:
        logger.error(f"Invalid operation or resource_type: {e}")
        return make_error(ErrorCode.INVALID_INPUT, f"Invalid parameter: {str(e)}")
    
    store = get_token_store()
    try:
        token = store.create(op, rt, timeout_seconds, params)
    except TransferStoreCapacityError as e:
        logger.warning(f"Transfer token creation rejected: {e}")
        return make_error(ErrorCode.RATE_LIMITED, str(e))
    
    # Get MCP Server URL from configuration
    transfer_base_url = get_mcp_server_url()

    expires_at = datetime.fromtimestamp(token.expires_at, tz=timezone.utc).isoformat()

    # Generate usage hint
    endpoint_map = {
        ResourceType.BATCH_CLASSES: "batch-classes",
        ResourceType.BATCH_METHODS: "batch-methods",
        ResourceType.PROJECT_EXPORT: "project-export"
    }
    endpoint = endpoint_map.get(rt, resource_type.replace("_", "-"))
    
    usage_hint = (
        f"GET {{transfer_url}}/download/{endpoint}?"
        f"token={{token}}&classes=com.example.A,com.example.B&format=json"
    )
    
    logger.info(f"Created transfer token for {resource_type}, expires in {timeout_seconds}s")
    
    return {
        "success": True,
        "token": token.token_id,
        "transfer_url": f"{transfer_base_url}/transfer",
        "expires_in": timeout_seconds,
        "expires_at": expires_at,
        "resource_type": resource_type,
        "operation": operation,
        "usage_hint": usage_hint,
        "supported_formats": ["json", "zip"],
        "supported_compressions": ["br", "gzip", "none", "auto"]
    }


async def get_transfer_token_status(token: str) -> dict:
    """
    Check the status of a transfer token.

    Args:
        token: Token string

    Returns:
        {
            "exists": true/false,
            "used": true/false,
            "expires_in": <remaining seconds>,
            "resource_type": "batch_classes",
            "operation": "download"
        }
    """
    store = get_token_store()
    status = store.get_status(token)
    
    logger.info(f"Token status check: exists={status['exists']}, used={status.get('used', False)}")
    
    return {
        "success": True,
        **status
    }


async def revoke_transfer_token(token: str) -> dict:
    """
    Immediately revoke a token to free resources.

    It is recommended to call this after download completes,
    although tokens will expire automatically.

    Args:
        token: Token string

    Returns:
        {
            "success": true/false,
            "message": "<description>"
        }
    """
    store = get_token_store()
    revoked = store.revoke(token)
    
    if revoked:
        logger.info(f"Token revoked successfully")
        return {
            "success": True,
            "message": "Token revoked successfully"
        }
    else:
        logger.warning(f"Token not found for revocation")
        return {
            "success": False,
            "message": "Token not found"
        }


def register_transfer_tools(mcp):
    """Register transfer API tools to MCP Server"""

    @mcp.tool(name="create_transfer_token")
    async def create_transfer_token_tool(
        operation: str = "download",
        resource_type: str = "batch_classes",
        timeout_seconds: int = 120,
        params: Optional[dict] = None,
        instance_id: Optional[str] = None
    ) -> dict:
        """Create a token for direct HTTP download, bypassing MCP message size limits (~16KB).

        Args:
            operation: "download" (only download supported). resource_type: batch_classes|batch_methods|project_export.
            timeout_seconds: Token TTL in seconds (default 120). instance_id: JADX instance ID.
        Returns:
            dict: {token, transfer_url, expires_in} — use GET {transfer_url}/download/{type}?token=...&format=json|zip
        """
        return await create_transfer_token(
            operation, resource_type, timeout_seconds, params, instance_id
        )
