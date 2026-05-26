"""Tests for async code search tools: submit_code_search and get_code_search_result."""

import pytest

from server.tools import search_tools


def _make_fake(captured: dict, response: dict = None):
    """Create a fake get_from_jadx that records the last call."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            timeout=timeout,
            method=method,
            json_body=json_body,
        )
        return response if response is not None else {"ticket": "t-001", "status": "submitted"}
    return fake


# ---------------------------------------------------------------------------
# submit_code_search
# ---------------------------------------------------------------------------

class TestSubmitCodeSearch:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint_with_post(self, monkeypatch):
        """submit_code_search must hit submit-code-search via POST."""
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake(captured))

        result = await search_tools.submit_code_search("Activity")

        assert captured["endpoint"] == "submit-code-search"
        assert captured["method"] == "POST"
        assert result["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_search_term_in_params(self, monkeypatch):
        """search_term must be passed as a query param (not json_body)."""
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake(captured))

        await search_tools.submit_code_search("Activity")

        assert captured["params"]["search_term"] == "Activity"
        assert captured["json_body"] is None

    @pytest.mark.asyncio
    async def test_search_in_param_forwarded(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake(captured))

        await search_tools.submit_code_search("Foo", search_in="comment", instance_id="inst1")

        assert captured["params"]["search_in"] == "comment"
        assert captured["instance_id"] == "inst1"

    @pytest.mark.asyncio
    async def test_package_param_forwarded(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake(captured))

        await search_tools.submit_code_search("Bar", package="com.example")

        assert captured["params"]["package"] == "com.example"

    @pytest.mark.asyncio
    async def test_uses_15s_timeout(self, monkeypatch):
        """submit_code_search should set a short timeout so the ticket call is fast."""
        captured = {}
        monkeypatch.setattr(search_tools, "get_from_jadx", _make_fake(captured))

        await search_tools.submit_code_search("Test")

        assert captured["timeout"] == 15


# ---------------------------------------------------------------------------
# get_code_search_result
# ---------------------------------------------------------------------------

class TestGetCodeSearchResult:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            search_tools, "get_from_jadx",
            _make_fake(captured, {"status": "running", "retry_after_seconds": 2})
        )

        await search_tools.get_code_search_result("ticket-123")

        assert captured["endpoint"] == "code-search-status"

    @pytest.mark.asyncio
    async def test_ticket_passed_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            search_tools, "get_from_jadx",
            _make_fake(captured, {"status": "running"})
        )

        await search_tools.get_code_search_result("ticket-123")

        assert captured["params"]["ticket"] == "ticket-123"

    @pytest.mark.asyncio
    async def test_running_status_returned_as_is(self, monkeypatch):
        """When status is running, function must return response unchanged."""
        running_response = {"status": "running", "retry_after_seconds": 3}
        monkeypatch.setattr(
            search_tools, "get_from_jadx",
            _make_fake({}, running_response)
        )

        result = await search_tools.get_code_search_result("ticket-123")

        assert result["status"] == "running"
        assert result["retry_after_seconds"] == 3

    @pytest.mark.asyncio
    async def test_done_status_with_results_returned_as_is(self, monkeypatch):
        """When status is done, the full result including classes list must be returned."""
        done_response = {
            "status": "done",
            "classes": [{"class_name": "com.example.Foo", "matches": []}],
            "search_info": {"total": 1},
        }
        monkeypatch.setattr(
            search_tools, "get_from_jadx",
            _make_fake({}, done_response)
        )

        result = await search_tools.get_code_search_result("ticket-123")

        assert result["status"] == "done"
        assert len(result["classes"]) == 1
        assert result["classes"][0]["class_name"] == "com.example.Foo"

    @pytest.mark.asyncio
    async def test_not_found_status_returned_as_is(self, monkeypatch):
        """When ticket is unknown, server returns status=not_found; function passes it through."""
        not_found_response = {"status": "not_found"}
        monkeypatch.setattr(
            search_tools, "get_from_jadx",
            _make_fake({}, not_found_response)
        )

        result = await search_tools.get_code_search_result("nonexistent-ticket")

        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_pagination_params_forwarded(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            search_tools, "get_from_jadx",
            _make_fake(captured, {"status": "done", "classes": []})
        )

        await search_tools.get_code_search_result("t-abc", offset=20, count=50)

        assert captured["params"]["offset"] == 20
        assert captured["params"]["count"] == 50

    @pytest.mark.asyncio
    async def test_instance_id_forwarded(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            search_tools, "get_from_jadx",
            _make_fake(captured, {"status": "running"})
        )

        await search_tools.get_code_search_result("t-xyz", instance_id="inst7")

        assert captured["instance_id"] == "inst7"
