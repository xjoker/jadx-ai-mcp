"""
Transfer Tools - MCP 工具封装
提供创建、查询、撤销传输令牌的 MCP 工具
"""

from typing import Optional
from datetime import datetime, timezone

from ..transfer_store import get_token_store, Operation, ResourceType
from ..logging_config import get_logger
from ..rate_limiter import get_token_limiter
from ..param_validator import ValidationError

logger = get_logger("transfer_tools")


async def create_transfer_token(
    operation: str = "download",
    resource_type: str = "batch_classes",
    timeout_seconds: int = 120,
    params: Optional[dict] = None,
    instance_id: Optional[str] = None
) -> dict:
    """
    创建大文件传输令牌
    
    绕过 MCP 消息大小限制（约 16KB），通过独立 HTTP 端点下载大批量数据。
    
    Args:
        operation: "download" (目前仅支持下载)
        resource_type: "batch_classes" | "batch_methods" | "project_export"
        timeout_seconds: 令牌有效期（秒），默认 120
        params: 可选的请求参数
        instance_id: JADX 实例 ID
    
    Returns:
        {
            "success": true,
            "token": "令牌字符串",
            "transfer_url": "http://localhost:8765/transfer",
            "expires_in": 120,
            "expires_at": "2024-01-20T10:00:00Z",
            "resource_type": "batch_classes",
            "usage_hint": "使用提示"
        }
    
    使用流程:
        1. token_result = create_transfer_token("download", "batch_classes")
        2. 使用 HTTP 客户端直接下载:
           GET {transfer_url}/download/batch-classes?classes=A,B,C&token={token}
        3. revoke_transfer_token(token)  # 可选，令牌会自动过期
    
    支持的 format 参数 (URL 查询参数):
        - json: 返回 JSON 数据（默认）
        - zip: 返回 ZIP 压缩包，每个类一个 .java 文件
    
    支持的 compression 参数 (URL 查询参数):
        - auto: 自动根据 Accept-Encoding 选择（默认）
        - br: Brotli 压缩（最佳压缩率）
        - gzip: GZIP 压缩
        - none: 不压缩
    
    示例:
        # JSON 格式 + Brotli 压缩
        GET /transfer/download/batch-classes?classes=com.A,com.B&token=xxx&format=json
        
        # ZIP 格式
        GET /transfer/download/batch-classes?classes=com.A,com.B&token=xxx&format=zip
    """
    # 速率限制检查（使用 instance_id 或 "default" 作为客户端标识）
    client_id = instance_id or "default"
    rate_limiter = get_token_limiter()
    
    if not rate_limiter.check(client_id):
        remaining_time = rate_limiter.get_reset_time(client_id)
        logger.warning(f"Token creation rate limit exceeded for {client_id}")
        return {
            "success": False,
            "error": "Rate limit exceeded",
            "retry_after": remaining_time,
            "message": f"Maximum token creation requests exceeded. Please try again in {remaining_time} seconds."
        }
    
    try:
        op = Operation(operation)
        rt = ResourceType(resource_type)
    except ValueError as e:
        logger.error(f"Invalid operation or resource_type: {e}")
        return {
            "success": False,
            "error": f"Invalid parameter: {str(e)}"
        }
    
    store = get_token_store()
    token = store.create(op, rt, timeout_seconds, params)
    
    # TODO: 从配置读取实际的服务器 URL
    # 暂时硬编码为 localhost:8765
    transfer_base_url = "http://localhost:8765"
    
    expires_at = datetime.fromtimestamp(token.expires_at, tz=timezone.utc).isoformat()
    
    # 生成使用提示
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
    检查令牌状态
    
    Args:
        token: 令牌字符串
    
    Returns:
        {
            "exists": true/false,
            "used": true/false,
            "expires_in": 剩余秒数,
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
    立即撤销令牌，释放资源
    
    建议在下载完成后调用此函数，虽然令牌会自动过期。
    
    Args:
        token: 令牌字符串
    
    Returns:
        {
            "success": true/false,
            "message": "描述信息"
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
