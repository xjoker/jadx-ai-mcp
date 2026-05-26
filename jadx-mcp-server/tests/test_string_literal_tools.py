"""
Tests for string_literal_tools.py HTTP request behavior and input validation.

The module exposes two surfaces:
  1. Module-level `search_string_literals` — no validation, passes directly to get_from_jadx.
  2. The MCP tool wrapper (registered inside register_string_literal_tools) — adds
     input validation for empty pattern, negative min_length, and limit < 1.

These tests cover both surfaces.  Validation tests use the wrapper by instantiating
a lightweight stub MCP that collects registered tools.

All HTTP calls are replaced by an in-process fake; no running JADX
server is required.
"""

import pytest

from server.tools import string_literal_tools


def _make_fake(captured: dict, response: dict = None):
    """Return a fake get_from_jadx that records the last call."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            method=method,
        )
        return response if response is not None else {"results": [], "total": 0}
    return fake


# ---------------------------------------------------------------------------
# Module-level search_string_literals (no input validation)
# ---------------------------------------------------------------------------

class TestSearchStringLiteralsModuleLevel:

    @pytest.mark.asyncio
    async def test_calls_search_string_literals_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured))
        await string_literal_tools.search_string_literals("https://api.")
        assert captured["endpoint"] == "search-string-literals"

    @pytest.mark.asyncio
    async def test_pattern_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured))
        await string_literal_tools.search_string_literals("SELECT ")
        assert captured["params"]["pattern"] == "SELECT "

    @pytest.mark.asyncio
    async def test_regex_flag_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured))
        await string_literal_tools.search_string_literals("[A-Z]{32}", regex=True)
        assert captured["params"]["regex"] == "true"

    @pytest.mark.asyncio
    async def test_regex_false_by_default(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured))
        await string_literal_tools.search_string_literals("password")
        assert captured["params"]["regex"] == "false"

    @pytest.mark.asyncio
    async def test_min_length_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured))
        await string_literal_tools.search_string_literals("token", min_length=16)
        assert captured["params"]["min_length"] == "16"

    @pytest.mark.asyncio
    async def test_limit_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured))
        await string_literal_tools.search_string_literals("Bearer", limit=50)
        assert captured["params"]["limit"] == "50"

    @pytest.mark.asyncio
    async def test_class_filter_absent_when_empty(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured))
        await string_literal_tools.search_string_literals("api", class_filter="")
        assert "class" not in captured["params"]

    @pytest.mark.asyncio
    async def test_class_filter_in_params_when_provided(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured))
        await string_literal_tools.search_string_literals("api", class_filter="com.example.app")
        assert captured["params"]["class"] == "com.example.app"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured))
        await string_literal_tools.search_string_literals("key", instance_id="inst-sl")
        assert captured["instance_id"] == "inst-sl"


# ---------------------------------------------------------------------------
# MCP tool wrapper (validation layer inside register_string_literal_tools)
# ---------------------------------------------------------------------------

class _StubMcp:
    """Minimal stub that captures the first tool registered with @mcp.tool()."""

    def __init__(self):
        self._tools = {}

    def tool(self, name=None):
        """Decorator factory mirroring mcp.tool()."""
        def decorator(func):
            key = name or func.__name__
            self._tools[key] = func
            return func
        return decorator

    def get_tool(self, name: str):
        return self._tools[name]


def _build_wrapper(monkeypatch, captured, response=None):
    """Register the string literal tools wrapper and return the wrapped async callable."""
    stub_mcp = _StubMcp()

    def with_busy_check(fn):
        return fn  # No-op for unit tests

    monkeypatch.setattr(string_literal_tools, "get_from_jadx", _make_fake(captured, response))
    string_literal_tools.register_string_literal_tools(stub_mcp, with_busy_check)
    return stub_mcp.get_tool("search_string_literals")


class TestSearchStringLiteralsWrapper:

    @pytest.mark.asyncio
    async def test_empty_pattern_returns_invalid_input(self, monkeypatch):
        wrapper = _build_wrapper(monkeypatch, {})
        result = await wrapper(pattern="")
        assert result["error_code"] == "INVALID_INPUT"
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_whitespace_only_pattern_returns_invalid_input(self, monkeypatch):
        wrapper = _build_wrapper(monkeypatch, {})
        result = await wrapper(pattern="   ")
        assert result["error_code"] == "INVALID_INPUT"
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_negative_min_length_returns_invalid_input(self, monkeypatch):
        wrapper = _build_wrapper(monkeypatch, {})
        result = await wrapper(pattern="key", min_length=-1)
        assert result["error_code"] == "INVALID_INPUT"
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_zero_limit_returns_invalid_input(self, monkeypatch):
        wrapper = _build_wrapper(monkeypatch, {})
        result = await wrapper(pattern="key", limit=0)
        assert result["error_code"] == "INVALID_INPUT"
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_negative_limit_returns_invalid_input(self, monkeypatch):
        wrapper = _build_wrapper(monkeypatch, {})
        result = await wrapper(pattern="key", limit=-5)
        assert result["error_code"] == "INVALID_INPUT"
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_valid_call_reaches_endpoint(self, monkeypatch):
        captured = {}
        wrapper = _build_wrapper(monkeypatch, captured)
        await wrapper(pattern="https://", min_length=8, limit=10)
        assert captured["endpoint"] == "search-string-literals"
        assert captured["params"]["pattern"] == "https://"

    @pytest.mark.asyncio
    async def test_instance_id_propagated_via_wrapper(self, monkeypatch):
        captured = {}
        wrapper = _build_wrapper(monkeypatch, captured)
        await wrapper(pattern="token", instance_id="wrap-inst")
        assert captured["instance_id"] == "wrap-inst"
