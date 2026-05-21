"""
Transfer Server - HTTP endpoint implementation.
Provides large file download endpoints that bypass MCP size limits.
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

# Brotli as an optional dependency
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
    Select the best compression algorithm based on the client's Accept-Encoding header.

    Args:
        accept_encoding: HTTP Accept-Encoding header value

    Returns:
        Compression algorithm: 'br', 'gzip', or 'identity'
    """
    accept_encoding = accept_encoding.lower()

    if "br" in accept_encoding and BROTLI_AVAILABLE:
        return "br"  # Brotli - best compression ratio
    elif "gzip" in accept_encoding:
        return "gzip"  # GZIP - broadly supported
    return "identity"  # No compression


def compress_data(data: bytes, encoding: str) -> tuple[bytes, str]:
    """
    Compress data with the specified encoding.

    Args:
        data: Raw data bytes
        encoding: Compression algorithm

    Returns:
        (compressed data, actual encoding used)
    """
    if encoding == "br" and BROTLI_AVAILABLE:
        try:
            compressed = brotli.compress(data, quality=6)  # quality 6 balances speed and ratio
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
    Fetch batch class source code from JADX via a single batch-class-source request.

    Args:
        class_names: List of class names
        instance_id: JADX instance ID

    Returns:
        List of results
    """
    logger.info(f"Fetching {len(class_names)} classes from JADX via batch endpoint")

    try:
        resp = await get_from_jadx(
            "batch-class-source",
            {"class_names": ",".join(class_names), "force_raw": "true"},
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
        - token: Transfer token (required)
        - classes: Comma-separated class names (required)
        - format: json or zip (optional, default json)
        - compression: br, gzip, none, auto (optional, default auto)
        - instance_id: JADX instance ID (optional)
    """
    # 0. Rate limit check
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

    # 1. Parameter validation and sanitization
    try:
        # Validate token
        token_param = request.headers.get("X-Transfer-Token") or request.query_params.get("token")
        if not token_param:
            return JSONResponse({"error": "Missing token parameter"}, status_code=400)

        token_id = validate_token(token_param)

        # Validate class names
        classes_param = request.query_params.get("classes", "")
        class_names = validate_class_names(classes_param)

        # Validate format
        format_type = validate_format(request.query_params.get("format", "json"))

        # Validate compression
        compression_param = validate_compression(request.query_params.get("compression", "auto"))

    except ValidationError as e:
        logger.warning(f"Validation error from {client_ip}: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)

    instance_id = request.query_params.get("instance_id")

    # 2. Atomically consume token
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

    # 3. Fetch data
    try:
        results = await _fetch_batch_classes(class_names, instance_id)
    except Exception as e:
        logger.error(f"Failed to fetch classes: {e}")
        return JSONResponse({"error": f"Failed to fetch classes: {str(e)}"}, status_code=500)

    # 4. Build response
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
        # Select compression algorithm
        if compression_param == "auto":
            accept_encoding = request.headers.get("Accept-Encoding", "")
            compression = select_compression(accept_encoding)
        elif compression_param == "none":
            compression = "identity"
        else:
            compression = compression_param  # br or gzip

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
    """GET /transfer/health - health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "brotli_available": BROTLI_AVAILABLE,
        "endpoints": [
            "/transfer/download/batch-classes",
            "/transfer/health"
        ]
    })


# Create Starlette application (to be mounted onto FastMCP later)
transfer_routes = [
    Route("/transfer/download/batch-classes", download_batch_classes, methods=["GET"]),
    Route("/transfer/health", download_health, methods=["GET"]),
]

transfer_app = Starlette(routes=transfer_routes)
