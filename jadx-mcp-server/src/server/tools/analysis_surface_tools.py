"""
JADX MCP Server - Attack Surface & Call Graph Analysis Tools

This module provides MCP tools for Android attack surface analysis and method
call graph export. It helps security researchers identify exported components,
deep-link entry points, dangerous permissions, and trace method call chains.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

from typing import Optional
from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx
from src.server.types import format_error_response

logger = get_logger("analysis_surface_tools")

# Maximum depth allowed client-side for callgraph to avoid server overload
_MAX_CALLGRAPH_DEPTH = 6


async def get_attack_surface(instance_id: Optional[str] = None) -> dict:
    """
    Fetch the attack surface analysis from the JADX instance.

    Returns exported components, deep-link intent filters, custom and dangerous
    permissions, and a summary count for quick assessment.

    Args:
        instance_id: Optional target JADX instance name.

    Returns:
        dict: Full attack surface data plus an LLM-friendly summary string.
    """
    result = await get_from_jadx("attack-surface", instance_id=instance_id)
    if isinstance(result, dict) and "error" not in result:
        # Build a quick summary string for LLM consumption
        total_exported = result.get("total_exported", 0)
        deeplinks = result.get("deeplink_summary", [])
        deeplink_count = len(deeplinks) if isinstance(deeplinks, list) else 0
        dangerous_perms = result.get("dangerous_permissions_used", [])
        dangerous_count = len(dangerous_perms) if isinstance(dangerous_perms, list) else 0
        custom_perms = result.get("custom_permissions", [])
        custom_count = len(custom_perms) if isinstance(custom_perms, list) else 0

        result["summary"] = (
            f"{total_exported} exported components found, "
            f"{deeplink_count} deeplink(s), "
            f"{dangerous_count} dangerous permission(s) used, "
            f"{custom_count} custom permission(s) declared."
        )
    return result


async def export_callgraph(
    class_name: str,
    method_name: str,
    depth: int = 3,
    output_format: str = "json",
    instance_id: Optional[str] = None,
) -> dict:
    """
    Export the call graph for a specific method.

    Traces all callers and callees up to the requested depth. Use format='dot'
    to get a DOT-language string that can be pasted directly into Graphviz or
    rendered with Mermaid for visual exploration.

    Args:
        class_name: Fully qualified class name (e.g. "com.example.MyClass").
        method_name: Method name (e.g. "handleIntent").
        depth: Call graph traversal depth (1-6). Capped at 6 to prevent
               extremely large graphs that degrade JADX performance.
        output_format: "json" (structured nodes+edges) or "dot" (Graphviz DOT string).
        instance_id: Optional target JADX instance name.

    Returns:
        dict: When format=json — {format, root, depth, nodes, edges, truncated}.
              When format=dot  — {format, dot: "digraph {...}"}.
    """
    # Clamp depth to safe range
    effective_depth = max(1, min(depth, _MAX_CALLGRAPH_DEPTH))

    params: dict = {
        "class": class_name,
        "method": method_name,
        "depth": str(effective_depth),
        "format": output_format,
    }

    result = await get_from_jadx("export-callgraph", params, instance_id=instance_id)
    return result


# Module-level references to avoid name shadowing inside register function
_get_attack_surface = get_attack_surface
_export_callgraph = export_callgraph


def register_analysis_surface_tools(mcp, with_busy_check):
    """Register attack surface and call graph tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def get_attack_surface(instance_id: Optional[str] = None) -> dict:
        """Analyze the Android attack surface: exported components, deep-links, and dangerous permissions.

        Calls the /attack-surface endpoint which enumerates every exported Activity,
        Service, BroadcastReceiver, and ContentProvider, cross-references intent-filter
        deep-link schemes, and lists dangerous/custom permissions used by the APK.

        This is the recommended first tool to call when doing security-focused analysis.
        No warmup required — results are derived from the manifest and metadata.

        Args:
            instance_id: Target JADX instance name.
        Returns:
            dict: {
                activities: list of exported activity names,
                services: list of exported service names,
                receivers: list of exported receiver names,
                providers: list of exported provider names,
                custom_permissions: list of custom permission names declared by the app,
                dangerous_permissions_used: list of android.permission.* dangerous permissions,
                deeplink_summary: list of {scheme, host, path} intent-filter deep-links,
                total_exported: int total count of all exported components,
                summary: human-readable one-line summary string
            }
        """
        return await _get_attack_surface(instance_id=instance_id)

    @mcp.tool()
    @with_busy_check
    async def export_callgraph(
        class_name: str,
        method_name: str,
        depth: int = 3,
        format: str = "json",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Export the call graph for a method as structured JSON or Graphviz DOT.

        Traces the full caller/callee graph starting from the given method up to the
        specified depth. Use format='dot' to get a DOT-language string that can be
        pasted into Graphviz (dot -Tpng) or Mermaid for visual diagrams.

        Depth is capped at 6 client-side to avoid producing graphs too large to process.
        For deep call chains, start with depth=2 and increase incrementally.

        Args:
            class_name: Fully qualified class name (e.g. "com.example.LoginActivity").
            method_name: Method name to root the graph at (e.g. "onCreate").
            depth: Traversal depth 1-6 (default 3). Values above 6 are clamped to 6.
            format: Output format — "json" (default, nodes+edges dict) or
                    "dot" (Graphviz DOT language string, paste to visualizer).
            instance_id: Target JADX instance name.
        Returns:
            When format=json: {format, root, depth, nodes:[{id,class,method,signature}],
                               edges:[{from,to}], truncated}
            When format=dot:  {format, dot:"digraph { ... }"}
        """
        if not class_name or not class_name.strip():
            return format_error_response(
                "INVALID_INPUT",
                "class_name is required and cannot be empty",
                {"hint": "Provide a fully qualified class name, e.g. 'com.example.MyClass'"},
            )
        if not method_name or not method_name.strip():
            return format_error_response(
                "INVALID_INPUT",
                "method_name is required and cannot be empty",
                {"hint": "Provide the method name, e.g. 'onCreate' or 'handleRequest'"},
            )
        if format not in ("json", "dot"):
            return format_error_response(
                "INVALID_INPUT",
                f"Invalid format: '{format}'. Must be 'json' or 'dot'.",
                {"valid_values": ["json", "dot"]},
            )

        return await _export_callgraph(
            class_name=class_name,
            method_name=method_name,
            depth=depth,
            output_format=format,
            instance_id=instance_id,
        )

    logger.info(
        "Analysis surface tools registered: get_attack_surface, export_callgraph"
    )
