"""
Rate Limiter - prevents abuse of token creation and download endpoints
"""

import time
from collections import defaultdict, deque
from typing import Deque, Dict
from dataclasses import dataclass
from src.server.logging_config import get_logger

logger = get_logger("rate_limiter")


@dataclass
class RateLimitConfig:
    """Rate limiter configuration"""
    max_requests: int = 10  # Maximum number of requests
    window_seconds: int = 60  # Time window in seconds
    max_keys: int = 10000  # Maximum number of active clients


class RateLimiter:
    """
    IP-based rate limiter.

    Features:
    - Sliding time window
    - Automatic cleanup of expired records
    - Thread-safe (single process)
    """

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
        logger.info(
            f"RateLimiter initialized: {self.config.max_requests} requests "
            f"per {self.config.window_seconds}s "
            f"(max_keys={self.config.max_keys})"
        )

    def _prune_expired_entries(self, now: float) -> None:
        """Drop expired timestamps and empty client buckets."""
        cutoff = now - self.config.window_seconds
        empty_clients = []

        for client_id, dq in self.requests.items():
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if not dq:
                empty_clients.append(client_id)

        for client_id in empty_clients:
            self.requests.pop(client_id, None)
    
    def check(self, client_id: str) -> bool:
        """
        Check whether a client has exceeded the rate limit.

        Args:
            client_id: Client identifier (typically an IP address)

        Returns:
            True if the request is allowed, False if the limit is exceeded
        """
        now = time.time()
        self._prune_expired_entries(now)

        if client_id not in self.requests and len(self.requests) >= self.config.max_keys:
            logger.warning(
                f"Rate limiter key capacity exceeded: {len(self.requests)}/{self.config.max_keys}"
            )
            return False

        dq = self.requests[client_id]

        # Check if limit is exceeded
        if len(dq) >= self.config.max_requests:
            logger.warning(
                f"Rate limit exceeded for {client_id}: "
                f"{len(dq)}/{self.config.max_requests} "
                f"in {self.config.window_seconds}s"
            )
            return False

        # Record the current request
        self.requests[client_id].append(now)
        return True

    def get_remaining(self, client_id: str) -> int:
        """Get the number of remaining allowed requests."""
        self._prune_expired_entries(time.time())
        dq = self.requests.get(client_id)
        if dq is None:
            return self.config.max_requests
        return max(0, self.config.max_requests - len(dq))

    def get_reset_time(self, client_id: str) -> int:
        """Get the time in seconds until the rate limit resets."""
        self._prune_expired_entries(time.time())
        dq = self.requests.get(client_id)
        if not dq:
            return 0

        # deque is naturally ordered; dq[0] is the earliest timestamp
        reset_time = dq[0] + self.config.window_seconds - time.time()
        return max(0, int(reset_time))


# Global instance - token creation limiter (stricter)
_token_limiter: RateLimiter = None

# Global instance - download limiter
_download_limiter: RateLimiter = None


def get_token_limiter() -> RateLimiter:
    """Get the token creation rate limiter (10 requests/minute)."""
    global _token_limiter
    if _token_limiter is None:
        _token_limiter = RateLimiter(RateLimitConfig(max_requests=10, window_seconds=60))
    return _token_limiter


def get_download_limiter() -> RateLimiter:
    """Get the download rate limiter (20 requests/minute)."""
    global _download_limiter
    if _download_limiter is None:
        _download_limiter = RateLimiter(RateLimitConfig(max_requests=20, window_seconds=60))
    return _download_limiter
