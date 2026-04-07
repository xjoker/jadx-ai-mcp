"""Tests for session persistence tools."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from server.tools.session_tools import (
    _validate_session_name,
    save_analysis_session,
    load_analysis_session,
    list_analysis_sessions,
)


# ==================== Validation Tests ====================


class TestValidateSessionName:
    """Test session name validation logic."""

    def test_valid_alphanumeric(self):
        assert _validate_session_name("mySession123") is None

    def test_valid_with_hyphens_underscores(self):
        assert _validate_session_name("my-session_v2") is None

    def test_valid_single_char(self):
        assert _validate_session_name("a") is None

    def test_valid_max_length(self):
        assert _validate_session_name("a" * 100) is None

    def test_invalid_empty(self):
        assert _validate_session_name("") is not None

    def test_invalid_spaces(self):
        assert _validate_session_name("my session") is not None

    def test_invalid_dots(self):
        assert _validate_session_name("my.session") is not None

    def test_invalid_slashes(self):
        assert _validate_session_name("../etc/passwd") is not None

    def test_invalid_special_chars(self):
        assert _validate_session_name("session@#$") is not None

    def test_invalid_too_long(self):
        assert _validate_session_name("a" * 101) is not None


# ==================== Save / Load Round-trip Tests ====================


class TestSaveLoadSession:
    """Test save and load round-trip."""

    @pytest.fixture()
    def sessions_dir(self, tmp_path, monkeypatch):
        """Redirect sessions directory to a temp path."""
        d = tmp_path / "sessions"
        d.mkdir()
        monkeypatch.setattr(
            "server.tools.session_tools._SESSIONS_DIR", d,
        )
        return d

    @pytest.fixture()
    def mock_get_from_jadx(self):
        """Mock get_from_jadx to return fake file-info."""
        fake_file_info = {
            "file_name": "test.apk",
            "file_type": "apk",
            "package_name": "com.example.test",
        }
        with patch(
            "server.tools.session_tools.get_from_jadx",
            new_callable=AsyncMock,
            return_value=fake_file_info,
        ) as mock:
            yield mock

    @pytest.fixture()
    def sample_context(self):
        return {
            "analyzed_classes": ["com.example.Main", "com.example.Util"],
            "findings": [{"type": "hardcoded_secret", "severity": "high"}],
            "notes": "Found suspicious encryption usage in Util class",
            "current_focus": "com.example.Util",
            "next_steps": ["Check key derivation", "Trace data flow"],
        }

    @pytest.mark.asyncio
    async def test_save_creates_file(self, sessions_dir, mock_get_from_jadx, sample_context):
        result = await save_analysis_session("test-session", sample_context)
        assert result["success"] is True
        assert result["session_name"] == "test-session"
        assert (sessions_dir / "test-session.json").exists()

    @pytest.mark.asyncio
    async def test_save_invalid_name_returns_error(self, sessions_dir, mock_get_from_jadx):
        result = await save_analysis_session("bad name!", {})
        assert "error" in result
        assert result["error"] == "INVALID_SESSION_NAME"

    @pytest.mark.asyncio
    async def test_round_trip(self, sessions_dir, mock_get_from_jadx, sample_context):
        await save_analysis_session("round-trip", sample_context)
        loaded = await load_analysis_session("round-trip")

        assert loaded["context"] == sample_context
        assert loaded["metadata"]["session_name"] == "round-trip"
        assert loaded["metadata"]["file_info"]["file_type"] == "apk"

    @pytest.mark.asyncio
    async def test_overwrite_preserves_previous_time(
        self, sessions_dir, mock_get_from_jadx, sample_context,
    ):
        result1 = await save_analysis_session("overwrite-test", sample_context)
        first_time = result1["saved_at"]

        result2 = await save_analysis_session("overwrite-test", sample_context)
        loaded = await load_analysis_session("overwrite-test")

        assert loaded["metadata"]["previous_save_time"] == first_time
        assert loaded["metadata"]["saved_at"] == result2["saved_at"]

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_error(self, sessions_dir):
        result = await load_analysis_session("does-not-exist")
        assert result["error"] == "SESSION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_load_invalid_name_returns_error(self, sessions_dir):
        result = await load_analysis_session("bad name!")
        assert result["error"] == "INVALID_SESSION_NAME"

    @pytest.mark.asyncio
    async def test_save_creates_directory(self, tmp_path, monkeypatch, mock_get_from_jadx):
        """Sessions dir is created automatically if it doesn't exist."""
        new_dir = tmp_path / "nonexistent" / "sessions"
        monkeypatch.setattr("server.tools.session_tools._SESSIONS_DIR", new_dir)

        result = await save_analysis_session("auto-dir", {"notes": "test"})
        assert result["success"] is True
        assert new_dir.exists()


# ==================== List Sessions Tests ====================


class TestListSessions:
    """Test list_analysis_sessions."""

    @pytest.fixture()
    def sessions_dir(self, tmp_path, monkeypatch):
        d = tmp_path / "sessions"
        d.mkdir()
        monkeypatch.setattr("server.tools.session_tools._SESSIONS_DIR", d)
        return d

    @pytest.mark.asyncio
    async def test_empty_directory(self, sessions_dir):
        result = await list_analysis_sessions()
        assert result["count"] == 0
        assert result["sessions"] == []

    @pytest.mark.asyncio
    async def test_lists_saved_sessions(self, sessions_dir):
        # Write two session files manually
        for name in ("session-a", "session-b"):
            data = {
                "metadata": {
                    "session_name": name,
                    "saved_at": "2026-01-01T00:00:00+00:00",
                    "file_info": {"file_type": "apk"},
                },
                "context": {"notes": f"Notes for {name} session"},
            }
            (sessions_dir / f"{name}.json").write_text(
                json.dumps(data), encoding="utf-8",
            )

        result = await list_analysis_sessions()
        assert result["count"] == 2
        names = [s["session_name"] for s in result["sessions"]]
        assert "session-a" in names
        assert "session-b" in names

    @pytest.mark.asyncio
    async def test_notes_preview_truncated(self, sessions_dir):
        long_notes = "x" * 200
        data = {
            "metadata": {
                "session_name": "long-notes",
                "saved_at": "2026-01-01T00:00:00+00:00",
                "file_info": {"file_type": "jar"},
            },
            "context": {"notes": long_notes},
        }
        (sessions_dir / "long-notes.json").write_text(
            json.dumps(data), encoding="utf-8",
        )

        result = await list_analysis_sessions()
        preview = result["sessions"][0]["notes_preview"]
        assert len(preview) == 100

    @pytest.mark.asyncio
    async def test_nonexistent_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "server.tools.session_tools._SESSIONS_DIR",
            tmp_path / "does-not-exist",
        )
        result = await list_analysis_sessions()
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_skips_corrupt_files(self, sessions_dir):
        (sessions_dir / "corrupt.json").write_text("not valid json", encoding="utf-8")
        # Also add a valid one
        data = {
            "metadata": {"session_name": "valid", "saved_at": "2026-01-01T00:00:00+00:00", "file_info": {}},
            "context": {"notes": "ok"},
        }
        (sessions_dir / "valid.json").write_text(json.dumps(data), encoding="utf-8")

        result = await list_analysis_sessions()
        assert result["count"] == 1
        assert result["sessions"][0]["session_name"] == "valid"
