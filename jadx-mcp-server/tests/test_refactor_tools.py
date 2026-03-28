"""Tests for refactor tool HTTP method selection."""

import pytest

from server.tools import refactor_tools


@pytest.mark.asyncio
async def test_rename_class_uses_post_json(monkeypatch):
    captured = {}

    async def fake_get_from_jadx(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            timeout=timeout,
            method=method,
            json_body=json_body,
        )
        return {"success": True}

    monkeypatch.setattr(refactor_tools, "get_from_jadx", fake_get_from_jadx)

    result = await refactor_tools.rename_class("com.example.Old", "NewName", instance_id="demo")

    assert result == {"success": True}
    assert captured == {
        "endpoint": "rename-class",
        "params": None,
        "instance_id": "demo",
        "timeout": None,
        "method": "POST",
        "json_body": {
            "class_name": "com.example.Old",
            "new_name": "NewName",
        },
    }
