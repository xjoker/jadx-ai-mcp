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
    """Transfer operation type"""
    DOWNLOAD = "download"
    UPLOAD = "upload"


class ResourceType(Enum):
    """Resource type"""
    BATCH_CLASSES = "batch_classes"
    BATCH_METHODS = "batch_methods"
    PROJECT_EXPORT = "project_export"


@dataclass
class TransferToken:
    """Transfer token"""
    token_id: str
    operation: Operation
    resource_type: ResourceType
    created_at: float
    expires_at: float
    used: bool = False
    # Request parameters (stored for use during download)
    params: Optional[dict] = field(default_factory=dict)


class TransferStoreCapacityError(RuntimeError):
    """Raised when the in-memory transfer token store reaches capacity."""


class TransferTokenStore:
    """
    In-memory token store with automatic expiry cleanup.

    Features:
    - Random 32-character token generation
    - Automatic expiry mechanism
    - Single-use marking
    - Background auto-cleanup
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
        Create a new token.

        Args:
            operation: Operation type (download/upload)
            resource_type: Resource type
            timeout_seconds: Token expiry duration in seconds
            params: Additional parameters

        Returns:
            TransferToken: The newly created token
        """
        token_id = secrets.token_urlsafe(24)  # Generate a 32-character URL-safe token
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
        Validate a token; returns None if expired or not found.

        Args:
            token_id: Token ID

        Returns:
            TransferToken or None
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
        Atomically consume a token.

        Steps:
        1. Existence check
        2. Expiry check
        3. Already-used check
        4. resource_type match check
        5. Mark as used
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
        Mark a token as used.

        Args:
            token_id: Token ID

        Returns:
            True if successfully marked, False otherwise
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
        Revoke a token.

        Args:
            token_id: Token ID

        Returns:
            True if successfully revoked, False otherwise
        """
        with self._lock:
            removed = self._tokens.pop(token_id, None)
            if removed:
                logger.info(f"Token {token_id[:8]}... revoked")
                return True
            return False
    
    def get_status(self, token_id: str) -> dict:
        """
        Get token status.

        Args:
            token_id: Token ID

        Returns:
            Status dict {exists, used, expires_in}
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
        """Background task to automatically clean up expired tokens."""
        logger.info("Started auto-cleanup task")
        while True:
            try:
                await asyncio.sleep(30)  # Run cleanup every 30 seconds

                with self._lock:
                    self._cleanup_expired_locked()
                    if not self._tokens:
                        logger.info("No tokens remaining, stopping cleanup task")
                        break

            except Exception as e:
                logger.error(f"Error in auto-cleanup: {e}")
                await asyncio.sleep(60)  # Extend wait time after an error


# Global singleton
_store: Optional[TransferTokenStore] = None


def get_token_store() -> TransferTokenStore:
    """Get the global token store instance."""
    global _store
    if _store is None:
        _store = TransferTokenStore()
    return _store
