"""
Layer 2 Unit Tests: Status Page

Tests operational status rendering logic without starting the MCP server.
"""

import json
from urllib.parse import urlencode

import pytest
from starlette.requests import Request

from server.config_loader import UserConfig
from server.busy_tracker import InstanceBusyTracker
from server.instance_registry import InstanceRegistry
from server.http_auth_middleware import STATUS_AUTH_COOKIE
from server.status_page import (
    build_status_snapshot,
    status_html_response,
    status_json_response,
    status_login_response,
    status_logout_response,
)
from server.user_auth import AuthenticatedUser, UserAuthManager


def make_request(
    path: str = "/status",
    headers: dict[str, str] | None = None,
    method: str = "GET",
    body: bytes = b"",
) -> Request:
    """Build a minimal Starlette request for route unit tests."""
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
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def make_form_request(
    path: str,
    form_data: dict[str, str],
    cookies: dict[str, str] | None = None,
) -> Request:
    """Build a form POST request with optional cookies."""
    body = urlencode(form_data).encode("utf-8")
    headers: dict[str, str] = {"Content-Type": "application/x-www-form-urlencoded"}
    if cookies:
        headers["cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    return make_request(
        path=path,
        method="POST",
        headers=headers,
        body=body,
    )


class TestStatusPage:
    """Tests for status snapshot generation and auth gating."""

    @pytest.fixture(autouse=True)
    def reset_tracker(self):
        InstanceBusyTracker.force_release_all()
        yield
        InstanceBusyTracker.force_release_all()

    def test_build_status_snapshot_filters_instances_for_regular_user(self):
        """Regular users should only see shared instances and their own dynamic ones."""
        UserAuthManager.configure([], allow_anonymous=True)

        InstanceRegistry.register_pending_instance(
            "cfg-shared",
            "127.0.0.1",
            8650,
            registration_source="config",
        )
        InstanceRegistry.register_pending_instance(
            "alice-ai",
            "127.0.0.1",
            8651,
            owner="alice",
            is_dynamic=True,
            registration_source="ai_dynamic",
        )
        InstanceRegistry.register_pending_instance(
            "bob-runtime",
            "127.0.0.1",
            8652,
            owner="bob",
            is_dynamic=True,
            registration_source="runtime",
        )

        snapshot = build_status_snapshot(
            server_host="0.0.0.0",
            server_port=8651,
            require_auth=False,
            viewer=AuthenticatedUser(name="alice", token="token-alice", is_admin=False),
            auth_source="bearer",
        )

        names = {inst["name"] for inst in snapshot["instances"]}
        assert names == {"cfg-shared", "alice-ai"}
        assert snapshot["summary"]["total_instances"] == 2
        assert snapshot["summary"]["default_instance"] == "cfg-shared"
        assert snapshot["summary"]["source_counts"] == {"config": 1, "ai_dynamic": 1}
        assert snapshot["summary"]["scheduler_counts"] == {
            "metadata_inflight": 0,
            "code_read_inflight": 0,
            "exclusive_inflight": 0,
            "queue_depth": 0,
            "queue_limit": 8,
            "active_limit": 4,
        }

        instance_map = {inst["name"]: inst for inst in snapshot["instances"]}
        assert instance_map["cfg-shared"]["source_label"] == "Config File"
        assert instance_map["cfg-shared"]["scope_label"] == "shared"
        assert instance_map["alice-ai"]["source_label"] == "AI Dynamic"
        assert instance_map["alice-ai"]["scope_label"] == "user:alice"
        assert instance_map["cfg-shared"]["scheduler"]["metadata_inflight"] == 0
        assert instance_map["cfg-shared"]["scheduler"]["queue_limit"] == 4
        assert instance_map["cfg-shared"]["scheduler"]["active_limit"] == 2
        assert instance_map["cfg-shared"]["scheduler_label"] == "m:0 c:0/2 x:0 q:0/4"

    @pytest.mark.asyncio
    async def test_status_html_response_renders_login_form_when_auth_required(self):
        """Unauthenticated browser requests should receive the login page."""
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        response = await status_html_response(
            make_request("/status"),
            server_host="127.0.0.1",
            server_port=8651,
            require_auth=True,
        )

        assert response.status_code == 401
        body = response.body.decode("utf-8")
        assert "Status Login" in body
        assert "user token" in body.lower()

    @pytest.mark.asyncio
    async def test_status_login_response_sets_cookie_and_redirects(self):
        """Valid token login should set a session cookie and redirect back to /status."""
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        csrf_token = "test-csrf-token"
        response = await status_login_response(
            make_form_request(
                "/status/login",
                {"token": "token-alice", "csrf_token": csrf_token},
                cookies={"csrf_token": csrf_token},
            )
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/status"
        set_cookie = response.headers["set-cookie"]
        assert f"{STATUS_AUTH_COOKIE}=token-alice" in set_cookie
        assert "HttpOnly" in set_cookie

    @pytest.mark.asyncio
    async def test_status_login_response_rejects_missing_csrf(self):
        """Login without CSRF token should return 403."""
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        response = await status_login_response(
            make_form_request("/status/login", {"token": "token-alice"})
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_status_json_response_requires_auth_when_configured(self):
        """Missing token should return 401 when auth is required."""
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )

        response = await status_json_response(
            make_request("/status.json"),
            server_host="127.0.0.1",
            server_port=8651,
            require_auth=True,
        )

        assert response.status_code == 401
        assert json.loads(response.body) == {"error": "Unauthorized"}

    @pytest.mark.asyncio
    async def test_status_json_response_accepts_cookie_login(self):
        """Authenticated browser sessions should receive a filtered JSON snapshot."""
        UserAuthManager.configure(
            [UserConfig(name="alice", token="token-alice")],
            allow_anonymous=False,
        )
        InstanceRegistry.register_pending_instance(
            "cfg-shared",
            "127.0.0.1",
            8650,
            registration_source="config",
        )
        InstanceRegistry.register_pending_instance(
            "alice-ai",
            "127.0.0.1",
            8651,
            owner="alice",
            is_dynamic=True,
            registration_source="ai_dynamic",
        )

        response = await status_json_response(
            make_request(
                "/status.json",
                headers={"Cookie": f"{STATUS_AUTH_COOKIE}=token-alice"},
            ),
            server_host="127.0.0.1",
            server_port=8651,
            require_auth=True,
        )

        payload = json.loads(response.body)
        assert response.status_code == 200
        assert payload["viewer"]["name"] == "alice"
        assert payload["viewer"]["auth_source"] == "cookie"
        assert {inst["name"] for inst in payload["instances"]} == {"cfg-shared", "alice-ai"}

    @pytest.mark.asyncio
    async def test_status_logout_response_clears_cookie(self):
        """Logout should clear the browser session cookie and redirect."""
        response = await status_logout_response(make_request("/status/logout", method="POST"))

        assert response.status_code == 303
        assert response.headers["location"] == "/status"
        assert f"{STATUS_AUTH_COOKIE}=" in response.headers["set-cookie"]
        assert "Max-Age=0" in response.headers["set-cookie"]
