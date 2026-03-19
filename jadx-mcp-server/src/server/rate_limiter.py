"""
Rate Limiter - 速率限制
防止令牌创建和下载滥用
"""

import time
from collections import defaultdict, deque
from typing import Deque, Dict
from dataclasses import dataclass
from src.server.logging_config import get_logger

logger = get_logger("rate_limiter")


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    max_requests: int = 10  # 最大请求数
    window_seconds: int = 60  # 时间窗口（秒）


class RateLimiter:
    """
    基于 IP 的速率限制器
    
    特性:
    - 滑动时间窗口
    - 自动清理过期记录
    - 线程安全（单进程）
    """
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
        logger.info(
            f"RateLimiter initialized: {self.config.max_requests} requests "
            f"per {self.config.window_seconds}s"
        )
    
    def check(self, client_id: str) -> bool:
        """
        检查客户端是否超过速率限制
        
        Args:
            client_id: 客户端标识（通常是 IP 地址）
        
        Returns:
            True 如果允许请求，False 如果超过限制
        """
        now = time.time()
        cutoff = now - self.config.window_seconds

        # 清理过期记录 — O(1) popleft（时间戳天然有序）
        dq = self.requests[client_id]
        while dq and dq[0] <= cutoff:
            dq.popleft()

        # 检查是否超过限制
        if len(dq) >= self.config.max_requests:
            logger.warning(
                f"Rate limit exceeded for {client_id}: "
                f"{len(self.requests[client_id])}/{self.config.max_requests} "
                f"in {self.config.window_seconds}s"
            )
            return False
        
        # 记录本次请求
        self.requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        """获取剩余可用请求数"""
        now = time.time()
        cutoff = now - self.config.window_seconds
        dq = self.requests[client_id]
        while dq and dq[0] <= cutoff:
            dq.popleft()
        return max(0, self.config.max_requests - len(dq))
    
    def get_reset_time(self, client_id: str) -> int:
        """获取限制重置时间（秒）"""
        dq = self.requests[client_id]
        if not dq:
            return 0

        # deque 天然有序，dq[0] 即最早的时间戳
        reset_time = dq[0] + self.config.window_seconds - time.time()
        return max(0, int(reset_time))


# 全局实例 - 令牌创建限制（更严格）
_token_limiter: RateLimiter = None

# 全局实例 - 下载限制
_download_limiter: RateLimiter = None


def get_token_limiter() -> RateLimiter:
    """获取令牌创建限制器（10 次/分钟）"""
    global _token_limiter
    if _token_limiter is None:
        _token_limiter = RateLimiter(RateLimitConfig(max_requests=10, window_seconds=60))
    return _token_limiter


def get_download_limiter() -> RateLimiter:
    """获取下载限制器（20 次/分钟）"""
    global _download_limiter
    if _download_limiter is None:
        _download_limiter = RateLimiter(RateLimitConfig(max_requests=20, window_seconds=60))
    return _download_limiter
