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

