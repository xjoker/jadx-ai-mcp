"""
JADX MCP Server - Class Analysis Tools

This module provides MCP tools for analyzing and retrieving Android application
classes through the JADX decompilation framework. These tools enable automated
reverse engineering workflows for Android APK analysis.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

from typing import Optional
from src.server.config import get_from_jadx
from src.PaginationUtils import PaginationUtils
from src.server.logging_config import get_logger

logger = get_logger("class_tools")


async def fetch_current_class(instance_id: Optional[str] = None) -> dict:
    """
    Fetch the currently selected class and its code from the JADX-GUI plugin.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains class name, package, and decompiled Java source code

    MCP Tool: fetch_current_class
    Description: Retrieves the class currently open in JADX-GUI editor
    """
    logger.info(f"fetch_current_class: instance={instance_id}")
    result = await get_from_jadx("current-class", instance_id=instance_id)
    if "error" in result:
        logger.warning(f"fetch_current_class error: {result.get('error')}")
    elif not result.get("class_name"):
        logger.warning("fetch_current_class: no class selected in JADX-GUI")
    else:
        logger.info(f"fetch_current_class: got class {result.get('class_name')}")
    return result


async def get_selected_text(instance_id: Optional[str] = None) -> dict:
    """
    Returns the currently selected text in the decompiled code view.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains the selected text snippet from the code editor

    MCP Tool: get_selected_text
    Description: Gets text selection from JADX-GUI for focused analysis
    """
    return await get_from_jadx("selected-text", instance_id=instance_id)


async def get_class_source(class_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Fetch the Java source of a specific class.

    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains complete decompiled Java source code for the class

    MCP Tool: get_class_source
    Description: Retrieves decompiled Java source for any class in the APK
    """
    return await get_from_jadx("class-source", {"class_name": class_name}, instance_id=instance_id)


async def batch_get_class_source(class_names: list[str], instance_id: Optional[str] = None) -> dict:
    """
    Fetch multiple class sources in a single request.
    
    This reduces MCP interaction overhead when analyzing multiple related classes.
    Maximum 20 classes per request.

    Args:
        class_names: List of fully qualified class names to fetch
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains 'classes' array with name, found status, and content/error for each class,
              plus 'total' and 'found' counts

    MCP Tool: batch_get_class_source
    Description: Batch retrieval of decompiled Java sources for multiple classes
    """
    logger.info(f"batch_get_class_source: classes={class_names}, instance={instance_id}")
    try:
        # Join class names with comma for the API
        class_names_str = ",".join(class_names)
        result = await get_from_jadx("batch-class-source", {"class_names": class_names_str}, instance_id=instance_id)
        
        if "error" in result:
            logger.error(f"batch_get_class_source failed: {result.get('error')}")
        else:
            found_count = result.get("found", 0)
            total_count = result.get("total", len(class_names))
            logger.info(f"batch_get_class_source: found {found_count}/{total_count} classes")
        
        return result
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e) or '(no message)'}"
        logger.error(f"batch_get_class_source exception: {error_msg}")
        return {"error": f"Unexpected error: {error_msg}"}


async def get_all_classes(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
    """
    Returns a list of all classes in the project with pagination support.

    Args:
        offset: Starting index for pagination (default: 0)
        count: Number of classes to return (0 = all, default: 0)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Paginated list of all class names in the decompiled APK

    MCP Tool: get_all_classes
    Description: Enumerates all classes with pagination for large APKs
    """
    return await PaginationUtils.get_paginated_data(
        endpoint="all-classes",
        offset=offset,
        count=count,
        data_extractor=lambda parsed: parsed.get("classes", []),
        fetch_function=lambda ep, params={}: get_from_jadx(ep, params, instance_id=instance_id)
    )


async def get_methods_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
    """
    List all method names in a class.

    Args:
        class_name: Fully qualified class name
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: List of all method signatures in the specified class

    MCP Tool: get_methods_of_class
    Description: Extracts all method declarations from a class
    """
    return await get_from_jadx("methods-of-class", {"class_name": class_name}, instance_id=instance_id)


async def get_fields_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
    """
    List all field names in a class.

    Args:
        class_name: Fully qualified class name
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: List of all field declarations in the specified class

    MCP Tool: get_fields_of_class
    Description: Extracts all field variables from a class
    """
    return await get_from_jadx("fields-of-class", {"class_name": class_name}, instance_id=instance_id)


async def get_smali_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Fetch the smali representation of a class.

    Args:
        class_name: Fully qualified class name (for inner classes use $ syntax: OuterClass$InnerClass)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Smali/Dalvik bytecode representation of the class

    MCP Tool: get_smali_of_class
    Description: Retrieves low-level smali bytecode for advanced analysis
    """
    # Auto-convert dot to $ for inner classes if needed
    normalized_name = class_name
    logger.info(f"get_smali_of_class: class={class_name}, instance={instance_id}")
    
    result = await get_from_jadx("smali-of-class", {"class_name": normalized_name}, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"get_smali_of_class error: {result.get('error')}")
    return result


async def get_main_application_classes_names(instance_id: Optional[str] = None) -> dict:
    """
    Fetch all the main application classes' names based on the package name defined in Manifest.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: List of class names belonging to the main application package

    MCP Tool: get_main_application_classes_names
    Description: Identifies core application classes (excludes libraries)
    """
    return await get_from_jadx("main-application-classes-names", instance_id=instance_id)


async def get_main_application_classes_code(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
    """
    Fetch main application classes' code with pagination.

    Args:
        offset: Starting index for pagination (default: 0)
        count: Number of classes to return (0 = all, default: 0)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Paginated decompiled source code of main application classes

    MCP Tool: get_main_application_classes_code
    Description: Retrieves source code for core app classes with pagination
    """
    return await PaginationUtils.get_paginated_data(
        endpoint="main-application-classes-code",
        offset=offset,
        count=count,
        data_extractor=lambda parsed: parsed.get("classes", []),
        fetch_function=lambda ep, params={}: get_from_jadx(ep, params, instance_id=instance_id)
    )


async def get_main_activity_class(instance_id: Optional[str] = None) -> dict:
    """
    Fetch the main activity class as defined in the AndroidManifest.xml.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Main launcher activity class name and source code

    MCP Tool: get_main_activity_class
    Description: Identifies and retrieves the app's entry point activity
    """
    return await get_from_jadx("main-activity", instance_id=instance_id)


async def get_class_info(class_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Get structured information about a class including inheritance, interfaces, and members.

    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Structured class information containing:
            - class_name: Full class name
            - simple_name: Short class name
            - package: Package name
            - super_class: Parent class name
            - interfaces: List of implemented interface names
            - inner_classes: List of inner class names
            - is_interface: Whether this is an interface
            - is_enum: Whether this is an enum
            - is_inner: Whether this is an inner class
            - methods_count: Number of methods
            - fields_count: Number of fields
            - method_names: List of method names
            - field_names: List of field names

    MCP Tool: get_class_info
    Description: Retrieves structured class metadata including inheritance hierarchy
    """
    logger.info(f"get_class_info: class={class_name}, instance={instance_id}")
    result = await get_from_jadx("class-info", {"class_name": class_name}, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"get_class_info error: {result.get('error')}")
    return result
