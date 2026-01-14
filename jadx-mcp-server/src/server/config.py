"""
JADX MCP Server - Configuration Module

This module manages server configuration, HTTP client setup, and communication
with the JADX Java plugin. Handles connection management, error handling,
and request/response processing.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

import httpx
import json
from typing import Union, Dict, Any, Optional

from .logging_config import get_logger

# Get module logger
logger = get_logger("config")

# Default Configuration
JADX_HOST = "127.0.0.1"
JADX_PORT = 8650
JADX_HTTP_BASE = f"http://{JADX_HOST}:{JADX_PORT}"
AUTH_TOKEN: Optional[str] = None
REQUEST_TIMEOUT: int = 120  # Default timeout in seconds (configurable)


# HTTP Connection Pool Manager
class HttpClientManager:
    """
    Manages a shared HTTP client with connection pooling for better performance.
    Reuses connections across multiple requests instead of creating new ones.
    """
    _client: Optional[httpx.AsyncClient] = None
    
    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """Get or create the shared async HTTP client."""
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


def set_jadx_port(port: int):
    """
    Updates the JADX plugin port (maintains backward compatibility).

    Args:
        port: TCP port number where JADX AI MCP plugin is listening

    Side Effects:
        Updates global JADX_PORT and JADX_HTTP_BASE configuration
    """
    set_jadx_config(JADX_HOST, port)


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


async def health_ping() -> Union[str, Dict[str, Any]]:
    """
    Checks if the JADX Java plugin is reachable (async version).

    Returns:
        Union[str, Dict[str, Any]]: Success message or error dictionary

    Note:
        Performs async HTTP health check with configurable timeout.
        Health check does not require authentication.
    """
    logger.info(f"Attempting to connect to {JADX_HTTP_BASE}/health")
    try:
        client = HttpClientManager.get_client()
        resp = await client.get(f"{JADX_HTTP_BASE}/health")
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.error(f"Health check failed: {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {str(e) or '(no details)'}"}


async def get_from_jadx(
    endpoint: str, 
    params: Dict[str, Any] = {},
    instance_id: Optional[str] = None
) -> Union[str, Dict[str, Any]]:
    """
    Generic async helper to request data from the JADX plugin.

    Args:
        endpoint: API endpoint path (e.g., "class-source", "manifest")
        params: Query parameters dictionary for the request
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

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
    # Determine the base URL based on instance_id
    base_url = JADX_HTTP_BASE
    auth_token = AUTH_TOKEN
    
    # Try to use InstanceRegistry for multi-instance support
    try:
        from .instance_registry import InstanceRegistry
        
        if instance_id:
            instance = InstanceRegistry.get_instance(instance_id)
            if not instance:
                return {"error": f"Instance '{instance_id}' not found"}
            base_url = instance.url
        else:
            # Use default instance if available
            instance = InstanceRegistry.get_default()
            if instance:
                base_url = instance.url
        
        # Use shared auth token from InstanceRegistry if available
        registry_token = InstanceRegistry.get_auth_token()
        if registry_token:
            auth_token = registry_token
            
    except ImportError as e:
        # InstanceRegistry not available, use legacy single-instance mode
        logger.warning(f"InstanceRegistry import failed, using legacy mode: {e}")
    
    url = f"{base_url}/{endpoint.lstrip('/')}"
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    logger.info(f"JADX request: GET {url} (params={list(params.keys()) if params else 'none'})")
    
    try:
        client = HttpClientManager.get_client()
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        
        logger.info(f"JADX response: {resp.status_code} OK (size={len(resp.content)} bytes)")

        # Try to parse JSON, fallback to text if not valid JSON
        try:
            return resp.json()
        except json.JSONDecodeError:
            return {"response": resp.text}

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
        if e.response.status_code == 401:
            error_msg = "Authentication failed. Please check your auth token configuration."
        logger.error(error_msg)
        return {"error": error_msg}

    except Exception as e:
        error_detail = str(e) if str(e) else f"(no message, type={type(e).__name__})"
        error_msg = f"Unexpected error: {type(e).__name__}: {error_detail}"
        logger.error(f"JADX request failed: {error_msg}")
        return {"error": error_msg}

