import asyncio
import secrets
import threading
import time
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


class TransferStoreCapacityError(RuntimeError):
    """Raised when the in-memory transfer token store reaches capacity."""


class TransferTokenStore:
    """
    内存令牌存储，支持自动过期清理
    
    特性:
    - 随机 32 字符令牌生成
    - 自动过期机制
    - 单次使用标记
    - 后台自动清理
    """
    
    def __init__(self, max_tokens: int = 1000):
        self._tokens: Dict[str, TransferToken] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        self._max_tokens = max_tokens
        logger.info(f"TransferTokenStore initialized (max_tokens={max_tokens})")

    def _cleanup_expired_locked(self, now: Optional[float] = None) -> int:
        """Remove expired tokens while holding the store lock."""
        now = time.time() if now is None else now
        expired_tokens = [
            token_id
            for token_id, token in self._tokens.items()
            if token.expires_at <= now
        ]

        for token_id in expired_tokens:
            self._tokens.pop(token_id, None)

        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")

        return len(expired_tokens)

    def _ensure_cleanup_task(self) -> None:
        """Start the background cleanup task when running inside an event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = loop.create_task(self._auto_cleanup())
    
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

        with self._lock:
            self._cleanup_expired_locked(now)
            if len(self._tokens) >= self._max_tokens:
                logger.warning(
                    f"Transfer token store full: {len(self._tokens)}/{self._max_tokens}"
                )
                raise TransferStoreCapacityError(
                    f"Too many active transfer tokens ({self._max_tokens} max). "
                    "Wait for existing tokens to expire before creating more."
                )

            token = TransferToken(
                token_id=token_id,
                operation=operation,
                resource_type=resource_type,
                created_at=now,
                expires_at=now + timeout_seconds,
                params=params or {}
            )

            self._tokens[token_id] = token

        self._ensure_cleanup_task()
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
        with self._lock:
            token = self._tokens.get(token_id)
            if token is None:
                logger.warning(f"Token {token_id[:8]}... not found")
                return None

            if time.time() >= token.expires_at:
                logger.warning(f"Token {token_id[:8]}... expired")
                self._tokens.pop(token_id, None)
                return None

            if token.used:
                logger.warning(f"Token {token_id[:8]}... already used")
                return None

            return token

    def consume(
        self,
        token_id: str,
        expected_resource_type: ResourceType,
    ) -> Optional[TransferToken]:
        """
        原子地消费令牌。

        步骤:
        1. 存在检查
        2. 过期检查
        3. 已使用检查
        4. resource_type 匹配检查
        5. 标记为已使用
        """
        with self._lock:
            token = self._tokens.get(token_id)
            if token is None:
                logger.warning(f"Token {token_id[:8]}... not found during consume")
                return None

            if time.time() >= token.expires_at:
                logger.warning(f"Token {token_id[:8]}... expired during consume")
                self._tokens.pop(token_id, None)
                return None

            if token.used:
                logger.warning(f"Token {token_id[:8]}... replay blocked (already used)")
                return None

            if token.resource_type != expected_resource_type:
                logger.warning(
                    f"Token {token_id[:8]}... resource mismatch: "
                    f"expected {expected_resource_type.value}, got {token.resource_type.value}"
                )
                return None

            token.used = True
            logger.info(f"Token {token_id[:8]}... consumed for {expected_resource_type.value}")
            return token
    
    def mark_used(self, token_id: str) -> bool:
        """
        标记令牌为已使用
        
        Args:
            token_id: 令牌 ID
        
        Returns:
            是否成功标记
        """
        with self._lock:
            token = self._tokens.get(token_id)
            if token is None:
                return False
            if time.time() >= token.expires_at:
                self._tokens.pop(token_id, None)
                return False
            token.used = True
            logger.info(f"Token {token_id[:8]}... marked as used")
            return True
    
    def revoke(self, token_id: str) -> bool:
        """
        撤销令牌
        
        Args:
            token_id: 令牌 ID
        
        Returns:
            是否成功撤销
        """
        with self._lock:
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
        with self._lock:
            token = self._tokens.get(token_id)
            if token is None:
                return {"exists": False, "used": False, "expires_in": 0}

            if time.time() >= token.expires_at:
                self._tokens.pop(token_id, None)
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

                with self._lock:
                    self._cleanup_expired_locked()
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
