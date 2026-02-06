"""
Transfer Server - HTTP 端点实现
提供绕过 MCP 限制的大文件下载端点
"""

import io
import zipfile
import json
import secrets
from typing import Optional
from starlette.applications import Starlette
from starlette.responses import Response, JSONResponse
from starlette.routing import Route
from starlette.requests import Request

from .transfer_store import get_token_store, ResourceType
from .config import get_from_jadx
from .logging_config import get_logger
from .rate_limiter import get_download_limiter
from .param_validator import (
    validate_class_names,
    validate_token,
    validate_format,
    validate_compression,
    ValidationError
)

logger = get_logger("transfer_server")

# Brotli 作为可选依赖
try:
    import brotli
    BROTLI_AVAILABLE = True
    logger.info("Brotli compression available")
except ImportError:
    BROTLI_AVAILABLE = False
    logger.warning("Brotli not available, falling back to GZIP")

import gzip


def select_compression(accept_encoding: str) -> str:
    """
    根据客户端 Accept-Encoding 头选择最佳压缩算法
    
    Args:
        accept_encoding: HTTP Accept-Encoding 头
    
    Returns:
        压缩算法: 'br', 'gzip', 或 'identity'
    """
    accept_encoding = accept_encoding.lower()
    
    if "br" in accept_encoding and BROTLI_AVAILABLE:
        return "br"  # Brotli - 最佳压缩率
    elif "gzip" in accept_encoding:
        return "gzip"  # GZIP - 通用支持
    return "identity"  # 不压缩


def compress_data(data: bytes, encoding: str) -> tuple[bytes, str]:
    """
    压缩数据
    
    Args:
        data: 原始数据
        encoding: 压缩算法
    
    Returns:
        (压缩后数据, 实际使用的编码)
    """
    if encoding == "br" and BROTLI_AVAILABLE:
        try:
            compressed = brotli.compress(data, quality=6)  # quality 6 平衡速度和压缩率
            logger.debug(f"Brotli compressed: {len(data)} -> {len(compressed)} bytes")
            return compressed, "br"
        except Exception as e:
            logger.warning(f"Brotli compression failed: {e}, falling back to gzip")
            encoding = "gzip"
    
    if encoding == "gzip":
        try:
            compressed = gzip.compress(data, compresslevel=6)
            logger.debug(f"GZIP compressed: {len(data)} -> {len(compressed)} bytes")
            return compressed, "gzip"
        except Exception as e:
            logger.warning(f"GZIP compression failed: {e}, using identity")
    
    return data, "identity"


async def _fetch_batch_classes(class_names: list, instance_id: Optional[str]) -> list:
    """
    从 JADX 批量获取类源码
    
    Args:
        class_names: 类名列表
        instance_id: JADX 实例 ID
    
    Returns:
        结果列表
    """
    results = []
    logger.info(f"Fetching {len(class_names)} classes from JADX")
    
    for name in class_names:
        try:
            resp = await get_from_jadx("class-source", {"class_name": name}, instance_id=instance_id)
            
            if "error" in resp:
                results.append({
                    "name": name,
                    "found": False,
                    "error": resp["error"]
                })
            else:
                results.append({
                    "name": name,
                    "found": True,
                    "content": resp.get("response", "")
                })
        except Exception as e:
            logger.error(f"Failed to fetch class {name}: {e}")
            results.append({
                "name": name,
                "found": False,
                "error": str(e)
            })
    
    found_count = sum(1 for r in results if r.get("found", False))
    logger.info(f"Fetched {found_count}/{len(class_names)} classes successfully")
    
    return results


async def download_batch_classes(request: Request):
    """
    GET /transfer/download/batch-classes
    
    Query Parameters:
        - token: 传输令牌 (必需)
        - classes: 逗号分隔的类名 (必需)
        - format: json 或 zip (可选, 默认 json)
        - compression: br, gzip, none, auto (可选, 默认 auto)
        - instance_id: JADX 实例 ID (可选)
    """
    # 0. 速率限制检查
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter = get_download_limiter()
    
    if not rate_limiter.check(client_ip):
        remaining_time = rate_limiter.get_reset_time(client_ip)
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            {
                "error": "Rate limit exceeded",
                "retry_after": remaining_time,
                "message": f"Maximum download requests exceeded. Please try again in {remaining_time} seconds."
            },
            status_code=429,
            headers={"Retry-After": str(remaining_time)}
        )
    
    # 1. 参数验证和清理
    try:
        # 验证令牌
        token_param = request.headers.get("X-Transfer-Token") or request.query_params.get("token")
        if not token_param:
            return JSONResponse({"error": "Missing token parameter"}, status_code=400)
        
        token_id = validate_token(token_param)
        
        # 验证类名
        classes_param = request.query_params.get("classes", "")
        class_names = validate_class_names(classes_param)
        
        # 验证格式
        format_type = validate_format(request.query_params.get("format", "json"))
        
        # 验证压缩
        compression_param = validate_compression(request.query_params.get("compression", "auto"))
        
    except ValidationError as e:
        logger.warning(f"Validation error from {client_ip}: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)
    
    instance_id = request.query_params.get("instance_id")
    
    # 2. 验证令牌
    store = get_token_store()
    token = store.validate(token_id)
    
    if token is None:
        logger.warning(f"Invalid or expired token from {client_ip}: {token_id[:8]}...")
        return JSONResponse({"error": "Invalid or expired token"}, status_code=401)
    
    if token.resource_type != ResourceType.BATCH_CLASSES:
        logger.warning(f"Token not authorized for batch_classes from {client_ip}: {token.resource_type}")
        return JSONResponse(
            {"error": f"Token not authorized for this resource. Expected batch_classes, got {token.resource_type.value}"}, 
            status_code=403
        )
    
    logger.info(f"Download request from {client_ip}: {len(class_names)} classes, format={format_type}, compression={compression_param}")

    
    # 3. 获取数据
    try:
        results = await _fetch_batch_classes(class_names, instance_id)
    except Exception as e:
        logger.error(f"Failed to fetch classes: {e}")
        return JSONResponse({"error": f"Failed to fetch classes: {str(e)}"}, status_code=500)
    
    # 4. 标记令牌已使用
    store.mark_used(token_id)
    
    # 5. 构建响应
    if format_type == "zip":
        # ZIP 格式：每个类一个文件
        buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for item in results:
                    if item.get("found", False):
                        # 转换类名为文件路径: com.example.A -> com/example/A.java
                        filename = item["name"].replace(".", "/") + ".java"
                        zf.writestr(filename, item["content"])
                
                # 添加索引文件
                index_data = {
                    "total": len(results),
                    "found": sum(1 for r in results if r.get("found", False)),
                    "classes": [
                        {"name": r["name"], "found": r.get("found", False)}
                        for r in results
                    ]
                }
                zf.writestr("_index.json", json.dumps(index_data, indent=2))
            
            logger.info(f"Created ZIP with {index_data['found']} classes")
            
            return Response(
                content=buffer.getvalue(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=classes.zip",
                    "X-Total-Classes": str(len(results)),
                    "X-Found-Classes": str(index_data['found'])
                }
            )
        except Exception as e:
            logger.error(f"Failed to create ZIP: {e}")
            return JSONResponse({"error": f"Failed to create ZIP: {str(e)}"}, status_code=500)
    
    else:
        # JSON 格式
        response_data = {
            "classes": results,
            "total": len(results),
            "found": sum(1 for r in results if r.get("found", False))
        }
        
        data_bytes = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
        
        # 选择压缩算法
        if compression_param == "auto":
            accept_encoding = request.headers.get("Accept-Encoding", "")
            compression = select_compression(accept_encoding)
        elif compression_param == "none":
            compression = "identity"
        else:
            compression = compression_param  # br 或 gzip
        
        compressed_data, actual_encoding = compress_data(data_bytes, compression)
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-Total-Classes": str(len(results)),
            "X-Found-Classes": str(response_data['found']),
            "X-Original-Size": str(len(data_bytes))
        }
        
        if actual_encoding != "identity":
            headers["Content-Encoding"] = actual_encoding
        
        logger.info(
            f"Returning JSON response: {len(data_bytes)} bytes "
            f"(compressed: {len(compressed_data)} bytes, encoding: {actual_encoding})"
        )
        
        return Response(content=compressed_data, headers=headers)


async def download_health(request: Request):
    """GET /transfer/health - 健康检查端点"""
    return JSONResponse({
        "status": "healthy",
        "brotli_available": BROTLI_AVAILABLE,
        "endpoints": [
            "/transfer/download/batch-classes",
            "/transfer/health"
        ]
    })


# 创建 Starlette 应用（稍后挂载到 FastMCP）
transfer_routes = [
    Route("/transfer/download/batch-classes", download_batch_classes, methods=["GET"]),
    Route("/transfer/health", download_health, methods=["GET"]),
]

transfer_app = Starlette(routes=transfer_routes)
