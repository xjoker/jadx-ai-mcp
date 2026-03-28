"""
Unit tests for instance management tool security and permission checks.
"""

from types import SimpleNamespace

import pytest

from server.config_loader import AppConfig, SecurityConfig, UserConfig, set_config_loader
from server.tools.instance_tools import (
    _is_local_address,
    _is_private_network_address,
    register_instance_tools,
)
from server.user_auth import AuthenticatedUser, UserAuthManager


class DummyMCP:
    """Minimal MCP stub that captures registered tool callables."""

    def __init__(self):
        self.tools = {}

    def tool(self, name=None):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


@pytest.fixture(autouse=True)
def reset_config_loader():
    set_config_loader(None)
    yield
    set_config_loader(None)


@pytest.fixture
def tools():
    mcp = DummyMCP()
    register_instance_tools(mcp)
    return mcp.tools


def _set_config(*, allow_dynamic_instances: bool, users: list[UserConfig]) -> None:
    config = AppConfig(
        security=SecurityConfig(allow_dynamic_instances=allow_dynamic_instances),
        users=users,
    )
    set_config_loader(SimpleNamespace(config=config))


def test_is_local_address_recognizes_loopback():
    assert _is_local_address("localhost") is True
    assert _is_local_address("127.0.0.1") is True
    assert _is_local_address("::1") is True
    assert _is_local_address("8.8.8.8") is False


def test_is_private_network_address_rejects_rfc1918_and_link_local():
    assert _is_private_network_address("10.0.0.5") is True
    assert _is_private_network_address("172.16.10.5") is True
    assert _is_private_network_address("192.168.1.5") is True
    assert _is_private_network_address("169.254.10.5") is True
    assert _is_private_network_address("127.0.0.1") is False
    assert _is_private_network_address("8.8.8.8") is False


@pytest.mark.asyncio
async def test_add_instance_denies_when_globally_disabled_even_with_user_permission(tools):
    _set_config(
        allow_dynamic_instances=False,
        users=[UserConfig(name="alice", token="token-alice", can_add_instances=True)],
    )
    UserAuthManager.set_current_user(
        AuthenticatedUser(name="alice", token="token-alice", is_admin=False)
    )

    result = await tools["add_jadx_instance"]("127.0.0.1", 8650)

    assert result["error"] == "PERMISSION_DENIED"
    assert result["message"] == "Dynamic instance addition is globally disabled"


@pytest.mark.asyncio
async def test_add_instance_denies_when_user_lacks_permission(tools):
    _set_config(
        allow_dynamic_instances=True,
        users=[UserConfig(name="alice", token="token-alice", can_add_instances=False)],
    )
    UserAuthManager.set_current_user(
        AuthenticatedUser(name="alice", token="token-alice", is_admin=False)
    )

    result = await tools["add_jadx_instance"]("127.0.0.1", 8650)

    assert result["error"] == "PERMISSION_DENIED"
    assert result["message"] == "User does not have can_add_instances permission"


@pytest.mark.asyncio
async def test_add_instance_requires_explicit_token_for_non_local_hosts(monkeypatch, tools):
    shared_token = "shared-secret-token"
    UserAuthManager.configure([], default_jadx_token=shared_token)
    _set_config(
        allow_dynamic_instances=True,
        users=[UserConfig(name="alice", token="token-alice", can_add_instances=True)],
    )
    UserAuthManager.set_current_user(
        AuthenticatedUser(name="alice", token="token-alice", is_admin=False)
    )

    called = False

    async def fake_add_instance(**kwargs):
        nonlocal called
        called = True
        return {"success": True}

    monkeypatch.setattr(
        "server.tools.instance_tools.InstanceRegistry.add_instance",
        fake_add_instance,
    )

    result = await tools["add_jadx_instance"]("8.8.8.8", 8650)

    assert called is False
    assert result["error"] == "INVALID_INPUT"
    assert "explicit token" in result["message"].lower()
    assert shared_token not in result["message"]


@pytest.mark.asyncio
async def test_add_instance_rejects_private_network_targets_for_non_admins(tools):
    _set_config(
        allow_dynamic_instances=True,
        users=[UserConfig(name="alice", token="token-alice", can_add_instances=True)],
    )
    UserAuthManager.set_current_user(
        AuthenticatedUser(name="alice", token="token-alice", is_admin=False)
    )

    result = await tools["add_jadx_instance"]("192.168.1.50", 8650, token="explicit-token")

    assert result["error"] == "PERMISSION_DENIED"
    assert "private network" in result["message"].lower()


@pytest.mark.asyncio
async def test_add_instance_uses_shared_token_for_localhost(monkeypatch, tools):
    UserAuthManager.configure([], default_jadx_token="shared-secret-token")
    _set_config(
        allow_dynamic_instances=True,
        users=[UserConfig(name="alice", token="token-alice", can_add_instances=True)],
    )
    UserAuthManager.set_current_user(
        AuthenticatedUser(name="alice", token="token-alice", is_admin=False)
    )

    captured = {}

    async def fake_add_instance(**kwargs):
        captured.update(kwargs)
        return {"success": True, "instance": {"name": "local"}, "message": "ok"}

    monkeypatch.setattr(
        "server.tools.instance_tools.InstanceRegistry.add_instance",
        fake_add_instance,
    )

    result = await tools["add_jadx_instance"]("localhost", 8650)

    assert result["success"] is True
    assert captured["host"] == "127.0.0.1"
    assert captured["token"] == "shared-secret-token"
    assert captured["registration_source"] == "ai_dynamic"
