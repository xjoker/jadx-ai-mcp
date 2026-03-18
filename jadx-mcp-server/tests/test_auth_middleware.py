"""
Layer 1 Unit Tests: Authentication Middleware

Tests request-scoped user context population from FastMCP access tokens.
"""

import pytest
from fastmcp.server.auth import AccessToken
from fastmcp.server.middleware import MiddlewareContext
from mcp import McpError

from server import auth_middleware
from server.auth_middleware import BearerAuthMiddleware
from server.config_loader import UserConfig
from server.user_auth import UserAuthManager


class TestBearerAuthMiddleware:
    """Tests for FastMCP access-token bridging middleware."""

    @pytest.mark.asyncio
    async def test_on_request_uses_fastmcp_access_token(self, monkeypatch):
        """Verified MCP requests should populate the current user from the access token."""
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        monkeypatch.setattr(
            auth_middleware,
            "get_access_token",
            lambda: AccessToken(
                token="token-alice",
                client_id="alice",
                scopes=["mcp:user"],
                claims={"username": "alice", "is_admin": False},
            ),
        )
        monkeypatch.setattr(
            auth_middleware.BearerAuthMiddleware,
            "_has_http_request",
            staticmethod(lambda: True),
        )

        middleware = BearerAuthMiddleware(require_auth=True)
        context = MiddlewareContext(message=object(), method="initialize")

        async def call_next(ctx):
            user = UserAuthManager.get_current_user()
            return user.name if user else None

        result = await middleware.on_request(context, call_next)

        assert result == "alice"
        assert UserAuthManager.get_current_user() is None

    @pytest.mark.asyncio
    async def test_on_request_allows_stdio_without_http_auth(self, monkeypatch):
        """Stdio requests should remain usable even when HTTP auth is configured."""
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        monkeypatch.setattr(auth_middleware, "get_access_token", lambda: None)
        monkeypatch.setattr(
            auth_middleware.BearerAuthMiddleware,
            "_has_http_request",
            staticmethod(lambda: False),
        )

        middleware = BearerAuthMiddleware(require_auth=True)
        context = MiddlewareContext(message=object(), method="initialize")

        async def call_next(ctx):
            user = UserAuthManager.get_current_user()
            return (user.name, user.is_admin) if user else None

        result = await middleware.on_request(context, call_next)

        assert result == ("stdio-local", True)

    @pytest.mark.asyncio
    async def test_on_request_rejects_missing_http_token_when_auth_required(self, monkeypatch):
        """HTTP MCP requests without a verified access token should be rejected."""
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )
        monkeypatch.setattr(auth_middleware, "get_access_token", lambda: None)
        monkeypatch.setattr(
            auth_middleware.BearerAuthMiddleware,
            "_has_http_request",
            staticmethod(lambda: True),
        )

        middleware = BearerAuthMiddleware(require_auth=True)
        context = MiddlewareContext(message=object(), method="initialize")

        async def call_next(ctx):
            return "should-not-run"

        with pytest.raises(McpError) as exc_info:
            await middleware.on_request(context, call_next)

        assert "Unauthorized" in str(exc_info.value)
