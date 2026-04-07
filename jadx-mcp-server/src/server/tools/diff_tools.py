"""
JADX MCP Server - Cross-Version Diff Tools

This module provides MCP tools for comparing two JADX instances that have loaded
different versions of the same APK/JAR. It identifies added, removed, and modified
classes and methods, and optionally produces unified diffs of method source code.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

import difflib
from typing import Optional

from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("diff_tools")

# Limits to prevent excessive API calls and response size
_MAX_CLASSES_REPORTED = 50
_MAX_MODIFIED_CLASSES_REPORTED = 30
_MAX_CLASSES_FOR_METHOD_DIFF = 200
_MAX_CODE_DIFFS = 20
_CLASS_FETCH_LIMIT = 5000


async def _fetch_file_info(instance_id: str) -> dict:
    """Fetch file-info from a JADX instance, returning error dict on failure."""
    try:
        return await get_from_jadx("file-info", instance_id=instance_id)
    except Exception as exc:
        return {"error": f"Failed to reach instance '{instance_id}': {exc}"}


async def _fetch_all_classes(instance_id: str, package: str) -> tuple[list[str], bool]:
    """Fetch class list from a JADX instance.

    Returns:
        A tuple of (class_name_list, was_truncated).
    """
    params: dict = {"offset": 0, "count": _CLASS_FETCH_LIMIT}
    if package:
        params["package"] = package

    result = await get_from_jadx("all-classes", params, instance_id=instance_id)
    classes = result.get("classes", [])
    total = result.get("total", len(classes))
    truncated = total > _CLASS_FETCH_LIMIT
    return classes, truncated


async def _fetch_methods(instance_id: str, class_name: str) -> list[str]:
    """Fetch method names for a class from a JADX instance."""
    result = await get_from_jadx(
        "methods-of-class", {"class_name": class_name}, instance_id=instance_id
    )
    methods = result.get("methods", [])
    # Extract method name strings; the API may return dicts or plain strings
    names: list[str] = []
    for m in methods:
        if isinstance(m, dict):
            names.append(m.get("name", str(m)))
        else:
            names.append(str(m))
    return names


async def _fetch_method_source(instance_id: str, class_name: str, method_name: str) -> str:
    """Fetch decompiled source of a single method. Returns empty string on error."""
    try:
        result = await get_from_jadx(
            "batch-method-by-name",
            {"class_name": class_name, "method_name": method_name},
            instance_id=instance_id,
        )
        # batch-method-by-name may nest under "results" or return "code" directly
        if isinstance(result, dict):
            if "code" in result:
                return result["code"]
            results = result.get("results", [])
            if results and isinstance(results[0], dict):
                return results[0].get("code", "")
        return ""
    except Exception:
        return ""


def _unified_diff(old_src: str, new_src: str, label: str) -> str:
    """Produce a compact unified diff string."""
    old_lines = old_src.splitlines(keepends=True)
    new_lines = new_src.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"old/{label}", tofile=f"new/{label}", n=2)
    return "".join(diff)


async def compare_versions(
    old_instance_id: str,
    new_instance_id: str,
    package: str = "",
    include_code_diff: bool = False,
) -> dict:
    """
    Compare two JADX instances loading different APK versions and produce a structured diff report.

    Each instance must already be running and have an APK/JAR loaded. Use package filtering
    to avoid comparing third-party library classes.

    Args:
        old_instance_id: Instance name for the older APK version
        new_instance_id: Instance name for the newer APK version
        package: Package prefix filter (e.g. "com.example.app"). Strongly recommended
                 to avoid comparing third-party libraries.
        include_code_diff: When True, fetch method source and produce unified diffs
                          for modified methods (slow, limited to 20 diffs). Default False.

    Returns:
        dict: Structured diff report with summary, added/removed/modified classes,
              and optional code diffs. See module docstring for full schema.

    MCP Tool: compare_versions
    Description: Compare classes and methods between two JADX instances to find cross-version differences
    """
    logger.info(
        f"compare_versions: old={old_instance_id}, new={new_instance_id}, "
        f"package={package!r}, code_diff={include_code_diff}"
    )

    tips: list[str] = []

    # 1. Validate both instances are reachable
    old_info = await _fetch_file_info(old_instance_id)
    if "error" in old_info:
        return {"error": "OLD_INSTANCE_UNREACHABLE", "message": old_info["error"]}

    new_info = await _fetch_file_info(new_instance_id)
    if "error" in new_info:
        return {"error": "NEW_INSTANCE_UNREACHABLE", "message": new_info["error"]}

    # 2. Fetch class lists
    old_classes, old_truncated = await _fetch_all_classes(old_instance_id, package)
    new_classes, new_truncated = await _fetch_all_classes(new_instance_id, package)

    if old_truncated or new_truncated:
        tips.append(
            f"Class list exceeded {_CLASS_FETCH_LIMIT}. Use the 'package' parameter to narrow scope."
        )

    old_set = set(old_classes)
    new_set = set(new_classes)

    added = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)
    common = sorted(old_set & new_set)

    # 3. Method-level comparison on common classes
    modified_classes: list[dict] = []
    total_methods_added = 0
    total_methods_removed = 0
    classes_unchanged = 0
    code_diff_count = 0

    compare_limit = min(len(common), _MAX_CLASSES_FOR_METHOD_DIFF)
    if len(common) > _MAX_CLASSES_FOR_METHOD_DIFF:
        tips.append(
            f"Only the first {_MAX_CLASSES_FOR_METHOD_DIFF} of {len(common)} common classes "
            "were compared at the method level. Use a more specific package filter."
        )

    for cls in common[:compare_limit]:
        old_methods = await _fetch_methods(old_instance_id, cls)
        new_methods = await _fetch_methods(new_instance_id, cls)

        old_method_set = set(old_methods)
        new_method_set = set(new_methods)

        m_added = sorted(new_method_set - old_method_set)
        m_removed = sorted(old_method_set - new_method_set)

        if not m_added and not m_removed:
            classes_unchanged += 1
            continue

        total_methods_added += len(m_added)
        total_methods_removed += len(m_removed)

        entry: dict = {
            "class_name": cls,
            "added_methods": m_added,
            "removed_methods": m_removed,
        }

        # Optional code diffs for changed methods
        if include_code_diff and code_diff_count < _MAX_CODE_DIFFS:
            diffs: list[dict] = []
            # Only diff methods that exist in both versions (same name, potentially changed body)
            shared_methods = sorted(old_method_set & new_method_set)
            for method_name in shared_methods:
                if code_diff_count >= _MAX_CODE_DIFFS:
                    tips.append(
                        f"Code diff limit ({_MAX_CODE_DIFFS}) reached; some methods were skipped."
                    )
                    break
                old_src = await _fetch_method_source(old_instance_id, cls, method_name)
                new_src = await _fetch_method_source(new_instance_id, cls, method_name)
                if old_src and new_src and old_src != new_src:
                    diff_text = _unified_diff(old_src, new_src, f"{cls}#{method_name}")
                    if diff_text:
                        diffs.append({"method_name": method_name, "diff": diff_text})
                        code_diff_count += 1
            if diffs:
                entry["code_diffs"] = diffs

        if len(modified_classes) < _MAX_MODIFIED_CLASSES_REPORTED:
            modified_classes.append(entry)

    if len(common) > compare_limit:
        classes_unchanged += len(common) - compare_limit  # not compared, count as unchanged

    # 4. Build response
    if not package:
        tips.append(
            "No package filter was applied. Results may include third-party library changes. "
            "Set the 'package' parameter for more focused results."
        )

    return {
        "old_version": {"instance_id": old_instance_id, "file_info": old_info},
        "new_version": {"instance_id": new_instance_id, "file_info": new_info},
        "package_filter": package,
        "summary": {
            "classes_added": len(added),
            "classes_removed": len(removed),
            "classes_modified": len(modified_classes),
            "classes_unchanged": classes_unchanged,
            "methods_added": total_methods_added,
            "methods_removed": total_methods_removed,
        },
        "added_classes": added[:_MAX_CLASSES_REPORTED],
        "removed_classes": removed[:_MAX_CLASSES_REPORTED],
        "modified_classes": modified_classes,
        "analysis_tips": tips,
    }


# Module-level reference to avoid shadowing in register wrapper
_compare_versions = compare_versions


def register_diff_tools(mcp, with_busy_check):
    """Register cross-version diff tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def compare_versions(
        old_instance_id: str,
        new_instance_id: str,
        package: str = "",
        include_code_diff: bool = False,
    ) -> dict:
        """Compare two JADX instances (old vs new APK) and produce a structured diff report.

        Both instances must be running with their respective APK/JAR loaded.
        Use 'package' to restrict comparison to application code and skip library classes.

        Args:
            old_instance_id: Instance name for the older APK version
            new_instance_id: Instance name for the newer APK version
            package: Package prefix filter (strongly recommended, e.g. "com.example.app")
            include_code_diff: Include unified diffs of method source (slow, default False)
        """
        return await _compare_versions(
            old_instance_id=old_instance_id,
            new_instance_id=new_instance_id,
            package=package,
            include_code_diff=include_code_diff,
        )

    logger.info("Diff tools registered: compare_versions")
