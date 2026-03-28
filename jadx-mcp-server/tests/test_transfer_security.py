import pytest
from starlette.testclient import TestClient

from src.server import rate_limiter, transfer_server, transfer_store
from src.server.rate_limiter import RateLimitConfig, RateLimiter
from src.server.transfer_store import (
    Operation,
    ResourceType,
    TransferStoreCapacityError,
    TransferTokenStore,
)


class AllowAllLimiter:
    def check(self, client_id: str) -> bool:
        return True

    def get_reset_time(self, client_id: str) -> int:
        return 0


def _sample_results() -> list[dict]:
    return [
        {
            "name": "com.example.A",
            "found": True,
            "content": "package com.example;\nclass A {}\n",
        }
    ]


def test_transfer_store_consume_blocks_replay():
    store = TransferTokenStore()
    token = store.create(Operation.DOWNLOAD, ResourceType.BATCH_CLASSES, timeout_seconds=60)

    consumed = store.consume(token.token_id, ResourceType.BATCH_CLASSES)

    assert consumed is not None
    assert consumed.used is True
    assert store.consume(token.token_id, ResourceType.BATCH_CLASSES) is None
    assert store.validate(token.token_id) is None


def test_transfer_store_consume_resource_mismatch_leaves_token_unused():
    store = TransferTokenStore()
    token = store.create(Operation.DOWNLOAD, ResourceType.BATCH_METHODS, timeout_seconds=60)

    assert store.consume(token.token_id, ResourceType.BATCH_CLASSES) is None

    validated = store.validate(token.token_id)
    assert validated is not None
    assert validated.used is False
    assert validated.resource_type == ResourceType.BATCH_METHODS


def test_transfer_store_create_cleans_expired_tokens_before_capacity_check(monkeypatch):
    store = TransferTokenStore(max_tokens=1)
    now = {"value": 1000.0}
    monkeypatch.setattr(transfer_store.time, "time", lambda: now["value"])

    expired = store.create(Operation.DOWNLOAD, ResourceType.BATCH_CLASSES, timeout_seconds=1)
    now["value"] = 1002.0
    fresh = store.create(Operation.DOWNLOAD, ResourceType.BATCH_CLASSES, timeout_seconds=60)

    assert fresh.token_id != expired.token_id
    assert store.get_status(expired.token_id)["exists"] is False
    assert store.get_status(fresh.token_id)["exists"] is True


def test_transfer_store_rejects_creation_when_capacity_exhausted(monkeypatch):
    store = TransferTokenStore(max_tokens=1)
    monkeypatch.setattr(transfer_store.time, "time", lambda: 1000.0)
    store.create(Operation.DOWNLOAD, ResourceType.BATCH_CLASSES, timeout_seconds=60)

    with pytest.raises(TransferStoreCapacityError):
        store.create(Operation.DOWNLOAD, ResourceType.BATCH_CLASSES, timeout_seconds=60)


def test_rate_limiter_prunes_expired_keys_and_enforces_max_keys(monkeypatch):
    limiter = RateLimiter(RateLimitConfig(max_requests=2, window_seconds=10, max_keys=2))
    now = {"value": 1000.0}
    monkeypatch.setattr(rate_limiter.time, "time", lambda: now["value"])

    assert limiter.check("client-a") is True
    assert limiter.check("client-b") is True
    assert limiter.check("client-c") is False

    now["value"] = 1015.0

    assert limiter.check("client-c") is True
    assert set(limiter.requests.keys()) == {"client-c"}


@pytest.mark.parametrize(
    ("format_type", "expected_helper"),
    [
        ("json", "_build_json_response_payload"),
        ("zip", "_build_zip_response_payload"),
    ],
)
def test_download_batch_classes_offloads_heavy_response_work(
    monkeypatch,
    format_type,
    expected_helper,
):
    store = TransferTokenStore()
    token = store.create(Operation.DOWNLOAD, ResourceType.BATCH_CLASSES, timeout_seconds=60)
    calls = []

    async def fake_fetch_batch_classes(class_names, instance_id):
        assert class_names == ["com.example.A"]
        assert instance_id is None
        return _sample_results()

    async def fake_to_thread(func, *args, **kwargs):
        calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr(transfer_server, "get_token_store", lambda: store)
    monkeypatch.setattr(transfer_server, "get_download_limiter", lambda: AllowAllLimiter())
    monkeypatch.setattr(transfer_server, "_fetch_batch_classes", fake_fetch_batch_classes)
    monkeypatch.setattr(transfer_server.asyncio, "to_thread", fake_to_thread)

    with TestClient(transfer_server.transfer_app) as client:
        response = client.get(
            "/transfer/download/batch-classes",
            params={
                "token": token.token_id,
                "classes": "com.example.A",
                "format": format_type,
                "compression": "none",
            },
        )

    assert response.status_code == 200
    assert calls == [expected_helper]
    if format_type == "json":
        assert response.json()["found"] == 1
    else:
        assert response.headers["content-type"] == "application/zip"


def test_download_batch_classes_rejects_token_replay(monkeypatch):
    store = TransferTokenStore()
    token = store.create(Operation.DOWNLOAD, ResourceType.BATCH_CLASSES, timeout_seconds=60)

    async def fake_fetch_batch_classes(class_names, instance_id):
        return _sample_results()

    monkeypatch.setattr(transfer_server, "get_token_store", lambda: store)
    monkeypatch.setattr(transfer_server, "get_download_limiter", lambda: AllowAllLimiter())
    monkeypatch.setattr(transfer_server, "_fetch_batch_classes", fake_fetch_batch_classes)

    with TestClient(transfer_server.transfer_app) as client:
        first = client.get(
            "/transfer/download/batch-classes",
            params={
                "token": token.token_id,
                "classes": "com.example.A",
                "format": "json",
                "compression": "none",
            },
        )
        second = client.get(
            "/transfer/download/batch-classes",
            params={
                "token": token.token_id,
                "classes": "com.example.A",
                "format": "json",
                "compression": "none",
            },
        )

    assert first.status_code == 200
    assert second.status_code == 401
    assert second.json() == {"error": "Invalid or expired token"}
