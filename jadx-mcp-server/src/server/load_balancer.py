"""
JADX Instance Load Balancer

Smart load balancer for multi-instance JADX routing.
Provides strategy-based instance selection with health scoring,
request tracking, and APK affinity support.
"""

import time
from collections import deque
from contextlib import contextmanager
from typing import Optional

from .instance_registry import InstanceRegistry, JadxInstance
from .logging_config import get_logger

logger = get_logger("load_balancer")

# Scoring constants
SCORE_BASE = 100
SCORE_PENALTY_PER_ACTIVE_REQUEST = 10
SCORE_PENALTY_HIGH_LATENCY = 20
SCORE_PENALTY_HIGH_ERROR_RATE = 30
LATENCY_THRESHOLD_MS = 5000.0
ERROR_RATE_THRESHOLD = 0.10
HISTORY_WINDOW_SIZE = 100


class LoadBalancer:
    """Smart load balancer for multi-instance JADX routing.

    Strategies:
    - round_robin: Simple round-robin across healthy instances
    - least_busy: Route to instance with lowest active request count
    - apk_affinity: Route to instance that has the requested APK cached
    - auto: apk_affinity > least_busy > round_robin fallback
    """

    VALID_STRATEGIES = frozenset({"round_robin", "least_busy", "apk_affinity", "auto"})

    def __init__(self) -> None:
        self._active_requests: dict[str, int] = {}
        self._request_history: dict[str, deque[tuple[float, float, bool]]] = {}
        # deque items: (timestamp, duration_ms, is_error)
        self._rr_index: int = 0

    # ------------------------------------------------------------------
    # Request tracking
    # ------------------------------------------------------------------

    @contextmanager
    def track_request(self, instance_name: str, is_error: bool = False):
        """Context manager to track an active request against an instance.

        Usage::

            with lb.track_request(inst.name) as tracker:
                result = await do_work()
                if is_bad(result):
                    tracker.mark_error()

        The ``is_error`` flag on the returned tracker defaults to False.
        Call ``tracker.mark_error()`` inside the block to record a failure.
        """
        self._active_requests[instance_name] = (
            self._active_requests.get(instance_name, 0) + 1
        )
        tracker = _RequestTracker()
        start = time.monotonic()
        try:
            yield tracker
        finally:
            self._active_requests[instance_name] = max(
                0, self._active_requests.get(instance_name, 1) - 1
            )
            duration_ms = (time.monotonic() - start) * 1000
            if instance_name not in self._request_history:
                self._request_history[instance_name] = deque(maxlen=HISTORY_WINDOW_SIZE)
            self._request_history[instance_name].append(
                (time.time(), duration_ms, tracker.error)
            )

    # ------------------------------------------------------------------
    # Instance selection
    # ------------------------------------------------------------------

    def select_instance(
        self,
        strategy: str = "auto",
        apk_hint: Optional[str] = None,
        username: Optional[str] = None,
        is_admin: bool = False,
    ) -> Optional[JadxInstance]:
        """Select a JADX instance based on the given strategy.

        Args:
            strategy: One of ``round_robin``, ``least_busy``, ``apk_affinity``,
                      or ``auto``.
            apk_hint: APK package name, file name, or partial identifier used
                      for affinity matching.
            username: Current user for ACL-filtered instance list.
            is_admin: Whether the caller has admin privileges.

        Returns:
            A connected ``JadxInstance``, or ``None`` if no healthy instance
            is available.
        """
        if strategy not in self.VALID_STRATEGIES:
            logger.warning(
                "Unknown strategy '%s', falling back to 'auto'", strategy
            )
            strategy = "auto"

        connected = self._get_connected_instances(username, is_admin)
        if not connected:
            return None

        if strategy == "round_robin":
            return self._round_robin(connected)
        if strategy == "least_busy":
            return self._least_busy(connected)
        if strategy == "apk_affinity":
            return self._apk_affinity(connected, apk_hint)
        # auto: apk_affinity -> least_busy -> round_robin
        return self._auto(connected, apk_hint)

    # ------------------------------------------------------------------
    # Health scoring
    # ------------------------------------------------------------------

    def get_instance_score(self, instance_name: str) -> dict:
        """Return a health score dict for the given instance.

        Returns:
            Dict with keys: instance_name, active_requests, avg_latency_ms,
            error_rate, has_apk_loaded, score.
        """
        instance = InstanceRegistry.get_instance(instance_name)
        if instance is None:
            return {
                "instance_name": instance_name,
                "active_requests": 0,
                "avg_latency_ms": 0.0,
                "error_rate": 0.0,
                "has_apk_loaded": False,
                "score": 0.0,
            }

        active = self._active_requests.get(instance_name, 0)
        avg_latency, error_rate = self._compute_stats(instance_name)
        has_apk = bool(instance.apk_info and instance.apk_info.get("apk_package"))
        score = self._compute_score(instance, active, avg_latency, error_rate)

        return {
            "instance_name": instance_name,
            "active_requests": active,
            "avg_latency_ms": round(avg_latency, 2),
            "error_rate": round(error_rate, 4),
            "has_apk_loaded": has_apk,
            "score": round(score, 2),
        }

    def get_all_scores(
        self,
        username: Optional[str] = None,
        is_admin: bool = False,
    ) -> list[dict]:
        """Return health scores for all instances visible to the user."""
        if username is not None:
            instances = InstanceRegistry.list_instances_for_user(username, is_admin)
        else:
            instances = InstanceRegistry.list_instances()
        return [self.get_instance_score(inst["name"]) for inst in instances]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_connected_instances(
        self,
        username: Optional[str] = None,
        is_admin: bool = False,
    ) -> list[JadxInstance]:
        """Return connected instances visible to the caller."""
        all_instances = InstanceRegistry.get_all_instances()
        results: list[JadxInstance] = []
        for inst in all_instances.values():
            if inst.status != "connected":
                continue
            if username is not None and not is_admin:
                if inst.owner is not None and inst.owner != username:
                    continue
            results.append(inst)
        return results

    def _round_robin(self, instances: list[JadxInstance]) -> JadxInstance:
        idx = self._rr_index % len(instances)
        self._rr_index += 1
        return instances[idx]

    def _least_busy(self, instances: list[JadxInstance]) -> JadxInstance:
        return min(
            instances,
            key=lambda inst: self._active_requests.get(inst.name, 0),
        )

    def _apk_affinity(
        self,
        instances: list[JadxInstance],
        apk_hint: Optional[str],
    ) -> Optional[JadxInstance]:
        """Find an instance whose loaded APK matches the hint."""
        if not apk_hint:
            return None
        hint_lower = apk_hint.lower()
        for inst in instances:
            apk_info = inst.apk_info or {}
            pkg = apk_info.get("apk_package", "")
            fname = apk_info.get("file_name", "")
            inst_name_jadx = apk_info.get("instance_name", "")
            if any(
                hint_lower in val.lower()
                for val in (pkg, fname, inst_name_jadx, inst.name)
                if val
            ):
                return inst
        return None

    def _auto(
        self,
        instances: list[JadxInstance],
        apk_hint: Optional[str],
    ) -> JadxInstance:
        """Auto strategy: apk_affinity -> least_busy -> round_robin."""
        if apk_hint:
            affinity = self._apk_affinity(instances, apk_hint)
            if affinity is not None:
                return affinity
        # Prefer least_busy when there are active requests tracked
        if any(self._active_requests.get(inst.name, 0) > 0 for inst in instances):
            return self._least_busy(instances)
        return self._round_robin(instances)

    def _compute_stats(self, instance_name: str) -> tuple[float, float]:
        """Compute average latency (ms) and error rate from recent history."""
        history = self._request_history.get(instance_name)
        if not history:
            return 0.0, 0.0
        total_latency = 0.0
        error_count = 0
        count = len(history)
        for _, duration_ms, is_error in history:
            total_latency += duration_ms
            if is_error:
                error_count += 1
        avg_latency = total_latency / count if count else 0.0
        error_rate = error_count / count if count else 0.0
        return avg_latency, error_rate

    def _compute_score(
        self,
        instance: JadxInstance,
        active_requests: int,
        avg_latency: float,
        error_rate: float,
    ) -> float:
        """Compute a 0-100 health score for an instance."""
        if instance.status != "connected":
            return 0.0
        score = float(SCORE_BASE)
        score -= active_requests * SCORE_PENALTY_PER_ACTIVE_REQUEST
        if avg_latency > LATENCY_THRESHOLD_MS:
            score -= SCORE_PENALTY_HIGH_LATENCY
        if error_rate > ERROR_RATE_THRESHOLD:
            score -= SCORE_PENALTY_HIGH_ERROR_RATE
        return max(0.0, score)


class _RequestTracker:
    """Mutable flag holder yielded by ``LoadBalancer.track_request``."""

    __slots__ = ("error",)

    def __init__(self) -> None:
        self.error: bool = False

    def mark_error(self) -> None:
        self.error = True


# ------------------------------------------------------------------
# Singleton access
# ------------------------------------------------------------------

_load_balancer: Optional[LoadBalancer] = None


def get_load_balancer() -> LoadBalancer:
    """Return the global LoadBalancer singleton (created on first call)."""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = LoadBalancer()
    return _load_balancer


# ------------------------------------------------------------------
# MCP tool registration
# ------------------------------------------------------------------


def register_loadbalancer_tools(mcp) -> None:  # type: ignore[no-untyped-def]
    """Register load-balancer information tools on the MCP server."""

    @mcp.tool()
    async def get_load_balance_status(
        username: Optional[str] = None,
        is_admin: bool = False,
    ) -> dict:
        """Get current load balancing status across all JADX instances.

        Shows active requests, average latency, and health scores for each
        instance. Useful for understanding instance utilization and debugging
        routing decisions.
        """
        lb = get_load_balancer()
        scores = lb.get_all_scores(username=username, is_admin=is_admin)
        return {
            "strategy": "auto",
            "instances": scores,
            "total_instances": len(scores),
            "healthy_instances": sum(1 for s in scores if s["score"] > 0),
        }
