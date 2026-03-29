"""
Layer 3 Integration Tests - rename, instance management, and transfer tokens.

Covers:
- Error-path validation for rename-method / rename-field / rename-package
- Direct Python tool-call integration for instance management tools
- Direct Python tool-call integration for transfer token lifecycle helpers
"""

from __future__ import annotations

import asyncio
import os
import time
from urllib.parse import urlparse

import pytest
import pytest_asyncio

from src.server.config import HttpClientManager, set_jadx_config
from src.server.instance_registry import InstanceRegistry
from src.server.tools.instance_tools import register_instance_tools
from src.server.tools.transfer_tools import (
    create_transfer_token,
    get_transfer_token_status,
    revoke_transfer_token,
)
from src.server.user_auth import AuthenticatedUser, UserAuthManager


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class DummyMCP:
    """Minimal MCP stub that captures registered tool callables."""

    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name=None):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


@pytest_asyncio.fixture
async def configured_python_tool_calls(jadx_base_url, mcp_base_url, monkeypatch):
    """
    Point direct Python tool calls at the configured integration target.

    This mirrors the fixture pattern used by test_new_features_integration.py,
    while also forcing transfer token URLs to reflect the integration MCP base.
    """
    assert jadx_base_url.startswith("http")
    assert mcp_base_url.startswith("http")

    parsed = urlparse(jadx_base_url)
    assert parsed.hostname, f"Invalid JADX base URL: {jadx_base_url}"
    assert parsed.port is not None, f"JADX base URL must include an explicit port: {jadx_base_url}"

    set_jadx_config(parsed.hostname, parsed.port)
    monkeypatch.setenv("MCP_SERVER_URL", mcp_base_url.rstrip("/"))

    plugin_token = (
        os.getenv("JADX_PLUGIN_AUTH_TOKEN")
        or os.getenv("JADX_MCP_AUTH_TOKEN")
        or ""
    )
    InstanceRegistry.set_auth_token(plugin_token)
    UserAuthManager.configure([], default_jadx_token=plugin_token, allow_anonymous=True)

    try:
        yield
    finally:
        await HttpClientManager.close()
        await InstanceRegistry.close_http_client()


@pytest_asyncio.fixture
async def configured_instance_tools(configured_python_tool_calls, jadx_base_url):
    """Register instance tools locally and seed a single connected `local` instance."""
    parsed = urlparse(jadx_base_url)
    assert parsed.hostname, f"Invalid JADX base URL: {jadx_base_url}"
    assert parsed.port is not None, f"JADX base URL must include an explicit port: {jadx_base_url}"

    UserAuthManager.set_current_user(
        AuthenticatedUser(name="integration-admin", token="integration-admin", is_admin=True)
    )

    mcp = DummyMCP()
    register_instance_tools(mcp)

    seeded = await InstanceRegistry.add_instance(
        host=parsed.hostname,
        port=parsed.port,
        name="local",
        token=InstanceRegistry.get_auth_token(),
        registration_source="integration_test",
    )
    assert seeded["success"] is True, f"Failed to seed local instance: {seeded}"

    try:
        yield mcp.tools
    finally:
        InstanceRegistry.clear_all()


@pytest_asyncio.fixture
async def created_transfer_token(configured_python_tool_calls, mcp_base_url):
    """Create a short-lived transfer token for status/revoke checks."""
    result = await create_transfer_token(
        resource_type="batch_classes",
        timeout_seconds=120,
        instance_id=f"integration-transfer-{time.monotonic_ns()}",
    )
    assert result["success"] is True, f"Failed to create transfer token: {result}"
    assert result["transfer_url"] == f"{mcp_base_url.rstrip('/')}/transfer"

    try:
        yield result
    finally:
        await revoke_transfer_token(result["token"])


async def _clear_class_cache_until_success(
    clear_class_cache_tool,
    instance_id: str = "local",
    max_wait_seconds: float = 35.0,
):
    """Handle the plugin's global 30s cache-clear cooldown without flaking."""
    deadline = time.monotonic() + max_wait_seconds
    last_payload = None

    while True:
        payload = await clear_class_cache_tool(instance_id)
        last_payload = payload
        if payload.get("success") is True:
            return payload

        remaining = payload.get("cooldown_remaining_seconds")
        if remaining is None:
            pytest.fail(f"Expected cache clear success or cooldown metadata, got: {payload}")

        now = time.monotonic()
        if now >= deadline:
            break

        try:
            sleep_for = float(remaining)
        except (TypeError, ValueError):
            sleep_for = 1.0

        sleep_for = max(0.5, min(sleep_for, deadline - now))
        await asyncio.sleep(sleep_for)

    pytest.fail(f"Cache clear stayed debounced until timeout: {last_payload}")


class TestRenameMethodIntegration:
    async def test_post_rename_method_without_required_params_returns_400(
        self, jadx_base_url, http_client
    ):
        resp = await http_client.post(f"{jadx_base_url}/rename-method", json={})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"

        data = resp.json()
        assert "error" in data
        assert "Missing required" in data["error"]

    async def test_post_rename_method_for_unknown_class_returns_404(
        self, jadx_base_url, http_client
    ):
        resp = await http_client.post(
            f"{jadx_base_url}/rename-method",
            json={
                "class_name": "com.integration.DoesNotExist",
                "method_name": "missingMethod",
                "new_name": "stillMissingMethod",
            },
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

        data = resp.json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    async def test_get_rename_method_is_not_allowed(self, jadx_base_url, http_client):
        resp = await http_client.get(f"{jadx_base_url}/rename-method")
        # Javalin returns 404 for unregistered GET when only POST is registered
        assert resp.status_code in (404, 405), f"Expected 404 or 405, got {resp.status_code}"


class TestRenameFieldIntegration:
    async def test_post_rename_field_without_required_params_returns_400(
        self, jadx_base_url, http_client
    ):
        resp = await http_client.post(f"{jadx_base_url}/rename-field", json={})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"

        data = resp.json()
        assert "error" in data
        assert "Missing required parameter" in data["error"]

    async def test_post_rename_field_for_unknown_class_returns_404(
        self, jadx_base_url, http_client
    ):
        resp = await http_client.post(
            f"{jadx_base_url}/rename-field",
            json={
                "class_name": "com.integration.DoesNotExist",
                "field_name": "missingField",
                "new_field_name": "stillMissingField",
            },
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

        data = resp.json()
        assert "error" in data
        assert "not found" in data["error"].lower()


class TestRenamePackageIntegration:
    async def test_post_rename_package_without_required_params_returns_400(
        self, jadx_base_url, http_client
    ):
        resp = await http_client.post(f"{jadx_base_url}/rename-package", json={})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"

        data = resp.json()
        assert "error" in data
        assert "Missing required" in data["error"]

    async def test_post_rename_package_for_unknown_package_is_not_applied(
        self, jadx_base_url, http_client
    ):
        resp = await http_client.post(
            f"{jadx_base_url}/rename-package",
            json={
                "old_package_name": "com.integration.does.not.exist",
                "new_package_name": "com.integration.renamed",
            },
        )
        data = resp.json()

        # Current plugin implementations may return a 404-style error or a 200
        # no-op payload with zero renamed classes; both ensure no rename occurs.
        if resp.status_code == 404:
            assert "error" in data
            assert "not found" in data["error"].lower()
            return

        assert resp.status_code == 200, f"Expected 200/404, got {resp.status_code}"
        assert data["renamed"] == 0
        assert data["total"] == 0
        assert data["errors"] == []


class TestInstanceManagementToolsIntegration:
    async def test_list_jadx_instances_returns_local_instance(self, configured_instance_tools):
        result = await configured_instance_tools["list_jadx_instances"]()

        assert result["count"] >= 1
        assert result["default_instance"] == "local"
        names = {instance["name"] for instance in result["instances"]}
        assert "local" in names

        local = next(instance for instance in result["instances"] if instance["name"] == "local")
        assert local["status"] in {"connected", "degraded"}

    async def test_health_check_jadx_instances_reports_local_health(self, configured_instance_tools):
        result = await configured_instance_tools["health_check_jadx_instances"]()

        assert result["total"] == 1
        assert len(result["instances"]) == 1
        assert result["instances"][0]["name"] == "local"
        assert result["instances"][0]["status"] in {"connected", "degraded"}

    async def test_get_jadx_instance_info_returns_local_details(self, configured_instance_tools):
        result = await configured_instance_tools["get_jadx_instance_info"]("local")

        assert result["success"] is True
        assert result["name"] == "local"
        assert result["status"] in {"connected", "degraded"}
        assert isinstance(result["apk_info"], dict)
        assert result["apk_info"].get("loaded") is True

    async def test_clear_class_cache_returns_success_and_queries_still_work(
        self, configured_instance_tools, jadx_base_url, http_client
    ):
        result = await _clear_class_cache_until_success(configured_instance_tools["clear_class_cache"])

        assert result["success"] is True
        assert "cooldown_seconds" in result

        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200, f"Expected 200 after cache clear, got {resp.status_code}"
        assert resp.json()["loaded"] is True

    async def test_add_jadx_instance_with_invalid_host_returns_error(self, configured_instance_tools):
        result = await configured_instance_tools["add_jadx_instance"](
            "definitely-invalid-host.example.invalid",
            8650,
            token="explicit-test-token",
        )
        assert result["success"] is False
        assert "Failed to add instance" in result["message"]

        instances = await configured_instance_tools["list_jadx_instances"]()
        assert instances["count"] == 1
        assert instances["instances"][0]["name"] == "local"

    async def test_remove_jadx_instance_with_unknown_name_returns_error(self, configured_instance_tools):
        result = await configured_instance_tools["remove_jadx_instance"]("missing-instance")

        assert result["error"] == "INSTANCE_NOT_FOUND"
        assert "not found" in result["message"].lower()

    async def test_set_default_jadx_instance_with_unknown_name_returns_error(
        self, configured_instance_tools
    ):
        result = await configured_instance_tools["set_default_jadx_instance"]("missing-instance")

        assert result["success"] is False
        assert "not found" in result["message"].lower()


class TestTransferTokenIntegration:
    async def test_create_transfer_token_returns_token_string(
        self, configured_python_tool_calls, mcp_base_url
    ):
        result = await create_transfer_token(
            resource_type="batch_classes",
            timeout_seconds=120,
            instance_id=f"integration-transfer-create-{time.monotonic_ns()}",
        )

        assert result["success"] is True
        assert isinstance(result["token"], str)
        assert result["token"]
        assert result["transfer_url"] == f"{mcp_base_url.rstrip('/')}/transfer"
        assert result["resource_type"] == "batch_classes"

        await revoke_transfer_token(result["token"])

    async def test_get_transfer_token_status_reports_existing_token(self, created_transfer_token):
        status = await get_transfer_token_status(created_transfer_token["token"])

        assert status["success"] is True
        assert status["exists"] is True
        assert status["used"] is False
        assert status["resource_type"] == "batch_classes"
        assert status["operation"] == "download"
        assert status["expires_in"] > 0

    async def test_revoke_transfer_token_removes_token(self, created_transfer_token):
        revoke_result = await revoke_transfer_token(created_transfer_token["token"])
        assert revoke_result["success"] is True

        status = await get_transfer_token_status(created_transfer_token["token"])
        assert status["success"] is True
        assert status["exists"] is False
        assert status["used"] is False
