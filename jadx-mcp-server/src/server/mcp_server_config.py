"""
MCP Server Configuration - global server configuration.
Stores MCP Server URL information for use by the Transfer API.

Configuration priority:
1. Environment variable MCP_SERVER_URL
2. Config file [server] mcp_url
"""

import os
from typing import Optional

from .logging_config import get_logger

logger = get_logger("mcp_server_config")

# Globally configured MCP Server URL
_MCP_SERVER_URL_FROM_CONFIG: Optional[str] = None


def set_mcp_server_url_from_config(url: str):
    """
    Set the MCP Server URL from the configuration file.

    Args:
        url: External access address of the MCP Server (e.g. http://192.168.1.100:8651)
    """
    global _MCP_SERVER_URL_FROM_CONFIG
    _MCP_SERVER_URL_FROM_CONFIG = url
    if url:
        logger.info(f"MCP Server URL set from config: {url}")


def get_mcp_server_url() -> str:
    """
    Get the full MCP Server URL.

    Returns:
        Full MCP Server URL (e.g. http://192.168.1.100:8651)

    Priority:
        1. Environment variable MCP_SERVER_URL (highest)
        2. Config file [server] mcp_url
        3. Default value http://localhost:8651
    """
    # 1. Highest priority: environment variable
    env_url = os.getenv("MCP_SERVER_URL")
    if env_url:
        return env_url.rstrip("/")

    # 2. Second priority: config file
    if _MCP_SERVER_URL_FROM_CONFIG:
        return _MCP_SERVER_URL_FROM_CONFIG.rstrip("/")

    # 3. Default value
    logger.warning("MCP Server URL not configured, using default http://localhost:8651")
    return "http://localhost:8651"


def get_transfer_base_url() -> str:
    """
    Get the base URL for the Transfer API.

    Returns:
        Transfer API base URL (e.g. http://192.168.1.100:8651/transfer)
    """
    return f"{get_mcp_server_url()}/transfer"
