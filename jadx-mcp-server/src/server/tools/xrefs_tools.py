"""
JADX MCP Server - Cross-Reference Analysis Tools

This module provides MCP tools for finding cross-references (xrefs) to classes,
methods, and fields in decompiled Android applications. Essential for understanding
code flow and dependency analysis during reverse engineering.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

from typing import Optional
from src.server.config import get_from_jadx
from src.PaginationUtils import PaginationUtils


async def get_xrefs_to_class(class_name: str, offset: int = 0, count: int = 20, instance_id: Optional[str] = None) -> dict:
    """
    Find all references to a class (including constructor calls).

    Args:
        class_name: Fully qualified class name
        offset: Starting index for pagination (default: 0)
        count: Number of references to return (default: 20)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Paginated list of locations where the class is referenced

    MCP Tool: get_xrefs_to_class
    Description: Finds all code locations that instantiate or reference a class
    """
    return await PaginationUtils.get_paginated_data(
        endpoint="xrefs-to-class",
        offset=offset,
        count=count,
        additional_params={"class_name": class_name},
        data_extractor=lambda parsed: parsed.get("references", []),
        fetch_function=lambda ep, params={}: get_from_jadx(ep, params, instance_id=instance_id)
    )


async def get_xrefs_to_method(class_name: str, method_name: str, offset: int = 0, count: int = 20, instance_id: Optional[str] = None) -> dict:
    """
    Find all references to a method (includes overrides).

    Args:
        class_name: Fully qualified class name containing the method
        method_name: Method name (can include signature)
        offset: Starting index for pagination (default: 0)
        count: Number of references to return (default: 20)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Paginated list of locations where the method is called

    MCP Tool: get_xrefs_to_method
    Description: Tracks all invocations of a specific method across the APK
    """
    return await PaginationUtils.get_paginated_data(
        endpoint="xrefs-to-method",
        offset=offset,
        count=count,
        additional_params={"class_name": class_name, "method_name": method_name},
        data_extractor=lambda parsed: parsed.get("references", []),
        fetch_function=lambda ep, params={}: get_from_jadx(ep, params, instance_id=instance_id)
    )


async def get_xrefs_to_field(class_name: str, field_name: str, offset: int = 0, count: int = 20, instance_id: Optional[str] = None) -> dict:
    """
    Find all references to a field.

    Args:
        class_name: Fully qualified class name containing the field
        field_name: Field/variable name
        offset: Starting index for pagination (default: 0)
        count: Number of references to return (default: 20)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Paginated list of locations where the field is accessed

    MCP Tool: get_xrefs_to_field
    Description: Identifies all read/write operations on a class field
    """
    return await PaginationUtils.get_paginated_data(
        endpoint="xrefs-to-field",
        offset=offset,
        count=count,
        additional_params={"class_name": class_name, "field_name": field_name},
        data_extractor=lambda parsed: parsed.get("references", []),
        fetch_function=lambda ep, params={}: get_from_jadx(ep, params, instance_id=instance_id)
    )


async def batch_get_xrefs(targets: list[str], instance_id: Optional[str] = None) -> dict:
    """
    Fetch cross-references for multiple targets in a single request.

    This reduces MCP interaction overhead when analyzing multiple related classes/methods/fields.
    Maximum 10 targets per request.

    Args:
        targets: List of "type:class[:member]" strings. Examples:
            - "class:com.example.MyClass"
            - "method:com.example.MyClass:myMethod"
            - "field:com.example.MyClass:myField"
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains 'results' array with target, found status, xrefs_count, and xrefs for each,
              plus 'total' count

    MCP Tool: batch_get_xrefs
    Description: Batch retrieval of cross-references for classes, methods, and fields
    """
    targets_str = ",".join(targets)
    return await get_from_jadx("batch-xrefs", {"targets": targets_str}, instance_id=instance_id)


def register_xrefs_tools(mcp, with_busy_check):
    """Register cross-reference tools to MCP Server"""

    @mcp.tool()
    @with_busy_check
    async def get_xrefs(
        target_type: str,
        class_name: str,
        member_name: str = "",
        offset: int = 0,
        count: int = 20,
        instance_id: Optional[str] = None
    ) -> dict:
        """Unified cross-reference (xrefs) finder for classes, methods, and fields.

        Args:
            target_type: Type of target to find xrefs for: "class" | "method" | "field"
            class_name: Fully qualified class name (e.g., 'com.example.Helper')
            member_name: Method or field name (required for method/field, ignored for class)
            offset: Pagination offset. Default: 0
            count: Max results. Default: 20
            instance_id: Target JADX instance name

        Returns:
            dict: {xrefs: [{from_class, from_method, line}, ...], total: int}

        Examples:
            # Find references to a class
            get_xrefs("class", "com.example.Helper")

            # Find references to a method
            get_xrefs("method", "com.example.MyClass", "myMethod")

            # Find references to a field
            get_xrefs("field", "com.example.MyClass", "myField")
        """
        target_type_lower = target_type.lower()

        if target_type_lower == "class":
            return await get_xrefs_to_class(class_name, offset, count, instance_id=instance_id)
        elif target_type_lower == "method":
            if not member_name:
                return {"error": "member_name required for method xrefs"}
            return await get_xrefs_to_method(class_name, member_name, offset, count, instance_id=instance_id)
        elif target_type_lower == "field":
            if not member_name:
                return {"error": "member_name required for field xrefs"}
            return await get_xrefs_to_field(class_name, member_name, offset, count, instance_id=instance_id)
        else:
            return {"error": f"Invalid target_type: {target_type}. Use: class, method, field"}

    @mcp.tool(name="batch_get_xrefs")
    @with_busy_check
    async def batch_get_xrefs_tool(targets: list[str], instance_id: Optional[str] = None) -> dict:
        """Fetch cross-references for multiple targets in a single request.

        Args:
            targets: List of "type:class[:member]" strings.
            instance_id: Optional. Target JADX instance name. Uses default if not specified.
        """
        return await batch_get_xrefs(targets, instance_id=instance_id)
