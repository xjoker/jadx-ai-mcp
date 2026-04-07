"""
Unit tests for smart decompilation management tools.
"""

from unittest.mock import AsyncMock, patch

import pytest

from server.tools.decompile_tools import (
    _classify_class,
    get_decompile_priority_list,
    smart_decompile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_class_source(class_name: str, delay_ms: float = 0) -> dict:
    """Build a fake class-source response."""
    return {"response": f"// source of {class_name}", "class_name": class_name}


def _mock_decompile_status(cached_pct: int = 50, processed: int = 50, total: int = 100) -> dict:
    return {
        "status": "ready",
        "processed_classes": processed,
        "total_classes": total,
        "percentage": cached_pct,
    }


# ---------------------------------------------------------------------------
# smart_decompile tests
# ---------------------------------------------------------------------------

class TestSmartDecompile:
    """Tests for the smart_decompile function."""

    @pytest.mark.asyncio
    async def test_empty_class_names_returns_error(self):
        result = await smart_decompile(class_names=[])
        assert result["error"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_invalid_priority_returns_error(self):
        result = await smart_decompile(class_names=["com.A"], priority="urgent")
        assert result["error"] == "INVALID_INPUT"
        assert "priority" in result["message"]

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_single_class_success(self, mock_jadx):
        mock_jadx.side_effect = [
            _mock_class_source("com.example.A"),
            _mock_decompile_status(),
        ]

        result = await smart_decompile(class_names=["com.example.A"])

        assert result["requested"] == 1
        assert result["failed"] == 0
        assert len(result["results"]) == 1
        assert result["results"][0]["class_name"] == "com.example.A"
        assert result["results"][0]["status"] in ("cached", "decompiled")
        assert result["total_time_seconds"] >= 0

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_failed_class_counted(self, mock_jadx):
        mock_jadx.side_effect = [
            {"error": "CLASS_NOT_FOUND"},
            _mock_decompile_status(),
        ]

        result = await smart_decompile(class_names=["com.Missing"])

        assert result["failed"] == 1
        assert result["results"][0]["status"] == "failed"
        assert result["results"][0]["error"] == "CLASS_NOT_FOUND"

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_batch_concurrency_respects_priority(self, mock_jadx):
        """Verify all classes are processed regardless of priority level."""
        classes = [f"com.example.C{i}" for i in range(6)]
        responses = [_mock_class_source(c) for c in classes]
        responses.append(_mock_decompile_status())
        mock_jadx.side_effect = responses

        result = await smart_decompile(class_names=classes, priority="low")

        assert result["requested"] == 6
        assert result["succeeded"] + result["already_cached"] + result["failed"] == 6

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_optimization_tips_on_low_cache(self, mock_jadx):
        mock_jadx.side_effect = [
            _mock_class_source("com.A"),
            _mock_decompile_status(cached_pct=10),
        ]

        result = await smart_decompile(class_names=["com.A"])

        assert any("Cache rate" in t for t in result["optimization_tips"])

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_decompile_status_after_included(self, mock_jadx):
        status = _mock_decompile_status(cached_pct=75)
        mock_jadx.side_effect = [
            _mock_class_source("com.A"),
            status,
        ]

        result = await smart_decompile(class_names=["com.A"])

        assert result["decompile_status_after"]["percentage"] == 75


# ---------------------------------------------------------------------------
# _classify_class tests
# ---------------------------------------------------------------------------

class TestClassifyClass:
    """Tests for the heuristic class classifier."""

    def test_activity_is_high_priority(self):
        prio, reason = _classify_class("com.example.MainActivity", "com.example")
        assert prio == "high"
        assert "Activity" in reason

    def test_service_is_high_priority(self):
        prio, reason = _classify_class("com.example.SyncService", "com.example")
        assert prio == "high"
        assert "Service" in reason

    def test_receiver_is_high_priority(self):
        prio, _ = _classify_class("com.example.BootReceiver", "com.example")
        assert prio == "high"

    def test_provider_is_high_priority(self):
        prio, _ = _classify_class("com.example.DataProvider", "com.example")
        assert prio == "high"

    def test_fragment_is_high_priority(self):
        prio, _ = _classify_class("com.example.HomeFragment", "com.example")
        assert prio == "high"

    def test_own_package_is_high_priority(self):
        prio, reason = _classify_class("com.example.utils.Helper", "com.example")
        assert prio == "high"
        assert "own package" in reason.lower()

    def test_third_party_sdk_is_low_priority(self):
        prio, reason = _classify_class("com.google.firebase.FirebaseApp", "com.example")
        assert prio == "low"
        assert "Third-party" in reason

    def test_short_name_is_medium_priority(self):
        prio, reason = _classify_class("a.b.c", "com.example")
        assert prio == "medium"
        assert "Short name" in reason

    def test_generic_class_is_medium(self):
        prio, _ = _classify_class("org.unknown.SomeLongClassName", "com.example")
        assert prio == "medium"

    def test_component_in_third_party_still_low(self):
        """Third-party prefix takes precedence over component suffix."""
        prio, _ = _classify_class("androidx.fragment.app.Fragment", "com.example")
        assert prio == "low"


# ---------------------------------------------------------------------------
# get_decompile_priority_list tests
# ---------------------------------------------------------------------------

class TestGetDecompilePriorityList:
    """Tests for the priority list generator."""

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_sorts_high_before_low(self, mock_jadx):
        mock_jadx.side_effect = [
            {
                "classes": [
                    "com.google.sdk.Tracker",
                    "com.example.MainActivity",
                    "com.example.util.Helper",
                ],
            },
            _mock_decompile_status(processed=0, total=3),
        ]

        result = await get_decompile_priority_list(package="com.example")

        names = [item["class_name"] for item in result["priority_list"]]
        # Activity should appear before the SDK class
        assert names.index("com.example.MainActivity") < names.index("com.google.sdk.Tracker")

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_no_classes_returns_error(self, mock_jadx):
        mock_jadx.return_value = {"classes": []}

        result = await get_decompile_priority_list()

        assert result["error"] == "NO_CLASSES"

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_limit_100_entries(self, mock_jadx):
        classes = [f"com.example.Class{i}" for i in range(200)]
        mock_jadx.side_effect = [
            {"classes": classes},
            _mock_decompile_status(processed=0, total=200),
        ]

        result = await get_decompile_priority_list(package="com.example")

        assert len(result["priority_list"]) == 100

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_suggested_batch_size_large_apk(self, mock_jadx):
        classes = [f"com.example.C{i}" for i in range(15000)]
        mock_jadx.side_effect = [
            {"classes": classes},
            _mock_decompile_status(processed=0, total=15000),
        ]

        result = await get_decompile_priority_list(package="com.example")

        assert result["suggested_batch_size"] == 3

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_suggested_batch_size_small_apk(self, mock_jadx):
        classes = [f"com.example.C{i}" for i in range(50)]
        mock_jadx.side_effect = [
            {"classes": classes},
            _mock_decompile_status(processed=0, total=50),
        ]

        result = await get_decompile_priority_list(package="com.example")

        assert result["suggested_batch_size"] == 10

    @pytest.mark.asyncio
    @patch("server.tools.decompile_tools.get_from_jadx", new_callable=AsyncMock)
    async def test_jadx_error_returns_error(self, mock_jadx):
        mock_jadx.side_effect = Exception("connection refused")

        result = await get_decompile_priority_list()

        assert result["error"] == "JADX_ERROR"
