"""
Unit tests for workflow_tools: analyze_apk and list_loaded_files.

Uses mock patches to avoid live HTTP calls.  conftest.py resets
InstanceRegistry and UserAuthManager before every test.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server.tools.workflow_tools import (
    _instance_has_no_file,
    analyze_apk,
    list_loaded_files,
)
from server.instance_registry import InstanceRegistry, JadxInstance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_instance(name: str, status: str = "connected", apk_pkg: str = "") -> JadxInstance:
    """Create a minimal JadxInstance and register it."""
    inst = JadxInstance(
        name=name,
        host="127.0.0.1",
        port=8650,
        status=status,
        apk_info={"apk_package": apk_pkg, "file_name": apk_pkg},
    )
    InstanceRegistry._instances[name] = inst
    if InstanceRegistry._default_instance is None:
        InstanceRegistry._default_instance = name
    return inst


def _no_file_apk_info() -> dict:
    return {"apk_package": "", "file_name": ""}


def _loaded_apk_info(pkg: str = "com.example.app") -> dict:
    return {"apk_package": pkg, "file_name": "target.apk"}


LOAD_SUCCESS = {
    "dispatched": True,
    "mode": "replace",
    "path": "target.apk",
    "ready": False,
    "poll_with": "get_decompile_status",
}

LOAD_ERROR = {"error": "Connection refused"}


# ---------------------------------------------------------------------------
# _instance_has_no_file unit tests
# ---------------------------------------------------------------------------

class TestInstanceHasNoFile:
    def test_empty_dict_is_no_file(self):
        assert _instance_has_no_file({}) is True

    def test_none_is_no_file(self):
        assert _instance_has_no_file(None) is True

    def test_empty_strings_is_no_file(self):
        assert _instance_has_no_file({"apk_package": "", "file_name": ""}) is True

    def test_populated_pkg_is_has_file(self):
        assert _instance_has_no_file({"apk_package": "com.example.app"}) is False

    def test_status_no_file_is_no_file(self):
        assert _instance_has_no_file({"apk_package": "", "status": "no_file"}) is True


# ---------------------------------------------------------------------------
# analyze_apk — auto strategy decision tree
# ---------------------------------------------------------------------------

class TestAnalyzeApkAuto:

    @pytest.mark.asyncio
    async def test_no_instances_returns_error(self):
        result = await analyze_apk("target.apk", strategy="auto")
        assert result["status"] == "error"
        assert result["instance"] is None
        assert any("No connected" in s for s in result["next_steps"])

    @pytest.mark.asyncio
    async def test_single_free_instance_loads(self):
        inst = _make_instance("default")
        with (
            patch(
                "server.tools.workflow_tools._fetch_apk_info",
                new=AsyncMock(return_value=_no_file_apk_info()),
            ),
            patch(
                "server.tools.workflow_tools._load_file_on_instance",
                new=AsyncMock(return_value=LOAD_SUCCESS),
            ),
        ):
            result = await analyze_apk("target.apk", strategy="auto")

        assert result["status"] == "loaded"
        assert result["instance"]["name"] == "default"
        assert result["poll_with"] == "get_decompile_status"

    @pytest.mark.asyncio
    async def test_single_busy_instance_returns_ambiguous(self):
        _make_instance("default")
        with patch(
            "server.tools.workflow_tools._fetch_apk_info",
            new=AsyncMock(return_value=_loaded_apk_info()),
        ):
            result = await analyze_apk("target.apk", strategy="auto")

        assert result["status"] == "ambiguous"
        # next_steps should explain the three choices
        joined = " ".join(result["next_steps"])
        assert "replace" in joined
        assert "new_instance" in joined

    @pytest.mark.asyncio
    async def test_multiple_instances_picks_free_one(self):
        _make_instance("busy")
        _make_instance("free")
        InstanceRegistry._default_instance = "busy"

        async def fake_apk_info(inst):
            if inst.name == "busy":
                return _loaded_apk_info("com.busy.app")
            return _no_file_apk_info()

        with (
            patch(
                "server.tools.workflow_tools._fetch_apk_info",
                new=AsyncMock(side_effect=fake_apk_info),
            ),
            patch(
                "server.tools.workflow_tools._load_file_on_instance",
                new=AsyncMock(return_value=LOAD_SUCCESS),
            ),
        ):
            result = await analyze_apk("target.apk", strategy="auto")

        assert result["status"] == "loaded"
        assert result["instance"]["name"] == "free"

    @pytest.mark.asyncio
    async def test_all_busy_returns_all_busy(self):
        _make_instance("busy1")
        _make_instance("busy2")

        with patch(
            "server.tools.workflow_tools._fetch_apk_info",
            new=AsyncMock(return_value=_loaded_apk_info()),
        ):
            result = await analyze_apk("target.apk", strategy="auto")

        assert result["status"] == "all_busy"
        assert result["instance"] is None
        assert any("scale_instances" in s or "all_busy" in s.lower() or "busy" in s.lower()
                   for s in result["next_steps"])


# ---------------------------------------------------------------------------
# analyze_apk — explicit strategies
# ---------------------------------------------------------------------------

class TestAnalyzeApkStrategies:

    @pytest.mark.asyncio
    async def test_replace_strategy_loads_on_default(self):
        _make_instance("default")
        with patch(
            "server.tools.workflow_tools._load_file_on_instance",
            new=AsyncMock(return_value=LOAD_SUCCESS),
        ):
            result = await analyze_apk("new.apk", strategy="replace")

        assert result["status"] == "loaded"
        assert result["instance"]["name"] == "default"

    @pytest.mark.asyncio
    async def test_replace_strategy_no_instance_returns_error(self):
        result = await analyze_apk("new.apk", strategy="replace")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_append_strategy_loads_in_append_mode(self):
        _make_instance("default")
        captured = {}

        async def fake_load(inst, path, mode="replace"):
            captured["mode"] = mode
            return LOAD_SUCCESS

        with patch(
            "server.tools.workflow_tools._load_file_on_instance",
            new=AsyncMock(side_effect=fake_load),
        ):
            result = await analyze_apk("lib.jar", strategy="append")

        assert result["status"] == "loaded"
        assert captured["mode"] == "append"

    @pytest.mark.asyncio
    async def test_new_instance_finds_free_instance(self):
        _make_instance("busy")
        _make_instance("free")

        async def fake_apk_info(inst):
            if inst.name == "busy":
                return _loaded_apk_info()
            return _no_file_apk_info()

        with (
            patch(
                "server.tools.workflow_tools._fetch_apk_info",
                new=AsyncMock(side_effect=fake_apk_info),
            ),
            patch(
                "server.tools.workflow_tools._load_file_on_instance",
                new=AsyncMock(return_value=LOAD_SUCCESS),
            ),
        ):
            result = await analyze_apk("other.apk", strategy="new_instance")

        assert result["status"] == "loaded"
        assert result["instance"]["name"] == "free"

    @pytest.mark.asyncio
    async def test_new_instance_all_busy_guidance(self):
        _make_instance("busy")

        with patch(
            "server.tools.workflow_tools._fetch_apk_info",
            new=AsyncMock(return_value=_loaded_apk_info()),
        ):
            result = await analyze_apk("other.apk", strategy="new_instance")

        assert result["status"] == "all_busy"
        joined = " ".join(result["next_steps"])
        assert "scale_instances" in joined

    @pytest.mark.asyncio
    async def test_invalid_strategy_returns_error(self):
        result = await analyze_apk("target.apk", strategy="magic")
        assert result["status"] == "error"
        assert any("strategy must be" in s for s in result["next_steps"])

    @pytest.mark.asyncio
    async def test_load_error_propagates(self):
        _make_instance("default")
        with (
            patch(
                "server.tools.workflow_tools._fetch_apk_info",
                new=AsyncMock(return_value=_no_file_apk_info()),
            ),
            patch(
                "server.tools.workflow_tools._load_file_on_instance",
                new=AsyncMock(return_value=LOAD_ERROR),
            ),
        ):
            result = await analyze_apk("bad.apk", strategy="auto")

        assert result["status"] == "error"
        assert "Connection refused" in result["next_steps"][0]


# ---------------------------------------------------------------------------
# list_loaded_files
# ---------------------------------------------------------------------------

class TestListLoadedFiles:

    @pytest.mark.asyncio
    async def test_empty_registry_returns_zero(self):
        result = await list_loaded_files()
        assert result["count"] == 0
        assert result["instances"] == []
        assert result["free_count"] == 0

    @pytest.mark.asyncio
    async def test_free_instance_shows_available(self):
        _make_instance("default")

        with (
            patch(
                "server.tools.workflow_tools._fetch_apk_info",
                new=AsyncMock(return_value=_no_file_apk_info()),
            ),
            patch(
                "server.tools.workflow_tools._fetch_decompile_status",
                new=AsyncMock(return_value={"cached_percentage": 0}),
            ),
        ):
            result = await list_loaded_files()

        assert result["count"] == 1
        assert result["free_count"] == 1
        assert result["instances"][0]["available"] is True
        assert result["instances"][0]["loaded_file"] is None

    @pytest.mark.asyncio
    async def test_busy_instance_shows_loaded_file(self):
        _make_instance("default")

        with (
            patch(
                "server.tools.workflow_tools._fetch_apk_info",
                new=AsyncMock(return_value=_loaded_apk_info("com.example.app")),
            ),
            patch(
                "server.tools.workflow_tools._fetch_decompile_status",
                new=AsyncMock(return_value={"cached_percentage": 70}),
            ),
        ):
            result = await list_loaded_files()

        inst_info = result["instances"][0]
        assert inst_info["available"] is False
        assert inst_info["loaded_file"] is not None
        assert inst_info["decompile_progress"] == pytest.approx(0.70)

    @pytest.mark.asyncio
    async def test_multiple_instances_aggregated(self):
        _make_instance("a")
        _make_instance("b")

        apk_responses = {
            "a": _loaded_apk_info("com.a.app"),
            "b": _no_file_apk_info(),
        }

        async def fake_apk(inst):
            return apk_responses.get(inst.name, {})

        with (
            patch(
                "server.tools.workflow_tools._fetch_apk_info",
                new=AsyncMock(side_effect=fake_apk),
            ),
            patch(
                "server.tools.workflow_tools._fetch_decompile_status",
                new=AsyncMock(return_value={"cached_percentage": 0}),
            ),
        ):
            result = await list_loaded_files()

        assert result["count"] == 2
        assert result["free_count"] == 1
        by_name = {i["name"]: i for i in result["instances"]}
        assert by_name["a"]["available"] is False
        assert by_name["b"]["available"] is True

    @pytest.mark.asyncio
    async def test_instance_id_filter(self):
        _make_instance("a")
        _make_instance("b")

        with (
            patch(
                "server.tools.workflow_tools._fetch_apk_info",
                new=AsyncMock(return_value=_no_file_apk_info()),
            ),
            patch(
                "server.tools.workflow_tools._fetch_decompile_status",
                new=AsyncMock(return_value={}),
            ),
        ):
            result = await list_loaded_files(instance_id="a")

        assert result["count"] == 1
        assert result["instances"][0]["name"] == "a"
