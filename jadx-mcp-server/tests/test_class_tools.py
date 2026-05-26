"""
Tests for class_tools.py HTTP request behavior.

Verifies that each tool function calls the correct JADX endpoint,
passes the correct query params / json_body, and propagates instance_id.
All HTTP calls are replaced by an in-process fake; no running JADX
server is required.
"""

import pytest

from server.tools import class_tools


def _make_fake(captured: dict, response: dict = None):
    """Return a fake get_from_jadx that records the last call."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            method=method,
            json_body=json_body,
        )
        return response if response is not None else {"status": "ready"}
    return fake


# ---------------------------------------------------------------------------
# get_class_source
# ---------------------------------------------------------------------------

class TestGetClassSource:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_class_source("com.example.MainActivity")
        assert captured["endpoint"] == "class-source"
        assert captured["params"]["class_name"] == "com.example.MainActivity"

    @pytest.mark.asyncio
    async def test_chunk_zero_not_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_class_source("com.example.Foo", chunk=0)
        assert "chunk" not in captured["params"]

    @pytest.mark.asyncio
    async def test_nonzero_chunk_included_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_class_source("com.example.Foo", chunk=2)
        assert captured["params"]["chunk"] == "2"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_class_source("com.example.Foo", instance_id="node-2")
        assert captured["instance_id"] == "node-2"


# ---------------------------------------------------------------------------
# batch_get_class_source
# ---------------------------------------------------------------------------

class TestBatchGetClassSource:

    @pytest.mark.asyncio
    async def test_calls_batch_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.batch_get_class_source(["com.A", "com.B"])
        assert captured["endpoint"] == "batch-class-source"

    @pytest.mark.asyncio
    async def test_class_names_joined_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.batch_get_class_source(["com.A", "com.B"])
        assert "com.A" in captured["params"]["class_names"]
        assert "com.B" in captured["params"]["class_names"]

    @pytest.mark.asyncio
    async def test_too_many_classes_returns_error(self):
        names = [f"com.example.Class{i}" for i in range(21)]
        result = await class_tools.batch_get_class_source(names)
        assert result["error"] == "TOO_MANY_CLASSES"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.batch_get_class_source(["com.A"], instance_id="inst-x")
        assert captured["instance_id"] == "inst-x"

    @pytest.mark.asyncio
    async def test_continuation_chunk_executes_directly(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        # chunk > 0 should bypass size guard and call the endpoint directly
        await class_tools.batch_get_class_source(["com.A"], chunk=1)
        assert captured["endpoint"] == "batch-class-source"
        assert captured["params"]["chunk"] == "1"


# ---------------------------------------------------------------------------
# get_class_info
# ---------------------------------------------------------------------------

class TestGetClassInfo:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_class_info("com.example.Login")
        assert captured["endpoint"] == "class-info"
        assert captured["params"]["class_name"] == "com.example.Login"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_class_info("com.example.Login", instance_id="prod")
        assert captured["instance_id"] == "prod"


# ---------------------------------------------------------------------------
# get_all_classes  (uses PaginationUtils → calls get_from_jadx via lambda)
# ---------------------------------------------------------------------------

class TestGetAllClasses:

    @pytest.mark.asyncio
    async def test_calls_all_classes_endpoint(self, monkeypatch):
        captured = {}

        async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
            captured.update(endpoint=endpoint, params=params, instance_id=instance_id)
            return {"classes": [], "pagination": {}}

        monkeypatch.setattr(class_tools, "get_from_jadx", fake)
        await class_tools.get_all_classes()
        assert captured["endpoint"] == "all-classes"

    @pytest.mark.asyncio
    async def test_offset_and_count_in_params(self, monkeypatch):
        captured = {}

        async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
            captured.update(endpoint=endpoint, params=params)
            return {"classes": [], "pagination": {}}

        monkeypatch.setattr(class_tools, "get_from_jadx", fake)
        await class_tools.get_all_classes(offset=10, count=50)
        assert captured["params"]["offset"] == 10
        assert captured["params"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}

        async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
            captured.update(instance_id=instance_id)
            return {"classes": [], "pagination": {}}

        monkeypatch.setattr(class_tools, "get_from_jadx", fake)
        await class_tools.get_all_classes(instance_id="test-inst")
        assert captured["instance_id"] == "test-inst"


# ---------------------------------------------------------------------------
# list_packages
# ---------------------------------------------------------------------------

class TestListPackages:

    @pytest.mark.asyncio
    async def test_calls_package_tree_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.list_packages()
        assert captured["endpoint"] == "package-tree"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.list_packages(instance_id="inst-a")
        assert captured["instance_id"] == "inst-a"


# ---------------------------------------------------------------------------
# get_main_activity_class
# ---------------------------------------------------------------------------

class TestGetMainActivityClass:

    @pytest.mark.asyncio
    async def test_calls_main_activity_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_main_activity_class()
        assert captured["endpoint"] == "main-activity"

    @pytest.mark.asyncio
    async def test_chunk_zero_sends_empty_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_main_activity_class(chunk=0)
        assert "chunk" not in captured["params"]

    @pytest.mark.asyncio
    async def test_nonzero_chunk_included(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_main_activity_class(chunk=3)
        assert captured["params"]["chunk"] == "3"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured))
        await class_tools.get_main_activity_class(instance_id="inst-b")
        assert captured["instance_id"] == "inst-b"


# ---------------------------------------------------------------------------
# get_decompile_status
# ---------------------------------------------------------------------------

class TestGetDecompileStatus:

    @pytest.mark.asyncio
    async def test_calls_decompile_status_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured, {"status": "ready", "percentage": 100}))
        await class_tools.get_decompile_status()
        assert captured["endpoint"] == "decompile-status"

    @pytest.mark.asyncio
    async def test_loading_status_adds_retry_after(self, monkeypatch):
        monkeypatch.setattr(
            class_tools, "get_from_jadx",
            _make_fake({}, {"status": "loading", "processed_classes": 10, "total_classes": 100})
        )
        result = await class_tools.get_decompile_status()
        assert result["status"] == "loading"
        assert "retry_after_seconds" in result
        assert result["retry_after_seconds"] == 3

    @pytest.mark.asyncio
    async def test_ready_status_no_retry_after(self, monkeypatch):
        monkeypatch.setattr(
            class_tools, "get_from_jadx",
            _make_fake({}, {"status": "ready", "percentage": 100})
        )
        result = await class_tools.get_decompile_status()
        assert result["status"] == "ready"
        assert "retry_after_seconds" not in result

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(class_tools, "get_from_jadx", _make_fake(captured, {"status": "ready"}))
        await class_tools.get_decompile_status(instance_id="inst-c")
        assert captured["instance_id"] == "inst-c"
