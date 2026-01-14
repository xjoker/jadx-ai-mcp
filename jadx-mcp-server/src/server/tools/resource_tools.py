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


async def get_strings(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
    """
    Retrieve strings.xml content and available locale variants.

    Args:
        offset: (Deprecated) Was used for pagination, now returns single file
        count: (Deprecated) Was used for pagination, now returns single file
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains 'content' (strings.xml content), 'loaded_variant', 
              'available_variants' (list of all locale files)

    MCP Tool: get_strings
    Description: Extracts default strings.xml and lists available locale variants
    """
    # New format: directly return Java response (no pagination extraction)
    response = await get_from_jadx("strings", {}, instance_id=instance_id)
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

    Args:
        resource_name: Path to the resource file (e.g., res/layout/activity_main.xml)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contents of the specified resource file

    MCP Tool: get_resource_file
    Description: Fetches content of any resource file by path
    """
    return await get_from_jadx("get-resource-file", {"file_name": resource_name}, instance_id=instance_id)
