"""Tests for the LoadBalancer module."""

import time
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from src.server.load_balancer import (
    HISTORY_WINDOW_SIZE,
    LoadBalancer,
    get_load_balancer,
)
from src.server.instance_registry import JadxInstance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instance(
    name: str,
    status: str = "connected",
    apk_package: str = "",
    file_name: str = "",
    owner: str | None = None,
) -> JadxInstance:
    """Create a minimal JadxInstance for testing."""
    apk_info: dict = {}
    if apk_package:
        apk_info["apk_package"] = apk_package
    if file_name:
        apk_info["file_name"] = file_name
    return JadxInstance(
        name=name,
        host="127.0.0.1",
        port=8650,
        status=status,
        apk_info=apk_info,
        owner=owner,
    )


def _instances_dict(*instances: JadxInstance) -> dict[str, JadxInstance]:
    return {inst.name: inst for inst in instances}


# ---------------------------------------------------------------------------
# Round-robin
# ---------------------------------------------------------------------------


class TestRoundRobin:
    def test_cycles_through_instances(self) -> None:
        lb = LoadBalancer()
        instances = [
            _make_instance("a"),
            _make_instance("b"),
            _make_instance("c"),
        ]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            names = [
                lb.select_instance(strategy="round_robin").name  # type: ignore[union-attr]
                for _ in range(6)
            ]
        assert names == ["a", "b", "c", "a", "b", "c"]

    def test_single_instance(self) -> None:
        lb = LoadBalancer()
        instances = [_make_instance("only")]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(strategy="round_robin")
        assert result is not None
        assert result.name == "only"


# ---------------------------------------------------------------------------
# Least-busy
# ---------------------------------------------------------------------------


class TestLeastBusy:
    def test_selects_instance_with_fewest_active_requests(self) -> None:
        lb = LoadBalancer()
        lb._active_requests = {"a": 5, "b": 1, "c": 3}
        instances = [
            _make_instance("a"),
            _make_instance("b"),
            _make_instance("c"),
        ]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(strategy="least_busy")
        assert result is not None
        assert result.name == "b"

    def test_selects_first_when_all_equal(self) -> None:
        lb = LoadBalancer()
        lb._active_requests = {"a": 2, "b": 2, "c": 2}
        instances = [
            _make_instance("a"),
            _make_instance("b"),
            _make_instance("c"),
        ]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(strategy="least_busy")
        assert result is not None
        assert result.name == "a"

    def test_unknown_instance_treated_as_zero(self) -> None:
        lb = LoadBalancer()
        lb._active_requests = {"a": 3}
        instances = [_make_instance("a"), _make_instance("b")]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(strategy="least_busy")
        assert result is not None
        assert result.name == "b"


# ---------------------------------------------------------------------------
# APK affinity
# ---------------------------------------------------------------------------


class TestApkAffinity:
    def test_matches_by_package_name(self) -> None:
        lb = LoadBalancer()
        instances = [
            _make_instance("inst1", apk_package="com.example.app1"),
            _make_instance("inst2", apk_package="com.example.app2"),
        ]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(
                strategy="apk_affinity", apk_hint="app2"
            )
        assert result is not None
        assert result.name == "inst2"

    def test_matches_by_file_name(self) -> None:
        lb = LoadBalancer()
        instances = [
            _make_instance("inst1", file_name="base.apk"),
            _make_instance("inst2", file_name="target.apk"),
        ]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(
                strategy="apk_affinity", apk_hint="target"
            )
        assert result is not None
        assert result.name == "inst2"

    def test_returns_none_without_hint(self) -> None:
        lb = LoadBalancer()
        instances = [_make_instance("inst1", apk_package="com.example.app")]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(strategy="apk_affinity", apk_hint=None)
        assert result is None

    def test_returns_none_when_no_match(self) -> None:
        lb = LoadBalancer()
        instances = [_make_instance("inst1", apk_package="com.example.app")]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(
                strategy="apk_affinity", apk_hint="nonexistent"
            )
        assert result is None


# ---------------------------------------------------------------------------
# Auto strategy
# ---------------------------------------------------------------------------


class TestAutoStrategy:
    def test_prefers_affinity_when_match_exists(self) -> None:
        lb = LoadBalancer()
        instances = [
            _make_instance("inst1", apk_package="com.example.app1"),
            _make_instance("inst2", apk_package="com.example.app2"),
        ]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(strategy="auto", apk_hint="app2")
        assert result is not None
        assert result.name == "inst2"

    def test_falls_back_to_least_busy(self) -> None:
        lb = LoadBalancer()
        lb._active_requests = {"inst1": 5, "inst2": 1}
        instances = [_make_instance("inst1"), _make_instance("inst2")]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(
                strategy="auto", apk_hint="nomatch"
            )
        assert result is not None
        assert result.name == "inst2"

    def test_falls_back_to_round_robin_when_no_active(self) -> None:
        lb = LoadBalancer()
        instances = [_make_instance("inst1"), _make_instance("inst2")]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(strategy="auto")
        assert result is not None
        # First round-robin pick
        assert result.name == "inst1"

    def test_returns_none_when_no_connected(self) -> None:
        lb = LoadBalancer()
        with patch.object(lb, "_get_connected_instances", return_value=[]):
            result = lb.select_instance(strategy="auto")
        assert result is None


# ---------------------------------------------------------------------------
# Health scoring
# ---------------------------------------------------------------------------


class TestHealthScore:
    def test_connected_instance_base_score(self) -> None:
        lb = LoadBalancer()
        inst = _make_instance("healthy")
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_instance",
            return_value=inst,
        ):
            score = lb.get_instance_score("healthy")
        assert score["score"] == 100.0
        assert score["active_requests"] == 0
        assert score["avg_latency_ms"] == 0.0
        assert score["error_rate"] == 0.0

    def test_active_requests_reduce_score(self) -> None:
        lb = LoadBalancer()
        lb._active_requests["busy"] = 3
        inst = _make_instance("busy")
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_instance",
            return_value=inst,
        ):
            score = lb.get_instance_score("busy")
        assert score["score"] == 70.0  # 100 - 3*10
        assert score["active_requests"] == 3

    def test_high_latency_penalty(self) -> None:
        lb = LoadBalancer()
        # Inject history with high latency
        lb._request_history["slow"] = deque(
            [(time.time(), 6000.0, False)] * 10,
            maxlen=HISTORY_WINDOW_SIZE,
        )
        inst = _make_instance("slow")
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_instance",
            return_value=inst,
        ):
            score = lb.get_instance_score("slow")
        assert score["score"] == 80.0  # 100 - 20
        assert score["avg_latency_ms"] == 6000.0

    def test_high_error_rate_penalty(self) -> None:
        lb = LoadBalancer()
        # 50% error rate
        history = [(time.time(), 100.0, True)] * 5 + [
            (time.time(), 100.0, False)
        ] * 5
        lb._request_history["flaky"] = deque(
            history, maxlen=HISTORY_WINDOW_SIZE
        )
        inst = _make_instance("flaky")
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_instance",
            return_value=inst,
        ):
            score = lb.get_instance_score("flaky")
        assert score["score"] == 70.0  # 100 - 30
        assert score["error_rate"] == 0.5

    def test_disconnected_instance_zero_score(self) -> None:
        lb = LoadBalancer()
        inst = _make_instance("down", status="disconnected")
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_instance",
            return_value=inst,
        ):
            score = lb.get_instance_score("down")
        assert score["score"] == 0.0

    def test_unknown_instance_zero_score(self) -> None:
        lb = LoadBalancer()
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_instance",
            return_value=None,
        ):
            score = lb.get_instance_score("ghost")
        assert score["score"] == 0.0

    def test_combined_penalties(self) -> None:
        lb = LoadBalancer()
        lb._active_requests["overloaded"] = 2  # -20
        # High latency + high errors: -20 + -30
        history = [(time.time(), 7000.0, True)] * 20
        lb._request_history["overloaded"] = deque(
            history, maxlen=HISTORY_WINDOW_SIZE
        )
        inst = _make_instance("overloaded")
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_instance",
            return_value=inst,
        ):
            score = lb.get_instance_score("overloaded")
        # 100 - 20 (active) - 20 (latency) - 30 (errors) = 30
        assert score["score"] == 30.0

    def test_score_floor_is_zero(self) -> None:
        lb = LoadBalancer()
        lb._active_requests["maxed"] = 15  # -150 alone exceeds 100
        inst = _make_instance("maxed")
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_instance",
            return_value=inst,
        ):
            score = lb.get_instance_score("maxed")
        assert score["score"] == 0.0

    def test_has_apk_loaded(self) -> None:
        lb = LoadBalancer()
        inst = _make_instance("with_apk", apk_package="com.test.app")
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_instance",
            return_value=inst,
        ):
            score = lb.get_instance_score("with_apk")
        assert score["has_apk_loaded"] is True


# ---------------------------------------------------------------------------
# Track request context manager
# ---------------------------------------------------------------------------


class TestTrackRequest:
    def test_increments_and_decrements(self) -> None:
        lb = LoadBalancer()
        assert lb._active_requests.get("inst") is None
        with lb.track_request("inst"):
            assert lb._active_requests["inst"] == 1
        assert lb._active_requests["inst"] == 0

    def test_records_history_entry(self) -> None:
        lb = LoadBalancer()
        with lb.track_request("inst"):
            pass
        assert len(lb._request_history["inst"]) == 1
        ts, duration_ms, is_error = lb._request_history["inst"][0]
        assert ts > 0
        assert duration_ms >= 0
        assert is_error is False

    def test_mark_error(self) -> None:
        lb = LoadBalancer()
        with lb.track_request("inst") as tracker:
            tracker.mark_error()
        _, _, is_error = lb._request_history["inst"][0]
        assert is_error is True

    def test_decrements_on_exception(self) -> None:
        lb = LoadBalancer()
        with pytest.raises(ValueError, match="boom"):
            with lb.track_request("inst"):
                raise ValueError("boom")
        assert lb._active_requests["inst"] == 0
        assert len(lb._request_history["inst"]) == 1

    def test_concurrent_tracking(self) -> None:
        lb = LoadBalancer()
        ctx1 = lb.track_request("inst")
        ctx2 = lb.track_request("inst")
        cm1 = ctx1.__enter__()
        assert lb._active_requests["inst"] == 1
        cm2 = ctx2.__enter__()
        assert lb._active_requests["inst"] == 2
        ctx2.__exit__(None, None, None)
        assert lb._active_requests["inst"] == 1
        ctx1.__exit__(None, None, None)
        assert lb._active_requests["inst"] == 0

    def test_history_bounded_by_window_size(self) -> None:
        lb = LoadBalancer()
        for _ in range(HISTORY_WINDOW_SIZE + 20):
            with lb.track_request("inst"):
                pass
        assert len(lb._request_history["inst"]) == HISTORY_WINDOW_SIZE


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_load_balancer_returns_same_instance(self) -> None:
        with patch(
            "src.server.load_balancer._load_balancer", None
        ):
            lb1 = get_load_balancer()
            # Patch the module-level var to the one just created
            with patch(
                "src.server.load_balancer._load_balancer", lb1
            ):
                lb2 = get_load_balancer()
            assert lb1 is lb2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_invalid_strategy_falls_back_to_auto(self) -> None:
        lb = LoadBalancer()
        instances = [_make_instance("inst1")]
        with patch.object(
            lb, "_get_connected_instances", return_value=instances
        ):
            result = lb.select_instance(strategy="invalid_strategy")
        assert result is not None
        assert result.name == "inst1"

    def test_filters_disconnected_instances(self) -> None:
        """Disconnected instances should never be selected."""
        lb = LoadBalancer()
        all_insts = _instances_dict(
            _make_instance("up", status="connected"),
            _make_instance("down", status="disconnected"),
        )
        with patch(
            "src.server.load_balancer.InstanceRegistry.get_all_instances",
            return_value=all_insts,
        ):
            result = lb.select_instance(strategy="round_robin")
        assert result is not None
        assert result.name == "up"
