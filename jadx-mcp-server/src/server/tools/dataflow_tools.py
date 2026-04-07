"""
JADX MCP Server - Simplified Data-Flow Tracing Tools

This module provides MCP tools for tracing call chains forward (callees) and
backward (callers/xrefs) from a given method. It uses BFS traversal over the
existing method-callees and xrefs-to-method APIs, and labels well-known sink
and source patterns for Android security analysis.

Note: This is pattern-based analysis, not full data-flow analysis. Results
should be treated as heuristic guidance rather than precise data-flow facts.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

from collections import deque
from typing import Optional

from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("dataflow_tools")

# Maximum traversal depth allowed
_ABSOLUTE_MAX_DEPTH = 5
# Maximum children expanded per BFS level
_MAX_CHILDREN_PER_LEVEL = 10

# ---------------------------------------------------------------------------
# Sink patterns (callee direction) — method substrings to match
# ---------------------------------------------------------------------------

_SINK_PATTERNS: dict[str, list[str]] = {
    "network": [
        "URLConnection.connect", "HttpClient.execute", "OkHttpClient",
        "Retrofit", "HttpURLConnection.getOutputStream",
        "Socket.connect", "Socket.getOutputStream",
    ],
    "storage": [
        "SharedPreferences.edit", "SQLiteDatabase.insert", "SQLiteDatabase.execSQL",
        "ContentResolver.insert", "ContentResolver.update",
        "FileOutputStream.write", "FileWriter.write",
    ],
    "ipc": [
        "sendBroadcast", "startActivity", "startService",
        "bindService", "ContentResolver.query", "sendOrderedBroadcast",
    ],
    "logging": [
        "Log.d", "Log.i", "Log.e", "Log.w", "Log.v",
        "System.out.println", "System.err.println",
    ],
    "crypto": [
        "Cipher.doFinal", "Cipher.init", "MessageDigest.digest",
        "SecretKey", "Mac.doFinal", "Signature.sign",
    ],
}

# ---------------------------------------------------------------------------
# Source patterns (caller direction) — input origins
# ---------------------------------------------------------------------------

_SOURCE_PATTERNS: dict[str, list[str]] = {
    "user_input": [
        "EditText.getText", "Intent.getExtra", "Intent.getStringExtra",
        "Intent.getIntExtra", "Bundle.get", "Bundle.getString",
        "onActivityResult", "onNewIntent",
    ],
    "network_input": [
        "InputStream.read", "BufferedReader.readLine",
        "Response.body", "JsonReader", "HttpURLConnection.getInputStream",
    ],
    "storage_input": [
        "SharedPreferences.get", "SharedPreferences.getString",
        "Cursor.getString", "Cursor.getInt",
        "ContentResolver.query", "FileInputStream.read",
    ],
}


def _match_sink(method_label: str) -> tuple[bool, Optional[str]]:
    """Check whether a method label matches a known sink pattern."""
    for sink_type, patterns in _SINK_PATTERNS.items():
        for pat in patterns:
            if pat in method_label:
                return True, sink_type
    return False, None


def _match_source(method_label: str) -> tuple[bool, Optional[str]]:
    """Check whether a method label matches a known input-source pattern."""
    for src_type, patterns in _SOURCE_PATTERNS.items():
        for pat in patterns:
            if pat in method_label:
                return True, src_type
    return False, None


def _method_label(class_name: str, method_name: str) -> str:
    """Build a 'class.method' label string."""
    short_class = class_name.rsplit(".", 1)[-1] if "." in class_name else class_name
    return f"{short_class}.{method_name}"


# ---------------------------------------------------------------------------
# Forward trace (callee direction)
# ---------------------------------------------------------------------------

async def trace_data_flow(
    source_class: str,
    source_method: str,
    max_depth: int = 3,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Trace the call chain forward from a method (callee direction) using BFS,
    and flag well-known Android sink patterns along the way.

    Args:
        source_class: Fully qualified class name of the starting method
        source_method: Method name to start tracing from
        max_depth: Maximum BFS depth (1-5, default 3)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: Call tree rooted at the source, list of sinks found with their
              paths, and traversal statistics.

    MCP Tool: trace_data_flow
    Description: Trace forward call chains from a method and detect sink patterns (network, storage, IPC, logging, crypto)
    """
    max_depth = max(1, min(max_depth, _ABSOLUTE_MAX_DEPTH))
    logger.info(
        f"trace_data_flow: {source_class}#{source_method}, depth={max_depth}, instance={instance_id}"
    )

    root_label = _method_label(source_class, source_method)
    root_node: dict = {
        "method": root_label,
        "full_class": source_class,
        "depth": 0,
        "is_sink": False,
        "sink_type": None,
        "children": [],
    }

    sinks_found: list[dict] = []
    visited: set[str] = {f"{source_class}#{source_method}"}
    nodes_explored = 0
    actual_max_depth = 0

    # BFS queue entries: (parent_children_list, class_name, method_name, depth, path)
    queue: deque[tuple[list, str, str, int, list[str]]] = deque()
    queue.append((root_node["children"], source_class, source_method, 1, [root_label]))

    while queue:
        parent_children, cls, method, depth, path = queue.popleft()

        if depth > max_depth:
            continue

        # Fetch callees for (cls, method)
        try:
            result = await get_from_jadx(
                "method-callees",
                {"class_name": cls, "method_name": method},
                instance_id=instance_id,
            )
        except Exception as exc:
            logger.debug(f"method-callees failed for {cls}#{method}: {exc}")
            continue

        callees = result.get("callees", [])
        expanded = 0

        for callee in callees:
            if expanded >= _MAX_CHILDREN_PER_LEVEL:
                break

            # callee may be a string "Class.method" or a dict with class_name/method_name
            if isinstance(callee, dict):
                c_class = callee.get("class_name", "")
                c_method = callee.get("method_name", callee.get("name", ""))
            else:
                parts = str(callee).rsplit(".", 1)
                c_class = parts[0] if len(parts) == 2 else ""
                c_method = parts[-1]

            label = _method_label(c_class, c_method) if c_class else str(callee)
            visit_key = f"{c_class}#{c_method}"

            is_sink, sink_type = _match_sink(label)
            child_node: dict = {
                "method": label,
                "full_class": c_class,
                "depth": depth,
                "is_sink": is_sink,
                "sink_type": sink_type,
                "children": [],
            }
            parent_children.append(child_node)
            nodes_explored += 1
            actual_max_depth = max(actual_max_depth, depth)

            if is_sink:
                sinks_found.append({
                    "method": label,
                    "sink_type": sink_type,
                    "path": path + [label],
                })

            # Continue BFS if not visited and within depth
            if visit_key not in visited and depth < max_depth:
                visited.add(visit_key)
                if c_class:
                    queue.append((
                        child_node["children"], c_class, c_method,
                        depth + 1, path + [label],
                    ))

            expanded += 1

    return {
        "source": {"class_name": source_class, "method_name": source_method},
        "max_depth": max_depth,
        "call_tree": root_node,
        "sinks_found": sinks_found,
        "stats": {
            "nodes_explored": nodes_explored,
            "max_depth_reached": actual_max_depth,
            "sinks_count": len(sinks_found),
        },
        "limitations": (
            "This is a simplified, pattern-based call-chain analysis. "
            "It does not perform true data-flow or taint tracking. "
            "Results may include false positives and miss indirect calls."
        ),
    }


# ---------------------------------------------------------------------------
# Backward trace (caller / xrefs direction)
# ---------------------------------------------------------------------------

async def find_callers_chain(
    target_class: str,
    target_method: str,
    max_depth: int = 3,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Trace the call chain backward from a method (caller direction) using xrefs BFS,
    and flag well-known input-source patterns along the way.

    Args:
        target_class: Fully qualified class name of the target method
        target_method: Target method name
        max_depth: Maximum BFS depth (1-5, default 3)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: Caller tree rooted at the target, list of sources found with their
              paths, and traversal statistics.

    MCP Tool: find_callers_chain
    Description: Trace backward caller chains to a method and detect input-source patterns (user input, network, storage)
    """
    max_depth = max(1, min(max_depth, _ABSOLUTE_MAX_DEPTH))
    logger.info(
        f"find_callers_chain: {target_class}#{target_method}, depth={max_depth}, instance={instance_id}"
    )

    root_label = _method_label(target_class, target_method)
    root_node: dict = {
        "method": root_label,
        "full_class": target_class,
        "depth": 0,
        "is_source": False,
        "source_type": None,
        "callers": [],
    }

    sources_found: list[dict] = []
    visited: set[str] = {f"{target_class}#{target_method}"}
    nodes_explored = 0
    actual_max_depth = 0

    # BFS queue entries: (parent_callers_list, class_name, method_name, depth, path)
    queue: deque[tuple[list, str, str, int, list[str]]] = deque()
    queue.append((root_node["callers"], target_class, target_method, 1, [root_label]))

    while queue:
        parent_callers, cls, method, depth, path = queue.popleft()

        if depth > max_depth:
            continue

        # Fetch xrefs-to-method
        try:
            result = await get_from_jadx(
                "xrefs-to-method",
                {"class_name": cls, "method_name": method},
                instance_id=instance_id,
            )
        except Exception as exc:
            logger.debug(f"xrefs-to-method failed for {cls}#{method}: {exc}")
            continue

        references = result.get("references", [])
        expanded = 0

        for ref in references:
            if expanded >= _MAX_CHILDREN_PER_LEVEL:
                break

            # xref reference format: dict with class_name, method_name (or mth_name)
            if isinstance(ref, dict):
                r_class = ref.get("class_name", ref.get("cls", ""))
                r_method = ref.get("method_name", ref.get("mth_name", ref.get("name", "")))
            else:
                parts = str(ref).rsplit(".", 1)
                r_class = parts[0] if len(parts) == 2 else ""
                r_method = parts[-1]

            label = _method_label(r_class, r_method) if r_class else str(ref)
            visit_key = f"{r_class}#{r_method}"

            is_source, source_type = _match_source(label)
            caller_node: dict = {
                "method": label,
                "full_class": r_class,
                "depth": depth,
                "is_source": is_source,
                "source_type": source_type,
                "callers": [],
            }
            parent_callers.append(caller_node)
            nodes_explored += 1
            actual_max_depth = max(actual_max_depth, depth)

            if is_source:
                sources_found.append({
                    "method": label,
                    "source_type": source_type,
                    "path": list(reversed(path + [label])),  # source -> ... -> target
                })

            if visit_key not in visited and depth < max_depth:
                visited.add(visit_key)
                if r_class:
                    queue.append((
                        caller_node["callers"], r_class, r_method,
                        depth + 1, path + [label],
                    ))

            expanded += 1

    return {
        "target": {"class_name": target_class, "method_name": target_method},
        "max_depth": max_depth,
        "caller_tree": root_node,
        "sources_found": sources_found,
        "stats": {
            "nodes_explored": nodes_explored,
            "max_depth_reached": actual_max_depth,
            "sources_count": len(sources_found),
        },
        "limitations": (
            "This is a simplified, pattern-based caller-chain analysis using xrefs. "
            "It does not perform true data-flow or taint tracking. "
            "Results may include false positives and miss indirect/reflective calls."
        ),
    }


# Module-level references to avoid shadowing inside register wrapper
_trace_data_flow = trace_data_flow
_find_callers_chain = find_callers_chain


def register_dataflow_tools(mcp, with_busy_check):
    """Register data-flow tracing tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def trace_data_flow(
        source_class: str,
        source_method: str,
        max_depth: int = 3,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Trace forward call chains from a method and detect sink patterns.

        Performs BFS over method-callees and flags known Android sinks
        (network, storage, IPC, logging, crypto).

        Args:
            source_class: Fully qualified class name of the starting method
            source_method: Method name to start tracing from
            max_depth: Maximum BFS depth (1-5, default 3)
            instance_id: Optional. Target JADX instance name
        """
        return await _trace_data_flow(
            source_class=source_class,
            source_method=source_method,
            max_depth=max_depth,
            instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def find_callers_chain(
        target_class: str,
        target_method: str,
        max_depth: int = 3,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Trace backward caller chains to a method and detect input-source patterns.

        Performs BFS over xrefs-to-method and flags known Android input sources
        (user input, network input, storage input).

        Args:
            target_class: Fully qualified class name of the target method
            target_method: Target method name
            max_depth: Maximum BFS depth (1-5, default 3)
            instance_id: Optional. Target JADX instance name
        """
        return await _find_callers_chain(
            target_class=target_class,
            target_method=target_method,
            max_depth=max_depth,
            instance_id=instance_id,
        )

    logger.info("Dataflow tools registered: trace_data_flow, find_callers_chain")
