"""
JADX MCP Server - Android Resource Analysis Tools

This module provides MCP tools for analyzing Android application resources
including the AndroidManifest.xml, strings, and resource files.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

from typing import Optional
from src.server.config import get_from_jadx
from src.PaginationUtils import PaginationUtils


async def get_android_manifest(instance_id: Optional[str] = None) -> dict:
    """
    Retrieve and return the AndroidManifest.xml content.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Parsed AndroidManifest.xml with permissions, activities, and metadata

    MCP Tool: get_android_manifest
    Description: Extracts app configuration, permissions, and component declarations
    """
    return await get_from_jadx("manifest", instance_id=instance_id)


async def get_strings(
    mode: str = "summary",
    query: Optional[str] = None,
    key: Optional[str] = None,
    locale: str = "values",
    offset: int = 0,
    limit: int = 50,
    instance_id: Optional[str] = None
) -> dict:
    """
    Get strings from APK with AI-friendly modes.

    Args:
        mode: Operation mode (summary|list|search|get). Default: summary
        query: Search keyword (required for mode=search)
        key: String key name (required for mode=get)
        locale: Locale variant like "values", "values-en". Default: values
        offset: Pagination offset for list mode. Default: 0
        limit: Results per page (max: 200). Default: 50
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Response from Java API with mode-specific structure

    MCP Tool: get_strings
    Description: AI-friendly strings API with summary, list, search, get modes
    """
    params = {
        "mode": mode,
        "locale": locale,
        "offset": offset,
        "limit": limit
    }
    
    # Add optional parameters only if provided
    if query is not None:
        params["query"] = query
    if key is not None:
        params["key"] = key
    
    response = await get_from_jadx("strings", params, instance_id=instance_id)
    return response


async def get_all_resource_file_names(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
    """
    Retrieve all resource files names that exist in application.

    Args:
        offset: Starting index for pagination (default: 0)
        count: Number of filenames to return (0 = all, default: 0)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Paginated list of all resource file paths in the APK

    MCP Tool: get_all_resource_file_names
    Description: Enumerates all resource files (layouts, drawables, etc.)
    """
    return await PaginationUtils.get_paginated_data(
        endpoint="list-all-resource-files-names",
        offset=offset,
        count=count,
        data_extractor=lambda parsed: parsed.get("files", []),
        fetch_function=lambda ep, params={}: get_from_jadx(ep, params, instance_id=instance_id)
    )


async def get_resource_file(resource_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Retrieve resource file content.

    NOTE: Some APKs use resource obfuscation (e.g., ResourceGuard), which may remove or rename
    resource files like res/layout/*.xml. Use get_all_resource_file_names first to check
    which resources exist. Very large files (e.g., strings.xml with 15000+ entries) may timeout.

    Args:
        resource_name: Path to the resource file (e.g., res/layout/activity_main.xml)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contents of the specified resource file

    MCP Tool: get_resource_file
    Description: Fetches content of any resource file by path
    """
    return await get_from_jadx("get-resource-file", {"file_name": resource_name}, instance_id=instance_id)
