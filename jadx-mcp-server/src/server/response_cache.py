"""
LRU response cache for deterministic JADX endpoints.

Caches metadata-only responses to avoid redundant HTTP round-trips.
Deterministic endpoints return the same result for the same parameters
until a rename or reconnect changes the underlying data.
"""

import time
from collections import OrderedDict
from typing import Any, Optional

from .logging_config import get_logger

logger = get_logger("response_cache")

# Endpoints safe to cache (metadata-only, deterministic for same class)
CACHEABLE_ENDPOINTS = frozenset({
    "class-info",
    "methods-of-class",
    "fields-of-class",
    "file-info",
    "main-application-classes-names",
})

# Endpoints that mutate class structure — any hit should invalidate cache
_MUTATING_ENDPOINTS = frozenset({
    "rename-class",
    "rename-method",
    "rename-field",
    "rename-package",
})


def _make_cache_key(instance_id: Optional[str], endpoint: str, params: dict[str, Any]) -> str:
    """Build a deterministic cache key from request parameters."""
    inst = instance_id or "default"
    # Sort params for deterministic key; exclude empty values
    sorted_params = sorted((k, v) for k, v in params.items() if v is not None)
    return f"{inst}:{endpoint}:{sorted_params}"


class ResponseCache:
    """LRU cache with TTL for JADX responses.

    Single-threaded (asyncio), but safe to use from coroutines since all
    operations are synchronous and non-blocking.
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 300) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[dict]:
        """Get cached response, or None if miss/expired."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            logger.debug("Cache MISS: %s", key)
            return None

        ts, value = entry
        if time.monotonic() - ts > self._ttl_seconds:
            # Expired — use pop to avoid KeyError if concurrent coroutine already removed it
            self._cache.pop(key, None)
            self._misses += 1
            logger.debug("Cache EXPIRED: %s", key)
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        logger.debug("Cache HIT: %s", key)
        return value

    def put(self, key: str, value: dict) -> None:
        """Store response in cache."""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (time.monotonic(), value)

        # Evict oldest if over capacity
        while len(self._cache) > self._max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug("Cache EVICT (LRU): %s", evicted_key)

    def invalidate_instance(self, instance_id: str) -> None:
        """Clear all cache entries for a specific instance."""
        prefix = f"{instance_id}:"
        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._cache[k]
        if keys_to_remove:
            logger.info("Cache invalidated %d entries for instance '%s'", len(keys_to_remove), instance_id)

    def clear(self) -> None:
        """Clear entire cache."""
        count = len(self._cache)
        self._cache.clear()
        if count:
            logger.info("Cache cleared (%d entries removed)", count)

    def stats(self) -> dict:
        """Return cache hit/miss stats."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }


# Module-level singleton
_cache = ResponseCache()


def get_response_cache() -> ResponseCache:
    """Get the module-level cache singleton."""
    return _cache


def clear_response_cache() -> None:
    """Convenience function to clear the global cache."""
    _cache.clear()
