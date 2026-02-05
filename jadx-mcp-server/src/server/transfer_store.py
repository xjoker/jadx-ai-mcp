"""
Transfer Token Store - 令牌管理
用于大文件传输的临时令牌生成、验证和过期管理
"""

import secrets
import time
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
from src.server.logging_config import get_logger

logger = get_logger("transfer_store")


class Operation(Enum):
    """传输操作类型"""
    DOWNLOAD = "download"
    UPLOAD = "upload"


class ResourceType(Enum):
    """资源类型"""
    BATCH_CLASSES = "batch_classes"
    BATCH_METHODS = "batch_methods"
    PROJECT_EXPORT = "project_export"


@dataclass
class TransferToken:
    """传输令牌"""
    token_id: str
    operation: Operation
    resource_type: ResourceType
    created_at: float
    expires_at: float
    used: bool = False
    # 请求参数（存储下载时需要的参数）
    params: Optional[dict] = field(default_factory=dict)


class TransferTokenStore:
    """
    内存令牌存储，支持自动过期清理
    
    特性:
    - 随机 32 字符令牌生成
    - 自动过期机制
    - 单次使用标记
    - 后台自动清理
    """
    
    def __init__(self):
        self._tokens: Dict[str, TransferToken] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        logger.info("TransferTokenStore initialized")
    
    def create(
        self, 
        operation: Operation, 
        resource_type: ResourceType, 
        timeout_seconds: int = 120,
        params: Optional[dict] = None
    ) -> TransferToken:
        """
        创建新令牌
        
        Args:
            operation: 操作类型 (download/upload)
            resource_type: 资源类型
            timeout_seconds: 超时时间（秒）
            params: 额外参数
        
        Returns:
            TransferToken: 新创建的令牌
        """
        token_id = secrets.token_urlsafe(24)  # 生成 32 字符 URL 安全令牌
        now = time.time()
        
        token = TransferToken(
            token_id=token_id,
            operation=operation,
            resource_type=resource_type,
            created_at=now,
            expires_at=now + timeout_seconds,
            params=params or {}
        )
        
        self._tokens[token_id] = token
        
        # 启动清理任务（如果尚未运行）
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._auto_cleanup())
        
        logger.info(f"Created token {token_id[:8]}... for {resource_type.value}, expires in {timeout_seconds}s")
        return token
    
    def validate(self, token_id: str) -> Optional[TransferToken]:
        """
        验证令牌，过期返回 None
        
        Args:
            token_id: 令牌 ID
        
        Returns:
            TransferToken 或 None
        """
        token = self._tokens.get(token_id)
        if token is None:
            logger.warning(f"Token {token_id[:8]}... not found")
            return None
        
        if time.time() > token.expires_at:
            logger.warning(f"Token {token_id[:8]}... expired")
            self.revoke(token_id)
            return None
        
        return token
    
    def mark_used(self, token_id: str) -> bool:
        """
        标记令牌为已使用
        
        Args:
            token_id: 令牌 ID
        
        Returns:
            是否成功标记
        """
        if token_id in self._tokens:
            self._tokens[token_id].used = True
            logger.info(f"Token {token_id[:8]}... marked as used")
            return True
        return False
    
    def revoke(self, token_id: str) -> bool:
        """
        撤销令牌
        
        Args:
            token_id: 令牌 ID
        
        Returns:
            是否成功撤销
        """
        removed = self._tokens.pop(token_id, None)
        if removed:
            logger.info(f"Token {token_id[:8]}... revoked")
            return True
        return False
    
    def get_status(self, token_id: str) -> dict:
        """
        获取令牌状态
        
        Args:
            token_id: 令牌 ID
        
        Returns:
            状态字典 {exists, used, expires_in}
        """
        token = self._tokens.get(token_id)
        if token is None:
            return {"exists": False, "used": False, "expires_in": 0}
        
        expires_in = max(0, int(token.expires_at - time.time()))
        return {
            "exists": True, 
            "used": token.used, 
            "expires_in": expires_in,
            "resource_type": token.resource_type.value,
            "operation": token.operation.value
        }
    
    async def _auto_cleanup(self):
        """后台自动清理过期令牌"""
        logger.info("Started auto-cleanup task")
        while True:
            try:
                await asyncio.sleep(30)  # 每 30 秒清理一次
                
                now = time.time()
                expired_tokens = [
                    token_id for token_id, token in self._tokens.items()
                    if token.expires_at < now
                ]
                
                for token_id in expired_tokens:
                    self._tokens.pop(token_id, None)
                
                if expired_tokens:
                    logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
                
                # 如果没有令牌了，停止清理任务
                if not self._tokens:
                    logger.info("No tokens remaining, stopping cleanup task")
                    break
                    
            except Exception as e:
                logger.error(f"Error in auto-cleanup: {e}")
                await asyncio.sleep(60)  # 出错后延长等待时间


# 全局单例
_store: Optional[TransferTokenStore] = None


def get_token_store() -> TransferTokenStore:
    """获取全局令牌存储实例"""
    global _store
    if _store is None:
        _store = TransferTokenStore()
    return _store
