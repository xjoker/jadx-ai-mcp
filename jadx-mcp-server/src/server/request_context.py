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


def get_default_instance_id() -> Optional[str]:
    """Return the name of the current default JADX instance, or None if none registered.

    Tool-layer code that wants to display or log the effective instance without
    making a full JADX request can call this helper instead of duplicating the
    InstanceRegistry lookup.

    When instance_id=None is passed to get_from_jadx_for_current_user, the
    routing layer already applies this same logic automatically — this helper
    is provided purely as a convenience for display/logging purposes.

    Returns:
        str: Name of the default instance (e.g. "xhs-v835"), or None if the
             registry is empty or unavailable.
    """
    try:
        from .instance_registry import InstanceRegistry
        user = UserAuthManager.get_current_user()
        if user is not None:
            inst = InstanceRegistry.get_default_for_user(user.name, user.is_admin)
        else:
            inst = InstanceRegistry.get_default()
        return inst.name if inst is not None else None
    except Exception:
        return None


async def get_from_jadx_for_current_user(
    endpoint: str,
    params: Optional[dict[str, Any]] = None,
    instance_id: Optional[str] = None,
    timeout: Optional[int] = None,
    method: str = "GET",
    json_body: Optional[dict[str, Any]] = None,
) -> dict[str, Any] | str:
    """Proxy JADX calls with the current user's ACL context when available.

    When instance_id is None (the default), the routing layer automatically
    selects the active default instance — callers do not need to resolve it
    themselves. Use get_default_instance_id() if you need the name for
    logging or display purposes.
    """
    return await get_from_jadx(
        endpoint,
        params or {},
        instance_id=instance_id,
        timeout=timeout,
        method=method,
        json_body=json_body,
        **get_current_user_request_kwargs(),
    )
