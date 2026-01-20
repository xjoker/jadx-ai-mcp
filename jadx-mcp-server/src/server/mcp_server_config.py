"""
MCP Server Configuration - 全局服务器配置
存储 MCP Server 的 host 和 port 信息供其他模块使用
"""

import os
from typing import Optional

# 全局 MCP Server 配置
_MCP_SERVER_HOST: Optional[str] = None
_MCP_SERVER_PORT: Optional[int] = None


def set_mcp_server_url(host: str, port: int):
    """
    设置 MCP Server 的 host 和 port
    
    Args:
        host: MCP Server 监听的主机地址
        port: MCP Server 监听的端口
    """
    global _MCP_SERVER_HOST, _MCP_SERVER_PORT
    _MCP_SERVER_HOST = host
    _MCP_SERVER_PORT = port


def get_mcp_server_url() -> str:
    """
    获取 MCP Server 的完整 URL
    
    Returns:
        完整的 MCP Server URL (如 http://192.168.1.100:8651)
    
    优先级:
        1. 环境变量 MCP_SERVER_URL
        2. 已设置的全局配置
        3. 默认值 http://localhost:8765
    """
    # 1. 优先使用环境变量
    env_url = os.getenv("MCP_SERVER_URL")
    if env_url:
        return env_url.rstrip("/")
    
    # 2. 使用已设置的配置
    if _MCP_SERVER_HOST and _MCP_SERVER_PORT:
        # 处理特殊情况: 0.0.0.0 应该替换为 localhost 或实际 IP
        host = _MCP_SERVER_HOST
        if host == "0.0.0.0":
            # Docker 环境下，使用 host.docker.internal 或 localhost
            # 但这是服务器端代码，AI 访问时应该用外部地址
            # 这里使用 localhost 作为回退
            host = "localhost"
        
        return f"http://{host}:{_MCP_SERVER_PORT}"
    
    # 3. 默认值（兼容旧代码）
    return "http://localhost:8765"


def get_transfer_base_url() -> str:
    """
    获取 Transfer API 的基础 URL
    
    Returns:
        Transfer API 基础 URL (如 http://192.168.1.100:8651/transfer)
    """
    return f"{get_mcp_server_url()}/transfer"
