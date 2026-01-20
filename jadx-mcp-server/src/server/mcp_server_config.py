"""
MCP Server Configuration - 全局服务器配置
存储 MCP Server 的 URL 信息供 Transfer API 使用

配置优先级:
1. 环境变量 MCP_SERVER_URL
2. 配置文件 [server] mcp_url
"""

import os
from typing import Optional

from .logging_config import get_logger

logger = get_logger("mcp_server_config")

# 全局配置的 MCP Server URL
_MCP_SERVER_URL_FROM_CONFIG: Optional[str] = None


def set_mcp_server_url_from_config(url: str):
    """
    从配置文件设置 MCP Server URL
    
    Args:
        url: MCP Server 的外部访问地址（如 http://192.168.1.100:8651）
    """
    global _MCP_SERVER_URL_FROM_CONFIG
    _MCP_SERVER_URL_FROM_CONFIG = url
    if url:
        logger.info(f"MCP Server URL set from config: {url}")


def get_mcp_server_url() -> str:
    """
    获取 MCP Server 的完整 URL
    
    Returns:
        完整的 MCP Server URL (如 http://192.168.1.100:8651)
    
    优先级:
        1. 环境变量 MCP_SERVER_URL（最高）
        2. 配置文件 [server] mcp_url
        3. 默认值 http://localhost:8651
    """
    # 1. 最高优先级：环境变量
    env_url = os.getenv("MCP_SERVER_URL")
    if env_url:
        return env_url.rstrip("/")
    
    # 2. 次优先级：配置文件
    if _MCP_SERVER_URL_FROM_CONFIG:
        return _MCP_SERVER_URL_FROM_CONFIG.rstrip("/")
    
    # 3. 默认值
    logger.warning("MCP Server URL not configured, using default http://localhost:8651")
    return "http://localhost:8651"


def get_transfer_base_url() -> str:
    """
    获取 Transfer API 的基础 URL
    
    Returns:
        Transfer API 基础 URL (如 http://192.168.1.100:8651/transfer)
    """
    return f"{get_mcp_server_url()}/transfer"
