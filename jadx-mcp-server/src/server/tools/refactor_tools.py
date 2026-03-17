"""
JADX MCP Server - Code Refactoring Tools

This module provides MCP tools for refactoring decompiled Android code,
including renaming classes, methods, fields, and packages to improve
code readability during reverse engineering analysis.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

from typing import Optional
from src.server.config import get_from_jadx


async def rename_class(class_name: str, new_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Renames a specific class.
    
    NOTE: This operation triggers ClassCacheManager reload with 30s global cooldown.
    Rapid successive renames will be debounced.

    Args:
        class_name: Fully qualified current class name
        new_name: New name for the class (without package)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Confirmation of rename operation

    MCP Tool: rename_class
    Description: Refactors class name across the entire decompiled codebase
    """
    return await get_from_jadx("rename-class", {"class_name": class_name, "new_name": new_name}, instance_id=instance_id)


async def rename_method(class_name: str, method_name: str, new_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Renames a specific method.

    NOTE: This operation triggers ClassCacheManager reload with 30s global cooldown.
    Rapid successive renames will be debounced.

    Args:
        class_name: Fully qualified class name containing the method
        method_name: Current method name (can include signature)
        new_name: New name for the method
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Confirmation of rename operation

    MCP Tool: rename_method
    Description: Refactors method name and updates all call sites
    """
    return await get_from_jadx("rename-method", {
        "class_name": class_name,
        "method_name": method_name,
        "new_name": new_name
    }, instance_id=instance_id)


async def rename_field(class_name: str, field_name: str, new_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Renames a specific field.
    
    NOTE: This operation triggers ClassCacheManager reload with 30s global cooldown.
    Rapid successive renames will be debounced.

    Args:
        class_name: Fully qualified class name containing the field
        field_name: Current field name
        new_name: New name for the field
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Confirmation of rename operation

    MCP Tool: rename_field
    Description: Refactors field name and updates all references
    """
    return await get_from_jadx("rename-field", {
        "class_name": class_name,
        "field_name": field_name,
        "new_field_name": new_name
    }, instance_id=instance_id)


async def rename_package(old_package_name: str, new_package_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Renames a package and all its classes.
    
    NOTE: This operation triggers ClassCacheManager reload with 30s global cooldown.
    Rapid successive renames will be debounced.

    Args:
        old_package_name: Current package name (e.g., com.example.old)
        new_package_name: New package name (e.g., com.example.new)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Confirmation of rename operation

    MCP Tool: rename_package
    Description: Refactors entire package structure and class namespaces
    """
    return await get_from_jadx("rename-package", {
        "old_package_name": old_package_name,
        "new_package_name": new_package_name
    }, instance_id=instance_id)


def register_refactor_tools(mcp, with_busy_check):
    """Register refactoring tools to MCP Server"""

    @mcp.tool()
    @with_busy_check
    async def rename(
        target_type: str,
        old_name: str,
        new_name: str,
        class_name: str = "",
        dry_run: bool = False,
        instance_id: Optional[str] = None
    ) -> dict:
        """Unified rename tool for classes, methods, fields, and packages.

        Args:
            target_type: Type of target to rename: "class" | "method" | "field" | "package"
            old_name: Current name (fully qualified for class/package, simple name for method/field)
            new_name: New name (simple name)
            class_name: Required for method/field - the class containing the member
            dry_run: If True, verify the target exists and return impact preview without renaming
            instance_id: Target JADX instance name

        Returns:
            dict: {success: bool, message: str, renamed_count: int (for package only)}
            dry_run: {dry_run: true, target_exists: bool, target_info: {...}}

        Examples:
            # Preview rename
            rename("class", "com.example.OldClass", "NewClass", dry_run=True)

            # Rename class
            rename("class", "com.example.OldClass", "NewClass")

            # Rename method
            rename("method", "oldMethod", "newMethod", class_name="com.example.MyClass")

            # Rename field
            rename("field", "oldField", "newField", class_name="com.example.MyClass")

            # Rename package
            rename("package", "com.example.old", "com.example.new")

        Note:
            Triggers 30s class cache cooldown (skipped for dry_run).
        """
        target_type_lower = target_type.lower()

        if dry_run:
            from src.server.config import get_from_jadx as _get
            # Verify target exists via get_class_info (lightweight, no decompile)
            lookup_class = old_name if target_type_lower in ("class", "package") else class_name
            if not lookup_class:
                return {"dry_run": True, "target_exists": False, "error": "class_name required"}
            info = await _get("class-info", {"class_name": lookup_class}, instance_id=instance_id)
            exists = not isinstance(info, dict) or "error" not in info
            return {
                "dry_run": True,
                "target_exists": exists,
                "target_type": target_type_lower,
                "target_info": info if exists else None,
            }

        if target_type_lower == "class":
            return await rename_class(old_name, new_name, instance_id=instance_id)
        elif target_type_lower == "method":
            if not class_name:
                return {"success": False, "error": "class_name required for method rename"}
            return await rename_method(class_name, old_name, new_name, instance_id=instance_id)
        elif target_type_lower == "field":
            if not class_name:
                return {"success": False, "error": "class_name required for field rename"}
            return await rename_field(class_name, old_name, new_name, instance_id=instance_id)
        elif target_type_lower == "package":
            return await rename_package(old_name, new_name, instance_id=instance_id)
        else:
            return {"success": False, "error": f"Invalid target_type: {target_type}. Use: class, method, field, package"}
