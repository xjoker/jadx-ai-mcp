"""Tests for annotation/bookmark/tag delete tools."""

import pytest

from server.tools import annotation_tools


def _make_fake_get_from_jadx(captured: dict):
    """Create a fake get_from_jadx that records calls."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            instance_id=instance_id,
            method=method,
        )
        return {"success": True, "deleted_id": 42}
    return fake


class TestDeleteAnnotation:

    @pytest.mark.asyncio
    async def test_uses_delete_method(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(annotation_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        result = await annotation_tools.delete_annotation(42)
        assert captured["endpoint"] == "annotations/42"
        assert captured["method"] == "DELETE"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(annotation_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await annotation_tools.delete_annotation(1, instance_id="inst1")
        assert captured["instance_id"] == "inst1"


class TestDeleteBookmark:

    @pytest.mark.asyncio
    async def test_uses_delete_method(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(annotation_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        result = await annotation_tools.delete_bookmark(99)
        assert captured["endpoint"] == "bookmarks/99"
        assert captured["method"] == "DELETE"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(annotation_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await annotation_tools.delete_bookmark(1, instance_id="inst2")
        assert captured["instance_id"] == "inst2"


class TestDeleteTag:

    @pytest.mark.asyncio
    async def test_uses_delete_method(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(annotation_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        result = await annotation_tools.delete_tag(7)
        assert captured["endpoint"] == "tags/7"
        assert captured["method"] == "DELETE"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(annotation_tools, "get_from_jadx", _make_fake_get_from_jadx(captured))
        await annotation_tools.delete_tag(1, instance_id="inst3")
        assert captured["instance_id"] == "inst3"
