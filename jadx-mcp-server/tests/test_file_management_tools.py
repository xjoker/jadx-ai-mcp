"""Tests for file_management_tools HTTP request behavior."""

import pytest

from server.tools import file_management_tools


def _make_fake(captured: dict, response: dict = None):
    """Create a fake get_from_jadx that records the last call."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            timeout=timeout,
            method=method,
            json_body=json_body,
        )
        return response if response is not None else {"ok": True}
    return fake


# ---------------------------------------------------------------------------
# load_file
# ---------------------------------------------------------------------------

class TestLoadFile:

    @pytest.mark.asyncio
    async def test_load_file_uses_post_with_json_body(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(file_management_tools, "get_from_jadx", _make_fake(captured))

        result = await file_management_tools.load_file("target.apk", mode="replace", instance_id="inst1")

        assert result == {"ok": True}
        assert captured["endpoint"] == "load-file"
        assert captured["method"] == "POST"
        assert captured["json_body"] == {"path": "target.apk", "mode": "replace"}
        assert captured["instance_id"] == "inst1"
        assert captured["params"] is None

    @pytest.mark.asyncio
    async def test_load_file_append_mode(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(file_management_tools, "get_from_jadx", _make_fake(captured))

        await file_management_tools.load_file("extra.jar", mode="append")

        assert captured["json_body"]["mode"] == "append"
        assert captured["json_body"]["path"] == "extra.jar"

    @pytest.mark.asyncio
    async def test_load_file_invalid_mode_returns_error_without_http(self, monkeypatch):
        """Invalid mode is rejected in Python before any HTTP call."""
        called = []

        async def should_not_be_called(*args, **kwargs):
            called.append(True)
            return {}

        monkeypatch.setattr(file_management_tools, "get_from_jadx", should_not_be_called)

        result = await file_management_tools.load_file("target.apk", mode="overwrite")

        assert "error" in result
        assert "overwrite" in result["error"]
        assert called == [], "get_from_jadx should not be called for invalid mode"


# ---------------------------------------------------------------------------
# list_available_files
# ---------------------------------------------------------------------------

class TestListAvailableFiles:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(file_management_tools, "get_from_jadx", _make_fake(captured))

        await file_management_tools.list_available_files()

        assert captured["endpoint"] == "list-available-files"
        assert captured["method"] == "GET"

    @pytest.mark.asyncio
    async def test_passes_subdir_and_pattern(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(file_management_tools, "get_from_jadx", _make_fake(captured))

        await file_management_tools.list_available_files(
            subdir="releases", pattern="*.apk", recursive=True, instance_id="i2"
        )

        assert captured["params"]["subdir"] == "releases"
        assert captured["params"]["pattern"] == "*.apk"
        assert captured["params"]["recursive"] == "true"
        assert captured["instance_id"] == "i2"

    @pytest.mark.asyncio
    async def test_no_subdir_omits_key(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(file_management_tools, "get_from_jadx", _make_fake(captured))

        await file_management_tools.list_available_files()

        assert "subdir" not in captured["params"]
        assert "pattern" not in captured["params"]

    @pytest.mark.asyncio
    async def test_recursive_false_sends_false_string(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(file_management_tools, "get_from_jadx", _make_fake(captured))

        await file_management_tools.list_available_files(recursive=False)

        assert captured["params"]["recursive"] == "false"


# ---------------------------------------------------------------------------
# cancel_search
# ---------------------------------------------------------------------------

class TestCancelSearch:

    @pytest.mark.asyncio
    async def test_uses_post_method(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(file_management_tools, "get_from_jadx", _make_fake(captured))

        await file_management_tools.cancel_search()

        assert captured["endpoint"] == "cancel-search"
        assert captured["method"] == "POST"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(file_management_tools, "get_from_jadx", _make_fake(captured))

        await file_management_tools.cancel_search(instance_id="inst-x")

        assert captured["instance_id"] == "inst-x"

    @pytest.mark.asyncio
    async def test_no_params_sent(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(file_management_tools, "get_from_jadx", _make_fake(captured))

        await file_management_tools.cancel_search()

        assert captured["params"] is None
        assert captured["json_body"] is None
