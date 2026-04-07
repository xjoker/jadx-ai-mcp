"""
JADX MCP Server - Analysis Report Export Tools

Export annotations, bookmarks, and tags as structured reports
in Markdown, JSON, or SARIF 2.1.0 format.

Author: JADX-AI-MCP Contributors
License: See LICENSE file
"""

import json
from datetime import datetime, timezone
from typing import Optional

from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("export_tools")

_SUPPORTED_FORMATS = ("markdown", "json", "sarif")


def _build_markdown_report(
    file_info: dict,
    annotations: list,
    bookmarks: list,
    tags: list,
    instance_id: Optional[str],
    timestamp: str,
) -> str:
    """Generate a Markdown-formatted analysis report."""
    package_name = file_info.get("package_name", file_info.get("name", "Unknown"))
    file_name = file_info.get("file_name", file_info.get("name", "Unknown"))
    file_type = file_info.get("file_type", file_info.get("type", "Unknown"))

    lines: list[str] = []
    lines.append(f"# Analysis Report: {package_name}")
    lines.append("")
    lines.append(f"**File**: {file_name} ({file_type})  ")
    lines.append(f"**Generated**: {timestamp}  ")
    if instance_id:
        lines.append(f"**Instance**: {instance_id}")
    lines.append("")

    # Annotations section
    lines.append(f"## Annotations ({len(annotations)})")
    lines.append("")
    if annotations:
        lines.append("| Target | Type | Content | Author |")
        lines.append("|--------|------|---------|--------|")
        for a in annotations:
            target = a.get("target_name", "")
            atype = a.get("target_type", "")
            content = a.get("content", "").replace("|", "\\|").replace("\n", " ")
            author = a.get("author", "")
            lines.append(f"| {target} | {atype} | {content} | {author} |")
    else:
        lines.append("_No annotations found._")
    lines.append("")

    # Bookmarks section
    lines.append(f"## Bookmarks ({len(bookmarks)})")
    lines.append("")
    if bookmarks:
        lines.append("| Target | Label | Note | Author |")
        lines.append("|--------|-------|------|--------|")
        for b in bookmarks:
            target = b.get("target_name", "")
            label = b.get("label", "").replace("|", "\\|")
            note = b.get("note", "").replace("|", "\\|").replace("\n", " ")
            author = b.get("author", "")
            lines.append(f"| {target} | {label} | {note} | {author} |")
    else:
        lines.append("_No bookmarks found._")
    lines.append("")

    # Tags section
    lines.append(f"## Tags ({len(tags)})")
    lines.append("")
    if tags:
        lines.append("| Target | Tag | Author |")
        lines.append("|--------|-----|--------|")
        for t in tags:
            target = t.get("target_name", "")
            tag = t.get("tag", "")
            author = t.get("author", "")
            lines.append(f"| {target} | {tag} | {author} |")
    else:
        lines.append("_No tags found._")
    lines.append("")

    return "\n".join(lines)


def _build_json_report(
    file_info: dict,
    annotations: list,
    bookmarks: list,
    tags: list,
    instance_id: Optional[str],
    timestamp: str,
) -> str:
    """Generate a JSON-formatted analysis report."""
    report = {
        "file_info": file_info,
        "instance_id": instance_id,
        "generated_at": timestamp,
        "annotations": annotations,
        "bookmarks": bookmarks,
        "tags": tags,
    }
    return json.dumps(report, ensure_ascii=False, indent=2)


def _build_sarif_report(
    file_info: dict,
    annotations: list,
    bookmarks: list,
    tags: list,
    instance_id: Optional[str],
    timestamp: str,
) -> str:
    """Generate a SARIF 2.1.0-formatted analysis report."""
    results: list[dict] = []

    for a in annotations:
        results.append({
            "ruleId": "annotation",
            "level": "note",
            "message": {"text": a.get("content", "")},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": a.get("target_name", ""),
                    },
                },
                "logicalLocations": [{
                    "name": a.get("target_name", ""),
                    "kind": a.get("target_type", ""),
                }],
            }],
            "properties": {
                "author": a.get("author", ""),
                "category": "annotation",
            },
        })

    for b in bookmarks:
        results.append({
            "ruleId": "bookmark",
            "level": "note",
            "message": {"text": b.get("note", b.get("label", ""))},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": b.get("target_name", ""),
                    },
                },
                "logicalLocations": [{
                    "name": b.get("target_name", ""),
                    "kind": b.get("target_type", ""),
                }],
            }],
            "properties": {
                "author": b.get("author", ""),
                "label": b.get("label", ""),
                "category": "bookmark",
            },
        })

    file_name = file_info.get("file_name", file_info.get("name", "unknown"))

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "jadx-ai-mcp",
                    "informationUri": "https://github.com/jadx-decompiler/jadx",
                    "rules": [
                        {
                            "id": "annotation",
                            "shortDescription": {"text": "User annotation"},
                        },
                        {
                            "id": "bookmark",
                            "shortDescription": {"text": "User bookmark"},
                        },
                    ],
                },
            },
            "results": results,
            "artifacts": [{
                "location": {"uri": file_name},
                "properties": file_info,
            }],
            "invocations": [{
                "executionSuccessful": True,
                "endTimeUtc": timestamp,
            }],
        }],
    }
    return json.dumps(sarif, ensure_ascii=False, indent=2)


async def export_analysis_report(
    format: str = "markdown",
    include_annotations: bool = True,
    include_bookmarks: bool = True,
    include_tags: bool = True,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Export analysis results (annotations, bookmarks, tags) as a structured report.

    Args:
        format: Output format - "markdown", "json", or "sarif"
        include_annotations: Whether to include annotations (default True)
        include_bookmarks: Whether to include bookmarks (default True)
        include_tags: Whether to include tags (default True)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: {format, report, stats, generated_at}

    MCP Tool: export_analysis_report
    Description: Export annotations, bookmarks, and tags as a Markdown, JSON, or SARIF report
    """
    logger.info(f"export_analysis_report: format={format}")

    fmt = format.lower().strip()
    if fmt not in _SUPPORTED_FORMATS:
        return {
            "error": "INVALID_FORMAT",
            "message": f"Unsupported format '{format}'. Use one of: {', '.join(_SUPPORTED_FORMATS)}",
        }

    # Fetch file info
    file_info: dict = {}
    try:
        file_info = await get_from_jadx("file-info", instance_id=instance_id)
        if isinstance(file_info, str):
            file_info = {}
    except Exception as exc:
        logger.warning(f"export_analysis_report: failed to fetch file-info: {exc}")

    # Fetch analysis notes (annotations, bookmarks, tags)
    analysis_data: dict = {}
    try:
        analysis_data = await get_from_jadx("analysis-notes", instance_id=instance_id)
        if isinstance(analysis_data, str):
            analysis_data = {}
    except Exception as exc:
        logger.warning(f"export_analysis_report: failed to fetch analysis-notes: {exc}")

    annotations = analysis_data.get("annotations", []) if include_annotations else []
    bookmarks = analysis_data.get("bookmarks", []) if include_bookmarks else []
    tags = analysis_data.get("tags", []) if include_tags else []

    timestamp = datetime.now(timezone.utc).isoformat()

    # Build report based on format
    if fmt == "markdown":
        report = _build_markdown_report(
            file_info, annotations, bookmarks, tags, instance_id, timestamp,
        )
    elif fmt == "json":
        report = _build_json_report(
            file_info, annotations, bookmarks, tags, instance_id, timestamp,
        )
    elif fmt == "sarif":
        report = _build_sarif_report(
            file_info, annotations, bookmarks, tags, instance_id, timestamp,
        )
    else:
        # Should not reach here due to validation above
        report = ""

    stats = {
        "annotations": len(annotations),
        "bookmarks": len(bookmarks),
        "tags": len(tags),
    }

    logger.info(
        f"export_analysis_report: generated {fmt} report "
        f"(annotations={stats['annotations']}, bookmarks={stats['bookmarks']}, tags={stats['tags']})"
    )

    return {
        "format": fmt,
        "report": report,
        "stats": stats,
        "generated_at": timestamp,
    }


# ==================== Module-level reference ====================

_export_analysis_report = export_analysis_report


def register_export_tools(mcp, with_busy_check):
    """Register export tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def export_analysis_report(
        format: str = "markdown",
        include_annotations: bool = True,
        include_bookmarks: bool = True,
        include_tags: bool = True,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Export analysis results (annotations, bookmarks, tags) as a structured report.

        Supports Markdown (human-readable), JSON (structured), and SARIF 2.1.0
        (security tooling standard) output formats.

        Args:
            format: Output format - "markdown", "json", or "sarif"
            include_annotations: Include annotations in the report (default True)
            include_bookmarks: Include bookmarks in the report (default True)
            include_tags: Include tags in the report (default True)
            instance_id: Optional. Target JADX instance name
        """
        return await _export_analysis_report(
            format=format,
            include_annotations=include_annotations,
            include_bookmarks=include_bookmarks,
            include_tags=include_tags,
            instance_id=instance_id,
        )

    logger.info("Export tools registered: export_analysis_report")
