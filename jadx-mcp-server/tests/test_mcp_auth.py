"""
Layer 1 Unit Tests: FastMCP Auth Provider Construction
"""

import pytest

from server.config_loader import UserConfig
from server.mcp_auth import (
    LEGACY_MCP_CLIENT_NAME,
    ReloadableStaticTokenVerifier,
    SwitchableTokenVerifier,
    build_auth_provider,
    build_legacy_cli_user,
)


class TestMcpAuthProvider:
    """Tests for building the FastMCP auth provider from project config."""

    @pytest.mark.asyncio
    async def test_build_auth_provider_returns_none_without_users(self):
        """No configured users means no official auth provider."""
        assert build_auth_provider([]) is None

    @pytest.mark.asyncio
    async def test_build_auth_provider_verifies_tokens(self):
        """Configured users should be exposed as a StaticTokenVerifier."""
        verifier = build_auth_provider([
            UserConfig(name="alice", token="token-alice", is_admin=True, can_add_instances=True)
        ])

        assert verifier is not None

        access_token = await verifier.verify_token("token-alice")
        assert access_token is not None
        assert access_token.client_id == "alice"
        assert access_token.claims["username"] == "alice"
        assert access_token.claims["is_admin"] is True
        assert "instances:write" in access_token.scopes

    @pytest.mark.asyncio
    async def test_reloadable_verifier_refreshes_token_table(self):
        """Hot-reload should swap the accepted token set without recreating the provider."""
        verifier = build_auth_provider([
            UserConfig(name="alice", token="token-alice", is_admin=False)
        ])

        assert isinstance(verifier, ReloadableStaticTokenVerifier)
        assert await verifier.verify_token("token-alice") is not None

        verifier.reload_users([UserConfig(name="bob", token="token-bob", is_admin=True)])

        assert await verifier.verify_token("token-alice") is None
        reloaded_token = await verifier.verify_token("token-bob")
        assert reloaded_token is not None
        assert reloaded_token.claims["username"] == "bob"
        assert reloaded_token.claims["is_admin"] is True

    def test_build_legacy_cli_user(self):
        """The legacy CLI token should be normalized into the shared user model."""
        user = build_legacy_cli_user("cli-token")

        assert user.name == LEGACY_MCP_CLIENT_NAME
        assert user.token == "cli-token"
        assert user.is_admin is False
        assert user.has_add_instances_permission is False


class TestSwitchableTokenVerifier:
    """Tests for SwitchableTokenVerifier hot-reload support."""

    @pytest.mark.asyncio
    async def test_grants_anonymous_when_inner_is_none(self):
        """With no inner verifier, any token should produce anonymous access."""
        verifier = SwitchableTokenVerifier(inner=None)
        access = await verifier.verify_token("anything")

        assert access is not None
        assert access.client_id == "anonymous"

    @pytest.mark.asyncio
    async def test_delegates_to_inner_when_set(self):
        """With an inner verifier, token lookup should behave normally."""
        inner = build_auth_provider([
            UserConfig(name="alice", token="token-alice", is_admin=False)
        ])
        verifier = SwitchableTokenVerifier(inner=inner)

        access = await verifier.verify_token("token-alice")
        assert access is not None
        assert access.client_id == "alice"

        assert await verifier.verify_token("bad-token") is None

    @pytest.mark.asyncio
    async def test_set_inner_enables_auth(self):
        """Switching from None to a real verifier should enable auth."""
        verifier = SwitchableTokenVerifier(inner=None)

        # Initially anonymous
        access = await verifier.verify_token("any")
        assert access is not None
        assert access.client_id == "anonymous"

        # Enable auth
        inner = build_auth_provider([
            UserConfig(name="bob", token="token-bob", is_admin=True)
        ])
        verifier.set_inner(inner)

        assert await verifier.verify_token("any") is None
        access = await verifier.verify_token("token-bob")
        assert access is not None
        assert access.client_id == "bob"

    @pytest.mark.asyncio
    async def test_set_inner_none_disables_auth(self):
        """Switching from a real verifier to None should disable auth."""
        inner = build_auth_provider([
            UserConfig(name="alice", token="token-alice", is_admin=False)
        ])
        verifier = SwitchableTokenVerifier(inner=inner)

        # Auth is on
        assert await verifier.verify_token("bad") is None

        # Disable auth
        verifier.set_inner(None)
        access = await verifier.verify_token("anything")
        assert access is not None
        assert access.client_id == "anonymous"
