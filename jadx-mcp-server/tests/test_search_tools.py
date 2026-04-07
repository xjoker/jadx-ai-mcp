"""Tests for search tools HTTP request behavior."""

import pytest

from server.tools import search_tools


def _make_fake_get_from_jadx(captured: dict):
    """Create a fake get_from_jadx that records calls."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
        )
        return captured.get("response", {"methods": [], "total": 0})
    return fake


class TestGetMethodByName:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await search_tools.get_method_by_name("com.example.Foo", "bar")
        assert captured["endpoint"] == "method-by-name"
        assert captured["params"] == {"class_name": "com.example.Foo", "method_name": "bar"}

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await search_tools.get_method_by_name("com.Foo", "bar", instance_id="inst1")
        assert captured["instance_id"] == "inst1"


class TestSearchMethodByName:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await search_tools.search_method_by_name("onCreate", offset=10, count=25)
        assert captured["endpoint"] == "search-method"
        assert captured["params"]["method_name"] == "onCreate"
        assert captured["params"]["offset"] == 10
        assert captured["params"]["count"] == 25

    @pytest.mark.asyncio
    async def test_error_response_includes_recovery_hint(self, monkeypatch):
        captured = {"response": {"error": "timeout"}}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        result = await search_tools.search_method_by_name("foo")
        assert "recovery_hint" in result

    @pytest.mark.asyncio
    async def test_exception_returns_error_dict(self, monkeypatch):
        async def fail(*args, **kwargs):
            raise ConnectionError("connection refused")
        monkeypatch.setattr(search_tools, "get_from_jadx", fail)
        result = await search_tools.search_method_by_name("foo")
        assert "error" in result
        assert "recovery_hint" in result


class TestBatchGetMethodByName:

    @pytest.mark.asyncio
    async def test_small_batch_executes_directly(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        methods = ["com.A:foo", "com.B:bar"]
        await search_tools.batch_get_method_by_name(methods)
        assert captured["endpoint"] == "batch-method-by-name"

    @pytest.mark.asyncio
    async def test_very_large_batch_returns_error(self):
        methods = [f"com.example.Class{i}:method{i}" for i in range(20)]
        result = await search_tools.batch_get_method_by_name(methods)
        assert result["error"] == "BATCH_TOO_LARGE"
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_force_bypasses_size_check(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        methods = [f"com.example.Class{i}:method{i}" for i in range(20)]
        await search_tools.batch_get_method_by_name(methods, force=True)
        assert captured["endpoint"] == "batch-method-by-name"

    @pytest.mark.asyncio
    async def test_continuation_chunk_executes_directly(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        methods = [f"com.example.Class{i}:method{i}" for i in range(20)]
        await search_tools.batch_get_method_by_name(methods, chunk=2)
        assert captured["endpoint"] == "batch-method-by-name"
        assert captured["params"]["chunk"] == "2"


class TestSearchClassesByKeyword:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await search_tools.search_classes_by_keyword("KeyStore", package="com.example", search_in="class")
        assert captured["endpoint"] == "search-classes-by-keyword"
        assert captured["params"]["search_term"] == "KeyStore"
        assert captured["params"]["package"] == "com.example"
        assert captured["params"]["search_in"] == "class"


class TestGetMethodSignature:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await search_tools.get_method_signature("com.Foo", "bar")
        assert captured["endpoint"] == "method-signature"
        assert captured["params"]["class_name"] == "com.Foo"
        assert captured["params"]["method_name"] == "bar"


class TestGetMethodCallees:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await search_tools.get_method_callees("com.Foo", "bar")
        assert captured["endpoint"] == "method-callees"


class TestSearchNativeMethods:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await search_tools.search_native_methods(package="com.example", offset=5, count=100)
        assert captured["endpoint"] == "search-native-methods"
        assert captured["params"]["package"] == "com.example"
        assert captured["params"]["offset"] == 5
        assert captured["params"]["count"] == 100

    @pytest.mark.asyncio
    async def test_no_package_omits_param(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await search_tools.search_native_methods()
        assert "package" not in captured["params"]
