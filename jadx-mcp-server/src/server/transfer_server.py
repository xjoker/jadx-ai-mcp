"""
Transfer Server - HTTP 端点实现
提供绕过 MCP 限制的大文件下载端点
"""

import asyncio
import io
import json
import zipfile
from typing import Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .transfer_store import get_token_store, ResourceType
from .logging_config import get_logger
from .rate_limiter import get_download_limiter
from .request_context import get_from_jadx_for_current_user as get_from_jadx
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


def _build_zip_response_payload(results: list[dict]) -> tuple[bytes, dict]:
    """Build the ZIP archive in a worker thread."""
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in results:
            if item.get("found", False):
                filename = item["name"].replace(".", "/") + ".java"
                zf.writestr(filename, item["content"])

        index_data = {
            "total": len(results),
            "found": sum(1 for r in results if r.get("found", False)),
            "classes": [
                {"name": r["name"], "found": r.get("found", False)}
                for r in results
            ]
        }
        zf.writestr("_index.json", json.dumps(index_data, indent=2))

    return buffer.getvalue(), index_data


def _build_json_response_payload(
    results: list[dict],
    compression: str,
) -> tuple[bytes, dict, str, int]:
    """Serialize and compress JSON in a worker thread."""
    response_data = {
        "classes": results,
        "total": len(results),
        "found": sum(1 for r in results if r.get("found", False))
    }
    data_bytes = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
    compressed_data, actual_encoding = compress_data(data_bytes, compression)
    return compressed_data, response_data, actual_encoding, len(data_bytes)


async def _fetch_batch_classes(class_names: list, instance_id: Optional[str]) -> list:
    """
    从 JADX 批量获取类源码（使用 batch-class-source 端点单次请求）

    Args:
        class_names: 类名列表
        instance_id: JADX 实例 ID

    Returns:
        结果列表
    """
    logger.info(f"Fetching {len(class_names)} classes from JADX via batch endpoint")

    try:
        resp = await get_from_jadx(
            "batch-class-source",
            {"class_names": ",".join(class_names)},
            instance_id=instance_id,
        )

        if isinstance(resp, dict) and "error" in resp:
            logger.error(f"Batch endpoint returned error: {resp['error']}")
            return [
                {"name": name, "found": False, "error": resp["error"]}
                for name in class_names
            ]

        # batch-class-source 返回 {"classes": [...], "total": N, "found": N}
        if isinstance(resp, dict) and "classes" in resp:
            results = resp["classes"]
        else:
            logger.warning("Unexpected batch response format, treating as error")
            return [
                {"name": name, "found": False, "error": "Unexpected batch response format"}
                for name in class_names
            ]
    except Exception as e:
        logger.error(f"Batch fetch failed: {e}")
        return [
            {"name": name, "found": False, "error": str(e)}
            for name in class_names
        ]

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
    
    # 2. 原子消费令牌
    store = get_token_store()
    token = store.consume(token_id, ResourceType.BATCH_CLASSES)
    
    if token is None:
        existing_token = store.validate(token_id)
        if existing_token is not None and existing_token.resource_type != ResourceType.BATCH_CLASSES:
            logger.warning(
                f"Token not authorized for batch_classes from {client_ip}: "
                f"{existing_token.resource_type}"
            )
            return JSONResponse(
                {
                    "error": (
                        "Token not authorized for this resource. "
                        f"Expected batch_classes, got {existing_token.resource_type.value}"
                    )
                },
                status_code=403
            )

        logger.warning(f"Invalid, expired, or used token from {client_ip}: {token_id[:8]}...")
        return JSONResponse({"error": "Invalid or expired token"}, status_code=401)
    
    logger.info(f"Download request from {client_ip}: {len(class_names)} classes, format={format_type}, compression={compression_param}")

    
    # 3. 获取数据
    try:
        results = await _fetch_batch_classes(class_names, instance_id)
    except Exception as e:
        logger.error(f"Failed to fetch classes: {e}")
        return JSONResponse({"error": f"Failed to fetch classes: {str(e)}"}, status_code=500)
    
    # 4. 构建响应
    if format_type == "zip":
        try:
            payload, index_data = await asyncio.to_thread(_build_zip_response_payload, results)
            logger.info(f"Created ZIP with {index_data['found']} classes")
            
            return Response(
                content=payload,
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
        # 选择压缩算法
        if compression_param == "auto":
            accept_encoding = request.headers.get("Accept-Encoding", "")
            compression = select_compression(accept_encoding)
        elif compression_param == "none":
            compression = "identity"
        else:
            compression = compression_param  # br 或 gzip

        try:
            compressed_data, response_data, actual_encoding, original_size = await asyncio.to_thread(
                _build_json_response_payload,
                results,
                compression,
            )
        except Exception as e:
            logger.error(f"Failed to build JSON response: {e}")
            return JSONResponse({"error": f"Failed to build JSON response: {str(e)}"}, status_code=500)
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-Total-Classes": str(len(results)),
            "X-Found-Classes": str(response_data['found']),
            "X-Original-Size": str(original_size)
        }
        
        if actual_encoding != "identity":
            headers["Content-Encoding"] = actual_encoding
        
        logger.info(
            f"Returning JSON response: {original_size} bytes "
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
