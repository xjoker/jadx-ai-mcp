"""
LRU response cache for deterministic JADX endpoints.

Caches metadata-only responses to avoid redundant HTTP round-trips.
Deterministic endpoints return the same result for the same parameters
until a rename or reconnect changes the underlying data.
"""

import time
import threading
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
    "cache/clear",
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

    Thread-safe for concurrent async tasks and background registry updates.
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 300) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _resolve_instance_name(self, instance_id: Optional[str]) -> str:
        """Resolve aliases/default to the canonical registry instance name when possible."""
        try:
            from .instance_registry import InstanceRegistry
        except ImportError:
            return instance_id or "default"

        if instance_id:
            instance = InstanceRegistry.get_instance(instance_id)
            if instance is None:
                instance = InstanceRegistry.find_instance_by_apk(instance_id)
            return instance.name if instance else instance_id

        default_instance = InstanceRegistry.get_default()
        if default_instance:
            return default_instance.name

        return "default"

    def _normalize_key(self, key: str) -> str:
        """Normalize the instance segment of a cache key."""
        if ":" not in key:
            return key

        instance_id, remainder = key.split(":", 1)
        return f"{self._resolve_instance_name(instance_id)}:{remainder}"

    def get(self, key: str) -> Optional[dict]:
        """Get cached response, or None if miss/expired."""
        normalized_key = self._normalize_key(key)
        with self._lock:
            entry = self._cache.get(normalized_key)
            if entry is None:
                self._misses += 1
                logger.debug("Cache MISS: %s", normalized_key)
                return None

            ts, value = entry
            if time.monotonic() - ts > self._ttl_seconds:
                # Expired — use pop to avoid KeyError if concurrent thread already removed it
                self._cache.pop(normalized_key, None)
                self._misses += 1
                logger.debug("Cache EXPIRED: %s", normalized_key)
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(normalized_key)
            self._hits += 1
            logger.debug("Cache HIT: %s", normalized_key)
            return value

    def put(self, key: str, value: dict) -> None:
        """Store response in cache."""
        normalized_key = self._normalize_key(key)
        with self._lock:
            if normalized_key in self._cache:
                self._cache.move_to_end(normalized_key)
            self._cache[normalized_key] = (time.monotonic(), value)

            # Evict oldest if over capacity
            while len(self._cache) > self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug("Cache EVICT (LRU): %s", evicted_key)

    def invalidate_instance(self, instance_id: str) -> None:
        """Clear all cache entries for a specific instance."""
        canonical_instance = self._resolve_instance_name(instance_id)
        prefix = f"{canonical_instance}:"
        with self._lock:
            keys_to_remove = [key for key in self._cache if key.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
        if keys_to_remove:
            logger.info("Cache invalidated %d entries for instance '%s'", len(keys_to_remove), canonical_instance)

    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
        if count:
            logger.info("Cache cleared (%d entries removed)", count)

    def stats(self) -> dict:
        """Return cache hit/miss stats."""
        with self._lock:
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
