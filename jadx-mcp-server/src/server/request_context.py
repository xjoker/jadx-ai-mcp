"""Helpers for propagating request-scoped user context to JADX requests."""

from typing import Any, Optional

from .config import get_from_jadx
from .user_auth import UserAuthManager


def get_current_user_request_kwargs() -> dict[str, Any]:
    """Return ACL kwargs for the current request, or an empty dict if unavailable."""
    user = UserAuthManager.get_current_user()
    if user is None:
        return {}
    return {
        "username": user.name,
        "is_admin": user.is_admin,
    }


async def get_from_jadx_for_current_user(
    endpoint: str,
    params: Optional[dict[str, Any]] = None,
    instance_id: Optional[str] = None,
    timeout: Optional[int] = None,
) -> dict[str, Any] | str:
    """Proxy JADX calls with the current user's ACL context when available."""
    return await get_from_jadx(
        endpoint,
        params or {},
        instance_id=instance_id,
        timeout=timeout,
        **get_current_user_request_kwargs(),
    )
