"""
JADX 实例管理 MCP 工具

提供 5 个工具用于管理多个 JADX 实例：
- list_jadx_instances: 列出所有实例
- add_jadx_instance: 添加新实例
- remove_jadx_instance: 移除实例
- set_default_jadx_instance: 设置默认实例
- get_jadx_instance_info: 获取实例详细信息
"""

from ..instance_registry import InstanceRegistry


def register_instance_tools(mcp):
    """注册实例管理工具到 MCP Server"""
    
    @mcp.tool()
    async def list_jadx_instances() -> dict:
        """
        列出所有已连接的 JADX 实例。
        
        返回每个实例的名称、地址、状态、APK信息等。
        用于了解当前可用的分析目标。
        
        Returns:
            {
                "instances": [
                    {
                        "name": "xhs-v8",
                        "host": "192.168.1.10",
                        "port": 8650,
                        "url": "http://192.168.1.10:8650",
                        "status": "connected",
                        "is_default": true,
                        "apk_info": {...}
                    }
                ],
                "count": 1,
                "default_instance": "xhs-v8"
            }
        """
        instances = InstanceRegistry.list_instances()
        default = InstanceRegistry.get_default()
        return {
            "instances": instances,
            "count": len(instances),
            "default_instance": default.name if default else None,
        }
    
    @mcp.tool()
    async def add_jadx_instance(
        host: str,
        port: int,
        name: str = ""
    ) -> dict:
        """
        动态添加新的 JADX 实例连接。
        
        添加后会自动尝试连接并获取 APK 信息。
        如果是第一个添加的实例，将自动设为默认。
        
        Args:
            host: JADX 实例的 IP 地址（如 "192.168.1.10" 或 "localhost"）
            port: JADX 实例的端口号（如 8650）
            name: 可选的自定义名称。留空则自动使用 APK 名称+版本号
            
        Returns:
            {
                "success": true,
                "instance": {...},
                "message": "成功添加实例 'xhs-v8'"
            }
        """
        # 处理 localhost
        if host.lower() == "localhost":
            host = "127.0.0.1"
        
        result = await InstanceRegistry.add_instance(host, port, name if name else None)
        return result
    
    @mcp.tool()
    async def remove_jadx_instance(name: str) -> dict:
        """
        移除指定的 JADX 实例连接。
        
        如果移除的是默认实例，会自动选择另一个可用实例作为新的默认。
        
        Args:
            name: 要移除的实例名称
            
        Returns:
            {
                "success": true,
                "message": "已移除实例 'xhs-v8'"
            }
        """
        return InstanceRegistry.remove_instance(name)
    
    @mcp.tool()
    async def set_default_jadx_instance(name: str) -> dict:
        """
        设置默认使用的 JADX 实例。
        
        后续不指定 instance_id 的工具调用将使用此实例。
        
        Args:
            name: 要设为默认的实例名称
            
        Returns:
            {
                "success": true,
                "message": "默认实例已设置为 'xhs-v8'"
            }
        """
        return InstanceRegistry.set_default(name)
    
    @mcp.tool()
    async def get_jadx_instance_info(name: str) -> dict:
        """
        获取指定实例的详细信息。
        
        包括连接状态、APK 元数据（包名、版本、SDK等）、最近健康检查时间等。
        
        Args:
            name: 实例名称
            
        Returns:
            {
                "name": "xhs-v8",
                "host": "192.168.1.10",
                "port": 8650,
                "status": "connected",
                "apk_info": {
                    "apk_package": "com.xingin.xhs",
                    "version_name": "8.35.0",
                    "version_code": 8350100,
                    ...
                },
                "last_health_check": "2026-01-12T10:00:00"
            }
        """
        instance = InstanceRegistry.get_instance(name)
        if not instance:
            return {
                "success": False,
                "message": f"实例 '{name}' 不存在",
            }
        return {
            "success": True,
            **instance.to_dict(),
        }
    
    @mcp.tool()
    async def health_check_jadx_instances() -> dict:
        """
        检查所有 JADX 实例的健康状态。
        
        对每个已注册的实例执行健康检查，更新其连接状态。
        
        Returns:
            {
                "total": 3,
                "healthy": 2,
                "instances": [
                    {"name": "xhs-v8", "status": "connected"},
                    {"name": "xhs-v9", "status": "disconnected"}
                ]
            }
        """
        return await InstanceRegistry.health_check_all()
