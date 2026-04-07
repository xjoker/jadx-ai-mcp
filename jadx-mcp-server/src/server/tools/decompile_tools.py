"""
JADX MCP Server - Smart Decompilation Management Tools

Provides intelligent decompilation scheduling and priority analysis to help
AI clients use limited resources more efficiently when analyzing APKs.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

import asyncio
import time
from typing import Optional

from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("decompile_tools")

# Concurrency limits by priority level
_CONCURRENCY = {"high": 5, "normal": 3, "low": 1}

# Well-known third-party SDK package prefixes (low priority)
_THIRD_PARTY_PREFIXES = (
    "android.", "androidx.", "com.google.", "com.facebook.", "com.squareup.",
    "okhttp3.", "retrofit2.", "io.reactivex.", "org.apache.", "kotlin.",
    "kotlinx.", "com.bumptech.glide.", "com.github.", "org.greenrobot.",
    "com.alibaba.", "com.tencent.", "io.flutter.", "com.unity3d.",
    "org.reactnative.", "com.airbnb.", "dagger.", "javax.", "org.json.",
)

# Android component suffixes that indicate high-priority classes
_COMPONENT_SUFFIXES = ("Activity", "Service", "Receiver", "Provider", "Fragment")


async def _decompile_single_class(
    class_name: str,
    instance_id: Optional[str],
) -> dict:
    """Decompile a single class and return timing/status info."""
    start = time.monotonic()
    try:
        result = await get_from_jadx(
            "class-source", {"class_name": class_name}, instance_id=instance_id,
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        if "error" in result:
            return {
                "class_name": class_name,
                "status": "failed",
                "time_ms": round(elapsed_ms, 1),
                "size_bytes": 0,
                "error": result.get("error", "unknown"),
            }

        # Determine if it was already cached (heuristic: very fast response)
        content = result.get("response", result.get("content", ""))
        size_bytes = len(content.encode("utf-8")) if isinstance(content, str) else 0
        status = "cached" if elapsed_ms < 50 else "decompiled"

        return {
            "class_name": class_name,
            "status": status,
            "time_ms": round(elapsed_ms, 1),
            "size_bytes": size_bytes,
            "error": None,
        }
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.warning(f"Decompile failed for {class_name}: {exc}")
        return {
            "class_name": class_name,
            "status": "failed",
            "time_ms": round(elapsed_ms, 1),
            "size_bytes": 0,
            "error": str(exc),
        }


async def smart_decompile(
    class_names: list[str],
    priority: str = "normal",
    instance_id: Optional[str] = None,
) -> dict:
    """
    Smart batch decompile with concurrency control and progress tracking.

    Decompiles the given classes in batches, respecting priority-based concurrency
    limits. Tracks timing and caching status for each class.

    Args:
        class_names: List of fully qualified class names to decompile.
        priority: Concurrency tier - "high" (5 concurrent), "normal" (3), "low" (1).
        instance_id: Optional target JADX instance name.

    Returns:
        dict: Summary with per-class results, timing, and optimization tips.

    MCP Tool: smart_decompile
    Description: Batch-decompile classes with priority-based concurrency and progress tracking
    """
    logger.info(
        f"smart_decompile: {len(class_names)} classes, priority={priority}"
    )

    if not class_names:
        return {
            "error": "INVALID_INPUT",
            "message": "class_names cannot be empty",
        }

    if priority not in _CONCURRENCY:
        return {
            "error": "INVALID_INPUT",
            "message": f"priority must be one of: {list(_CONCURRENCY.keys())}",
        }

    concurrency = _CONCURRENCY[priority]
    semaphore = asyncio.Semaphore(concurrency)

    async def _limited(cls: str) -> dict:
        async with semaphore:
            return await _decompile_single_class(cls, instance_id)

    overall_start = time.monotonic()
    results = await asyncio.gather(*[_limited(cls) for cls in class_names])
    total_time = time.monotonic() - overall_start

    succeeded = sum(1 for r in results if r["status"] == "decompiled")
    cached = sum(1 for r in results if r["status"] == "cached")
    failed = sum(1 for r in results if r["status"] == "failed")

    # Fetch post-decompile status
    decompile_status_after = {}
    try:
        decompile_status_after = await get_from_jadx(
            "decompile-status", instance_id=instance_id,
        )
    except Exception as exc:
        logger.warning(f"Failed to fetch decompile-status: {exc}")
        decompile_status_after = {"error": str(exc)}

    # Build optimization tips
    tips: list[str] = []
    if failed > 0:
        tips.append(
            f"{failed} class(es) failed. Check class names and JADX memory usage."
        )
    if cached == len(class_names):
        tips.append("All classes were already cached. No decompilation needed.")
    avg_ms = sum(r["time_ms"] for r in results) / len(results) if results else 0
    if avg_ms > 2000:
        tips.append(
            "Average decompile time >2s. Consider reducing batch size or "
            "increasing JADX heap memory."
        )
    pct = decompile_status_after.get("percentage", 0)
    if isinstance(pct, (int, float)) and pct < 50:
        tips.append(
            f"Cache rate is {pct}%. Use get_decompile_priority_list to identify "
            "high-value classes to decompile next."
        )

    return {
        "requested": len(class_names),
        "succeeded": succeeded,
        "failed": failed,
        "already_cached": cached,
        "total_time_seconds": round(total_time, 2),
        "results": list(results),
        "decompile_status_after": decompile_status_after,
        "optimization_tips": tips,
    }


def _classify_class(class_name: str, package: str) -> tuple[str, str]:
    """Return (priority, reason) for a class based on heuristics.

    Args:
        class_name: Fully qualified class name.
        package: Application package prefix for filtering.

    Returns:
        Tuple of (priority_level, reason_string).
    """
    simple_name = class_name.rsplit(".", 1)[-1] if "." in class_name else class_name

    # Third-party SDK detection
    for prefix in _THIRD_PARTY_PREFIXES:
        if class_name.startswith(prefix):
            return "low", f"Third-party SDK ({prefix.rstrip('.')})"

    # Android component detection (high priority)
    for suffix in _COMPONENT_SUFFIXES:
        if simple_name.endswith(suffix):
            return "high", f"Android component ({suffix})"

    # Application own package (high priority)
    if package and class_name.startswith(package):
        return "high", "Application own package"

    # Short names may indicate obfuscated core logic
    if len(simple_name) <= 3:
        return "medium", "Short name (possible obfuscated core logic)"

    return "medium", "General class"


async def get_decompile_priority_list(
    analysis_goal: str = "",
    package: str = "",
    instance_id: Optional[str] = None,
) -> dict:
    """
    Recommend which classes to decompile first based on heuristic analysis.

    Fetches all classes, checks cache status, and ranks uncached classes by
    likely importance for reverse engineering.

    Args:
        analysis_goal: Optional natural language hint (e.g., "find network APIs").
                       Currently used for logging; heuristic rules drive ranking.
        package: Application package prefix (e.g., "com.example.app") to boost
                 own-package classes. If empty, all non-SDK classes are treated equally.
        instance_id: Optional target JADX instance name.

    Returns:
        dict: Priority-sorted list of uncached classes with reasons and batch size hint.

    MCP Tool: get_decompile_priority_list
    Description: Rank uncached classes by reverse-engineering importance to guide decompilation order
    """
    logger.info(
        f"get_decompile_priority_list: goal='{analysis_goal}', package='{package}'"
    )

    # Fetch all classes
    try:
        all_classes_resp = await get_from_jadx(
            "all-classes", instance_id=instance_id,
        )
    except Exception as exc:
        return {"error": "JADX_ERROR", "message": f"Failed to fetch classes: {exc}"}

    all_classes: list[str] = all_classes_resp.get("classes", [])
    if not all_classes:
        return {
            "error": "NO_CLASSES",
            "message": "No classes found. Ensure a file is loaded in JADX.",
        }

    # Fetch decompile status for cache info
    decompile_status = {}
    try:
        decompile_status = await get_from_jadx(
            "decompile-status", instance_id=instance_id,
        )
    except Exception as exc:
        logger.warning(f"Failed to fetch decompile-status: {exc}")

    cached_count = decompile_status.get("processed_classes", 0)
    total_count = len(all_classes)

    # Build priority list for all classes
    priority_order = {"high": 0, "medium": 1, "low": 2}
    classified: list[dict] = []

    for cls in all_classes:
        prio, reason = _classify_class(cls, package)
        classified.append({
            "class_name": cls,
            "priority": prio,
            "reason": reason,
        })

    # Sort by priority (high first), then alphabetically within same priority
    classified.sort(key=lambda x: (priority_order.get(x["priority"], 99), x["class_name"]))

    # Limit to top 100
    priority_list = classified[:100]

    # Suggest batch size based on total count
    if total_count > 10000:
        suggested_batch = 3
    elif total_count > 1000:
        suggested_batch = 5
    else:
        suggested_batch = 10

    return {
        "total_classes": total_count,
        "already_cached": cached_count,
        "uncached": max(total_count - cached_count, 0),
        "priority_list": priority_list,
        "suggested_batch_size": suggested_batch,
    }


# Module-level references for registration wrappers
_smart_decompile = smart_decompile
_get_decompile_priority_list = get_decompile_priority_list


def register_decompile_tools(mcp, with_busy_check):
    """Register smart decompilation tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def smart_decompile(
        class_names: list[str],
        priority: str = "normal",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Batch-decompile classes with priority-based concurrency control.

        Concurrency tiers: high=5, normal=3, low=1 concurrent requests.
        Tracks per-class timing, cache hits, and failures.

        Args:
            class_names: Fully qualified class names to decompile.
            priority: "high", "normal", or "low" concurrency tier.
            instance_id: Optional target JADX instance name.
        """
        return await _smart_decompile(
            class_names, priority=priority, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def get_decompile_priority_list(
        analysis_goal: str = "",
        package: str = "",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Rank uncached classes by importance to guide decompilation order.

        Uses heuristics: Android components > app package > obfuscated names > SDKs.

        Args:
            analysis_goal: Optional hint like "find network APIs" (for logging).
            package: App package prefix to boost own classes (e.g., "com.example.app").
            instance_id: Optional target JADX instance name.
        """
        return await _get_decompile_priority_list(
            analysis_goal=analysis_goal, package=package, instance_id=instance_id,
        )

    logger.info(
        "Decompile tools registered: smart_decompile, get_decompile_priority_list"
    )
