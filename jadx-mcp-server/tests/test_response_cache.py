"""Tests for the JADX response cache."""

import time

import pytest

from src.server.instance_registry import InstanceRegistry
from src.server.response_cache import (
    CACHEABLE_ENDPOINTS,
    ResponseCache,
    _MUTATING_ENDPOINTS,
    _make_cache_key,
)


class TestCacheKey:
    def test_default_instance(self):
        key = _make_cache_key(None, "class-info", {"class_name": "com.A"})
        assert key.startswith("default:class-info:")

    def test_named_instance(self):
        key = _make_cache_key("my-app", "class-info", {"class_name": "com.A"})
        assert key.startswith("my-app:class-info:")

    def test_params_sorted(self):
        k1 = _make_cache_key(None, "ep", {"b": "2", "a": "1"})
        k2 = _make_cache_key(None, "ep", {"a": "1", "b": "2"})
        assert k1 == k2

    def test_different_params_different_key(self):
        k1 = _make_cache_key(None, "class-info", {"class_name": "com.A"})
        k2 = _make_cache_key(None, "class-info", {"class_name": "com.B"})
        assert k1 != k2


class TestResponseCache:
    def test_put_and_get(self):
        cache = ResponseCache(max_size=10, ttl_seconds=60)
        cache.put("k1", {"data": 1})
        assert cache.get("k1") == {"data": 1}

    def test_miss_returns_none(self):
        cache = ResponseCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = ResponseCache(max_size=10, ttl_seconds=0)
        cache.put("k1", {"data": 1})
        # TTL=0 means immediately expired
        assert cache.get("k1") is None

    def test_lru_eviction(self):
        cache = ResponseCache(max_size=2, ttl_seconds=60)
        cache.put("k1", {"a": 1})
        cache.put("k2", {"b": 2})
        cache.put("k3", {"c": 3})  # should evict k1
        assert cache.get("k1") is None
        assert cache.get("k2") == {"b": 2}
        assert cache.get("k3") == {"c": 3}

    def test_lru_access_refreshes(self):
        cache = ResponseCache(max_size=2, ttl_seconds=60)
        cache.put("k1", {"a": 1})
        cache.put("k2", {"b": 2})
        cache.get("k1")  # refresh k1
        cache.put("k3", {"c": 3})  # should evict k2 (oldest untouched)
        assert cache.get("k1") == {"a": 1}
        assert cache.get("k2") is None

    def test_invalidate_instance(self):
        cache = ResponseCache(max_size=10, ttl_seconds=60)
        cache.put("app1:class-info:x", {"a": 1})
        cache.put("app1:methods:y", {"b": 2})
        cache.put("app2:class-info:z", {"c": 3})
        cache.invalidate_instance("app1")
        assert cache.get("app1:class-info:x") is None
        assert cache.get("app1:methods:y") is None
        assert cache.get("app2:class-info:z") == {"c": 3}

    def test_clear(self):
        cache = ResponseCache(max_size=10, ttl_seconds=60)
        cache.put("k1", {"a": 1})
        cache.put("k2", {"b": 2})
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_stats(self):
        cache = ResponseCache(max_size=10, ttl_seconds=60)
        cache.put("k1", {"a": 1})
        cache.get("k1")      # hit
        cache.get("missing")  # miss
        s = cache.stats()
        assert s["size"] == 1
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["hit_rate"] == 0.5

    def test_update_existing_key(self):
        cache = ResponseCache(max_size=10, ttl_seconds=60)
        cache.put("k1", {"v": 1})
        cache.put("k1", {"v": 2})
        assert cache.get("k1") == {"v": 2}
        assert cache.stats()["size"] == 1

    def test_aliases_resolve_to_canonical_instance_name(self):
        InstanceRegistry.register_pending_instance("demo-main", "127.0.0.1", 8650)
        InstanceRegistry.update_instance_status(
            "demo-main",
            "connected",
            apk_info={"apk_package": "com.example.demo"},
        )

        cache = ResponseCache(max_size=10, ttl_seconds=60)
        cache.put(_make_cache_key("com.example.demo", "class-info", {"class_name": "com.A"}), {"data": 1})

        canonical_key = _make_cache_key("demo-main", "class-info", {"class_name": "com.A"})
        assert cache.get(canonical_key) == {"data": 1}

    def test_invalidate_instance_accepts_aliases(self):
        InstanceRegistry.register_pending_instance("demo-main", "127.0.0.1", 8650)
        InstanceRegistry.update_instance_status(
            "demo-main",
            "connected",
            apk_info={"apk_package": "com.example.demo"},
        )

        cache = ResponseCache(max_size=10, ttl_seconds=60)
        cache.put(_make_cache_key("demo-main", "class-info", {"class_name": "com.A"}), {"data": 1})

        cache.invalidate_instance("com.example.demo")
        assert cache.get(_make_cache_key("demo-main", "class-info", {"class_name": "com.A"})) is None


class TestEndpointSets:
    def test_cacheable_endpoints_are_metadata_only(self):
        # Ensure no code/search endpoints snuck in
        for ep in CACHEABLE_ENDPOINTS:
            assert "source" not in ep
            assert "smali" not in ep
            assert "search" not in ep

    def test_mutating_endpoints_are_write_operations(self):
        for ep in _MUTATING_ENDPOINTS:
            assert "rename" in ep or ep == "cache/clear"
