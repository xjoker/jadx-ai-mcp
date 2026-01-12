"""
JADX MCP Server - Configuration Module

This module manages server configuration, HTTP client setup, and communication
with the JADX Java plugin. Handles connection management, error handling,
and request/response processing.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

import logging
import httpx
import json
import sys
from typing import Union, Dict, Any, Optional

# Default Configuration
JADX_HOST = "127.0.0.1"
JADX_PORT = 8650
JADX_HTTP_BASE = f"http://{JADX_HOST}:{JADX_PORT}"
AUTH_TOKEN: Optional[str] = None

# Logging Setup
logger = logging.getLogger("jadx-mcp-server")
logger.setLevel(logging.ERROR)
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)


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


def _get_auth_headers() -> Dict[str, str]:
    """
    Generates authentication headers if token is configured.

    Returns:
        Dict containing Authorization header if token is set, empty dict otherwise
    """
    if AUTH_TOKEN:
        return {"Authorization": f"Bearer {AUTH_TOKEN}"}
    return {}


def health_ping() -> Union[str, Dict[str, Any]]:
    """
    Checks if the JADX Java plugin is reachable.

    Returns:
        Union[str, Dict[str, Any]]: Success message or error dictionary

    Note:
        Performs synchronous HTTP health check with 60-second timeout.
        Health check does not require authentication.
    """
    print(f"Attempting to connect to {JADX_HTTP_BASE}/health")
    try:
        with httpx.Client() as client:
            # Health check endpoint does not require auth
            resp = client.get(f"{JADX_HTTP_BASE}/health", timeout=60)
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"error": str(e)}


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
            
    except ImportError:
        # InstanceRegistry not available, use legacy single-instance mode
        pass
    
    url = f"{base_url}/{endpoint.lstrip('/')}"
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=60)
            resp.raise_for_status()

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
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

