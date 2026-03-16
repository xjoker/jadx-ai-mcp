"""
Unified HTTP authentication for all custom route handlers.

Extracts Bearer tokens or session cookies and resolves them to an
AuthenticatedUser via UserAuthManager. This eliminates duplicated
token-extraction logic across status_page, transfer_server, etc.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Coroutine

from starlette.requests import Request
from starlette.responses import JSONResponse

from .user_auth import AuthenticatedUser, UserAuthManager


STATUS_AUTH_COOKIE = "jadx_status_token"


def authenticate_http_request(
    request: Request,
    require_auth: bool,
) -> tuple[AuthenticatedUser | None, str]:
    """
    Authenticate an HTTP request via Bearer token or session cookie.

    Returns:
        (user, auth_source) where auth_source is "bearer", "cookie", or "anonymous".
        user is None when authentication is required but no valid credential was found.
    """
    # 1. Try Bearer token from Authorization header
    auth_header = request.headers.get("authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    auth_source = "bearer"

    # 2. Fall back to session cookie (browser access)
    if not token:
        token = request.cookies.get(STATUS_AUTH_COOKIE, "")
        auth_source = "cookie" if token else "anonymous"

    # 3. Authenticate via the shared UserAuthManager path
    user = UserAuthManager.authenticate(token)

    if user is None and require_auth and not UserAuthManager.allows_anonymous():
        return None, auth_source

    if user is None:
        return AuthenticatedUser(name="anonymous", token="", is_admin=False), "anonymous"

    return user, auth_source


def require_user_auth(
    handler: Callable[..., Coroutine[Any, Any, Any]],
    *,
    require_auth: bool,
    exempt_paths: frozenset[str] = frozenset(),
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """
    Decorator that authenticates the request and sets the user context
    before calling *handler*, then cleans up the context var afterwards.

    Exempt paths (e.g. login/logout) skip authentication entirely.
    """

    @wraps(handler)
    async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
        # Skip auth for explicitly exempted paths
        if request.url.path in exempt_paths:
            return await handler(request, *args, **kwargs)

        user, _auth_source = authenticate_http_request(request, require_auth)
        if user is None:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        UserAuthManager.set_current_user(user)
        try:
            return await handler(request, *args, **kwargs)
        finally:
            UserAuthManager.set_current_user(None)

    return wrapper
