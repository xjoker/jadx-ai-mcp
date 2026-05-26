"""
JADX MCP Server - Async Task Tools

Submit-then-poll wrappers for long-running operations (security scan, callgraph export).
Use submit_* to start the operation immediately; poll get_task_result(ticket) until done.
"""

from typing import Optional
from src.server.logging_config import get_logger
from src.server.tools.security_tools import _run_security_scan
from src.server.tools.analysis_surface_tools import _export_callgraph
from src.server import async_tasks

logger = get_logger("task_tools")


def register_task_tools(mcp, with_busy_check):
    """Register async task tools with the MCP server."""

    @mcp.tool()
    async def submit_security_scan(
        scan_type: str = "full",
        package: str = "",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Submit a security scan as a background task. Returns a ticket immediately.

        Args:
            scan_type: full|secrets|crypto|network|permissions.
            package: Optional package filter to narrow scope.
            instance_id: Target JADX instance name.
        Returns:
            dict: {ticket, status:"submitted", retry_after_seconds:5}
        """
        ticket = async_tasks.submit(_run_security_scan(scan_type, package, instance_id))
        logger.info(f"submit_security_scan: ticket={ticket}, scan_type={scan_type}")
        return {"ticket": ticket, "status": "submitted", "retry_after_seconds": 5}

    @mcp.tool()
    async def submit_callgraph(
        class_name: str,
        method_name: str,
        depth: int = 3,
        output_format: str = "json",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Submit a call graph export as a background task. Returns a ticket immediately.

        Args:
            class_name: Fully qualified class name (e.g. "com.example.MyClass").
            method_name: Method name to trace.
            depth: Traversal depth 1-6 (default 3).
            output_format: "json" or "dot".
            instance_id: Target JADX instance name.
        Returns:
            dict: {ticket, status:"submitted", retry_after_seconds:5}
        """
        ticket = async_tasks.submit(
            _export_callgraph(class_name, method_name, depth, output_format, instance_id)
        )
        logger.info(f"submit_callgraph: ticket={ticket}, class={class_name}, method={method_name}")
        return {"ticket": ticket, "status": "submitted", "retry_after_seconds": 5}

    @mcp.tool()
    async def get_task_result(ticket: str) -> dict:
        """Poll the result of a submitted background task.

        Args:
            ticket: Ticket string returned by submit_security_scan or submit_callgraph.
        Returns:
            dict: {status:"running"|"done"|"error"|"not_found", result?}
                  When status="running", retry after retry_after_seconds.
        """
        return async_tasks.poll(ticket)

    logger.info("Task tools registered: submit_security_scan, submit_callgraph, get_task_result")
