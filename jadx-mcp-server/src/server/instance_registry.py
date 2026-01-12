"""
JADX 实例注册中心

管理多个 JADX 实例的连接、状态和健康检查。
所有实例共用一个认证 Token。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class JadxInstance:
    """JADX 实例信息"""
    name: str                 # 实例名称 (用户自定义或自动生成)
    host: str                 # IP 地址
    port: int                 # 端口
    status: str = "unknown"   # "connected" | "disconnected" | "error"
    apk_info: dict = field(default_factory=dict)  # 从 /apk-info 获取的信息
    last_health_check: Optional[datetime] = None
    error_message: str = ""   # 最近的错误信息
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "url": self.url,
            "status": self.status,
            "apk_info": self.apk_info,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "error_message": self.error_message,
        }


class InstanceRegistry:
    """JADX 实例注册中心（单例）"""
    
    _instances: Dict[str, JadxInstance] = {}
    _default_instance: Optional[str] = None
    _shared_auth_token: Optional[str] = None
    _lock = asyncio.Lock()
    
    @classmethod
    def set_auth_token(cls, token: str) -> None:
        """设置所有实例共用的认证 Token"""
        cls._shared_auth_token = token
        logger.info("认证 Token 已设置")
    
    @classmethod
    def get_auth_token(cls) -> Optional[str]:
        """获取共用的认证 Token"""
        return cls._shared_auth_token
    
    @classmethod
    async def add_instance(
        cls, 
        host: str, 
        port: int, 
        name: str = None
    ) -> dict:
        """
        添加新的 JADX 实例
        
        Args:
            host: JADX 实例的 IP 地址
            port: JADX 实例的端口号
            name: 可选的自定义名称，留空则自动使用 APK 名称+版本号
            
        Returns:
            {"success": bool, "instance": dict, "message": str}
        """
        async with cls._lock:
            try:
                # 1. 连接并获取 /apk-info
                apk_info = await cls._fetch_apk_info(host, port)
                
                # 2. 确定实例名称
                if not name:
                    name = apk_info.get("instance_name") or f"jadx-{port}"
                
                # 3. 检查名称是否已存在
                if name in cls._instances:
                    return {
                        "success": False,
                        "message": f"实例名称 '{name}' 已存在，请使用不同的名称",
                    }
                
                # 4. 创建并注册实例
                instance = JadxInstance(
                    name=name,
                    host=host,
                    port=port,
                    status="connected",
                    apk_info=apk_info,
                    last_health_check=datetime.now(),
                )
                cls._instances[name] = instance
                
                # 5. 如果是第一个实例，设为默认
                if cls._default_instance is None:
                    cls._default_instance = name
                    logger.info(f"设置默认实例: {name}")
                
                logger.info(f"成功添加 JADX 实例: {name} ({host}:{port})")
                return {
                    "success": True,
                    "instance": instance.to_dict(),
                    "message": f"成功添加实例 '{name}'",
                }
                
            except Exception as e:
                error_msg = f"添加实例失败: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "message": error_msg,
                }
    
    @classmethod
    async def _fetch_apk_info(cls, host: str, port: int) -> dict:
        """从 JADX 实例获取 APK 信息"""
        url = f"http://{host}:{port}/apk-info"
        headers = {}
        if cls._shared_auth_token:
            headers["Authorization"] = f"Bearer {cls._shared_auth_token}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    
    @classmethod
    async def _check_health(cls, host: str, port: int) -> bool:
        """检查 JADX 实例健康状态"""
        url = f"http://{host}:{port}/health"
        headers = {}
        if cls._shared_auth_token:
            headers["Authorization"] = f"Bearer {cls._shared_auth_token}"
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers=headers)
                return response.status_code == 200
        except Exception:
            return False
    
    @classmethod
    def remove_instance(cls, name: str) -> dict:
        """
        移除指定的 JADX 实例
        
        Args:
            name: 实例名称
            
        Returns:
            {"success": bool, "message": str}
        """
        if name not in cls._instances:
            return {
                "success": False,
                "message": f"实例 '{name}' 不存在",
            }
        
        del cls._instances[name]
        
        # 如果移除的是默认实例，重新选择
        if cls._default_instance == name:
            cls._default_instance = next(iter(cls._instances), None)
            if cls._default_instance:
                logger.info(f"默认实例已更改为: {cls._default_instance}")
        
        logger.info(f"已移除实例: {name}")
        return {
            "success": True,
            "message": f"已移除实例 '{name}'",
        }
    
    @classmethod
    def list_instances(cls) -> List[dict]:
        """列出所有已注册的实例"""
        instances = [inst.to_dict() for inst in cls._instances.values()]
        for inst in instances:
            inst["is_default"] = inst["name"] == cls._default_instance
        return instances
    
    @classmethod
    def set_default(cls, name: str) -> dict:
        """
        设置默认实例
        
        Args:
            name: 实例名称
            
        Returns:
            {"success": bool, "message": str}
        """
        if name not in cls._instances:
            return {
                "success": False,
                "message": f"实例 '{name}' 不存在",
            }
        
        cls._default_instance = name
        logger.info(f"默认实例已设置为: {name}")
        return {
            "success": True,
            "message": f"默认实例已设置为 '{name}'",
        }
    
    @classmethod
    def get_default(cls) -> Optional[JadxInstance]:
        """获取默认实例"""
        if cls._default_instance and cls._default_instance in cls._instances:
            return cls._instances[cls._default_instance]
        # 如果没有默认实例，返回第一个
        if cls._instances:
            return next(iter(cls._instances.values()))
        return None
    
    @classmethod
    def get_instance(cls, name: str) -> Optional[JadxInstance]:
        """获取指定名称的实例"""
        return cls._instances.get(name)
    
    @classmethod
    async def health_check_all(cls) -> dict:
        """
        检查所有实例的健康状态
        
        Returns:
            {"total": int, "healthy": int, "instances": [{"name": str, "status": str}]}
        """
        results = []
        healthy_count = 0
        
        for name, instance in cls._instances.items():
            try:
                is_healthy = await cls._check_health(instance.host, instance.port)
                instance.status = "connected" if is_healthy else "disconnected"
                instance.last_health_check = datetime.now()
                if is_healthy:
                    healthy_count += 1
                    instance.error_message = ""
                else:
                    instance.error_message = "健康检查失败"
            except Exception as e:
                instance.status = "error"
                instance.error_message = str(e)
            
            results.append({
                "name": name,
                "status": instance.status,
            })
        
        return {
            "total": len(cls._instances),
            "healthy": healthy_count,
            "instances": results,
        }
    
    @classmethod
    def get_instance_count(cls) -> int:
        """获取已注册的实例数量"""
        return len(cls._instances)
    
    @classmethod
    def clear_all(cls) -> None:
        """清除所有实例（用于测试）"""
        cls._instances.clear()
        cls._default_instance = None
