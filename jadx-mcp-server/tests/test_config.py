"""Tests for ACL-aware JADX request routing."""

import json

import pytest
import respx
from httpx import Response

from server.config import HttpClientManager, get_from_jadx
from server.instance_registry import InstanceRegistry


@pytest.fixture(autouse=True)
def reset_http_client_manager():
    HttpClientManager._client = None
    HttpClientManager._lock = None
    yield
    HttpClientManager._client = None
    HttpClientManager._lock = None


class TestGetFromJadxAcl:
    @pytest.mark.asyncio
    async def test_explicit_instance_uses_user_acl(self):
        InstanceRegistry.register_pending_instance("bob-private", "127.0.0.1", 8650, owner="bob")
        InstanceRegistry.update_instance_status(
            "bob-private",
            "connected",
            apk_info={"apk_package": "com.example.bob"},
        )

        result = await get_from_jadx(
            "file-info",
            instance_id="bob-private",
            username="alice",
            is_admin=False,
        )

        assert result["error"] == "INSTANCE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_fuzzy_instance_lookup_respects_user_acl(self):
        InstanceRegistry.register_pending_instance("bob-private", "127.0.0.1", 8650, owner="bob")
        InstanceRegistry.update_instance_status(
            "bob-private",
            "connected",
            apk_info={"apk_package": "com.example.bob"},
        )

        result = await get_from_jadx(
            "file-info",
            instance_id="com.example.bob",
            username="alice",
            is_admin=False,
        )

        assert result["error"] == "INSTANCE_NOT_FOUND"

    @respx.mock
    @pytest.mark.asyncio
    async def test_default_instance_uses_visible_user_default(self):
        InstanceRegistry.register_pending_instance("bob-private", "127.0.0.1", 8650, owner="bob")
        InstanceRegistry.update_instance_status(
            "bob-private",
            "connected",
            apk_info={"apk_package": "com.example.bob"},
        )
        InstanceRegistry.register_pending_instance("shared", "127.0.0.1", 8651, owner=None)
        InstanceRegistry.update_instance_status(
            "shared",
            "connected",
            apk_info={"apk_package": "com.example.shared"},
        )

        route = respx.get("http://127.0.0.1:8651/file-info").mock(
            return_value=Response(200, json={"file_name": "shared.apk"})
        )

        result = await get_from_jadx(
            "file-info",
            username="alice",
            is_admin=False,
        )

        assert result["file_name"] == "shared.apk"
        assert route.called is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_request_uses_json_body(self):
        route = respx.post("http://127.0.0.1:8650/rename-class").mock(
            return_value=Response(200, json={"result": "ok"})
        )

        result = await get_from_jadx(
            "rename-class",
            method="POST",
            json_body={"class_name": "a.b.C", "new_name": "RenamedC"},
        )

        assert result["result"] == "ok"
        assert route.called is True
        request = route.calls.last.request
        assert request.method == "POST"
        assert json.loads(request.content.decode()) == {
            "class_name": "a.b.C",
            "new_name": "RenamedC",
        }
