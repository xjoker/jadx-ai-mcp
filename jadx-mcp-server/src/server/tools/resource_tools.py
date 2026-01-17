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


# ============================================================================
# Unified Interface Tools (APK + JAR)
# ============================================================================

async def get_file_info(instance_id: Optional[str] = None) -> dict:
    """
    Get unified file information for both APK and JAR files.
    
    This is the recommended first tool to call when starting analysis.
    It provides file type detection and recommends which tools to use.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
        
    Returns:
        dict: Unified file information
        
        Common fields:
        - file_type: "apk", "jar", "dex", "aar"
        - file_name: Original filename
        - class_count: Total classes
        - android_features: True if Android tools available
        - smali_available: True if Smali generation works
        - features: Map of feature availability
        - recommended_tools: List of suggested tools for this file type
        
        For APK/AAR (android_features=true):
        - apk_package, version_name, version_code
        
        For JAR (file_type="jar"):
        - main_class, implementation_title, spring_boot_version
    
    MCP Tool: get_file_info
    Description: Unified file info - start here to understand file type and available tools
    """
    return await get_from_jadx("file-info", instance_id=instance_id)


async def get_config_strings(
    mode: str = "summary",
    query: Optional[str] = None,
    key: Optional[str] = None,
    file: Optional[str] = None,
    instance_id: Optional[str] = None
) -> dict:
    """
    Get configuration strings from both APK and JAR files.
    
    This unified tool handles:
    - APK/AAR: Provides info about strings.xml (use get_strings for full access)
    - JAR: Reads .properties files with search/get capabilities
    
    Args:
        mode: "summary" (default) | "search" | "get" | "all"
        query: Search keyword for mode=search
        key: Property key for mode=get
        file: Filter by specific properties file (JAR only)
        instance_id: Optional. Target JADX instance name.
        
    Returns:
        dict: Configuration strings based on file type
        
        For APK:
        {
            "source_type": "android_strings",
            "available": true,
            "recommended_tool": "get_strings"
        }
        
        For JAR:
        {
            "source_type": "java_properties",
            "files": [{"file": "application.properties", "key_count": 25, ...}],
            "total_files": 3
        }
    
    MCP Tool: get_config_strings
    Description: Unified config strings - handles APK strings.xml and JAR .properties
    """
    params = {"mode": mode}
    if query: params["query"] = query
    if key: params["key"] = key
    if file: params["file"] = file
    
    return await get_from_jadx("config-strings", params, instance_id=instance_id)


async def get_package_classes(
    package: Optional[str] = None,
    auto: bool = False,
    include_inner: bool = True,
    offset: int = 0,
    count: int = 100,
    instance_id: Optional[str] = None
) -> dict:
    """
    Get classes by package prefix. Works for both APK and JAR files.
    
    This unified tool replaces get_main_application_classes_names and works
    with any package prefix, not just the main application package.
    
    Args:
        package: Package prefix to filter (e.g., "com.example.app")
        auto: Auto-detect main package from manifest (default: False)
        include_inner: Include inner classes (default: True)
        offset: Pagination offset
        count: Max results (default: 100, max: 500)
        instance_id: Optional. Target JADX instance name.
        
    Returns:
        dict: Filtered class list with pagination
        
        {
            "package": "com.example.app",
            "classes": [{"name": "...", "is_inner": false}, ...],
            "total_matched": 150,
            "has_more": true
        }
    
    MCP Tool: get_package_classes
    Description: Get classes by package prefix - works for APK and JAR files
    """
    params = {}
    if package: params["package"] = package
    if auto: params["auto"] = "true"
    if not include_inner: params["include_inner"] = "false"
    if offset: params["offset"] = str(offset)
    if count != 100: params["count"] = str(count)
    
    return await get_from_jadx("package-classes", params, instance_id=instance_id)


# ============================================================================
# JAR-specific Tools
# ============================================================================

async def jar_get_manifest(instance_id: Optional[str] = None) -> dict:
    """
    Read META-INF/MANIFEST.MF from JAR files.
    
    This tool extracts structured information from JAR manifest including:
    - Main-Class: Entry point for executable JARs
    - Implementation-Title/Version: Library identification
    - Spring Boot specific attributes (Start-Class, Spring-Boot-Lib, etc.)
    - OSGi Bundle attributes
    - All custom manifest attributes
    
    NOTE: Only available for JAR files. Returns NOT_APPLICABLE for APK/AAR/DEX files.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
        
    Returns:
        dict: Structured manifest data with common and all attributes
        
        Success response:
        {
            "status": "success",
            "type": "jar-manifest",
            "main_class": "com.example.App",
            "implementation_title": "my-app",
            "implementation_version": "1.0.0",
            "spring_boot_version": "2.7.0",  // if Spring Boot JAR
            "all_attributes": {"key": "value", ...},
            "attribute_count": 15
        }
        
        NOT_APPLICABLE response (for APK/AAR):
        {
            "status": "NOT_APPLICABLE",
            "reason": "JAR Manifest is only available for JAR files",
            "file_type": "apk",
            "alternatives": [{"tool": "apk_get_manifest", "description": "..."}]
        }
    
    MCP Tool: jar_get_manifest
    Description: Read and parse MANIFEST.MF from JAR files for library metadata and entry point discovery
    """
    return await get_from_jadx("jar-manifest", instance_id=instance_id)


async def jar_get_services(instance_id: Optional[str] = None) -> dict:
    """
    Read META-INF/services/* from JAR files to discover SPI service providers.
    
    Java SPI (Service Provider Interface) is used by many frameworks:
    - JDBC drivers (java.sql.Driver)
    - Logging frameworks (org.slf4j.spi.SLF4JServiceProvider)
    - Servlet containers
    - Plugin architectures
    
    NOTE: Only available for JAR files. Returns NOT_APPLICABLE for APK/AAR/DEX files.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
        
    Returns:
        dict: List of service interfaces and their implementations
        
        Success response:
        {
            "status": "success",
            "services": [
                {"interface": "java.sql.Driver", "implementations": ["com.mysql.cj.jdbc.Driver"], "count": 1}
            ],
            "total_services": 1
        }
    
    MCP Tool: jar_get_services
    Description: Discover Java SPI service providers in JAR files
    """
    return await get_from_jadx("jar-services", instance_id=instance_id)


async def jar_get_entry_points(instance_id: Optional[str] = None) -> dict:
    """
    Intelligently discover entry points for JAR files.
    
    This tool finds all possible entry points in a JAR:
    1. Main-Class from MANIFEST.MF (standard executable JAR)
    2. Start-Class for Spring Boot (actual application class)
    3. Classes with @SpringBootApplication annotation
    4. Classes with public static void main(String[]) method
    
    The result includes a "primary_entry" field recommending the best entry point.
    
    NOTE: Only available for JAR files. Returns NOT_APPLICABLE for APK/AAR/DEX files.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
        
    Returns:
        dict: List of discovered entry points with priority
        
        Success response:
        {
            "status": "success",
            "primary_entry": "com.example.Application",
            "entry_points": [
                {"type": "spring_boot_start_class", "class": "...", "priority": 1},
                {"type": "main_class", "class": "...", "priority": 1}
            ],
            "total_found": 2
        }
    
    MCP Tool: jar_get_entry_points
    Description: Discover entry points (Main-Class, Spring Boot, main()) in JAR files
    """
    return await get_from_jadx("jar-entry-points", instance_id=instance_id)


async def jar_get_dependencies(instance_id: Optional[str] = None) -> dict:
    """
    Analyze dependencies embedded in JAR files.
    
    This tool discovers dependencies from multiple sources:
    1. META-INF/maven/*/pom.properties - Maven coordinates
    2. MANIFEST.MF Class-Path entries
    3. BOOT-INF/lib/*.jar - Spring Boot nested dependencies
    
    NOTE: Only available for JAR files. Returns NOT_APPLICABLE for APK/AAR/DEX files.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
        
    Returns:
        dict: Dependency analysis results
        
        Success response:
        {
            "status": "success",
            "group_id": "com.example",
            "artifact_id": "my-app",
            "version": "1.0.0",
            "dependencies": [
                {"name": "spring-core", "version": "6.1.0", "source": "BOOT-INF/lib"}
            ],
            "total_dependencies": 150,
            "nested_jars_count": 150
        }
    
    MCP Tool: jar_get_dependencies
    Description: Analyze Maven coordinates and embedded dependencies in JAR files
    """
    return await get_from_jadx("jar-dependencies", instance_id=instance_id)
