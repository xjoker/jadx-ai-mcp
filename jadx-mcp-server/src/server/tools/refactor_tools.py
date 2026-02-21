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


async def rename_variable(class_name: str, method_name: str, variable_name: str, new_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Renames a local variable within a specific method.

    NOTE: This operation triggers ClassCacheManager reload with 30s global cooldown.
    Rapid successive renames will be debounced.

    Variable renaming is scoped to the method body. Use this to improve readability
    of obfuscated local variables (e.g., renaming 'a', 'b', 'c' to meaningful names).

    Args:
        class_name: Fully qualified class name containing the method (e.g., com.example.MyClass)
        method_name: Method name containing the variable (e.g., onCreate)
        variable_name: Current variable name to rename
        new_name: New descriptive name for the variable
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Confirmation of rename operation

    MCP Tool: rename_variable
    Description: Renames a local variable within a method to improve code readability
    """
    return await get_from_jadx("rename-variable", {
        "class_name": class_name,
        "method_name": method_name,
        "variable_name": variable_name,
        "new_name": new_name
    }, instance_id=instance_id)
