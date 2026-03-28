"""
JADX MCP Server - Annotation, Bookmark and Tag Tools

协作工作区 Phase 1：注释、书签、标签的持久化存储工具。
数据存储于 JADX 插件侧 SQLite 数据库（~/.jadx-ai-mcp/annotations.db）。

Author: JADX-AI-MCP Contributors
License: See LICENSE file
"""

from typing import Optional
from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("annotation_tools")


# ==================== 注释工具 ====================

async def add_annotation(
    target_type: str,
    target_name: str,
    content: str,
    author: str = "anonymous",
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    为指定目标（类/方法/字段）添加文字注释，并持久化至 SQLite。

    Args:
        target_type: 目标类型，如 "class"、"method"、"field"
        target_name: 目标全限定名，如 "com.example.MainActivity" 或 "com.example.Foo#bar()"
        content: 注释内容
        author: 作者名（默认 "anonymous"）
        apk_hash: APK 哈希标识（留空则由插件自动推断当前打开文件）
        instance_id: 可选，目标 JADX 实例名

    Returns:
        dict: { success, id, target_type, target_name, apk_hash }

    MCP Tool: add_annotation
    Description: 为反编译代码元素添加持久化注释，支持协作标注
    """
    body = {
        "target_type": target_type,
        "target_name": target_name,
        "content": content,
        "author": author,
    }
    if apk_hash:
        body["apk_hash"] = apk_hash

    logger.info(f"add_annotation: type={target_type} name={target_name} author={author}")
    return await get_from_jadx(
        "annotations",
        instance_id=instance_id,
        method="POST",
        json_body=body,
    )


async def get_annotations(
    target_type: Optional[str] = None,
    target_name: Optional[str] = None,
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    查询当前 APK 的注释列表。

    Args:
        target_type: 按目标类型过滤（可选）
        target_name: 按目标名称过滤（可选）
        apk_hash: 按 APK 哈希过滤（留空则使用当前打开的 APK）
        instance_id: 可选，目标 JADX 实例名

    Returns:
        dict: { annotations: [...], count }

    MCP Tool: get_annotations
    Description: 查询指定目标或当前 APK 的所有注释
    """
    params: dict = {}
    if target_type:
        params["target_type"] = target_type
    if target_name:
        params["target_name"] = target_name
    if apk_hash:
        params["apk_hash"] = apk_hash

    logger.info(f"get_annotations: params={params}")
    return await get_from_jadx("annotations", params=params, instance_id=instance_id)


# ==================== 书签工具 ====================

async def add_bookmark(
    target_type: str,
    target_name: str,
    label: str,
    note: str = "",
    author: str = "anonymous",
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    为指定目标添加书签（带标签和备注），并持久化至 SQLite。

    Args:
        target_type: 目标类型，如 "class"、"method"、"field"
        target_name: 目标全限定名
        label: 书签标签名，如 "入口点"、"加密逻辑"
        note: 可选备注
        author: 作者名（默认 "anonymous"）
        apk_hash: APK 哈希标识（留空则自动推断）
        instance_id: 可选，目标 JADX 实例名

    Returns:
        dict: { success, id, label, target_type, target_name, apk_hash }

    MCP Tool: add_bookmark
    Description: 为重要代码位置创建带标签的书签，便于快速导航
    """
    body = {
        "target_type": target_type,
        "target_name": target_name,
        "label": label,
        "note": note,
        "author": author,
    }
    if apk_hash:
        body["apk_hash"] = apk_hash

    logger.info(f"add_bookmark: type={target_type} name={target_name} label={label}")
    return await get_from_jadx(
        "bookmarks",
        instance_id=instance_id,
        method="POST",
        json_body=body,
    )


async def list_bookmarks(
    target_type: Optional[str] = None,
    target_name: Optional[str] = None,
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    查询当前 APK 的书签列表。

    Args:
        target_type: 按目标类型过滤（可选）
        target_name: 按目标名称过滤（可选）
        apk_hash: 按 APK 哈希过滤（留空则使用当前打开的 APK）
        instance_id: 可选，目标 JADX 实例名

    Returns:
        dict: { bookmarks: [...], count }

    MCP Tool: list_bookmarks
    Description: 列出当前 APK 的所有书签
    """
    params: dict = {}
    if target_type:
        params["target_type"] = target_type
    if target_name:
        params["target_name"] = target_name
    if apk_hash:
        params["apk_hash"] = apk_hash

    logger.info(f"list_bookmarks: params={params}")
    return await get_from_jadx("bookmarks", params=params, instance_id=instance_id)


# ==================== 标签工具 ====================

async def add_tag(
    target_type: str,
    target_name: str,
    tag: str,
    author: str = "anonymous",
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    为指定目标添加分类标签，并持久化至 SQLite。

    Args:
        target_type: 目标类型，如 "class"、"method"、"field"
        target_name: 目标全限定名
        tag: 标签字符串，如 "crypto"、"network"、"entry-point"
        author: 作者名（默认 "anonymous"）
        apk_hash: APK 哈希标识（留空则自动推断）
        instance_id: 可选，目标 JADX 实例名

    Returns:
        dict: { success, id, tag, target_type, target_name, apk_hash }

    MCP Tool: add_tag
    Description: 为代码元素添加分类标签，支持多维度代码组织
    """
    body = {
        "target_type": target_type,
        "target_name": target_name,
        "tag": tag,
        "author": author,
    }
    if apk_hash:
        body["apk_hash"] = apk_hash

    logger.info(f"add_tag: type={target_type} name={target_name} tag={tag}")
    return await get_from_jadx(
        "tags",
        instance_id=instance_id,
        method="POST",
        json_body=body,
    )


async def get_tags(
    target_type: Optional[str] = None,
    target_name: Optional[str] = None,
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    查询当前 APK 的标签列表。

    Args:
        target_type: 按目标类型过滤（可选）
        target_name: 按目标名称过滤（可选）
        apk_hash: 按 APK 哈希过滤（留空则使用当前打开的 APK）
        instance_id: 可选，目标 JADX 实例名

    Returns:
        dict: { tags: [...], count }

    MCP Tool: get_tags
    Description: 查询当前 APK 所有分类标签
    """
    params: dict = {}
    if target_type:
        params["target_type"] = target_type
    if target_name:
        params["target_name"] = target_name
    if apk_hash:
        params["apk_hash"] = apk_hash

    logger.info(f"get_tags: params={params}")
    return await get_from_jadx("tags", params=params, instance_id=instance_id)


# ==================== 汇总工具 ====================

async def get_analysis_summary(
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    汇总当前 APK 的所有分析笔记（注释 + 书签 + 标签）。

    适合在开始新的分析会话时，快速恢复之前的分析上下文。

    Args:
        apk_hash: APK 哈希标识（留空则使用当前打开的 APK）
        instance_id: 可选，目标 JADX 实例名

    Returns:
        dict: {
            apk_hash,
            annotations: [...], annotations_count,
            bookmarks: [...],   bookmarks_count,
            tags: [...],        tags_count
        }

    MCP Tool: get_analysis_summary
    Description: 一次性获取当前 APK 的完整分析记录，用于恢复分析上下文
    """
    params: dict = {}
    if apk_hash:
        params["apk_hash"] = apk_hash

    logger.info(f"get_analysis_summary: apk_hash={apk_hash}")
    return await get_from_jadx("analysis-notes", params=params, instance_id=instance_id)


# ==================== 模块级引用（避免 register 内被遮蔽）====================

_add_annotation = add_annotation
_get_annotations = get_annotations
_add_bookmark = add_bookmark
_list_bookmarks = list_bookmarks
_add_tag = add_tag
_get_tags = get_tags
_get_analysis_summary = get_analysis_summary


def register_annotation_tools(mcp, with_busy_check):
    """向 MCP Server 注册注释/书签/标签工具"""

    @mcp.tool()
    @with_busy_check
    async def add_annotation(
        target_type: str,
        target_name: str,
        content: str,
        author: str = "anonymous",
        apk_hash: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """为反编译代码元素（类/方法/字段）添加持久化文字注释。

        注释存储于本地 SQLite 数据库，跨会话保留。

        Args:
            target_type: 目标类型："class"、"method" 或 "field"
            target_name: 目标全限定名（如 "com.example.MainActivity"）
            content: 注释内容
            author: 作者名（默认 "anonymous"）
            apk_hash: APK 哈希（留空则自动使用当前打开的 APK）
            instance_id: 可选，目标 JADX 实例名
        """
        return await _add_annotation(
            target_type, target_name, content,
            author=author, apk_hash=apk_hash, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def get_annotations(
        target_type: Optional[str] = None,
        target_name: Optional[str] = None,
        apk_hash: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """查询当前 APK 的注释列表，支持按 target_type 或 target_name 过滤。

        Args:
            target_type: 按目标类型过滤（可选）
            target_name: 按目标名称过滤（可选）
            apk_hash: 按 APK 哈希过滤（留空则使用当前打开的 APK）
            instance_id: 可选，目标 JADX 实例名
        """
        return await _get_annotations(
            target_type=target_type, target_name=target_name,
            apk_hash=apk_hash, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def add_bookmark(
        target_type: str,
        target_name: str,
        label: str,
        note: str = "",
        author: str = "anonymous",
        apk_hash: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """为重要代码位置创建带标签的持久化书签。

        书签存储于本地 SQLite 数据库，跨会话保留。

        Args:
            target_type: 目标类型："class"、"method" 或 "field"
            target_name: 目标全限定名
            label: 书签标签，如 "入口点"、"加密逻辑"、"可疑代码"
            note: 可选备注说明
            author: 作者名（默认 "anonymous"）
            apk_hash: APK 哈希（留空则自动使用当前打开的 APK）
            instance_id: 可选，目标 JADX 实例名
        """
        return await _add_bookmark(
            target_type, target_name, label,
            note=note, author=author, apk_hash=apk_hash, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def list_bookmarks(
        target_type: Optional[str] = None,
        target_name: Optional[str] = None,
        apk_hash: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """列出当前 APK 的所有书签，支持按 target_type 或 target_name 过滤。

        Args:
            target_type: 按目标类型过滤（可选）
            target_name: 按目标名称过滤（可选）
            apk_hash: 按 APK 哈希过滤（留空则使用当前打开的 APK）
            instance_id: 可选，目标 JADX 实例名
        """
        return await _list_bookmarks(
            target_type=target_type, target_name=target_name,
            apk_hash=apk_hash, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def add_tag(
        target_type: str,
        target_name: str,
        tag: str,
        author: str = "anonymous",
        apk_hash: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """为代码元素添加分类标签，支持多维度代码组织。

        标签存储于本地 SQLite 数据库，跨会话保留。

        Args:
            target_type: 目标类型："class"、"method" 或 "field"
            target_name: 目标全限定名
            tag: 标签字符串，如 "crypto"、"network"、"entry-point"、"obfuscated"
            author: 作者名（默认 "anonymous"）
            apk_hash: APK 哈希（留空则自动使用当前打开的 APK）
            instance_id: 可选，目标 JADX 实例名
        """
        return await _add_tag(
            target_type, target_name, tag,
            author=author, apk_hash=apk_hash, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def get_tags(
        target_type: Optional[str] = None,
        target_name: Optional[str] = None,
        apk_hash: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """查询当前 APK 的标签列表，支持按 target_type 或 target_name 过滤。

        Args:
            target_type: 按目标类型过滤（可选）
            target_name: 按目标名称过滤（可选）
            apk_hash: 按 APK 哈希过滤（留空则使用当前打开的 APK）
            instance_id: 可选，目标 JADX 实例名
        """
        return await _get_tags(
            target_type=target_type, target_name=target_name,
            apk_hash=apk_hash, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def get_analysis_summary(
        apk_hash: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """获取当前 APK 的完整分析记录（注释 + 书签 + 标签）。

        适合在开始新的分析会话时，一次性恢复之前的分析上下文。

        Args:
            apk_hash: APK 哈希（留空则使用当前打开的 APK）
            instance_id: 可选，目标 JADX 实例名

        Returns:
            dict with: apk_hash, annotations, bookmarks, tags, and respective counts
        """
        return await _get_analysis_summary(apk_hash=apk_hash, instance_id=instance_id)
