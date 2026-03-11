import asyncio

import pytest

from src.server.busy_tracker import (
    DEFAULT_EXCLUSIVE_WAIT_SECONDS,
    DEFAULT_CODE_READ_ACTIVE_LIMIT,
    DEFAULT_CODE_READ_QUEUE_LIMIT,
    LANE_CODE_READ,
    LANE_EXCLUSIVE,
    LANE_METADATA,
    InstanceBusyTracker,
    get_operation_policy,
    should_bypass_busy_check,
)


@pytest.fixture(autouse=True)
def reset_busy_tracker_state():
    InstanceBusyTracker.force_release_all()
    InstanceBusyTracker.set_timeout(300)
    InstanceBusyTracker.set_exclusive_wait_seconds(DEFAULT_EXCLUSIVE_WAIT_SECONDS)
    yield
    InstanceBusyTracker.force_release_all()


def test_policy_mapping_for_metadata_and_search_scope():
    assert get_operation_policy("get_file_info").lane == LANE_METADATA
    assert get_operation_policy("get_class_info").lane == LANE_METADATA
    assert get_operation_policy("search_classes_by_keyword", {"search_in": "class"}).lane == LANE_METADATA
    assert get_operation_policy("search_classes_by_keyword", {"search_in": "method,field"}).lane == LANE_METADATA


def test_policy_mapping_for_code_read_and_exclusive_operations():
    assert get_operation_policy("get_class_source").lane == LANE_CODE_READ
    assert get_operation_policy("get_method_by_name").lane == LANE_CODE_READ
    assert get_operation_policy("get_class_source").active_limit == DEFAULT_CODE_READ_ACTIVE_LIMIT
    assert get_operation_policy("rename").lane == LANE_EXCLUSIVE
    assert get_operation_policy("batch_get_class_source").lane == LANE_EXCLUSIVE
    assert get_operation_policy("search_classes_by_keyword", {"search_in": "code"}).lane == LANE_EXCLUSIVE
    assert get_operation_policy("search_classes_by_keyword", {"search_in": "class/comment"}).lane == LANE_EXCLUSIVE


def test_should_bypass_busy_check_tracks_metadata_policy_only():
    assert should_bypass_busy_check("get_file_info") is True
    assert should_bypass_busy_check("search_classes_by_keyword", {"search_in": "class"}) is True
    assert should_bypass_busy_check("get_class_source") is False
    assert should_bypass_busy_check("search_classes_by_keyword", {"search_in": "code"}) is False


@pytest.mark.asyncio
async def test_metadata_requests_can_run_concurrently():
    first = await InstanceBusyTracker.try_acquire("demo", "get_file_info")
    second = await InstanceBusyTracker.try_acquire("demo", "get_class_info")

    assert first["success"] is True
    assert second["success"] is True

    snapshot = InstanceBusyTracker.get_snapshot("demo")
    assert snapshot["metadata_inflight"] == 2
    assert snapshot["code_read_inflight"] == 0
    assert snapshot["exclusive_inflight"] == 0

    await InstanceBusyTracker.release("demo", first["token"])
    await InstanceBusyTracker.release("demo", second["token"])


@pytest.mark.asyncio
async def test_two_code_read_requests_can_run_concurrently():
    first = await InstanceBusyTracker.try_acquire("demo", "get_class_source")
    second = await InstanceBusyTracker.try_acquire("demo", "get_method_by_name")

    assert first["success"] is True
    assert second["success"] is True
    snapshot = InstanceBusyTracker.get_snapshot("demo")
    assert snapshot["code_read_inflight"] == 2
    assert snapshot["active_limit"] == DEFAULT_CODE_READ_ACTIVE_LIMIT
    assert snapshot["queue_depth"] == 0

    await InstanceBusyTracker.release("demo", first["token"])
    await InstanceBusyTracker.release("demo", second["token"])


@pytest.mark.asyncio
async def test_third_code_read_request_waits_in_queue_and_acquires_after_release():
    first = await InstanceBusyTracker.try_acquire("demo", "get_class_source")
    second = await InstanceBusyTracker.try_acquire("demo", "get_method_by_name")

    queued_task = asyncio.create_task(InstanceBusyTracker.try_acquire("demo", "get_method_callees"))
    await asyncio.sleep(0)
    assert not queued_task.done()

    snapshot = InstanceBusyTracker.get_snapshot("demo")
    assert snapshot["code_read_inflight"] == 2
    assert snapshot["queue_depth"] == 1

    await InstanceBusyTracker.release("demo", first["token"])
    third = await queued_task

    assert third["success"] is True
    post_snapshot = InstanceBusyTracker.get_snapshot("demo")
    assert post_snapshot["code_read_inflight"] == 2
    assert post_snapshot["queue_depth"] == 0

    await InstanceBusyTracker.release("demo", second["token"])
    await InstanceBusyTracker.release("demo", third["token"])


@pytest.mark.asyncio
async def test_code_read_queue_has_bounded_capacity():
    first = await InstanceBusyTracker.try_acquire("demo", "get_class_source")
    second = await InstanceBusyTracker.try_acquire("demo", "get_method_by_name")
    assert first["success"] is True
    assert second["success"] is True

    queued_tasks = [
        asyncio.create_task(InstanceBusyTracker.try_acquire("demo", "get_method_by_name"))
        for _ in range(DEFAULT_CODE_READ_QUEUE_LIMIT)
    ]
    await asyncio.sleep(0)

    saturated = await InstanceBusyTracker.try_acquire("demo", "get_smali_of_class")
    assert saturated["error"] == "INSTANCE_BUSY"
    assert saturated["lane"] == LANE_CODE_READ
    assert saturated["queue_limit"] == DEFAULT_CODE_READ_QUEUE_LIMIT
    assert saturated["busy_reason"] == "code_read_queue_full"

    await InstanceBusyTracker.release("demo", first["token"])
    await InstanceBusyTracker.release("demo", second["token"])
    for task in queued_tasks:
        acquired = await task
        assert acquired["success"] is True
        await InstanceBusyTracker.release("demo", acquired["token"])


@pytest.mark.asyncio
async def test_exclusive_request_returns_busy_when_metadata_is_active():
    metadata = await InstanceBusyTracker.try_acquire("demo", "get_file_info")
    assert metadata["success"] is True

    InstanceBusyTracker.set_exclusive_wait_seconds(0.05)
    exclusive = await InstanceBusyTracker.try_acquire(
        "demo",
        "search_classes_by_keyword",
        {"search_in": "code"},
    )

    assert exclusive["error"] == "INSTANCE_BUSY"
    assert exclusive["lane"] == LANE_EXCLUSIVE
    assert exclusive["busy_reason"] == "exclusive_lane_blocked"
    assert exclusive["waited_seconds"] >= 0.05

    await InstanceBusyTracker.release("demo", metadata["token"])


@pytest.mark.asyncio
async def test_metadata_waits_behind_exclusive_and_then_acquires():
    exclusive = await InstanceBusyTracker.try_acquire(
        "demo",
        "search_classes_by_keyword",
        {"search_in": "code"},
    )
    assert exclusive["success"] is True

    metadata_task = asyncio.create_task(InstanceBusyTracker.try_acquire("demo", "get_file_info"))
    await asyncio.sleep(0)
    assert not metadata_task.done()

    await InstanceBusyTracker.release("demo", exclusive["token"])
    metadata = await metadata_task

    assert metadata["success"] is True
    snapshot = InstanceBusyTracker.get_snapshot("demo")
    assert snapshot["metadata_inflight"] == 1
    assert snapshot["exclusive_inflight"] == 0

    await InstanceBusyTracker.release("demo", metadata["token"])


@pytest.mark.asyncio
async def test_exclusive_request_waits_briefly_and_acquires_after_code_read_release():
    InstanceBusyTracker.set_exclusive_wait_seconds(0.2)

    code_read = await InstanceBusyTracker.try_acquire("demo", "get_class_source")
    assert code_read["success"] is True

    exclusive_task = asyncio.create_task(
        InstanceBusyTracker.try_acquire(
            "demo",
            "search_classes_by_keyword",
            {"search_in": "code"},
        )
    )

    await asyncio.sleep(0.05)
    await InstanceBusyTracker.release("demo", code_read["token"])
    exclusive = await exclusive_task

    assert exclusive["success"] is True
    assert exclusive["lane"] == LANE_EXCLUSIVE

    await InstanceBusyTracker.release("demo", exclusive["token"])
