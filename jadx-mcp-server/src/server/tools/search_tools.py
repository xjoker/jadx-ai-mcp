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
from src.server.logging_config import get_logger

logger = get_logger("search_tools")


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
    logger.info(f"get_method_by_name: class={class_name}, method={method_name}, instance={instance_id}")
    result = await get_from_jadx(
        "method-by-name", {"class_name": class_name, "method_name": method_name}, instance_id=instance_id
    )
    if "error" in result:
        logger.warning(f"get_method_by_name failed: {result.get('error')}")
    return result


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
    logger.info(f"search_method_by_name: method={method_name}, instance={instance_id}")
    try:
        result = await get_from_jadx("search-method", {"method_name": method_name}, instance_id=instance_id)
        if "error" in result:
            logger.warning(f"search_method_by_name error response: {result.get('error')}")
        else:
            match_count = len(result.get("methods", result.get("classes", [])))
            logger.info(f"search_method_by_name: found {match_count} matches")
        return result
    except Exception as e:
        logger.error(f"search_method_by_name exception: {type(e).__name__}: {e}")
        return {"error": f"Unexpected error: {e}"}


async def batch_get_method_by_name(methods: list[str], instance_id: Optional[str] = None) -> dict:
    """
    Fetch multiple method sources in a single request.
    
    This reduces MCP interaction overhead when analyzing multiple methods.
    Maximum 20 methods per request.

    Args:
        methods: List of "class_name:method_name" pairs (e.g., ["com.example.A:methodA", "com.example.B:methodB"])
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains 'methods' array with class_name, method_name, found status, and code/error for each,
              plus 'total' and 'found' counts

    MCP Tool: batch_get_method_by_name
    Description: Batch retrieval of method sources using class:method format
    """
    # Join method pairs with comma for the API
    methods_str = ",".join(methods)
    return await get_from_jadx("batch-method-by-name", {"methods": methods_str}, instance_id=instance_id)


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


async def get_method_signature(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Get structured signature information for a method including return type and parameters.

    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        method_name: Method name to get signature for
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Structured method signature containing:
            - class_name: Containing class name
            - method_name: Method name
            - overloads: Number of overloaded versions
            - signatures: List of signature objects with:
                - return_type: Return type
                - parameters: List of {name, type} objects
                - access_flags: Access modifiers
                - is_constructor: Whether this is a constructor

    MCP Tool: get_method_signature
    Description: Retrieves structured method signature for hook code generation
    """
    logger.info(f"get_method_signature: class={class_name}, method={method_name}, instance={instance_id}")
    result = await get_from_jadx(
        "method-signature", {"class_name": class_name, "method_name": method_name}, instance_id=instance_id
    )
    if "error" in result:
        logger.warning(f"get_method_signature error: {result.get('error')}")
    return result


async def get_method_callees(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Get methods called by the specified method (callees analysis).

    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        method_name: Method name to analyze
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Analysis result containing:
            - class_name: Containing class name
            - method_name: Method name
            - callees_count: Number of potential callees found
            - callees: List of "receiver.method" patterns found in code
            - note: Warning about pattern-based analysis accuracy

    MCP Tool: get_method_callees
    Description: Analyzes method code to identify called methods (pattern-based)
    """
    logger.info(f"get_method_callees: class={class_name}, method={method_name}, instance={instance_id}")
    result = await get_from_jadx(
        "method-callees", {"class_name": class_name, "method_name": method_name}, instance_id=instance_id
    )
    if "error" in result:
        logger.warning(f"get_method_callees error: {result.get('error')}")
    return result
