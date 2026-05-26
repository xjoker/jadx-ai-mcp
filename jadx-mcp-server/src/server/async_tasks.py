"""
Generic Python-side async task store for long-running MCP operations.

Usage:
    ticket = async_tasks.submit(some_coroutine(...))   # returns immediately
    result = async_tasks.poll(ticket)                   # check status
"""

import asyncio
import time
import uuid
from typing import Any

_store: dict[str, dict[str, Any]] = {}
_TTL_SECONDS = 300  # 5 min TTL for completed/failed tasks


def _prune() -> None:
    now = time.monotonic()
    expired = [k for k, v in _store.items()
               if now - v.get("_ts", 0) > _TTL_SECONDS]
    for k in expired:
        del _store[k]


async def _run(ticket: str, coro) -> None:
    ts = _store.get(ticket, {}).get("_ts", time.monotonic())
    try:
        result = await coro
        _store[ticket] = {"status": "done", "result": result, "_ts": ts}
    except Exception as exc:
        _store[ticket] = {"status": "error", "message": str(exc), "_ts": ts}


def submit(coro) -> str:
    """Submit a coroutine as a background asyncio task. Returns an opaque ticket."""
    _prune()
    ticket = uuid.uuid4().hex[:16]
    _store[ticket] = {"status": "running", "_ts": time.monotonic()}
    asyncio.create_task(_run(ticket, coro))
    return ticket


def poll(ticket: str) -> dict[str, Any]:
    """Poll the result of a submitted task by ticket."""
    _prune()
    entry = _store.get(ticket)
    if entry is None:
        return {
            "status": "not_found",
            "message": f"Ticket '{ticket}' not found or expired (TTL {_TTL_SECONDS}s). Resubmit.",
        }
    status = entry.get("status", "unknown")
    if status == "done":
        return {"status": "done", "result": entry.get("result")}
    if status == "error":
        return {"status": "error", "message": entry.get("message")}
    return {"status": "running", "retry_after_seconds": 5, "message": "Task in progress."}
