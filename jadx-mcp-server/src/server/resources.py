"""
MCP Resources for JADX AI MCP Server.

Resources provide read-only data that AI can access to understand system state
and make better decisions about tool usage.
"""

from typing import Optional


USAGE_GUIDE = """
# JADX AI MCP Server - Usage Guide

## Quick Start

1. **Always check status first**: Call `get_decompile_status()` before any operation
2. **Use fast searches**: Prefer `search_in='class'` or `search_in='method'` over `search_in='code'`
3. **Monitor memory**: Check `memory.usage_percentage` before large batch operations

## Decision Matrix

| Status Field | Threshold | Recommended Action |
|--------------|-----------|-------------------|
| cached_percentage < 20% | Low cache | Use metadata search only |
| cached_percentage > 50% | Good cache | Code search is viable |
| memory.usage_percentage > 85% | High memory | Reduce batch size to 5 |
| search_lock.locked = true | Busy | Wait 5s and retry |
| threads.active_count > 100 | Overloaded | Pause heavy operations |

## Performance Expectations

| Operation | Expected Time | Notes |
|-----------|--------------|-------|
| search_in=class/method/field | <100ms | No cache needed |
| search_in=code/comment | 1-60s | Requires cache |
| get_class_source | <1s | Fast when cached |
| get_smali_of_class | <5s | Memory intensive |
| batch_get_* (20 items) | <3s | Monitor memory |

## Tool Categories

### Fast (Always Available)
- `get_android_manifest`
- `get_all_classes`
- `search_classes_by_keyword` (class/method/field mode)
- `get_class_info`

### Moderate (Check Status First)
- `get_class_source`
- `get_method_by_name`
- `get_xrefs_to_*`
- `batch_get_*`

### Slow (Requires Cache)
- `search_classes_by_keyword` (code/comment mode)
- `get_smali_of_class`

## Prompts Available

- `status-check`: Detailed guidance on interpreting get_decompile_status
- `search-code`: Best practices for searching
- `analyze-activity`: Workflow for Android Activity analysis
- `trace-method`: How to trace method calls
- `batch-operations`: Efficient batch processing
"""

DECISION_MATRIX = {
    "cached_percentage": {
        "low_threshold": 20,
        "high_threshold": 50,
        "low_action": "Use search_in='class' or 'method' only",
        "high_action": "Code search is viable"
    },
    "memory_usage_percentage": {
        "warning_threshold": 85,
        "critical_threshold": 95,
        "warning_action": "Reduce batch size to 5",
        "critical_action": "Pause operations, wait for GC"
    },
    "search_lock": {
        "locked_action": "Wait 5 seconds and retry",
        "held_timeout_warning": 30
    }
}


def register_resources(mcp):
    """Register MCP resources for JADX AI MCP Server."""
    
    @mcp.resource("jadx://usage-guide")
    def get_usage_guide() -> str:
        """Complete usage guide for JADX AI MCP Server.
        
        Read this resource to understand:
        - How to check system status before operations
        - Performance expectations for each tool
        - Decision matrix for choosing the right approach
        """
        return USAGE_GUIDE
    
    @mcp.resource("jadx://decision-matrix")
    def get_decision_matrix() -> dict:
        """Decision matrix for AI to make informed choices.
        
        Returns structured data with thresholds and recommended actions
        based on get_decompile_status() response fields.
        """
        return DECISION_MATRIX
    
    @mcp.resource("jadx://performance-benchmarks")
    def get_performance_benchmarks() -> dict:
        """Performance benchmarks for each tool category.
        
        Use this to set expectations for tool response times.
        """
        return {
            "fast_tools": {
                "expected_time_ms": 100,
                "tools": [
                    "get_android_manifest",
                    "get_all_classes",
                    "get_class_info",
                    "search_classes_by_keyword (class/method/field)"
                ]
            },
            "moderate_tools": {
                "expected_time_ms": 1000,
                "tools": [
                    "get_class_source",
                    "get_method_by_name",
                    "get_xrefs_to_class",
                    "get_xrefs_to_method",
                    "batch_get_class_source"
                ]
            },
            "slow_tools": {
                "expected_time_ms": 60000,
                "may_timeout": True,
                "tools": [
                    "search_classes_by_keyword (code/comment)",
                    "get_smali_of_class"
                ]
            }
        }
