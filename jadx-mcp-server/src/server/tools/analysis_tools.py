"""
JADX MCP Server - Analysis Planning Tools

This module provides MCP tools for generating interactive analysis plans,
guiding AI clients through structured APK reverse engineering workflows.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

from typing import Optional
from src.server.logging_config import get_logger

logger = get_logger("analysis_tools")

# ---------------------------------------------------------------------------
# Analysis plan definitions
# ---------------------------------------------------------------------------

_PLANS = {
    "quick_analysis": {
        "name": "Quick Overview Analysis (Quick Analysis)",
        "description": "Get a basic overall understanding of the APK, suitable for first contact with an unknown APK.",
        "steps": [
            {
                "step": 1,
                "tool": "get_file_info",
                "params": {},
                "reason": "Get basic file info: type and size, determine if this is a large APK.",
            },
            {
                "step": 2,
                "tool": "get_apk_info",
                "params": {},
                "reason": "Get package name, version, SDK version and other metadata to understand the app profile.",
            },
            {
                "step": 3,
                "tool": "get_main_application_classes_names",
                "params": {},
                "reason": "List application-owned classes (excluding third-party libraries) to narrow down the analysis scope.",
            },
            {
                "step": 4,
                "tool": "batch_get_class_source",
                "params": {"class_names": ["<select 3-5 representative classes from step 3>"]},
                "reason": "Fetch core class source code to quickly build an overall understanding.",
            },
        ],
        "tips": [
            "When file_type=jar, skip APK-specific steps (get_apk_info, get_android_manifest).",
            "total_classes > 50000 indicates a large APK; use search_classes_by_keyword with package filtering.",
            "The response_size_bytes field is visible in each tool response; batch fetching is recommended when it exceeds 5MB.",
        ],
    },

    "security_audit": {
        "name": "Security Audit",
        "description": "Systematically check the APK for security risks, including sensitive APIs, permissions, hardcoded secrets, and network security configuration.",
        "steps": [
            {
                "step": 1,
                "tool": "get_android_manifest",
                "params": {},
                "reason": "Check permission declarations (INTERNET, READ_CONTACTS, ACCESS_FINE_LOCATION, etc.) and security configuration.",
            },
            {
                "step": 2,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "KeyStore", "search_in": "class"},
                "reason": "Find encryption-related classes (KeyStore, Cipher, SecretKey) — fast metadata search, no cache required.",
            },
            {
                "step": 3,
                "tool": "search_native_methods",
                "params": {},
                "reason": "List all native methods — these are potential attack surfaces that bypass Java-layer analysis.",
            },
            {
                "step": 4,
                "tool": "get_decompile_status",
                "params": {},
                "reason": "Check cache rate to determine whether code content search can be performed (cached_percentage > 20% required).",
            },
            {
                "step": 5,
                "tool": "search_classes_by_keyword",
                "params": {
                    "search_term": "password",
                    "search_in": "code",
                    "count": 20,
                },
                "reason": "Search code for hardcoded passwords/secrets — execute only after step 4 confirms sufficient cache rate.",
                "condition": "cached_percentage > 20",
            },
            {
                "step": 6,
                "tool": "search_classes_by_keyword",
                "params": {
                    "search_term": "http://",
                    "search_in": "code",
                    "count": 20,
                },
                "reason": "Find plaintext HTTP communication — presence of http:// URLs indicates data may be transmitted in cleartext.",
                "condition": "cached_percentage > 20",
            },
        ],
        "tips": [
            "Steps 5 and 6 require code cache; confirm get_decompile_status cached_percentage > 20% first.",
            "Also search for: 'secret', 'api_key', 'Bearer ', 'DexClassLoader', 'Runtime.exec'.",
            "Call get_class_source on suspicious classes to review their full implementation.",
        ],
    },

    "network_analysis": {
        "name": "Network Communication Analysis (Network Analysis)",
        "description": "Map the APK's network communication layer: HTTP clients, API interfaces, URL endpoints, and certificate validation.",
        "steps": [
            {
                "step": 1,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "OkHttpClient", "search_in": "class"},
                "reason": "Find OkHttp client initialization classes, which typically contain interceptors and timeout configuration.",
            },
            {
                "step": 2,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "Retrofit", "search_in": "class"},
                "reason": "Find Retrofit instance creation to locate API interface annotations and baseUrl.",
            },
            {
                "step": 3,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "ApiService", "search_in": "class"},
                "reason": "Find Retrofit API interface classes (common names: ApiService, ApiInterface, RetrofitService).",
            },
            {
                "step": 4,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "Interceptor", "search_in": "class"},
                "reason": "Find request interceptors — Authorization/Token headers are typically added here.",
            },
            {
                "step": 5,
                "tool": "search_classes_by_keyword",
                "params": {
                    "search_term": "https://",
                    "search_in": "code",
                    "count": 30,
                },
                "reason": "Search for hardcoded API endpoint URLs — requires code cache.",
                "condition": "cached_percentage > 20",
            },
            {
                "step": 6,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "CertificatePinner", "search_in": "class"},
                "reason": "Check whether Certificate Pinning is implemented.",
            },
        ],
        "tips": [
            "After finding API interface classes, use get_class_source to inspect all @GET/@POST/@PUT annotations.",
            "Use get_xrefs('class', class_name) to trace callers of network classes.",
            "Check the android:usesCleartextTraffic attribute in the Manifest.",
        ],
    },

    "entry_points": {
        "name": "Entry Points Analysis (Entry Points)",
        "description": "Enumerate all Android component entry points, analyze lifecycle methods and exported components.",
        "steps": [
            {
                "step": 1,
                "tool": "get_android_manifest",
                "params": {},
                "reason": "Get all component declarations: Activity, Service, BroadcastReceiver, ContentProvider.",
            },
            {
                "step": 2,
                "tool": "get_class_info",
                "params": {"class_name": "<main Activity class name obtained from step 1>"},
                "reason": "View the class inheritance hierarchy, implemented interfaces, and method list.",
            },
            {
                "step": 3,
                "tool": "batch_get_class_source",
                "params": {"class_names": ["<Activity1>", "<Activity2>", "<Service1>"]},
                "reason": "Batch-fetch core component source code, more efficient than calling individually.",
            },
            {
                "step": 4,
                "tool": "get_method_by_name",
                "params": {
                    "class_name": "<MainActivity>",
                    "method_name": "onCreate",
                },
                "reason": "Deep-dive into key lifecycle method implementations.",
            },
            {
                "step": 5,
                "tool": "get_xrefs",
                "params": {
                    "ref_type": "class",
                    "class_name": "<MainActivity>",
                },
                "reason": "Find who calls/starts this component (Intent source tracing).",
            },
        ],
        "tips": [
            "Components with android:exported='true' or <intent-filter> are external attack surfaces.",
            "Check BroadcastReceiver.onReceive to verify whether the Intent source is validated.",
            "Check ContentProvider to verify whether readPermission/writePermission are set.",
        ],
    },
}

# Keyword-to-plan mapping (used for fuzzy matching)
_KEYWORD_MAP = {
    # quick_analysis
    "quick": "quick_analysis",
    "overview": "quick_analysis",
    "概览": "quick_analysis",
    "快速": "quick_analysis",
    "initial": "quick_analysis",
    "start": "quick_analysis",
    "开始": "quick_analysis",

    # security_audit
    "security": "security_audit",
    "audit": "security_audit",
    "安全": "security_audit",
    "漏洞": "security_audit",
    "vulnerability": "security_audit",
    "password": "security_audit",
    "密码": "security_audit",
    "secret": "security_audit",
    "密钥": "security_audit",
    "hardcode": "security_audit",
    "硬编码": "security_audit",
    "permission": "security_audit",
    "权限": "security_audit",

    # network_analysis
    "network": "network_analysis",
    "网络": "network_analysis",
    "http": "network_analysis",
    "url": "network_analysis",
    "api": "network_analysis",
    "retrofit": "network_analysis",
    "okhttp": "network_analysis",
    "endpoint": "network_analysis",
    "接口": "network_analysis",
    "请求": "network_analysis",

    # entry_points
    "entry": "entry_points",
    "入口": "entry_points",
    "activity": "entry_points",
    "service": "entry_points",
    "receiver": "entry_points",
    "provider": "entry_points",
    "manifest": "entry_points",
    "lifecycle": "entry_points",
    "生命周期": "entry_points",
    "组件": "entry_points",
}


def _match_plan(goal: str) -> list[str]:
    """Match recommended plan list by analysis goal keywords (may return multiple)."""
    goal_lower = goal.lower()
    matched = set()
    for keyword, plan_id in _KEYWORD_MAP.items():
        if keyword in goal_lower:
            matched.add(plan_id)
    return list(matched) if matched else list(_PLANS.keys())


async def suggest_analysis_plan(
    analysis_goal: str,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Recommend tool call sequences, parameters, and descriptions based on the analysis goal.

    Args:
        analysis_goal: Natural language description of the analysis goal, for example:
                       "I want to find network API endpoints"
                       "Check if this APK has security vulnerabilities"
                       "Analyze the lifecycle of all Activities"
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains the recommended plan list, step sequences, and tips for each plan

    MCP Tool: suggest_analysis_plan
    Description: Recommends structured tool call sequences and analysis plans based on the analysis goal
    """
    logger.info(f"suggest_analysis_plan: goal='{analysis_goal}'")

    if not analysis_goal or not analysis_goal.strip():
        return {
            "error": "INVALID_INPUT",
            "message": "analysis_goal cannot be empty",
            "available_plans": list(_PLANS.keys()),
        }

    matched_plan_ids = _match_plan(analysis_goal.strip())
    logger.debug(f"suggest_analysis_plan: matched plans={matched_plan_ids}")

    recommended_plans = []
    for plan_id in matched_plan_ids:
        plan = _PLANS[plan_id]
        recommended_plans.append({
            "plan_id": plan_id,
            "name": plan["name"],
            "description": plan["description"],
            "steps": plan["steps"],
            "tips": plan["tips"],
        })

    # When no specific plan is matched, return all plans for the AI to choose from
    is_fallback = len(matched_plan_ids) == len(_PLANS)

    return {
        "analysis_goal": analysis_goal,
        "recommended_plans": recommended_plans,
        "plan_count": len(recommended_plans),
        "is_fallback": is_fallback,
        "fallback_message": (
            "No specific plan could be matched from the goal description; all available plans are returned for reference."
            if is_fallback
            else None
        ),
        "available_plan_ids": list(_PLANS.keys()),
        "usage_hint": (
            "Call the corresponding tools in the order of the steps array. Steps with a condition field must satisfy the condition before execution."
            " The response_size_bytes field in each tool's response can be used to determine whether batch processing is needed."
        ),
    }


def register_analysis_tools(mcp):
    """Register analysis planning tools with the MCP server."""
    mcp.tool()(suggest_analysis_plan)
    logger.info("Analysis tools registered: suggest_analysis_plan")
