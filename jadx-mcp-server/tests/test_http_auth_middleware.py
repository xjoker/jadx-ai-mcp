"""
Unit tests for the unified HTTP authentication middleware.
"""

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from server.config_loader import UserConfig
from server.http_auth_middleware import (
    STATUS_AUTH_COOKIE,
    authenticate_http_request,
    require_user_auth,
)
from server.user_auth import AuthenticatedUser, UserAuthManager


def _make_request(
    path: str = "/status",
    headers: dict[str, str] | None = None,
    method: str = "GET",
) -> Request:
    header_items = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": header_items,
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


class TestAuthenticateHttpRequest:
    """Tests for the unified authenticate_http_request function."""

    def test_bearer_token_takes_priority(self):
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        request = _make_request(
            headers={
                "Authorization": "Bearer token-alice",
                "Cookie": f"{STATUS_AUTH_COOKIE}=stale-cookie",
            }
        )
        user, source = authenticate_http_request(request, require_auth=True)

        assert user is not None
        assert user.name == "alice"
        assert source == "bearer"

    def test_cookie_fallback(self):
        UserAuthManager.configure(
            [UserConfig(name="bob", token="token-bob")],
            allow_anonymous=False,
        )

        request = _make_request(
            headers={"Cookie": f"{STATUS_AUTH_COOKIE}=token-bob"}
        )
        user, source = authenticate_http_request(request, require_auth=True)

        assert user is not None
        assert user.name == "bob"
        assert source == "cookie"

    def test_anonymous_when_allowed(self):
        UserAuthManager.configure([], allow_anonymous=True)

        request = _make_request()
        user, source = authenticate_http_request(request, require_auth=False)

        assert user is not None
        assert user.name == "anonymous"
        assert source == "anonymous"

    def test_none_when_auth_required_and_no_token(self):
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        request = _make_request()
        user, source = authenticate_http_request(request, require_auth=True)

        assert user is None
        assert source == "anonymous"

    def test_invalid_token_returns_none_when_required(self):
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        request = _make_request(headers={"Authorization": "Bearer wrong-token"})
        user, source = authenticate_http_request(request, require_auth=True)

        assert user is None
        assert source == "bearer"


class TestRequireUserAuth:
    """Tests for the require_user_auth decorator."""

    @pytest.mark.asyncio
    async def test_sets_and_clears_user_context(self):
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        captured_user = None

        async def handler(request):
            nonlocal captured_user
            captured_user = UserAuthManager.get_current_user()
            return JSONResponse({"ok": True})

        wrapped = require_user_auth(handler, require_auth=True)
        request = _make_request(headers={"Authorization": "Bearer token-alice"})
        response = await wrapped(request)

        assert response.status_code == 200
        assert captured_user is not None
        assert captured_user.name == "alice"
        # Context should be cleaned up after handler returns
        assert UserAuthManager.get_current_user() is None

    @pytest.mark.asyncio
    async def test_returns_401_when_auth_fails(self):
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        async def handler(request):
            return JSONResponse({"ok": True})

        wrapped = require_user_auth(handler, require_auth=True)
        request = _make_request()
        response = await wrapped(request)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_exempt_paths_skip_auth(self):
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        async def handler(request):
            return JSONResponse({"ok": True})

        wrapped = require_user_auth(
            handler,
            require_auth=True,
            exempt_paths=frozenset(["/status/login"]),
        )
        request = _make_request(path="/status/login")
        response = await wrapped(request)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cleans_up_context_on_handler_error(self):
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        async def handler(request):
            raise ValueError("boom")

        wrapped = require_user_auth(handler, require_auth=True)
        request = _make_request(headers={"Authorization": "Bearer token-alice"})

        with pytest.raises(ValueError, match="boom"):
            await wrapped(request)

        assert UserAuthManager.get_current_user() is None
