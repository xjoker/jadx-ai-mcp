"""
JADX MCP Server - Cross-Version Diff Tools

This module provides MCP tools for comparing two JADX instances that have loaded
different versions of the same APK/JAR. It identifies added, removed, and modified
classes and methods, and optionally produces unified diffs of method source code.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

import difflib
import re
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


def _parse_manifest_permissions(manifest_xml: str) -> set[str]:
    """Extract uses-permission names from manifest XML text."""
    return set(re.findall(
        r'<uses-permission[^>]+android:name=["\']([^"\']+)["\']',
        manifest_xml,
    ))


def _parse_exported_components(manifest_xml: str) -> list[dict[str, str]]:
    """
    Extract exported components (activity, service, receiver, provider) from manifest XML.
    A component is considered exported if it has android:exported="true" or contains
    an <intent-filter> child (implicit export).
    """
    components: list[dict[str, str]] = []

    # Match component tags with their full attribute block
    component_pattern = re.compile(
        r'<(activity|service|receiver|provider)\s([^>]*?)(/?>)',
        re.DOTALL,
    )

    # For intent-filter detection we look for the component block end
    # This is a simplified heuristic — not full XML parsing
    for m in component_pattern.finditer(manifest_xml):
        comp_type = m.group(1)
        attrs = m.group(2)

        name_match = re.search(r'android:name=["\']([^"\']+)["\']', attrs)
        if not name_match:
            continue
        comp_name = name_match.group(1)

        exported_match = re.search(r'android:exported=["\']([^"\']+)["\']', attrs)
        explicitly_exported = exported_match and exported_match.group(1).lower() == "true"

        if explicitly_exported:
            components.append({"type": comp_type, "name": comp_name})

    return components


def _parse_sdk_versions(manifest_xml: str) -> tuple[Optional[int], Optional[int]]:
    """Return (min_sdk_version, target_sdk_version) from manifest XML, or None if absent."""
    min_sdk: Optional[int] = None
    target_sdk: Optional[int] = None

    min_match = re.search(r'android:minSdkVersion=["\'](\d+)["\']', manifest_xml)
    if min_match:
        try:
            min_sdk = int(min_match.group(1))
        except ValueError:
            pass

    target_match = re.search(r'android:targetSdkVersion=["\'](\d+)["\']', manifest_xml)
    if target_match:
        try:
            target_sdk = int(target_match.group(1))
        except ValueError:
            pass

    return min_sdk, target_sdk


async def _fetch_manifest(instance_id: str) -> Optional[str]:
    """Fetch the AndroidManifest.xml text from a JADX instance. Returns None on failure."""
    try:
        result = await get_from_jadx("android-manifest", instance_id=instance_id)
        if isinstance(result, dict):
            # Common response shapes: {"manifest": "..."} or {"content": "..."} or {"xml": "..."}
            for key in ("manifest", "content", "xml", "text"):
                if key in result and isinstance(result[key], str):
                    return result[key]
        if isinstance(result, str):
            return result
        return None
    except Exception:
        return None


async def _build_manifest_diff(
    old_instance_id: str,
    new_instance_id: str,
) -> Optional[dict]:
    """
    Compare AndroidManifest.xml between two JADX instances.

    Returns a manifest_diff dict, or None if manifest is not available on either instance.
    """
    old_xml = await _fetch_manifest(old_instance_id)
    new_xml = await _fetch_manifest(new_instance_id)

    if not old_xml or not new_xml:
        return None

    old_perms = _parse_manifest_permissions(old_xml)
    new_perms = _parse_manifest_permissions(new_xml)
    old_exported = _parse_exported_components(old_xml)
    new_exported = _parse_exported_components(new_xml)

    old_min_sdk, old_target_sdk = _parse_sdk_versions(old_xml)
    new_min_sdk, new_target_sdk = _parse_sdk_versions(new_xml)

    # Exported component sets (by type+name for comparison)
    old_comp_keys = {(c["type"], c["name"]) for c in old_exported}
    new_comp_keys = {(c["type"], c["name"]) for c in new_exported}

    comps_added = [
        {"type": t, "name": n}
        for t, n in sorted(new_comp_keys - old_comp_keys)
    ]
    comps_removed = [
        {"type": t, "name": n}
        for t, n in sorted(old_comp_keys - new_comp_keys)
    ]

    def _sdk_change(old: Optional[int], new: Optional[int]) -> Optional[dict]:
        if old != new:
            return {"from": old, "to": new}
        return None

    return {
        "permissions_added": sorted(new_perms - old_perms),
        "permissions_removed": sorted(old_perms - new_perms),
        "exported_components_added": comps_added,
        "exported_components_removed": comps_removed,
        "min_sdk_changed": _sdk_change(old_min_sdk, new_min_sdk),
        "target_sdk_changed": _sdk_change(old_target_sdk, new_target_sdk),
    }


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

    # 4. Manifest diff
    manifest_diff = await _build_manifest_diff(old_instance_id, new_instance_id)

    # 5. Build response
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
        "manifest_diff": manifest_diff,
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
        """Compare two loaded JADX instances (old vs new APK) and produce a class/method diff report.

        Args:
            old_instance_id: Older APK instance name. new_instance_id: Newer APK instance name.
            package: Package filter (strongly recommended). include_code_diff: Unified method diffs (slow).
        Returns:
            dict: {summary: {classes_added, removed, modified}, added_classes, removed_classes, modified_classes}
        """
        return await _compare_versions(
            old_instance_id=old_instance_id,
            new_instance_id=new_instance_id,
            package=package,
            include_code_diff=include_code_diff,
        )

    logger.info("Diff tools registered: compare_versions")
