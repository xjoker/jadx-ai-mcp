"""Tests for analysis_surface_tools: get_attack_surface, export_callgraph."""

import pytest

from server.tools import analysis_surface_tools


def _make_fake(captured: dict, response: dict = None):
    """Create a fake get_from_jadx that records calls and returns a configurable response."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            method=method,
        )
        if response is not None:
            return response
        return {}
    return fake


# ---------------------------------------------------------------------------
# get_attack_surface (module-level function)
# ---------------------------------------------------------------------------

class TestGetAttackSurface:

    @pytest.mark.asyncio
    async def test_calls_attack_surface_endpoint(self, monkeypatch):
        """get_attack_surface calls the 'attack-surface' endpoint."""
        captured = {}
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake(captured, {}))

        await analysis_surface_tools.get_attack_surface()

        assert captured["endpoint"] == "attack-surface"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        """get_attack_surface forwards instance_id to get_from_jadx."""
        captured = {}
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake(captured, {}))

        await analysis_surface_tools.get_attack_surface(instance_id="inst-xyz")

        assert captured["instance_id"] == "inst-xyz"

    @pytest.mark.asyncio
    async def test_appends_summary_on_success(self, monkeypatch):
        """get_attack_surface appends a 'summary' string when response has no error key."""
        response = {
            "total_exported": 3,
            "deeplink_summary": [{"scheme": "myapp"}],
            "dangerous_permissions_used": ["android.permission.CAMERA"],
            "custom_permissions": [],
        }
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake({}, response))

        result = await analysis_surface_tools.get_attack_surface()

        assert "summary" in result
        assert "3 exported" in result["summary"]

    @pytest.mark.asyncio
    async def test_no_summary_when_error_key_present(self, monkeypatch):
        """get_attack_surface does not append summary when response contains error."""
        error_response = {"error": "JADX_ERROR", "message": "connection refused"}
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake({}, error_response))

        result = await analysis_surface_tools.get_attack_surface()

        assert "summary" not in result


# ---------------------------------------------------------------------------
# export_callgraph (module-level function)
# ---------------------------------------------------------------------------

class TestExportCallgraph:

    @pytest.mark.asyncio
    async def test_calls_export_callgraph_endpoint(self, monkeypatch):
        """export_callgraph calls the 'export-callgraph' endpoint."""
        captured = {}
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake(captured))

        await analysis_surface_tools.export_callgraph("com.Foo", "bar")

        assert captured["endpoint"] == "export-callgraph"

    @pytest.mark.asyncio
    async def test_passes_class_method_depth_format_params(self, monkeypatch):
        """export_callgraph passes class, method, depth, format as query params."""
        captured = {}
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake(captured))

        await analysis_surface_tools.export_callgraph(
            "com.example.LoginActivity", "onCreate", depth=2, output_format="dot"
        )

        params = captured["params"]
        assert params["class"] == "com.example.LoginActivity"
        assert params["method"] == "onCreate"
        assert params["depth"] == "2"
        assert params["format"] == "dot"

    @pytest.mark.asyncio
    async def test_depth_clamped_to_max_six(self, monkeypatch):
        """export_callgraph clamps depth to maximum of 6."""
        captured = {}
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake(captured))

        await analysis_surface_tools.export_callgraph("com.Foo", "bar", depth=99)

        assert int(captured["params"]["depth"]) <= 6

    @pytest.mark.asyncio
    async def test_depth_clamped_to_min_one(self, monkeypatch):
        """export_callgraph clamps depth to minimum of 1."""
        captured = {}
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake(captured))

        await analysis_surface_tools.export_callgraph("com.Foo", "bar", depth=0)

        assert int(captured["params"]["depth"]) >= 1

    @pytest.mark.asyncio
    async def test_json_format_passed_correctly(self, monkeypatch):
        """export_callgraph passes output_format='json' correctly."""
        captured = {}
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake(captured))

        await analysis_surface_tools.export_callgraph("com.Foo", "bar", output_format="json")

        assert captured["params"]["format"] == "json"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        """export_callgraph forwards instance_id to get_from_jadx."""
        captured = {}
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake(captured))

        await analysis_surface_tools.export_callgraph("com.Foo", "bar", instance_id="inst-1")

        assert captured["instance_id"] == "inst-1"


# ---------------------------------------------------------------------------
# Registered wrapper: export_callgraph validates inputs
# ---------------------------------------------------------------------------

def _make_registered_export_callgraph():
    """Register analysis_surface tools and return the inner export_callgraph function."""
    registered = {}

    class CaptureMcp:
        def tool(self):
            def decorator(func):
                registered[func.__name__] = func
                return func
            return decorator

    mcp = CaptureMcp()
    analysis_surface_tools.register_analysis_surface_tools(mcp, lambda f: f)
    return registered.get("export_callgraph")


class TestRegisteredExportCallgraph:

    @pytest.mark.asyncio
    async def test_empty_class_name_returns_invalid_input(self, monkeypatch):
        """Registered export_callgraph returns INVALID_INPUT for empty class_name."""
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake({}))

        fn = _make_registered_export_callgraph()
        result = await fn(class_name="", method_name="bar")

        assert result.get("error_code") == "INVALID_INPUT" or result.get("ok") is False

    @pytest.mark.asyncio
    async def test_invalid_format_returns_invalid_input(self, monkeypatch):
        """Registered export_callgraph returns INVALID_INPUT for unknown format."""
        monkeypatch.setattr(analysis_surface_tools, "get_from_jadx", _make_fake({}))

        fn = _make_registered_export_callgraph()
        result = await fn(class_name="com.Foo", method_name="bar", format="xml")

        assert result.get("error_code") == "INVALID_INPUT" or result.get("ok") is False
