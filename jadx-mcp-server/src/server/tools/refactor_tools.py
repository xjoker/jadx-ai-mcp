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
from src.server.types import format_error_response


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


async def rename_method(
    class_name: str,
    method_name: str,
    new_name: str,
    method_signature: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Renames a specific method.

    NOTE: This operation triggers ClassCacheManager reload with 30s global cooldown.
    Rapid successive renames will be debounced.

    When the class has overloaded methods with the same name, supply
    ``method_signature`` (JVM short descriptor) to target the exact overload.
    If omitted and multiple overloads exist, the server returns an
    ``available_descriptors`` list; pick one and call again.

    Args:
        class_name: Fully qualified class name containing the method
            (e.g. ``"com.example.Parser"``).
        method_name: Current method name (e.g. ``"parse"``).
        new_name: New name for the method.
        method_signature: Optional JVM short descriptor to disambiguate overloads,
            e.g. ``"parse(Ljava/lang/String;)V"`` or ``"parse(I)Z"``.
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Confirmation of rename operation, or error with ``available_descriptors``
        when multiple overloads exist and no descriptor was provided.

    MCP Tool: rename_method
    Description: Refactors method name and updates all call sites
    """
    json_body: dict = {
        "class_name": class_name,
        "method_name": method_name,
        "new_name": new_name,
    }
    if method_signature:
        json_body["method_signature"] = method_signature
    return await get_from_jadx(
        "rename-method",
        instance_id=instance_id,
        method="POST",
        json_body=json_body,
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


async def rename_variable(
    class_name: str,
    method_name: str,
    variable_name: str,
    new_name: str,
    reg: Optional[str] = None,
    ssa: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Renames a local variable inside a method using SSA variable tracking.

    Args:
        class_name: Fully qualified class name containing the method
        method_name: Method name (signature stripped if present)
        variable_name: Current variable name to rename
        new_name: New variable name
        reg: Optional. Register number for disambiguation when multiple vars share a name
        ssa: Optional. SSA version number for further disambiguation
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Confirmation of rename operation

    MCP Tool: rename_variable
    Description: Renames a local variable within a specific method
    """
    body: dict = {
        "class_name": class_name,
        "method_name": method_name,
        "variable_name": variable_name,
        "new_name": new_name,
    }
    if reg is not None:
        body["reg"] = reg
    if ssa is not None:
        body["ssa"] = ssa
    return await get_from_jadx(
        "rename-variable",
        instance_id=instance_id,
        method="POST",
        json_body=body,
    )


async def export_rename_mappings(instance_id: Optional[str] = None) -> dict:
    """
    Export all renamed class/method/field mappings.

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
    Batch-import rename mappings and apply them to the current JADX project.

    Args:
        mappings: Array of mapping entries, each in the format:
                  {type: "class"|"method"|"field",
                   original_name: str,
                   new_name: str,
                   class_context: str}  # required for method/field
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


async def apply_proguard_mapping(mapping_content: str, instance_id: Optional[str] = None) -> dict:
    """
    Apply a ProGuard/R8 mapping.txt to batch-rename all matching obfuscated classes.

    Parses the standard ProGuard mapping format:
        original.class.Name -> obfuscated.a:
            int originalField -> b
            void originalMethod() -> c

    All obfuscated class names found in JADX that match entries in the mapping
    are renamed in bulk. This is much faster than calling rename() individually.

    Args:
        mapping_content: Full contents of a ProGuard/R8 mapping.txt file.
        instance_id: Optional target JADX instance name.

    Returns:
        dict: {applied: int, failed: int, errors: list[str], total: int, format: str}

    MCP Tool: apply_proguard_mapping
    Description: Batch-apply a ProGuard/R8 mapping.txt to rename all obfuscated classes at once
    """
    return await get_from_jadx(
        "apply-proguard-mapping",
        instance_id=instance_id,
        method="POST",
        json_body={"mapping_content": mapping_content},
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
    async def rename_variable_tool(
        class_name: str,
        method_name: str,
        variable_name: str,
        new_name: str,
        reg: Optional[str] = None,
        ssa: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Rename a local variable inside a method using JADX SSA tracking.

        Args:
            class_name: Fully qualified class name. method_name: Method name.
            variable_name: Current variable name. new_name: New name.
            reg: Register number (disambiguation). ssa: SSA version (disambiguation).
            instance_id: Target JADX instance name.
        Returns:
            dict: {result: str} on success or {error: str, status: 404} if not found.
        """
        return await rename_variable(
            class_name=class_name,
            method_name=method_name,
            variable_name=variable_name,
            new_name=new_name,
            reg=reg,
            ssa=ssa,
            instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def export_rename_mappings_tool(
        instance_id: Optional[str] = None
    ) -> dict:
        """Export all rename mappings (classes, methods, fields) from the current JADX session.

        Args:
            instance_id: Target JADX instance name.
        Returns:
            dict: {mappings: [{type, original_name, new_name, class_context}], total: int}
        """
        return await export_rename_mappings(instance_id=instance_id)

    @mcp.tool()
    @with_busy_check
    async def import_rename_mappings_tool(
        mappings: list,
        instance_id: Optional[str] = None
    ) -> dict:
        """Batch-apply rename mappings (same format as export_rename_mappings output).

        Args:
            mappings: List of {type, original_name, new_name, class_context} dicts.
            instance_id: Target JADX instance name.
        Returns:
            dict: {success: bool, total: int, applied: int, failed: int, errors: [str]}
        """
        return await import_rename_mappings(mappings=mappings, instance_id=instance_id)

    @mcp.tool()
    @with_busy_check
    async def rename(
        target_type: str,
        old_name: str,
        new_name: str,
        class_name: str = "",
        method_signature: Optional[str] = None,
        dry_run: bool = False,
        instance_id: Optional[str] = None
    ) -> dict:
        """Unified rename for classes, methods, fields, and packages. Triggers 30s cache cooldown.

        Args:
            target_type: class|method|field|package. old_name: Current name. new_name: New name.
            class_name: Required for method/field. method_signature: JVM descriptor for overloads.
            dry_run: Preview without renaming. instance_id: Target JADX instance name.
        Returns:
            dict: {success: bool, message: str} or dry_run: {target_exists: bool, target_info: {...}}
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
            return await rename_method(
                class_name, old_name, new_name,
                method_signature=method_signature,
                instance_id=instance_id,
            )
        elif target_type_lower == "field":
            if not class_name:
                return {"success": False, "error": "class_name required for field rename"}
            return await rename_field(class_name, old_name, new_name, instance_id=instance_id)
        elif target_type_lower == "package":
            return await rename_package(old_name, new_name, instance_id=instance_id)
        else:
            return {"success": False, "error": f"Invalid target_type: {target_type}. Use: class, method, field, package"}

    @mcp.tool()
    @with_busy_check
    async def apply_proguard_mapping_tool(
        mapping_content: str,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Apply a ProGuard/R8 mapping.txt to batch-rename all obfuscated classes at once.

        Accepts the standard ProGuard mapping format produced by R8/ProGuard:
            original.package.ClassName -> a.b.c:
                int originalField -> d
                void originalMethod() -> e

        All obfuscated class names found in the loaded APK that match mapping entries
        are renamed in bulk. This is orders of magnitude faster than calling rename()
        for each class individually and is the recommended approach when a mapping file
        is available.

        Input validation: mapping_content must be non-empty and must contain at least
        one '->' arrow (the core ProGuard mapping separator). Empty or malformed content
        is rejected before sending to the JADX instance.

        Args:
            mapping_content: Complete contents of a ProGuard/R8 mapping.txt file.
            instance_id: Target JADX instance name.
        Returns:
            dict: {applied: int, failed: int, errors: [str], total: int, format: str}
        """
        if not mapping_content or not mapping_content.strip():
            return format_error_response(
                "INVALID_INPUT",
                "mapping_content cannot be empty",
                {"hint": "Provide the full contents of a ProGuard/R8 mapping.txt file"},
            )
        if "->" not in mapping_content:
            return format_error_response(
                "INVALID_INPUT",
                "mapping_content does not appear to be a valid ProGuard mapping file",
                {
                    "hint": (
                        "ProGuard/R8 mapping files contain '->' arrows, e.g.:\n"
                        "  com.example.RealName -> a.b:\n"
                        "      void realMethod() -> c\n"
                        "Ensure you are pasting the complete mapping.txt content."
                    )
                },
            )
        return await apply_proguard_mapping(
            mapping_content=mapping_content,
            instance_id=instance_id,
        )
