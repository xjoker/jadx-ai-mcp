"""Tests for diagnostics_tools: get_index_stats."""

import pytest

from server.tools import diagnostics_tools


def _make_fake(captured: dict, response=None, raise_exc=None):
    """Create a fake get_from_jadx for diagnostics_tools."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            method=method,
        )
        if raise_exc is not None:
            raise raise_exc
        if response is not None:
            return response
        return {}
    return fake


# ---------------------------------------------------------------------------
# get_index_stats
# ---------------------------------------------------------------------------

class TestGetIndexStats:

    @pytest.mark.asyncio
    async def test_calls_index_stats_endpoint(self, monkeypatch):
        """get_index_stats calls the 'index-stats' endpoint."""
        captured = {}
        monkeypatch.setattr(diagnostics_tools, "get_from_jadx", _make_fake(captured))

        await diagnostics_tools.get_index_stats()

        assert captured["endpoint"] == "index-stats"

    @pytest.mark.asyncio
    async def test_uses_get_method(self, monkeypatch):
        """get_index_stats uses the GET HTTP method (default)."""
        captured = {}
        monkeypatch.setattr(diagnostics_tools, "get_from_jadx", _make_fake(captured))

        await diagnostics_tools.get_index_stats()

        assert captured["method"] == "GET"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        """get_index_stats forwards instance_id to get_from_jadx."""
        captured = {}
        monkeypatch.setattr(diagnostics_tools, "get_from_jadx", _make_fake(captured))

        await diagnostics_tools.get_index_stats(instance_id="inst1")

        assert captured["instance_id"] == "inst1"

    @pytest.mark.asyncio
    async def test_returns_jadx_response_unchanged(self, monkeypatch):
        """get_index_stats returns the raw response from get_from_jadx."""
        fake_stats = {
            "name_indices": {"index_ready": True},
            "trigram_index": {"enabled": True, "saturation_percent": 80},
        }
        captured = {}
        monkeypatch.setattr(diagnostics_tools, "get_from_jadx", _make_fake(captured, fake_stats))

        result = await diagnostics_tools.get_index_stats()

        assert result == fake_stats

    @pytest.mark.asyncio
    async def test_returns_error_dict_on_exception(self, monkeypatch):
        """get_index_stats returns {'error': 'JADX_ERROR', ...} when get_from_jadx raises."""
        exc = ConnectionError("connection refused")
        monkeypatch.setattr(
            diagnostics_tools, "get_from_jadx",
            _make_fake({}, raise_exc=exc),
        )

        result = await diagnostics_tools.get_index_stats()

        assert result.get("error") == "JADX_ERROR"
        assert "connection refused" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_no_instance_id_passes_none(self, monkeypatch):
        """get_index_stats omits instance_id (passes None) when not specified."""
        captured = {}
        monkeypatch.setattr(diagnostics_tools, "get_from_jadx", _make_fake(captured))

        await diagnostics_tools.get_index_stats()

        assert captured["instance_id"] is None

    @pytest.mark.asyncio
    async def test_exception_message_preserved(self, monkeypatch):
        """get_index_stats includes the exception message in the error response."""
        exc = RuntimeError("timeout after 30s")
        monkeypatch.setattr(
            diagnostics_tools, "get_from_jadx",
            _make_fake({}, raise_exc=exc),
        )

        result = await diagnostics_tools.get_index_stats(instance_id="broken-inst")

        assert result["error"] == "JADX_ERROR"
        assert "timeout after 30s" in result["message"]
