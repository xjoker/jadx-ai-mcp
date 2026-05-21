"""
JADX MCP Server - Internal Index Diagnostics Tools

Exposes internal index health so AI clients can self-orient:
  - Are the name indices warm? (O(1) exact-match lookups available)
  - Is the trigram index warm? (fast code-search available)
  - How full is the snapshot cache?

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

from typing import Optional

from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("diagnostics_tools")


async def get_index_stats(instance_id: Optional[str] = None) -> dict:
    """Internal index health (name indices, trigram index, snapshot cache).

    Call this to decide whether code-search will be fast (trigram warm) or
    if you should stick to metadata searches.

    Args:
        instance_id: Target JADX instance; omit for default.
    Returns:
        dict: {name_indices, trigram_index, snapshot_cache, code_cache}
    """
    logger.debug("get_index_stats called, instance_id=%s", instance_id)
    try:
        result = await get_from_jadx("index-stats", instance_id=instance_id)
        return result
    except Exception as exc:
        logger.warning("get_index_stats failed: %s", exc)
        return {"error": "JADX_ERROR", "message": str(exc)}


# Module-level reference for registration wrapper
_get_index_stats = get_index_stats


def register_diagnostics_tools(mcp, with_busy_check):
    """Register diagnostics/index-health tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def get_index_stats(instance_id: Optional[str] = None) -> dict:
        """Internal index health snapshot (name indices, trigram index, snapshot cache).

        Use this to decide whether trigram code-search is warm enough for efficient use,
        or whether to stick to metadata (class/method/field name) searches.

        Returns saturation_percent for the trigram index:
          - < 20%: trigram index mostly cold, prefer metadata searches
          - >= 50%: trigram index warmed, code-search (search_classes_by_keyword with
                    search_in='code') should be fast

        Args:
            instance_id: Target JADX instance; omit for default.
        Returns:
            dict: {name_indices: {class_name_buckets, method_name_buckets,
                                  field_name_buckets, raw_name_map_size, index_ready},
                   trigram_index: {enabled, indexed_classes, trigram_count, max_trigrams,
                                   max_class_size_bytes, estimated_memory_mb,
                                   saturation_percent},
                   snapshot_cache: {method_snapshot_classes, field_snapshot_classes},
                   code_cache: {class_index_size, delegates_to_jadx_icodecache}}
        """
        return await _get_index_stats(instance_id=instance_id)

    logger.info("Diagnostics tools registered: get_index_stats")
