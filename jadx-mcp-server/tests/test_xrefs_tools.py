"""
Tests for xrefs_tools.py HTTP request behavior.

Verifies that get_xrefs_to_class, get_xrefs_to_method, get_xrefs_to_field,
and batch_get_xrefs call the correct JADX endpoints with the expected
query parameters, and that instance_id is correctly propagated.

All HTTP calls are replaced by an in-process fake; no running JADX
server is required.
"""

import pytest

from server.tools import xrefs_tools


def _make_fake(captured: dict, response: dict = None):
    """Return a fake get_from_jadx that records the last HTTP call."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            method=method,
            json_body=json_body,
        )
        return response if response is not None else {"references": [], "pagination": {}}
    return fake


# ---------------------------------------------------------------------------
# get_xrefs_to_class  (via PaginationUtils → lambda fetch_function)
# ---------------------------------------------------------------------------

class TestGetXrefsToClass:

    @pytest.mark.asyncio
    async def test_calls_xrefs_to_class_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_class("com.example.Crypto")
        assert captured["endpoint"] == "xrefs-to-class"

    @pytest.mark.asyncio
    async def test_class_name_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_class("com.example.Crypto")
        assert captured["params"]["class_name"] == "com.example.Crypto"

    @pytest.mark.asyncio
    async def test_include_snippet_adds_param(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_class("com.example.Crypto", include_snippet=True)
        assert captured["params"]["include_snippet"] == "true"

    @pytest.mark.asyncio
    async def test_no_snippet_by_default(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_class("com.example.Crypto")
        assert "include_snippet" not in captured["params"]

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_class("com.example.Crypto", instance_id="inst-1")
        assert captured["instance_id"] == "inst-1"


# ---------------------------------------------------------------------------
# get_xrefs_to_method  (via PaginationUtils)
# ---------------------------------------------------------------------------

class TestGetXrefsToMethod:

    @pytest.mark.asyncio
    async def test_calls_xrefs_to_method_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_method("com.example.Auth", "login")
        assert captured["endpoint"] == "xrefs-to-method"

    @pytest.mark.asyncio
    async def test_class_and_method_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_method("com.example.Auth", "login")
        assert captured["params"]["class_name"] == "com.example.Auth"
        assert captured["params"]["method_name"] == "login"

    @pytest.mark.asyncio
    async def test_include_snippet_adds_param(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_method("com.example.Auth", "login", include_snippet=True)
        assert captured["params"]["include_snippet"] == "true"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_method("com.A", "foo", instance_id="inst-2")
        assert captured["instance_id"] == "inst-2"


# ---------------------------------------------------------------------------
# get_xrefs_to_field  (via PaginationUtils)
# ---------------------------------------------------------------------------

class TestGetXrefsToField:

    @pytest.mark.asyncio
    async def test_calls_xrefs_to_field_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_field("com.example.Config", "API_KEY")
        assert captured["endpoint"] == "xrefs-to-field"

    @pytest.mark.asyncio
    async def test_class_and_field_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_field("com.example.Config", "API_KEY")
        assert captured["params"]["class_name"] == "com.example.Config"
        assert captured["params"]["field_name"] == "API_KEY"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured))
        await xrefs_tools.get_xrefs_to_field("com.A", "myField", instance_id="inst-3")
        assert captured["instance_id"] == "inst-3"


# ---------------------------------------------------------------------------
# batch_get_xrefs
# ---------------------------------------------------------------------------

class TestBatchGetXrefs:

    @pytest.mark.asyncio
    async def test_calls_batch_xrefs_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured, {"results": []}))
        await xrefs_tools.batch_get_xrefs(["class:com.example.Foo"])
        assert captured["endpoint"] == "batch-xrefs"

    @pytest.mark.asyncio
    async def test_targets_joined_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured, {"results": []}))
        targets = ["class:com.example.Foo", "method:com.example.Bar:doWork"]
        await xrefs_tools.batch_get_xrefs(targets)
        assert captured["params"]["targets"] == ",".join(targets)

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured, {"results": []}))
        await xrefs_tools.batch_get_xrefs(["class:com.A"], instance_id="batch-inst")
        assert captured["instance_id"] == "batch-inst"

    @pytest.mark.asyncio
    async def test_uses_get_method(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(xrefs_tools, "get_from_jadx", _make_fake(captured, {"results": []}))
        await xrefs_tools.batch_get_xrefs(["class:com.A"])
        # batch_get_xrefs does not explicitly pass method="POST", so it defaults to GET
        assert captured["method"] == "GET"
