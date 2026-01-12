"""
JADX MCP Server - Code Search Tools

This module provides MCP tools for searching through decompiled Android code,
enabling discovery of classes, methods, and keywords across the entire APK.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

from typing import Optional
from src.server.config import get_from_jadx
from src.PaginationUtils import PaginationUtils


async def get_method_by_name(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Fetch the source code of a method from a specific class.

    Args:
        class_name: Fully qualified class name
        method_name: Method name (can include signature)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Method source code and metadata

    MCP Tool: get_method_by_name
    Description: Retrieves specific method implementation from a known class
    """
    return await get_from_jadx(
        "method-by-name", {"class_name": class_name, "method_name": method_name}, instance_id=instance_id
    )


async def search_method_by_name(method_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Search for a method name across all classes.

    Args:
        method_name: Method name to search for (partial matching supported)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: List of all classes containing methods with matching names

    MCP Tool: search_method_by_name
    Description: Finds all occurrences of a method name across the APK
    """
    return await get_from_jadx("search-method", {"method_name": method_name}, instance_id=instance_id)


async def search_classes_by_keyword(
    search_term: str,
    package: str = "",
    search_in: str = "code",
    offset: int = 0,
    count: int = 20,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Search for classes containing a specific keyword with flexible filtering options.

    Args:
        search_term: The keyword or string to search for.
        package (optional): Package name to limit the search scope.
        search_in (optional): Comma-separated list of search scopes (class,method,field,code,comment).
        offset (optional): Starting index for pagination. Default: 0
        count (optional): Maximum number of results to return. Default: 20
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Paginated list of classes containing the search term

    MCP Tool: search_classes_by_keyword
    Description: Advanced search tool that finds classes matching a keyword with filtering
    """
    return await PaginationUtils.get_paginated_data(
        endpoint="search-classes-by-keyword",
        offset=offset,
        count=count,
        additional_params={
            "search_term": search_term,
            "package": package,
            "search_in": search_in,
        },
        data_extractor=lambda parsed: parsed.get("classes", []),
        fetch_function=lambda ep, params={}: get_from_jadx(ep, params, instance_id=instance_id),
    )
