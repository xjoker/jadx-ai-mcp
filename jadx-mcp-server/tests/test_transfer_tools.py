"""Tests for transfer_tools: create_transfer_token, get_transfer_token_status, revoke_transfer_token."""

import time
import pytest
from unittest.mock import MagicMock, patch

from server.tools import transfer_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_token(token_id="tok_abc123", resource_type_value="batch_classes", expires_in=120):
    """Build a minimal mock TransferToken-like object."""
    token = MagicMock()
    token.token_id = token_id
    token.expires_at = time.time() + expires_in
    return token


def _make_mock_store(token=None, status=None, revoked=True):
    """Build a mock TransferTokenStore."""
    store = MagicMock()
    store.create.return_value = token or _make_mock_token()
    store.get_status.return_value = status or {
        "exists": True,
        "used": False,
        "expires_in": 100,
        "resource_type": "batch_classes",
        "operation": "download",
    }
    store.revoke.return_value = revoked
    return store


def _make_passing_rate_limiter():
    """Return a mock rate limiter that always allows requests."""
    limiter = MagicMock()
    limiter.check.return_value = True
    return limiter


# ---------------------------------------------------------------------------
# create_transfer_token
# ---------------------------------------------------------------------------

class TestCreateTransferToken:

    @pytest.mark.asyncio
    async def test_returns_success_and_token(self, monkeypatch):
        """create_transfer_token returns success=True and a token string."""
        store = _make_mock_store()
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: store)
        monkeypatch.setattr(transfer_tools, "get_token_limiter", lambda: _make_passing_rate_limiter())
        monkeypatch.setattr(transfer_tools, "get_mcp_server_url", lambda: "http://localhost:8765")

        result = await transfer_tools.create_transfer_token()

        assert result["success"] is True
        assert "token" in result
        assert "transfer_url" in result
        assert "expires_in" in result

    @pytest.mark.asyncio
    async def test_returns_invalid_input_for_bad_operation(self, monkeypatch):
        """create_transfer_token returns INVALID_INPUT error for unknown operation."""
        monkeypatch.setattr(transfer_tools, "get_token_limiter", lambda: _make_passing_rate_limiter())
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: _make_mock_store())
        monkeypatch.setattr(transfer_tools, "get_mcp_server_url", lambda: "http://localhost:8765")

        result = await transfer_tools.create_transfer_token(operation="upload_invalid_op")

        assert result.get("error") == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_returns_invalid_input_for_bad_resource_type(self, monkeypatch):
        """create_transfer_token returns INVALID_INPUT error for unknown resource_type."""
        monkeypatch.setattr(transfer_tools, "get_token_limiter", lambda: _make_passing_rate_limiter())
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: _make_mock_store())
        monkeypatch.setattr(transfer_tools, "get_mcp_server_url", lambda: "http://localhost:8765")

        result = await transfer_tools.create_transfer_token(resource_type="not_a_valid_type")

        assert result.get("error") == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_returns_rate_limited_when_limiter_rejects(self, monkeypatch):
        """create_transfer_token returns RATE_LIMITED when the limiter denies the request."""
        limiter = MagicMock()
        limiter.check.return_value = False
        limiter.get_reset_time.return_value = 30

        monkeypatch.setattr(transfer_tools, "get_token_limiter", lambda: limiter)
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: _make_mock_store())
        monkeypatch.setattr(transfer_tools, "get_mcp_server_url", lambda: "http://localhost:8765")

        result = await transfer_tools.create_transfer_token()

        assert result.get("error") == "RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_transfer_url_contains_base_url(self, monkeypatch):
        """create_transfer_token embeds the configured server URL in transfer_url."""
        store = _make_mock_store()
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: store)
        monkeypatch.setattr(transfer_tools, "get_token_limiter", lambda: _make_passing_rate_limiter())
        monkeypatch.setattr(transfer_tools, "get_mcp_server_url", lambda: "http://myserver:9999")

        result = await transfer_tools.create_transfer_token()

        assert "myserver:9999" in result["transfer_url"]

    @pytest.mark.asyncio
    async def test_returns_rate_limited_when_store_capacity_exceeded(self, monkeypatch):
        """create_transfer_token returns RATE_LIMITED when token store is at capacity."""
        from server.transfer_store import TransferStoreCapacityError

        store = MagicMock()
        store.create.side_effect = TransferStoreCapacityError("Too many tokens")

        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: store)
        monkeypatch.setattr(transfer_tools, "get_token_limiter", lambda: _make_passing_rate_limiter())
        monkeypatch.setattr(transfer_tools, "get_mcp_server_url", lambda: "http://localhost:8765")

        result = await transfer_tools.create_transfer_token()

        assert result.get("error") == "RATE_LIMITED"


# ---------------------------------------------------------------------------
# get_transfer_token_status
# ---------------------------------------------------------------------------

class TestGetTransferTokenStatus:

    @pytest.mark.asyncio
    async def test_returns_status_for_existing_token(self, monkeypatch):
        """get_transfer_token_status returns exists=True for a known token."""
        status = {
            "exists": True,
            "used": False,
            "expires_in": 90,
            "resource_type": "batch_classes",
            "operation": "download",
        }
        store = _make_mock_store(status=status)
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: store)

        result = await transfer_tools.get_transfer_token_status("tok_abc123")

        assert result["success"] is True
        assert result["exists"] is True
        assert result["expires_in"] == 90

    @pytest.mark.asyncio
    async def test_returns_exists_false_for_unknown_token(self, monkeypatch):
        """get_transfer_token_status returns exists=False for an unknown token."""
        status = {"exists": False, "used": False, "expires_in": 0}
        store = _make_mock_store(status=status)
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: store)

        result = await transfer_tools.get_transfer_token_status("tok_not_found")

        assert result["exists"] is False

    @pytest.mark.asyncio
    async def test_forwards_token_to_store(self, monkeypatch):
        """get_transfer_token_status passes the token string to store.get_status."""
        store = _make_mock_store(status={"exists": False, "used": False, "expires_in": 0})
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: store)

        await transfer_tools.get_transfer_token_status("specific_token_id")

        store.get_status.assert_called_once_with("specific_token_id")


# ---------------------------------------------------------------------------
# revoke_transfer_token
# ---------------------------------------------------------------------------

class TestRevokeTransferToken:

    @pytest.mark.asyncio
    async def test_returns_success_when_token_revoked(self, monkeypatch):
        """revoke_transfer_token returns success=True when store.revoke returns True."""
        store = _make_mock_store(revoked=True)
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: store)

        result = await transfer_tools.revoke_transfer_token("tok_to_revoke")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_returns_success_false_when_token_not_found(self, monkeypatch):
        """revoke_transfer_token returns success=False when the token does not exist."""
        store = _make_mock_store(revoked=False)
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: store)

        result = await transfer_tools.revoke_transfer_token("tok_nonexistent")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_forwards_token_to_store_revoke(self, monkeypatch):
        """revoke_transfer_token passes the exact token string to store.revoke."""
        store = _make_mock_store(revoked=True)
        monkeypatch.setattr(transfer_tools, "get_token_store", lambda: store)

        await transfer_tools.revoke_transfer_token("exact_token_string")

        store.revoke.assert_called_once_with("exact_token_string")
