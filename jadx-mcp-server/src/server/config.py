"""
JADX MCP Server - Configuration Module

This module manages server configuration, HTTP client setup, and communication
with the JADX Java plugin. Handles connection management, error handling,
and request/response processing.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

import asyncio
import httpx
import json
from typing import Union, Dict, Any, Optional

from .logging_config import get_logger
from .types import ErrorCode, make_error

# Get module logger
logger = get_logger("config")

# Default Configuration
JADX_HOST = "127.0.0.1"
JADX_PORT = 8650
JADX_HTTP_BASE = f"http://{JADX_HOST}:{JADX_PORT}"
AUTH_TOKEN: Optional[str] = None
REQUEST_TIMEOUT: int = 120  # Default timeout in seconds (configurable)

# Tiered timeout constants (seconds)
TIMEOUT_HEALTH: int = 10      # Health/ping endpoints
TIMEOUT_METADATA: int = 30    # Lightweight metadata (class-info, methods-of-class, fields-of-class, etc.)
TIMEOUT_CODE_READ: int = 120  # Heavy code retrieval (class-source, smali, batch-class-source, etc.)

# Endpoints classified by timeout tier
_METADATA_ENDPOINTS = frozenset({
    "class-info", "methods-of-class", "fields-of-class", "all-classes",
    "main-application-classes-names", "search-classes-by-keyword",
    "search-native-methods", "file-info", "package-classes",
    "decompile-status", "apk-info", "current-class", "selected-text",
    "batch-xrefs", "jar-manifest", "jar-services", "jar-entry-points",
    "jar-dependencies", "rename-class", "rename-method", "rename-field",
    "rename-package", "get-method-signature",
})
_HEALTH_ENDPOINTS = frozenset({"health", "warmup"})


def _infer_timeout(endpoint: str) -> int:
    """Infer the appropriate timeout for a JADX endpoint."""
    ep = endpoint.strip("/")
    if ep in _HEALTH_ENDPOINTS:
        return TIMEOUT_HEALTH
    if ep in _METADATA_ENDPOINTS:
        return TIMEOUT_METADATA
    return TIMEOUT_CODE_READ


# HTTP Connection Pool Manager
class HttpClientManager:
    """
    Manages a shared HTTP client with connection pooling for better performance.
    Reuses connections across multiple requests instead of creating new ones.
    """
    _client: Optional[httpx.AsyncClient] = None
    _lock: Optional[asyncio.Lock] = None
    
    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """Get or create the asyncio lock (must be called within event loop)."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock
    
    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        """Get or create the shared async HTTP client (thread-safe)."""
        if cls._client is not None and not cls._client.is_closed:
            return cls._client
        async with cls._get_lock():
            if cls._client is None or cls._client.is_closed:
                cls._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(REQUEST_TIMEOUT),
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
                )
        return cls._client
    
    @classmethod
    async def close(cls):
        """Close the shared HTTP client."""
        if cls._client is not None and not cls._client.is_closed:
            await cls._client.aclose()
            cls._client = None


def set_jadx_config(host: str = "127.0.0.1", port: int = 8650):
    """
    Updates the JADX plugin connection configuration.

    Args:
        host: IP address or hostname where JADX AI MCP plugin is listening
        port: TCP port number where JADX AI MCP plugin is listening

    Side Effects:
        Updates global JADX_HOST, JADX_PORT, and JADX_HTTP_BASE configuration
    """
    global JADX_HOST, JADX_PORT, JADX_HTTP_BASE
    JADX_HOST = host
    JADX_PORT = port
    JADX_HTTP_BASE = f"http://{JADX_HOST}:{JADX_PORT}"



def set_auth_token(token: Optional[str]):
    """
    Sets the authentication token for JADX plugin requests.

    Args:
        token: Bearer token for authentication, or None to disable auth

    Side Effects:
        Updates global AUTH_TOKEN configuration
    """
    global AUTH_TOKEN
    AUTH_TOKEN = token
    if token:
        logger.info("Authentication token configured")
    else:
        logger.info("Authentication disabled (no token provided)")


def set_request_timeout(timeout: int):
    """
    Sets the request timeout for JADX plugin requests.

    Args:
        timeout: Timeout in seconds for HTTP requests

    Side Effects:
        Updates global REQUEST_TIMEOUT and recreates HTTP client
    """
    global REQUEST_TIMEOUT
    REQUEST_TIMEOUT = timeout
    # Force client recreation with new timeout
    HttpClientManager._client = None
    logger.info(f"Request timeout set to {timeout} seconds")


def _get_auth_headers() -> Dict[str, str]:
    """
    Generates authentication headers if token is configured.

    Returns:
        Dict containing Authorization header if token is set, empty dict otherwise
    """
    if AUTH_TOKEN:
        return {"Authorization": f"Bearer {AUTH_TOKEN}"}
    return {}



async def get_from_jadx(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    instance_id: Optional[str] = None,
    timeout: Optional[int] = None,
    username: Optional[str] = None,
    is_admin: bool = False,
) -> Union[str, Dict[str, Any]]:
    """
    Generic async helper to request data from the JADX plugin.

    Args:
        endpoint: API endpoint path (e.g., "class-source", "manifest")
        params: Query parameters dictionary for the request
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
        timeout: Optional per-request timeout in seconds. Overrides the client default.
        username: Optional current username for ACL-aware instance resolution.
        is_admin: Whether the current user has admin access.

    Returns:
        Union[str, Dict[str, Any]]: Parsed JSON response or error dictionary

    Raises:
        Returns error dict on HTTP failures or connection issues

    Note:
        Automatically handles JSON parsing with fallback to text response.
        Includes authentication headers if AUTH_TOKEN is configured.
        Supports multi-instance routing when InstanceRegistry is available.
        Uses connection pooling for better performance.
    """
    params = params or {}

    # Determine the base URL based on instance_id
    base_url = JADX_HTTP_BASE
    auth_token = AUTH_TOKEN
    
    # Try to use InstanceRegistry for multi-instance support
    instance_obj = None
    try:
        from .instance_registry import InstanceRegistry

        if instance_id:
            if username is not None:
                instance_obj = InstanceRegistry.get_instance_for_user(instance_id, username, is_admin)
            else:
                instance_obj = InstanceRegistry.get_instance(instance_id)

            if not instance_obj:
                # Fuzzy match: try APK package name, file name, or partial instance name
                instance_obj = InstanceRegistry.find_instance_by_apk(
                    instance_id,
                    username=username,
                    is_admin=is_admin,
                )
                if instance_obj:
                    logger.info(f"Fuzzy matched instance_id '{instance_id}' -> '{instance_obj.name}'")
                else:
                    return make_error(
                        ErrorCode.INSTANCE_NOT_FOUND,
                        f"Instance '{instance_id}' not found",
                        suggestion="Use 'list_jadx_instances' to see available instances. "
                                   "You can specify instance by name, APK package, or partial match.",
                    )
            base_url = instance_obj.url
        else:
            # Resolve the effective default instance.
            # With user context, this is the user's visible default or first visible fallback.
            if username is not None:
                instance_obj = InstanceRegistry.get_default_for_user(username, is_admin)
                if not instance_obj:
                    return make_error(
                        ErrorCode.NO_INSTANCE,
                        f"No JADX instance is available for user '{username}'",
                        suggestion="Use 'list_jadx_instances' to see the instances you can access.",
                    )
            else:
                instance_obj = InstanceRegistry.get_default()
            if instance_obj:
                base_url = instance_obj.url

        # Use shared auth token from InstanceRegistry if available
        registry_token = InstanceRegistry.get_auth_token()
        if registry_token:
            auth_token = registry_token

    except ImportError as e:
        # InstanceRegistry not available, use legacy single-instance mode
        logger.warning(f"InstanceRegistry import failed, using legacy mode: {e}")

    # Pre-check: if instance is pending/disconnected, attempt a quick probe before failing.
    # This eliminates the startup race where tools are called before the health monitor
    # has had time to promote the instance from "pending" to "connected".
    if instance_obj and hasattr(instance_obj, 'status') and instance_obj.status in ("disconnected", "pending"):
        instance_name = getattr(instance_obj, 'name', instance_id or 'default')
        try:
            from .instance_registry import InstanceRegistry
            apk_info = await InstanceRegistry._fetch_apk_info(
                instance_obj.host, instance_obj.port, instance_obj.token,
                timeout=3.0  # quick probe, don't block long
            )
            # Instance is actually reachable — promote it now
            InstanceRegistry.update_instance_status(
                name=instance_obj.name,
                status="connected",
                apk_info=apk_info,
            )
            logger.info(f"Instance '{instance_name}' promoted to connected via on-demand probe")
            base_url = instance_obj.url
        except Exception as probe_err:
            # Distinguish auth failures from connectivity issues
            import httpx as _httpx
            if isinstance(probe_err, _httpx.HTTPStatusError) and probe_err.response.status_code == 401:
                return make_error(
                    ErrorCode.CONNECTION_FAILED,
                    f"JADX instance '{instance_name}' authentication failed (401 Unauthorized)",
                    status="auth_failed",
                    detail="The JADX plugin rejected the request: token is missing or incorrect.",
                    suggestion="Set 'jadx_token' in your config TOML under [defaults], "
                               "or pass --auth-token on the CLI. "
                               "The token must match the JADX plugin's JADX_MCP_AUTH_TOKEN.",
                )
            return make_error(
                ErrorCode.CONNECTION_FAILED,
                f"JADX instance '{instance_name}' is {instance_obj.status}",
                status=instance_obj.status,
                detail=f"The JADX instance is currently {instance_obj.status} and cannot process requests. "
                       "This may happen after a 'Reset Code Cache' operation or if JADX was closed.",
                suggestion="Use 'list_instances' tool to check instance status. "
                           "If the instance was restarted, wait a few seconds and try again.",
            )

    # Pre-check: instance in error/auth_failed state — show stored error message
    if instance_obj and hasattr(instance_obj, 'status') and instance_obj.status in ("error", "auth_failed"):
        instance_name = getattr(instance_obj, 'name', instance_id or 'default')
        error_msg = getattr(instance_obj, 'error_message', '') or "Unknown error"
        if instance_obj.status == "auth_failed":
            return make_error(
                ErrorCode.CONNECTION_FAILED,
                f"JADX instance '{instance_name}' authentication failed (401 Unauthorized)",
                status="auth_failed",
                detail=error_msg,
                suggestion="Set 'jadx_token' in your config TOML under [defaults], "
                           "or pass --auth-token on the CLI. "
                           "Then use 'health_check_jadx_instances' to retry.",
            )
        return make_error(
            ErrorCode.CONNECTION_FAILED,
            f"JADX instance '{instance_name}' is in error state",
            status="error",
            detail=error_msg,
            suggestion="Fix the configuration issue and restart, or use 'health_check_jadx_instances' to retry.",
        )

    # Pre-check: warn AI client if instance is in degraded state (OOM or critical memory)
    if instance_obj and hasattr(instance_obj, 'status') and instance_obj.status == "degraded":
        instance_name = getattr(instance_obj, 'name', instance_id or 'default')
        return make_error(
            ErrorCode.INTERNAL_ERROR,
            f"JADX instance '{instance_name}' is degraded (out of memory)",
            status="degraded",
            detail="The JADX instance has encountered an OutOfMemoryError or is critically low on memory. "
                   "Requests may fail or return incomplete results. "
                   "The JVM is still running but cannot reliably process decompilation.",
            suggestion="1. Restart JADX to recover from OOM state. "
                       "2. If using Docker, increase memory limit (e.g., --memory=4g). "
                       "3. For native JADX, increase JVM heap: edit jadx-gui script, add -Xmx4g. "
                       "4. Try analyzing a smaller file or fewer classes at once.",
        )
    
    url = f"{base_url}/{endpoint.lstrip('/')}"
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    # Response cache: check for cached result on deterministic endpoints
    from .response_cache import (
        CACHEABLE_ENDPOINTS, _MUTATING_ENDPOINTS, _make_cache_key, get_response_cache,
    )
    ep_stripped = endpoint.strip("/")
    cache = get_response_cache()

    # Mutating endpoints invalidate cache for the affected instance only
    if ep_stripped in _MUTATING_ENDPOINTS:
        effective_id = (instance_obj.name if instance_obj else None) or instance_id or "default"
        cache.invalidate_instance(effective_id)

    # Check cache for cacheable endpoints
    cache_key = None
    if ep_stripped in CACHEABLE_ENDPOINTS:
        cache_key = _make_cache_key(
            instance_obj.name if instance_obj else instance_id,
            ep_stripped,
            params,
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    logger.debug(f"JADX request: GET {url} (params={list(params.keys()) if params else 'none'})")

    try:
        client = await HttpClientManager.get_client()
        effective_timeout = timeout if timeout is not None else _infer_timeout(endpoint)
        req_timeout = httpx.Timeout(effective_timeout)
        resp = await client.get(url, params=params, headers=headers, timeout=req_timeout)
        resp.raise_for_status()

        logger.debug(f"JADX response: {resp.status_code} OK (size={len(resp.content)} bytes)")

        # Try to parse JSON, fallback to text if not valid JSON
        try:
            result = resp.json()
        except json.JSONDecodeError:
            result = {"response": resp.text}

        # Cache successful non-error responses for cacheable endpoints
        if cache_key and isinstance(result, dict) and "error" not in result:
            cache.put(cache_key, result)

        return result

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code

        if status_code == 401:
            error_msg = "Authentication failed. Please check your auth token configuration."
            logger.error(error_msg)
            return make_error(ErrorCode.AUTHENTICATION_FAILED, error_msg)

        elif status_code == 500:
            error_detail = e.response.text[:200] if e.response.text else "(no details)"
            error_msg = f"JADX internal error (HTTP 500): {error_detail}"
            logger.error(f"JADX 500 error: {error_detail}")
            return make_error(
                ErrorCode.INTERNAL_ERROR,
                error_msg,
                status="error",
                detail="The JADX instance encountered an internal error. "
                       "This may be a temporary issue after a 'Reset Code Cache' operation.",
                suggestion="Wait a few seconds and retry. If the problem persists, "
                           "check the JADX GUI for error dialogs.",
            )

        elif status_code == 503:
            # Parse 503 response for structured retry information
            try:
                error_data = e.response.json()
                retry_after = error_data.get("retry_after", 5)
                suggestion = error_data.get("suggestion", "Service temporarily unavailable. Please retry in a few seconds.")

                logger.warning(f"Service unavailable (503): {suggestion} (retry_after={retry_after}s)")
                return make_error(
                    ErrorCode.CONNECTION_FAILED,
                    "JADX service unavailable (HTTP 503)",
                    status="initializing",
                    retry_after=retry_after,
                    detail="The JADX instance is still initializing or temporarily unavailable.",
                    suggestion=suggestion,
                )
            except (json.JSONDecodeError, AttributeError):
                logger.warning("JADX returned 503 Service Unavailable")
                return make_error(
                    ErrorCode.CONNECTION_FAILED,
                    "JADX service unavailable (HTTP 503)",
                    status="initializing",
                    detail="The JADX instance is still initializing or temporarily unavailable.",
                    suggestion="Wait a few seconds and retry. Use 'list_instances' to check status.",
                )

        else:
            error_msg = f"HTTP error {status_code}: {e.response.text}"
        logger.error(error_msg)
        return make_error(ErrorCode.INTERNAL_ERROR, error_msg)

    except httpx.ConnectError as e:
        logger.error(f"JADX connection refused: {e}")
        # Mark instance disconnected immediately (don't wait for health monitor)
        if instance_obj:
            try:
                from .instance_registry import InstanceRegistry
                InstanceRegistry.update_instance_status(
                    name=instance_obj.name, status="disconnected",
                    error_message=f"Connection refused: {type(e).__name__}",
                )
            except Exception:
                pass
        return make_error(
            ErrorCode.CONNECTION_FAILED,
            "Connection refused: JADX instance is not reachable",
            status="disconnected",
            detail="Could not connect to the JADX plugin HTTP server. "
                   "The JADX application may not be running or the plugin may not be started.",
            suggestion="1. Verify JADX is running with the AI MCP plugin enabled. "
                       "2. Check the port configuration matches. "
                       "3. Use 'list_instances' to verify instance settings.",
        )

    except httpx.ConnectTimeout as e:
        logger.error(f"JADX connection timeout: {e}")
        # Mark instance disconnected immediately
        if instance_obj:
            try:
                from .instance_registry import InstanceRegistry
                InstanceRegistry.update_instance_status(
                    name=instance_obj.name, status="disconnected",
                    error_message=f"Connection timeout: {type(e).__name__}",
                )
            except Exception:
                pass
        return make_error(
            ErrorCode.TIMEOUT,
            "Connection timeout: JADX instance did not respond",
            status="timeout",
            detail="The connection to the JADX plugin timed out. "
                   "The instance may be overloaded or the network may be unreachable.",
            suggestion="Wait a moment and retry. If the problem persists, "
                       "check network connectivity and JADX instance health.",
        )

    except httpx.ReadTimeout as e:
        logger.error(f"JADX read timeout: {e}")
        return make_error(
            ErrorCode.TIMEOUT,
            "Response timeout: JADX took too long to respond",
            status="timeout",
            detail="The JADX instance accepted the connection but did not respond in time. "
                   "This may happen with large classes or complex decompilation operations.",
            suggestion="Try narrowing your request scope (e.g., specific class instead of batch). "
                       "You can also increase the timeout in server configuration.",
        )

    except Exception as e:
        # Security: log keeps full details, external returns only exception type
        error_detail = str(e) if str(e) else "(no message)"
        logger.error(f"JADX request failed: {type(e).__name__}: {error_detail}")
        return make_error(ErrorCode.INTERNAL_ERROR, f"Request failed: {type(e).__name__}")
