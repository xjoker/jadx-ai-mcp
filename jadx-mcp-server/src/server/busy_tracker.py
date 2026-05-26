"""
Instance busy tracking and per-lane scheduling for MCP tool calls.

The tracker keeps lightweight per-instance scheduling state so metadata-only
requests can proceed concurrently, code-read requests can queue, and exclusive
operations keep the stronger serialization guarantees required by heavy search
paths.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .logging_config import get_logger
from .types import ErrorCode


logger = get_logger("busy_tracker")

DEFAULT_INSTANCE_TRACKING_KEY = "__default__"
DEFAULT_CODE_READ_QUEUE_LIMIT = 8
DEFAULT_CODE_READ_ACTIVE_LIMIT = 4
DEFAULT_EXCLUSIVE_WAIT_SECONDS = 2.0

LANE_METADATA = "metadata"
LANE_CODE_READ = "code_read"
LANE_EXCLUSIVE = "exclusive"

_SEARCH_IN_SPLIT_RE = re.compile(r"[,/]")

METADATA_OPERATIONS = {
    "get_all_classes",
    "get_methods_of_class",
    "get_fields_of_class",
    "get_file_info",
    "get_package_classes",
    "get_class_info",
    "get_decompile_status",
    "get_method_signature",
    "search_native_methods",
    "get_xrefs",
    "batch_get_xrefs",
    "get_all_resource_file_names",
    "get_code_search_result",   # poll-only, instant read
    "get_task_result",           # poll-only, instant read
}

CODE_READ_OPERATIONS = {
    "get_class_source",
    "get_method_by_name",
    "get_smali_of_class",
    "get_android_manifest",
    "get_resource_file",
    "jar_get_manifest",
    "jar_get_services",
    "jar_get_entry_points",
    "jar_get_dependencies",
    "jar_get_bytecode",
    "get_main_activity_class",
    "get_strings",
    "get_config_strings",
    "get_method_callees",
    "batch_get_class_source",
    "batch_get_method_by_name",
}

EXCLUSIVE_OPERATIONS = {
    "rename",
}


@dataclass(frozen=True)
class OperationPolicy:
    lane: str
    queue_limit: int = 0
    active_limit: int = 1


@dataclass
class ActiveOperation:
    token: str
    operation: str
    lane: str
    started_monotonic: float
    started_at: str


@dataclass
class QueuedOperation:
    token: str
    operation: str
    requested_monotonic: float
    requested_at: str


@dataclass
class InstanceSchedulerState:
    metadata_active: dict[str, ActiveOperation] = field(default_factory=dict)
    code_read_active: dict[str, ActiveOperation] = field(default_factory=dict)
    exclusive_active: dict[str, ActiveOperation] = field(default_factory=dict)
    code_read_queue: deque[QueuedOperation] = field(default_factory=deque)
    last_busy_reason: str = ""
    last_busy_at: str | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_search_in(value: Any) -> set[str]:
    if not isinstance(value, str) or not value.strip():
        return {"code"}
    tokens = {
        token.strip().lower()
        for token in _SEARCH_IN_SPLIT_RE.split(value)
        if token.strip()
    }
    return tokens or {"code"}


def get_operation_policy(operation_name: str, kwargs: dict[str, Any] | None = None) -> OperationPolicy:
    if operation_name == "search_classes_by_keyword":
        search_in = _split_search_in((kwargs or {}).get("search_in"))
        if search_in & {"code", "comment"}:
            return OperationPolicy(lane=LANE_EXCLUSIVE)
        return OperationPolicy(lane=LANE_METADATA)

    if operation_name in METADATA_OPERATIONS:
        return OperationPolicy(lane=LANE_METADATA)

    if operation_name in CODE_READ_OPERATIONS:
        return OperationPolicy(
            lane=LANE_CODE_READ,
            queue_limit=DEFAULT_CODE_READ_QUEUE_LIMIT,
            active_limit=DEFAULT_CODE_READ_ACTIVE_LIMIT,
        )

    if operation_name in EXCLUSIVE_OPERATIONS:
        return OperationPolicy(lane=LANE_EXCLUSIVE)

    return OperationPolicy(lane=LANE_EXCLUSIVE)


def should_bypass_busy_check(operation_name: str, kwargs: dict[str, Any] | None = None) -> bool:
    return get_operation_policy(operation_name, kwargs).lane == LANE_METADATA


class InstanceBusyTracker:
    _states: dict[str, InstanceSchedulerState] = {}
    _timeout_seconds: int = 300
    _exclusive_wait_seconds: float = DEFAULT_EXCLUSIVE_WAIT_SECONDS

    @classmethod
    def set_timeout(cls, timeout_seconds: int) -> None:
        cls._timeout_seconds = max(1, int(timeout_seconds))

    @classmethod
    def set_exclusive_wait_seconds(cls, wait_seconds: float) -> None:
        cls._exclusive_wait_seconds = max(0.0, float(wait_seconds))

    @classmethod
    def force_release_all(cls) -> None:
        cls._states = {}

    @classmethod
    def _get_state(cls, instance_name: str) -> InstanceSchedulerState:
        state = cls._states.get(instance_name)
        if state is None:
            state = InstanceSchedulerState()
            cls._states[instance_name] = state
        return state

    @classmethod
    def _serialize_active(cls, op: ActiveOperation) -> dict[str, Any]:
        return {
            "token": op.token,
            "operation": op.operation,
            "lane": op.lane,
            "started_at": op.started_at,
            "age_seconds": round(max(0.0, time.monotonic() - op.started_monotonic), 3),
        }

    @classmethod
    def _active_operations(cls, state: InstanceSchedulerState) -> list[ActiveOperation]:
        return [
            *state.metadata_active.values(),
            *state.code_read_active.values(),
            *state.exclusive_active.values(),
        ]

    @classmethod
    def _prune_expired_locked(cls, state: InstanceSchedulerState) -> bool:
        now = time.monotonic()
        released = False

        for bucket in (state.metadata_active, state.code_read_active, state.exclusive_active):
            expired_tokens = [
                token
                for token, operation in bucket.items()
                if now - operation.started_monotonic >= cls._timeout_seconds
            ]
            for token in expired_tokens:
                bucket.pop(token, None)
                released = True

        if released:
            state.last_busy_reason = "auto_release_timeout"
            state.last_busy_at = _utc_now_iso()
        return released

    @classmethod
    def _record_busy_locked(cls, state: InstanceSchedulerState, reason: str) -> None:
        state.last_busy_reason = reason
        state.last_busy_at = _utc_now_iso()

    @classmethod
    def _conflicting_active_locked(
        cls,
        state: InstanceSchedulerState,
        lane: str,
    ) -> list[ActiveOperation]:
        if lane == LANE_METADATA:
            return list(state.exclusive_active.values())
        if lane == LANE_CODE_READ:
            return list(state.exclusive_active.values()) + list(state.code_read_active.values())
        return cls._active_operations(state)

    @classmethod
    def _can_start_code_read_locked(cls, state: InstanceSchedulerState, active_limit: int) -> bool:
        return not state.exclusive_active and len(state.code_read_active) < active_limit

    @classmethod
    def _can_start_exclusive_locked(cls, state: InstanceSchedulerState) -> bool:
        return (
            not state.metadata_active
            and not state.code_read_active
            and not state.exclusive_active
            and not state.code_read_queue
        )

    @classmethod
    def _build_busy_result(
        cls,
        *,
        state: InstanceSchedulerState,
        instance_name: str,
        lane: str,
        operation_name: str,
        queue_limit: int,
        reason: str,
        waited_seconds: float = 0.0,
    ) -> dict[str, Any]:
        cls._record_busy_locked(state, reason)

        conflicts = cls._conflicting_active_locked(state, lane)
        current = min(conflicts, key=lambda item: item.started_monotonic, default=None)
        if current is None and state.code_read_queue:
            head = state.code_read_queue[0]
            current_operation = f"queued:{head.operation}"
            busy_since = head.requested_at
            elapsed_seconds = round(max(0.0, time.monotonic() - head.requested_monotonic), 3)
        elif current is None:
            current_operation = operation_name
            busy_since = state.last_busy_at or _utc_now_iso()
            elapsed_seconds = 0.0
        else:
            current_operation = current.operation
            busy_since = current.started_at
            elapsed_seconds = round(max(0.0, time.monotonic() - current.started_monotonic), 3)

        return {
            "error": ErrorCode.INSTANCE_BUSY,
            "message": f"Instance '{instance_name}' is busy with {current_operation}",
            "instance": instance_name,
            "lane": lane,
            "current_operation": current_operation,
            "busy_since": busy_since,
            "elapsed_seconds": elapsed_seconds,
            "timeout_seconds": cls._timeout_seconds,
            "queue_depth": len(state.code_read_queue),
            "queue_limit": queue_limit,
            "active_limit": DEFAULT_CODE_READ_ACTIVE_LIMIT if lane == LANE_CODE_READ else 1,
            "busy_reason": reason,
            "waited_seconds": round(max(0.0, waited_seconds), 3),
        }

    @classmethod
    def _resolve_instance_name(
        cls,
        requested_instance: str | None,
        username: str | None = None,
        is_admin: bool = False,
    ) -> str | None:
        try:
            from .instance_registry import InstanceRegistry
        except ImportError:
            return requested_instance or DEFAULT_INSTANCE_TRACKING_KEY

        if requested_instance:
            instance = InstanceRegistry.get_instance(requested_instance)
            if instance is None:
                instance = InstanceRegistry.find_instance_by_apk(
                    requested_instance,
                    username=username,
                    is_admin=is_admin,
                )
            return instance.name if instance else requested_instance

        default_instance = (
            InstanceRegistry.get_default_for_user(username, is_admin)
            if username is not None
            else InstanceRegistry.get_default()
        )
        if default_instance:
            return default_instance.name

        return DEFAULT_INSTANCE_TRACKING_KEY

    @classmethod
    async def try_acquire(
        cls,
        instance_name: str,
        operation_name: str,
        kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = cls._get_state(instance_name)
        policy = get_operation_policy(operation_name, kwargs)
        token = uuid.uuid4().hex

        async with state.condition:
            if cls._prune_expired_locked(state):
                state.condition.notify_all()

            if policy.lane == LANE_METADATA:
                while state.exclusive_active:
                    try:
                        await asyncio.wait_for(state.condition.wait(), timeout=1.0)
                    except TimeoutError:
                        pass
                    if cls._prune_expired_locked(state):
                        state.condition.notify_all()
                state.metadata_active[token] = ActiveOperation(
                    token=token,
                    operation=operation_name,
                    lane=policy.lane,
                    started_monotonic=time.monotonic(),
                    started_at=_utc_now_iso(),
                )
                return {
                    "success": True,
                    "token": token,
                    "lane": policy.lane,
                    "queue_depth": len(state.code_read_queue),
                    "queue_limit": policy.queue_limit,
                    "active_limit": policy.active_limit,
                }

            if policy.lane == LANE_CODE_READ:
                if cls._can_start_code_read_locked(state, policy.active_limit):
                    state.code_read_active[token] = ActiveOperation(
                        token=token,
                        operation=operation_name,
                        lane=policy.lane,
                        started_monotonic=time.monotonic(),
                        started_at=_utc_now_iso(),
                    )
                    return {
                        "success": True,
                        "token": token,
                        "lane": policy.lane,
                        "queue_depth": len(state.code_read_queue),
                        "queue_limit": policy.queue_limit,
                        "active_limit": policy.active_limit,
                    }

                if len(state.code_read_queue) >= policy.queue_limit:
                    return cls._build_busy_result(
                        state=state,
                        instance_name=instance_name,
                        lane=policy.lane,
                        operation_name=operation_name,
                        queue_limit=policy.queue_limit,
                        reason="code_read_queue_full",
                    )

                queued = QueuedOperation(
                    token=token,
                    operation=operation_name,
                    requested_monotonic=time.monotonic(),
                    requested_at=_utc_now_iso(),
                )
                state.code_read_queue.append(queued)

                try:
                    while True:
                        if cls._prune_expired_locked(state):
                            state.condition.notify_all()

                        is_head = bool(state.code_read_queue) and state.code_read_queue[0].token == token
                        if is_head and cls._can_start_code_read_locked(state, policy.active_limit):
                            state.code_read_queue.popleft()
                            state.code_read_active[token] = ActiveOperation(
                                token=token,
                                operation=operation_name,
                                lane=policy.lane,
                                started_monotonic=time.monotonic(),
                                started_at=_utc_now_iso(),
                            )
                            return {
                                "success": True,
                                "token": token,
                                "lane": policy.lane,
                                "queue_depth": len(state.code_read_queue),
                                "queue_limit": policy.queue_limit,
                                "active_limit": policy.active_limit,
                            }
                        try:
                            await asyncio.wait_for(state.condition.wait(), timeout=1.0)
                        except TimeoutError:
                            pass
                except asyncio.CancelledError:
                    state.code_read_queue = deque(
                        item for item in state.code_read_queue if item.token != token
                    )
                    state.condition.notify_all()
                    raise

            exclusive_wait_started = time.monotonic()
            while True:
                if cls._can_start_exclusive_locked(state):
                    state.exclusive_active[token] = ActiveOperation(
                        token=token,
                        operation=operation_name,
                        lane=policy.lane,
                        started_monotonic=time.monotonic(),
                        started_at=_utc_now_iso(),
                    )
                    return {
                        "success": True,
                        "token": token,
                        "lane": policy.lane,
                        "queue_depth": len(state.code_read_queue),
                        "queue_limit": policy.queue_limit,
                        "active_limit": policy.active_limit,
                    }

                waited_seconds = time.monotonic() - exclusive_wait_started
                remaining = cls._exclusive_wait_seconds - waited_seconds
                if remaining <= 0:
                    break

                try:
                    await asyncio.wait_for(state.condition.wait(), timeout=min(1.0, remaining))
                except TimeoutError:
                    pass
                if cls._prune_expired_locked(state):
                    state.condition.notify_all()

            return cls._build_busy_result(
                state=state,
                instance_name=instance_name,
                lane=policy.lane,
                operation_name=operation_name,
                queue_limit=policy.queue_limit,
                reason="exclusive_lane_blocked",
                waited_seconds=time.monotonic() - exclusive_wait_started,
            )

    @classmethod
    async def release(cls, instance_name: str, token: str | None) -> None:
        if not token:
            return

        state = cls._states.get(instance_name)
        if state is None:
            return

        async with state.condition:
            removed = False
            for bucket in (state.metadata_active, state.code_read_active, state.exclusive_active):
                if token in bucket:
                    bucket.pop(token, None)
                    removed = True

            if removed:
                # notify_all: condition is shared across lanes (metadata/code_read/exclusive),
                # notify(1) could wake a wrong-lane waiter causing up to 1s delay
                state.condition.notify_all()

    @classmethod
    def get_snapshot(cls, instance_name: str | None = None) -> dict[str, Any]:
        def serialize_state(state: InstanceSchedulerState) -> dict[str, Any]:
            metadata_active = [cls._serialize_active(op) for op in state.metadata_active.values()]
            code_read_active = [cls._serialize_active(op) for op in state.code_read_active.values()]
            exclusive_active = [cls._serialize_active(op) for op in state.exclusive_active.values()]
            queue_entries = [
                {
                    "token": item.token,
                    "operation": item.operation,
                    "requested_at": item.requested_at,
                    "age_seconds": round(max(0.0, time.monotonic() - item.requested_monotonic), 3),
                }
                for item in list(state.code_read_queue)
            ]
            return {
                "metadata_inflight": len(metadata_active),
                "code_read_inflight": len(code_read_active),
                "exclusive_inflight": len(exclusive_active),
                "queue_depth": len(queue_entries),
                "queue_limit": DEFAULT_CODE_READ_QUEUE_LIMIT,
                "active_limit": DEFAULT_CODE_READ_ACTIVE_LIMIT,
                "active_operations": {
                    "metadata": metadata_active,
                    "code_read": code_read_active,
                    "exclusive": exclusive_active,
                },
                "queued_operations": queue_entries,
                "last_busy_reason": state.last_busy_reason or "",
                "last_busy_at": state.last_busy_at,
            }

        if instance_name is not None:
            state = cls._states.get(instance_name)
            if state is None:
                return {
                    "metadata_inflight": 0,
                    "code_read_inflight": 0,
                    "exclusive_inflight": 0,
                    "queue_depth": 0,
                    "queue_limit": DEFAULT_CODE_READ_QUEUE_LIMIT,
                    "active_limit": DEFAULT_CODE_READ_ACTIVE_LIMIT,
                    "active_operations": {"metadata": [], "code_read": [], "exclusive": []},
                    "queued_operations": [],
                    "last_busy_reason": "",
                    "last_busy_at": None,
                }
            return serialize_state(state)

        return {
            name: serialize_state(state)
            for name, state in cls._states.items()
        }


def with_busy_check(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    signature = inspect.signature(func)

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = signature.bind_partial(*args, **kwargs)
        requested_instance = bound.arguments.get("instance_id")
        username = None
        is_admin = False
        try:
            from .user_auth import UserAuthManager

            user = UserAuthManager.get_current_user()
            if user is not None:
                username = user.name
                is_admin = user.is_admin
        except ImportError:
            pass

        instance_name = InstanceBusyTracker._resolve_instance_name(
            requested_instance,
            username=username,
            is_admin=is_admin,
        )

        if instance_name is None:
            return {
                "error": ErrorCode.NO_INSTANCE,
                "message": "No JADX instance configured. Pure pull mode requires an explicit instance registration.",
            }

        acquisition = await InstanceBusyTracker.try_acquire(
            instance_name,
            func.__name__,
            kwargs=dict(bound.arguments),
        )
        if not acquisition.get("success"):
            return acquisition

        token = acquisition.get("token")
        try:
            return await func(*args, **kwargs)
        finally:
            await InstanceBusyTracker.release(instance_name, token)

    return wrapper
