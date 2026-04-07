"""
JADX MCP Server - Annotation, Bookmark and Tag Tools

Collaborative workspace Phase 1: persistent storage tools for annotations, bookmarks, and tags.
Data is stored in the JADX plugin-side SQLite database (~/.jadx-ai-mcp/annotations.db).

Author: JADX-AI-MCP Contributors
License: See LICENSE file
"""

from typing import Optional
from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("annotation_tools")


# ==================== Annotation Tools ====================

async def add_annotation(
    target_type: str,
    target_name: str,
    content: str,
    author: str = "anonymous",
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Add a text annotation to the specified target (class/method/field) and persist it to SQLite.

    Args:
        target_type: Target type, e.g. "class", "method", "field"
        target_name: Fully qualified target name, e.g. "com.example.MainActivity" or "com.example.Foo#bar()"
        content: Annotation content
        author: Author name (default "anonymous")
        apk_hash: APK hash identifier (leave empty to let the plugin auto-infer from the currently open file)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: { success, id, target_type, target_name, apk_hash }

    MCP Tool: add_annotation
    Description: Add persistent annotations to decompiled code elements, supporting collaborative annotation
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
    Query the annotation list for the current APK.

    Args:
        target_type: Filter by target type (optional)
        target_name: Filter by target name (optional)
        apk_hash: Filter by APK hash (leave empty to use the currently open APK)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: { annotations: [...], count }

    MCP Tool: get_annotations
    Description: Query all annotations for the specified target or current APK
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


# ==================== Bookmark Tools ====================

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
    Add a bookmark (with label and note) to the specified target and persist it to SQLite.

    Args:
        target_type: Target type, e.g. "class", "method", "field"
        target_name: Fully qualified target name
        label: Bookmark label name, e.g. "entry point", "crypto logic"
        note: Optional note
        author: Author name (default "anonymous")
        apk_hash: APK hash identifier (leave empty to auto-infer)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: { success, id, label, target_type, target_name, apk_hash }

    MCP Tool: add_bookmark
    Description: Create labeled bookmarks for important code locations to enable quick navigation
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
    Query the bookmark list for the current APK.

    Args:
        target_type: Filter by target type (optional)
        target_name: Filter by target name (optional)
        apk_hash: Filter by APK hash (leave empty to use the currently open APK)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: { bookmarks: [...], count }

    MCP Tool: list_bookmarks
    Description: List all bookmarks for the current APK
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


# ==================== Tag Tools ====================

async def add_tag(
    target_type: str,
    target_name: str,
    tag: str,
    author: str = "anonymous",
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Add a classification tag to the specified target and persist it to SQLite.

    Args:
        target_type: Target type, e.g. "class", "method", "field"
        target_name: Fully qualified target name
        tag: Tag string, e.g. "crypto", "network", "entry-point"
        author: Author name (default "anonymous")
        apk_hash: APK hash identifier (leave empty to auto-infer)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: { success, id, tag, target_type, target_name, apk_hash }

    MCP Tool: add_tag
    Description: Add classification tags to code elements, supporting multi-dimensional code organization
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
    Query the tag list for the current APK.

    Args:
        target_type: Filter by target type (optional)
        target_name: Filter by target name (optional)
        apk_hash: Filter by APK hash (leave empty to use the currently open APK)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: { tags: [...], count }

    MCP Tool: get_tags
    Description: Query all classification tags for the current APK
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


# ==================== Delete Tools ====================

async def delete_annotation(
    annotation_id: int,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Delete an annotation by its ID.

    Args:
        annotation_id: The numeric ID of the annotation to delete
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: { success, deleted_id }

    MCP Tool: delete_annotation
    Description: Delete an annotation by ID
    """
    logger.info(f"delete_annotation: id={annotation_id}")
    return await get_from_jadx(
        f"annotations/{annotation_id}",
        instance_id=instance_id,
        method="DELETE",
    )


async def delete_bookmark(
    bookmark_id: int,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Delete a bookmark by its ID.

    Args:
        bookmark_id: The numeric ID of the bookmark to delete
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: { success, deleted_id }

    MCP Tool: delete_bookmark
    Description: Delete a bookmark by ID
    """
    logger.info(f"delete_bookmark: id={bookmark_id}")
    return await get_from_jadx(
        f"bookmarks/{bookmark_id}",
        instance_id=instance_id,
        method="DELETE",
    )


async def delete_tag(
    tag_id: int,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Delete a tag by its ID.

    Args:
        tag_id: The numeric ID of the tag to delete
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: { success, deleted_id }

    MCP Tool: delete_tag
    Description: Delete a tag by ID
    """
    logger.info(f"delete_tag: id={tag_id}")
    return await get_from_jadx(
        f"tags/{tag_id}",
        instance_id=instance_id,
        method="DELETE",
    )


# ==================== Summary Tools ====================

async def get_analysis_summary(
    apk_hash: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Summarize all analysis notes (annotations + bookmarks + tags) for the current APK.

    Useful for quickly restoring previous analysis context at the start of a new analysis session.

    Args:
        apk_hash: APK hash identifier (leave empty to use the currently open APK)
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: {
            apk_hash,
            annotations: [...], annotations_count,
            bookmarks: [...],   bookmarks_count,
            tags: [...],        tags_count
        }

    MCP Tool: get_analysis_summary
    Description: Retrieve the complete analysis record for the current APK in one call, used to restore analysis context
    """
    params: dict = {}
    if apk_hash:
        params["apk_hash"] = apk_hash

    logger.info(f"get_analysis_summary: apk_hash={apk_hash}")
    return await get_from_jadx("analysis-notes", params=params, instance_id=instance_id)


# ==================== Module-level references (to avoid shadowing inside register) ====================

_add_annotation = add_annotation
_get_annotations = get_annotations
_delete_annotation = delete_annotation
_add_bookmark = add_bookmark
_list_bookmarks = list_bookmarks
_delete_bookmark = delete_bookmark
_add_tag = add_tag
_get_tags = get_tags
_delete_tag = delete_tag
_get_analysis_summary = get_analysis_summary


def register_annotation_tools(mcp, with_busy_check):
    """Register annotation/bookmark/tag tools with the MCP Server"""

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
        """Add persistent text annotations to decompiled code elements (class/method/field).

        Annotations are stored in a local SQLite database and persist across sessions.

        Args:
            target_type: Target type: "class", "method", or "field"
            target_name: Fully qualified target name (e.g. "com.example.MainActivity")
            content: Annotation content
            author: Author name (default "anonymous")
            apk_hash: APK hash (leave empty to auto-use the currently open APK)
            instance_id: Optional. Target JADX instance name
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
        """Query the annotation list for the current APK, with optional filtering by target_type or target_name.

        Args:
            target_type: Filter by target type (optional)
            target_name: Filter by target name (optional)
            apk_hash: Filter by APK hash (leave empty to use the currently open APK)
            instance_id: Optional. Target JADX instance name
        """
        return await _get_annotations(
            target_type=target_type, target_name=target_name,
            apk_hash=apk_hash, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def delete_annotation(
        annotation_id: int,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Delete an annotation by its ID.

        Args:
            annotation_id: The numeric ID of the annotation to delete (from get_annotations results)
            instance_id: Optional. Target JADX instance name
        """
        return await _delete_annotation(annotation_id, instance_id=instance_id)

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
        """Create persistent labeled bookmarks for important code locations.

        Bookmarks are stored in a local SQLite database and persist across sessions.

        Args:
            target_type: Target type: "class", "method", or "field"
            target_name: Fully qualified target name
            label: Bookmark label, e.g. "entry point", "crypto logic", "suspicious code"
            note: Optional note description
            author: Author name (default "anonymous")
            apk_hash: APK hash (leave empty to auto-use the currently open APK)
            instance_id: Optional. Target JADX instance name
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
        """List all bookmarks for the current APK, with optional filtering by target_type or target_name.

        Args:
            target_type: Filter by target type (optional)
            target_name: Filter by target name (optional)
            apk_hash: Filter by APK hash (leave empty to use the currently open APK)
            instance_id: Optional. Target JADX instance name
        """
        return await _list_bookmarks(
            target_type=target_type, target_name=target_name,
            apk_hash=apk_hash, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def delete_bookmark(
        bookmark_id: int,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Delete a bookmark by its ID.

        Args:
            bookmark_id: The numeric ID of the bookmark to delete (from list_bookmarks results)
            instance_id: Optional. Target JADX instance name
        """
        return await _delete_bookmark(bookmark_id, instance_id=instance_id)

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
        """Add classification tags to code elements, supporting multi-dimensional code organization.

        Tags are stored in a local SQLite database and persist across sessions.

        Args:
            target_type: Target type: "class", "method", or "field"
            target_name: Fully qualified target name
            tag: Tag string, e.g. "crypto", "network", "entry-point", "obfuscated"
            author: Author name (default "anonymous")
            apk_hash: APK hash (leave empty to auto-use the currently open APK)
            instance_id: Optional. Target JADX instance name
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
        """Query the tag list for the current APK, with optional filtering by target_type or target_name.

        Args:
            target_type: Filter by target type (optional)
            target_name: Filter by target name (optional)
            apk_hash: Filter by APK hash (leave empty to use the currently open APK)
            instance_id: Optional. Target JADX instance name
        """
        return await _get_tags(
            target_type=target_type, target_name=target_name,
            apk_hash=apk_hash, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def delete_tag(
        tag_id: int,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Delete a tag by its ID.

        Args:
            tag_id: The numeric ID of the tag to delete (from get_tags results)
            instance_id: Optional. Target JADX instance name
        """
        return await _delete_tag(tag_id, instance_id=instance_id)

    @mcp.tool()
    @with_busy_check
    async def get_analysis_summary(
        apk_hash: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Retrieve the complete analysis record (annotations + bookmarks + tags) for the current APK.

        Useful for restoring previous analysis context in one call at the start of a new analysis session.

        Args:
            apk_hash: APK hash (leave empty to use the currently open APK)
            instance_id: Optional. Target JADX instance name

        Returns:
            dict with: apk_hash, annotations, bookmarks, tags, and respective counts
        """
        return await _get_analysis_summary(apk_hash=apk_hash, instance_id=instance_id)
