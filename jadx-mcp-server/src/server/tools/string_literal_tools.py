"""
JADX MCP Server - DEX String Literal Search Tools

This module provides MCP tools for searching string constants embedded directly
in DEX bytecode. Unlike get_strings (which reads strings.xml resources), this
tool scans compiled class fields and method bodies for Java/Kotlin string literals
such as hardcoded URLs, API keys, SQL queries, encryption keys, and debug tokens.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

from typing import Optional
from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx
from src.server.types import format_error_response

logger = get_logger("string_literal_tools")


async def search_string_literals(
    pattern: str,
    regex: bool = False,
    min_length: int = 8,
    class_filter: str = "",
    limit: int = 100,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Search for string constants in DEX bytecode across all decompiled classes.

    This searches Java/Kotlin string literals compiled into the DEX — not
    Android resource strings (strings.xml). Useful for finding hardcoded
    credentials, API endpoints, SQL queries, and encryption material.

    No cache warmup is required; the scan uses JADX's metadata index.

    Args:
        pattern: Search string or regex pattern.
        regex: When True, treat pattern as a regular expression.
        min_length: Minimum string length to include (filters trivial constants).
        class_filter: Limit search to classes whose fully-qualified name starts
                      with this prefix (e.g. "com.example.app").
        limit: Maximum number of results to return (default 100).
        instance_id: Optional target JADX instance name.

    Returns:
        dict: {results: [{class_name, literal, line_number}], total, truncated,
               scanned_classes, cached_percentage_at_scan}
    """
    params: dict = {
        "pattern": pattern,
        "regex": str(regex).lower(),
        "min_length": str(min_length),
        "limit": str(limit),
    }
    if class_filter:
        params["class"] = class_filter

    return await get_from_jadx("search-string-literals", params, instance_id=instance_id)


# Module-level reference to avoid name shadowing inside register function
_search_string_literals = search_string_literals


def register_string_literal_tools(mcp, with_busy_check):
    """Register DEX string literal search tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def search_string_literals(
        pattern: str,
        regex: bool = False,
        min_length: int = 8,
        class_filter: str = "",
        limit: int = 100,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Search for string constants (URL, API key, SQL, etc.) embedded in DEX bytecode.

        This tool scans Java/Kotlin string literals that are compiled directly into the
        DEX — NOT Android resource strings from strings.xml (use get_strings for those).

        Typical use cases:
        - Find hardcoded API endpoints:       pattern="https://api.", regex=False
        - Find potential API keys/secrets:    pattern="[A-Za-z0-9]{32,}", regex=True
        - Find SQL queries:                   pattern="SELECT ", regex=False
        - Find Base64 secrets:                pattern="[A-Za-z0-9+/]{40,}={0,2}", regex=True

        No cache warmup required — results are available immediately. Narrow the
        search with class_filter to reduce scan time on large APKs.

        Args:
            pattern: String to search for, or a regex pattern when regex=True.
            regex: When True, treat pattern as a Java regular expression (default False).
            min_length: Skip string literals shorter than this (default 8). Raise to
                        filter trivial constants like "OK", "null", single chars.
            class_filter: Restrict to classes whose fully-qualified name starts with
                          this prefix (e.g. "com.example.app" to skip third-party libs).
                          Leave empty to scan all classes.
            limit: Maximum results to return (default 100, max 200 server-side).
            instance_id: Target JADX instance name.
        Returns:
            dict: {
                results: [{class_name: str, literal: str, line_number: int}],
                total: int,
                truncated: bool,
                scanned_classes: int,
                cached_percentage_at_scan: float
            }
        """
        if not pattern or not pattern.strip():
            return format_error_response(
                "INVALID_INPUT",
                "pattern is required and cannot be empty",
                {"hint": "Provide a search string or regex pattern to match string literals"},
            )
        if min_length < 0:
            return format_error_response(
                "INVALID_INPUT",
                "min_length must be non-negative",
                {"hint": "Use 0 to include all strings, or 8 (default) to skip trivial constants"},
            )
        if limit < 1:
            return format_error_response(
                "INVALID_INPUT",
                "limit must be at least 1",
                {"hint": "Use limit=100 (default) or up to 200"},
            )

        return await _search_string_literals(
            pattern=pattern,
            regex=regex,
            min_length=min_length,
            class_filter=class_filter,
            limit=limit,
            instance_id=instance_id,
        )

    logger.info("String literal tools registered: search_string_literals")
