"""
JADX MCP Server - FastMCP Authentication Helpers

Builds the official FastMCP auth provider from the project's existing user config.
"""

from __future__ import annotations

from fastmcp.server.auth import AccessToken, StaticTokenVerifier

from .config_loader import UserConfig


LEGACY_MCP_CLIENT_NAME = "mcp-client"


def _build_token_table(users: list[UserConfig]) -> dict[str, dict]:
    tokens: dict[str, dict] = {}
    for user in users:
        if not user.token:
            continue

        scopes = ["mcp:user"]
        if user.is_admin:
            scopes.append("mcp:admin")
        if user.has_add_instances_permission:
            scopes.append("instances:write")

        tokens[user.token] = {
            "client_id": user.name,
            "username": user.name,
            "is_admin": user.is_admin,
            "can_add_instances": user.has_add_instances_permission,
            "scopes": scopes,
        }
    return tokens


class ReloadableStaticTokenVerifier(StaticTokenVerifier):
    """Static token verifier that can refresh its token table at runtime."""

    def reload_users(self, users: list[UserConfig]) -> None:
        self.tokens = _build_token_table(users)


class SwitchableTokenVerifier(StaticTokenVerifier):
    """
    Token verifier assigned once to ``mcp.auth`` at startup.

    The inner verifier can be swapped at runtime via ``set_inner()`` to
    support hot-reload between auth-enabled and auth-disabled modes
    without recreating the FastMCP app.

    When ``_inner`` is ``None`` (auth disabled), every token is accepted
    as an anonymous access token.
    """

    def __init__(self, inner: ReloadableStaticTokenVerifier | None = None) -> None:
        # Parent expects a tokens dict; give it an empty one since we delegate.
        super().__init__(tokens={})
        self._inner: ReloadableStaticTokenVerifier | None = inner

    async def verify_token(self, token: str) -> AccessToken | None:
        if self._inner is None:
            # Auth disabled — grant anonymous access
            return AccessToken(
                token=token,
                client_id="anonymous",
                scopes=[],
            )
        return await self._inner.verify_token(token)

    def set_inner(self, inner: ReloadableStaticTokenVerifier | None) -> None:
        """Swap the underlying verifier (called on hot-reload)."""
        self._inner = inner


def build_auth_provider(users: list[UserConfig]) -> ReloadableStaticTokenVerifier | None:
    """
    Build a FastMCP auth provider from configured users.

    The provider uses a static token table today so we can preserve the project's
    current token model while moving onto FastMCP's official `auth=` API.
    """
    if not users:
        return None

    tokens = _build_token_table(users)
    if not tokens:
        return None

    return ReloadableStaticTokenVerifier(tokens=tokens)


def build_legacy_cli_user(token: str) -> UserConfig:
    """
    Convert the legacy `--mcp-auth-token` flag into the same user model as config users.
    """
    return UserConfig(
        name=LEGACY_MCP_CLIENT_NAME,
        token=token,
        is_admin=False,
        can_add_instances=False,
    )
