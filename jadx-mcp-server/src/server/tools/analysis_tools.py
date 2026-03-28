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
        "name": "快速概览分析 (Quick Analysis)",
        "description": "对 APK 做基础全貌了解，适合初次接触一个未知 APK。",
        "steps": [
            {
                "step": 1,
                "tool": "get_file_info",
                "params": {},
                "reason": "获取文件基本信息：类型、大小，判断是否为大 APK。",
            },
            {
                "step": 2,
                "tool": "get_apk_info",
                "params": {},
                "reason": "获取包名、版本、SDK 版本等元数据，了解 App 定位。",
            },
            {
                "step": 3,
                "tool": "get_main_application_classes_names",
                "params": {},
                "reason": "列出应用自有类（排除第三方库），缩小分析范围。",
            },
            {
                "step": 4,
                "tool": "batch_get_class_source",
                "params": {"class_names": ["<从步骤3选取 3-5 个代表性类>"]},
                "reason": "获取核心类源码，快速建立整体认知。",
            },
        ],
        "tips": [
            "file_type=jar 时跳过 APK 专属步骤（get_apk_info, get_android_manifest）。",
            "total_classes > 50000 说明是大 APK，使用 search_classes_by_keyword 配合 package 过滤。",
            "response_size_bytes 字段在每个工具返回中可见，超过 5MB 时建议分批获取。",
        ],
    },

    "security_audit": {
        "name": "安全审计 (Security Audit)",
        "description": "系统检查 APK 中的安全风险，包括敏感 API、权限、硬编码密钥和网络安全配置。",
        "steps": [
            {
                "step": 1,
                "tool": "get_android_manifest",
                "params": {},
                "reason": "检查权限声明（INTERNET、READ_CONTACTS、ACCESS_FINE_LOCATION 等）和安全配置。",
            },
            {
                "step": 2,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "KeyStore", "search_in": "class"},
                "reason": "查找加密相关类（KeyStore, Cipher, SecretKey）——快速元数据搜索，无需缓存。",
            },
            {
                "step": 3,
                "tool": "search_native_methods",
                "params": {},
                "reason": "列出所有 native 方法，这些是绕过 Java 层分析的潜在攻击面。",
            },
            {
                "step": 4,
                "tool": "get_decompile_status",
                "params": {},
                "reason": "检查缓存率，决定是否可以执行代码内容搜索（cached_percentage > 20% 才适合）。",
            },
            {
                "step": 5,
                "tool": "search_classes_by_keyword",
                "params": {
                    "search_term": "password",
                    "search_in": "code",
                    "count": 20,
                },
                "reason": "在代码中搜索硬编码密码/密钥——需要步骤4确认缓存率充足后执行。",
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
                "reason": "查找明文 HTTP 通信——存在 http:// URL 说明数据可能被明文传输。",
                "condition": "cached_percentage > 20",
            },
        ],
        "tips": [
            "步骤5、6 需要代码缓存，先确认 get_decompile_status 的 cached_percentage > 20%。",
            "还需额外搜索：'secret', 'api_key', 'Bearer ', 'DexClassLoader', 'Runtime.exec'。",
            "对可疑类调用 get_class_source 查看完整实现。",
        ],
    },

    "network_analysis": {
        "name": "网络通信分析 (Network Analysis)",
        "description": "梳理 APK 的网络通信层：HTTP 客户端、API 接口、URL 端点、证书校验。",
        "steps": [
            {
                "step": 1,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "OkHttpClient", "search_in": "class"},
                "reason": "查找 OkHttp 客户端初始化类，通常包含拦截器和超时配置。",
            },
            {
                "step": 2,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "Retrofit", "search_in": "class"},
                "reason": "查找 Retrofit 实例创建，可以定位 API 接口注解和 baseUrl。",
            },
            {
                "step": 3,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "ApiService", "search_in": "class"},
                "reason": "查找 Retrofit API 接口类（常见命名：ApiService, ApiInterface, RetrofitService）。",
            },
            {
                "step": 4,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "Interceptor", "search_in": "class"},
                "reason": "查找请求拦截器——通常在此处添加 Authorization/Token 请求头。",
            },
            {
                "step": 5,
                "tool": "search_classes_by_keyword",
                "params": {
                    "search_term": "https://",
                    "search_in": "code",
                    "count": 30,
                },
                "reason": "搜索硬编码的 API 端点 URL——需要代码缓存。",
                "condition": "cached_percentage > 20",
            },
            {
                "step": 6,
                "tool": "search_classes_by_keyword",
                "params": {"search_term": "CertificatePinner", "search_in": "class"},
                "reason": "检查是否实现证书固定（Certificate Pinning）。",
            },
        ],
        "tips": [
            "找到 API 接口类后，用 get_class_source 查看所有 @GET/@POST/@PUT 注解。",
            "用 get_xrefs('class', class_name) 追踪网络类的调用方。",
            "检查 Manifest 中 android:usesCleartextTraffic 属性。",
        ],
    },

    "entry_points": {
        "name": "入口点分析 (Entry Points)",
        "description": "枚举所有 Android 组件入口点，分析生命周期方法和导出组件。",
        "steps": [
            {
                "step": 1,
                "tool": "get_android_manifest",
                "params": {},
                "reason": "获取所有组件声明：Activity、Service、BroadcastReceiver、ContentProvider。",
            },
            {
                "step": 2,
                "tool": "get_class_info",
                "params": {"class_name": "<主 Activity 类名，从步骤1获取>"},
                "reason": "查看类的继承关系、实现的接口和方法列表。",
            },
            {
                "step": 3,
                "tool": "batch_get_class_source",
                "params": {"class_names": ["<Activity1>", "<Activity2>", "<Service1>"]},
                "reason": "批量获取核心组件源码，比逐个调用效率更高。",
            },
            {
                "step": 4,
                "tool": "get_method_by_name",
                "params": {
                    "class_name": "<MainActivity>",
                    "method_name": "onCreate",
                },
                "reason": "深入分析关键生命周期方法实现。",
            },
            {
                "step": 5,
                "tool": "get_xrefs",
                "params": {
                    "ref_type": "class",
                    "class_name": "<MainActivity>",
                },
                "reason": "找出谁调用/启动了这个组件（Intent 来源追踪）。",
            },
        ],
        "tips": [
            "android:exported='true' 或带 <intent-filter> 的组件是外部攻击面。",
            "BroadcastReceiver.onReceive 要检查是否验证 Intent 来源。",
            "ContentProvider 要检查 readPermission/writePermission 是否设置。",
        ],
    },
}

# 关键词到计划的映射（用于模糊匹配）
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
    """根据分析目标关键词匹配推荐计划列表（可能多个）。"""
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
    根据分析目标推荐工具调用序列、参数和说明。

    Args:
        analysis_goal: 分析目标描述（自然语言），例如：
                       "I want to find network API endpoints"
                       "检查这个 APK 有没有安全漏洞"
                       "分析所有 Activity 的生命周期"
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: 包含推荐计划列表、每个计划的步骤序列和提示

    MCP Tool: suggest_analysis_plan
    Description: 根据分析目标推荐结构化的工具调用序列和分析计划
    """
    logger.info(f"suggest_analysis_plan: goal='{analysis_goal}'")

    if not analysis_goal or not analysis_goal.strip():
        return {
            "error": "INVALID_INPUT",
            "message": "analysis_goal 不能为空",
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

    # 未匹配到特定计划时，返回全部计划供 AI 选择
    is_fallback = len(matched_plan_ids) == len(_PLANS)

    return {
        "analysis_goal": analysis_goal,
        "recommended_plans": recommended_plans,
        "plan_count": len(recommended_plans),
        "is_fallback": is_fallback,
        "fallback_message": (
            "未能从目标描述中匹配到特定计划，已返回所有可用计划供参考。"
            if is_fallback
            else None
        ),
        "available_plan_ids": list(_PLANS.keys()),
        "usage_hint": (
            "按 steps 数组顺序调用对应工具。带 condition 字段的步骤需满足条件后再执行。"
            " 每个工具返回的 response_size_bytes 字段可用于判断是否需要分批处理。"
        ),
    }


def register_analysis_tools(mcp):
    """Register analysis planning tools with the MCP server."""
    mcp.tool()(suggest_analysis_plan)
    logger.info("Analysis tools registered: suggest_analysis_plan")
