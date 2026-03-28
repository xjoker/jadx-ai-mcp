"""
JADX MCP Server - Code Refactoring Tools

This module provides MCP tools for refactoring decompiled Android code,
including renaming classes, methods, fields, and packages to improve
code readability during reverse engineering analysis.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

from typing import Optional
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx


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
    return await get_from_jadx(
        "rename-class",
        instance_id=instance_id,
        method="POST",
        json_body={"class_name": class_name, "new_name": new_name},
    )


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
    return await get_from_jadx(
        "rename-method",
        instance_id=instance_id,
        method="POST",
        json_body={
            "class_name": class_name,
            "method_name": method_name,
            "new_name": new_name,
        },
    )


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
    return await get_from_jadx(
        "rename-field",
        instance_id=instance_id,
        method="POST",
        json_body={
            "class_name": class_name,
            "field_name": field_name,
            "new_field_name": new_name,
        },
    )


async def export_rename_mappings(instance_id: Optional[str] = None) -> dict:
    """
    导出所有已重命名的类/方法/字段映射。

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: {mappings: [{type, original_name, new_name, class_context}], total: int}

    MCP Tool: export_rename_mappings
    Description: Exports all user-applied rename mappings for backup or transfer
    """
    return await get_from_jadx(
        "export-rename-mappings",
        instance_id=instance_id,
    )


async def import_rename_mappings(mappings: list, instance_id: Optional[str] = None) -> dict:
    """
    批量导入重命名映射并应用到当前 JADX 项目。

    Args:
        mappings: 映射数组，每项格式为:
                  {type: "class"|"method"|"field",
                   original_name: str,
                   new_name: str,
                   class_context: str}  # method/field 必填
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: {success: bool, total: int, applied: int, failed: int, errors: list[str]}

    MCP Tool: import_rename_mappings
    Description: Batch-applies rename mappings exported from another session
    """
    return await get_from_jadx(
        "import-rename-mappings",
        instance_id=instance_id,
        method="POST",
        json_body={"mappings": mappings},
    )


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
    return await get_from_jadx(
        "rename-package",
        instance_id=instance_id,
        method="POST",
        json_body={
            "old_package_name": old_package_name,
            "new_package_name": new_package_name,
        },
    )


def register_refactor_tools(mcp, with_busy_check):
    """Register refactoring tools to MCP Server"""

    @mcp.tool()
    @with_busy_check
    async def export_rename_mappings_tool(
        instance_id: Optional[str] = None
    ) -> dict:
        """Export all user-applied rename mappings from the current JADX session.

        Returns a JSON array of {type, original_name, new_name, class_context} entries
        covering every class, method, and field that has been renamed.
        Use this to back up or transfer rename work between sessions.

        Args:
            instance_id: Target JADX instance name. Uses default if not specified.

        Returns:
            dict: {mappings: list[dict], total: int}
        """
        return await export_rename_mappings(instance_id=instance_id)

    @mcp.tool()
    @with_busy_check
    async def import_rename_mappings_tool(
        mappings: list,
        instance_id: Optional[str] = None
    ) -> dict:
        """Batch-apply rename mappings to the current JADX session.

        Accepts the same format produced by export_rename_mappings.
        Each entry must have: type ("class"|"method"|"field"), original_name,
        new_name, and class_context (required for method/field entries).

        Args:
            mappings: List of rename mapping dicts.
            instance_id: Target JADX instance name. Uses default if not specified.

        Returns:
            dict: {success: bool, total: int, applied: int, failed: int, errors: list[str]}

        Examples:
            import_rename_mappings_tool([
                {"type": "class", "original_name": "a.b.c", "new_name": "UserService", "class_context": ""},
                {"type": "method", "original_name": "a", "new_name": "fetchUser",
                 "class_context": "UserService"},
            ])
        """
        return await import_rename_mappings(mappings=mappings, instance_id=instance_id)

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
            from src.server.request_context import get_from_jadx_for_current_user as _get
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
