"""Tests for task_tools: submit_security_scan, submit_callgraph, get_task_result."""

import pytest
from unittest.mock import MagicMock, patch


def _make_mcp_capture():
    """Return a mock mcp object with a capture_tool() decorator factory."""
    registered = {}

    class CaptureMcp:
        def tool(self):
            def decorator(func):
                registered[func.__name__] = func
                return func
            return decorator

    return CaptureMcp(), registered


def _register(registered_funcs=None):
    """Register task tools and return the captured functions dict."""
    mcp, registered = _make_mcp_capture()
    # Import lazily so monkeypatching happens before import side effects
    from server.tools import task_tools
    task_tools.register_task_tools(mcp, lambda f: f)
    if registered_funcs is not None:
        registered_funcs.update(registered)
    return registered


# ---------------------------------------------------------------------------
# submit_security_scan
# ---------------------------------------------------------------------------

class TestSubmitSecurityScan:

    @pytest.mark.asyncio
    async def test_returns_ticket_and_submitted_status(self, monkeypatch):
        """submit_security_scan returns ticket, status=submitted, retry_after_seconds."""
        from server.tools import task_tools

        monkeypatch.setattr(task_tools, "_run_security_scan", lambda *a, **kw: "dummy_coro")
        monkeypatch.setattr(task_tools.async_tasks, "submit", lambda coro: "ticket-abc-001")

        registered = _register()
        fn = registered["submit_security_scan"]
        result = await fn(scan_type="secrets")

        assert result["ticket"] == "ticket-abc-001"
        assert result["status"] == "submitted"
        assert "retry_after_seconds" in result
        assert result["retry_after_seconds"] > 0

    @pytest.mark.asyncio
    async def test_passes_scan_type_and_package(self, monkeypatch):
        """submit_security_scan passes scan_type and package to _run_security_scan."""
        from server.tools import task_tools

        call_args = {}

        def fake_run_security_scan(scan_type, package, instance_id):
            call_args.update(scan_type=scan_type, package=package, instance_id=instance_id)
            return "dummy_coro"

        monkeypatch.setattr(task_tools, "_run_security_scan", fake_run_security_scan)
        monkeypatch.setattr(task_tools.async_tasks, "submit", lambda coro: "t1")

        registered = _register()
        fn = registered["submit_security_scan"]
        await fn(scan_type="full", package="com.example", instance_id="inst1")

        assert call_args["scan_type"] == "full"
        assert call_args["package"] == "com.example"
        assert call_args["instance_id"] == "inst1"

    @pytest.mark.asyncio
    async def test_default_scan_type_is_full(self, monkeypatch):
        """submit_security_scan uses scan_type='full' as default."""
        from server.tools import task_tools

        call_args = {}

        def fake_run_security_scan(scan_type, package, instance_id):
            call_args["scan_type"] = scan_type
            return "coro"

        monkeypatch.setattr(task_tools, "_run_security_scan", fake_run_security_scan)
        monkeypatch.setattr(task_tools.async_tasks, "submit", lambda coro: "t2")

        registered = _register()
        fn = registered["submit_security_scan"]
        await fn()

        assert call_args["scan_type"] == "full"


# ---------------------------------------------------------------------------
# submit_callgraph
# ---------------------------------------------------------------------------

class TestSubmitCallgraph:

    @pytest.mark.asyncio
    async def test_returns_ticket_and_submitted_status(self, monkeypatch):
        """submit_callgraph returns ticket, status=submitted, retry_after_seconds."""
        from server.tools import task_tools

        monkeypatch.setattr(task_tools, "_export_callgraph", lambda *a, **kw: "dummy_coro")
        monkeypatch.setattr(task_tools.async_tasks, "submit", lambda coro: "ticket-cg-001")

        registered = _register()
        fn = registered["submit_callgraph"]
        result = await fn(class_name="com.Foo", method_name="bar", depth=3)

        assert result["ticket"] == "ticket-cg-001"
        assert result["status"] == "submitted"
        assert result["retry_after_seconds"] > 0

    @pytest.mark.asyncio
    async def test_passes_class_method_depth_format(self, monkeypatch):
        """submit_callgraph passes all params to _export_callgraph."""
        from server.tools import task_tools

        call_args = {}

        def fake_export_callgraph(class_name, method_name, depth, output_format, instance_id):
            call_args.update(
                class_name=class_name,
                method_name=method_name,
                depth=depth,
                output_format=output_format,
                instance_id=instance_id,
            )
            return "coro"

        monkeypatch.setattr(task_tools, "_export_callgraph", fake_export_callgraph)
        monkeypatch.setattr(task_tools.async_tasks, "submit", lambda coro: "t3")

        registered = _register()
        fn = registered["submit_callgraph"]
        await fn(class_name="com.Foo", method_name="bar", depth=4, output_format="dot", instance_id="inst2")

        assert call_args["class_name"] == "com.Foo"
        assert call_args["method_name"] == "bar"
        assert call_args["depth"] == 4
        assert call_args["output_format"] == "dot"
        assert call_args["instance_id"] == "inst2"


# ---------------------------------------------------------------------------
# get_task_result
# ---------------------------------------------------------------------------

class TestGetTaskResult:

    @pytest.mark.asyncio
    async def test_returns_running_when_task_in_progress(self, monkeypatch):
        """get_task_result returns running status when async_tasks.poll returns running."""
        from server.tools import task_tools

        monkeypatch.setattr(
            task_tools.async_tasks, "poll",
            lambda ticket: {"status": "running", "retry_after_seconds": 5, "message": "Task in progress."},
        )

        registered = _register()
        fn = registered["get_task_result"]
        result = await fn(ticket="abc-123")

        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_returns_done_with_result(self, monkeypatch):
        """get_task_result returns done and result payload when poll reports done."""
        from server.tools import task_tools

        fake_result = {"findings": [{"type": "secret", "value": "API_KEY"}]}
        monkeypatch.setattr(
            task_tools.async_tasks, "poll",
            lambda ticket: {"status": "done", "result": fake_result},
        )

        registered = _register()
        fn = registered["get_task_result"]
        result = await fn(ticket="abc-123")

        assert result["status"] == "done"
        assert result["result"] == fake_result

    @pytest.mark.asyncio
    async def test_returns_not_found_for_unknown_ticket(self, monkeypatch):
        """get_task_result returns not_found when ticket does not exist."""
        from server.tools import task_tools

        monkeypatch.setattr(
            task_tools.async_tasks, "poll",
            lambda ticket: {"status": "not_found", "message": "Ticket 'nonexistent' not found or expired"},
        )

        registered = _register()
        fn = registered["get_task_result"]
        result = await fn(ticket="nonexistent")

        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_forwards_ticket_string_to_poll(self, monkeypatch):
        """get_task_result forwards the exact ticket string to async_tasks.poll."""
        from server.tools import task_tools

        received = {}
        def fake_poll(ticket):
            received["ticket"] = ticket
            return {"status": "running", "retry_after_seconds": 5}

        monkeypatch.setattr(task_tools.async_tasks, "poll", fake_poll)

        registered = _register()
        fn = registered["get_task_result"]
        await fn(ticket="my-specific-ticket-xyz")

        assert received["ticket"] == "my-specific-ticket-xyz"
