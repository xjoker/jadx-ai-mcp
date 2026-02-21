#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [ "fastmcp", "httpx" ]
# ///

"""
Copyright (c) 2025 jadx mcp server developer(s) (https://github.com/zinja-coder/jadx-ai-mcp)
See the file 'LICENSE' for copying permission
"""

import argparse
import sys
from fastmcp import FastMCP
from src.banner import jadx_mcp_server_banner
from src.server import config, tools

# Initialize MCP Server with stateless HTTP mode (no session required)
# Instructions are shown to AI when connecting to help with proper tool usage
MCP_INSTRUCTIONS = """
JADX AI MCP Server - Android APK Reverse Engineering Tools

IMPORTANT: Before using any resource-intensive operation, always call get_decompile_status() first!

DECISION GUIDE based on get_decompile_status() response:
- If cached_percentage < 20%: Use search_in='class' or 'method' only (avoid 'code')
- If memory.usage_percentage > 85%: Reduce batch size to 5, avoid get_smali_of_class
- If search_lock.locked = true: Wait 5 seconds and retry

PERFORMANCE EXPECTATIONS:
| Operation              | Expected Time | Notes                          |
|------------------------|--------------|--------------------------------|
| search_in=class/method | <100ms       | Always fast, no cache needed   |
| search_in=code         | 1-60s        | Slow, may timeout on large APK |
| get_class_source       | <1s          | Fast when cached               |
| batch_get_*            | <3s          | Up to 20 items per batch       |

RECOMMENDED WORKFLOW:
1. Call get_decompile_status() to check system status
2. Use metadata searches first (class, method, field)
3. Use code search only when cache is ready (cached_percentage > 50%)
4. Use package filter to narrow search scope for better performance

TRANSFER API - Bypass MCP Size Limits:
When batch operations might exceed MCP message limits (~16KB):
1. Call create_transfer_token(resource_type="batch_classes")
2. Use HTTP client to download directly from transfer_url
3. Supports JSON and ZIP formats, Brotli/GZIP compression
4. Example: GET {transfer_url}/download/batch-classes?classes=A,B&token=xxx&format=zip

For detailed guidance, use the 'status-check' or 'search-code' prompts.
"""


mcp = FastMCP(
    "JADX-AI-MCP Plugin Reverse Engineering Server",
    instructions=MCP_INSTRUCTIONS
)

# Note: Tool functions are defined below with @mcp.tool() decorator
# They delegate to src.server.tools modules for implementation
from src.server.prompts import register_prompts
from src.server.resources import register_resources
from src.server.tools.instance_tools import register_instance_tools
from src.server.instance_registry import InstanceRegistry
from src.server.busy_tracker import with_busy_check, InstanceBusyTracker
from src.server.auth_middleware import BearerAuthMiddleware
from src.server.health_monitor import HealthMonitor
from src.server.logging_config import configure_logging, get_logger
from src.server import tools

# Transfer API imports
from src.server.tools import transfer_tools
from src.server import transfer_server
from src.server.mcp_server_config import set_mcp_server_url_from_config

# Register Transfer API custom routes
# Using @mcp.custom_route() to add HTTP endpoints alongside MCP
@mcp.custom_route("/transfer/download/batch-classes", methods=["GET"])
async def transfer_download_batch_classes(request):
    """Transfer API: Download batch classes bypassing MCP size limits"""
    return await transfer_server.download_batch_classes(request)

@mcp.custom_route("/transfer/health", methods=["GET"])
async def transfer_health(request):
    """Transfer API: Health check endpoint"""
    return await transfer_server.download_health(request)

logger = get_logger("main")


# CORRECT REGISTRATION PATTERN for FastMCP
# All tools support optional instance_id for multi-instance targeting
from typing import Optional



@mcp.tool()
@with_busy_check
async def fetch_current_class(chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """Retrieves the currently opened/active class in JADX-GUI.

    CHUNKING: Large classes (>8KB) are automatically chunked. If response contains
    `_chunking.has_more=true`, call again with chunk=N to get remaining content.

    Args:
        chunk: Chunk number (0=first chunk with metadata, 1-N=specific chunk). Default: 0
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.fetch_current_class(chunk=chunk, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_selected_text(instance_id: Optional[str] = None) -> dict:
    """Returns the currently selected text in the JADX-GUI decompiled code view.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_selected_text(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_main_application_classes_names(instance_id: Optional[str] = None) -> dict:
    """Fetch all main application class names based on the package defined in AndroidManifest.xml.

    Returns class names belonging to the main application package (excludes libraries).

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_main_application_classes_names(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_main_application_classes_code(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
    """Fetch main application classes' decompiled source code with pagination.

    WARNING: Large responses may timeout. Use small count values (1-5).
    Prefer get_main_application_classes_names first, then get_class_source for specific classes.

    Args:
        offset: Starting index for pagination (default: 0)
        count: Number of classes to return (0=all). Recommended: 1-5 to avoid timeout.
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_main_application_classes_code(offset, count, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_method_by_name(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
    """Fetch the source code of a method from a specific class.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.MainActivity').
        method_name: Method name to search for.
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.search_tools.get_method_by_name(class_name, method_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_all_classes(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
    """Returns a list of all classes in the project with pagination support.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_all_classes(offset, count, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_class_source(class_name: str, chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """Fetch the Java source of a specific class.
    
    CHUNKING: Large classes (>8KB) are automatically chunked. If response contains
    `_chunking.has_more=true`, call again with chunk=N to get remaining content.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.MainActivity').
        chunk: Chunk number (0=first chunk with metadata, 1-N=specific chunk). Default: 0
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_class_source(class_name, chunk=chunk, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def batch_get_class_source(
    class_names: list[str],
    chunk: int = 0,
    force: bool = False,
    instance_id: Optional[str] = None
) -> dict:
    """Fetch multiple class sources in a single request with intelligent size management.

    SMART BATCHING: Automatically estimates response size and provides optimization guidance.
    - Small batches (<20KB): Execute directly
    - Large batches (20-50KB): Execute with performance warning
    - Very large batches (>50KB): Returns BATCH_TOO_LARGE error with class summaries

    CHUNKING: Large responses (>8KB) are automatically chunked. If response contains
    `_chunking.has_more=true`, call again with chunk=N to get remaining content.

    TIERED STRATEGY:
    1. Continuation requests (chunk>0): Execute immediately
    2. Very large requests (>50KB estimated): Pre-flight check fails, returns optimization suggestions
    3. Large requests (20-50KB): Execute with performance warning
    4. Normal requests (<20KB): Execute directly

    Args:
        class_names: List of fully qualified class names (e.g., ['com.example.A', 'com.example.B']). Max 20.
        chunk: Chunk number for continuation (0=first request, 1-N=subsequent chunks). Default: 0
        force: Force execution even for very large requests (bypasses size check). Default: False
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        Success: {classes: [{class_name, content, found}, ...], total, found_count}
        BATCH_TOO_LARGE error: {error, estimated_size_kb, class_summaries, suggestions}
    """
    return await tools.class_tools.batch_get_class_source(
        class_names, chunk=chunk, force=force, instance_id=instance_id
    )


@mcp.tool()
@with_busy_check
async def search_method_by_name(
    method_name: str,
    offset: int = 0,
    count: int = 50,
    instance_id: Optional[str] = None
) -> dict:
    """Search for a method name across all classes in the APK.
    
    WARNING: This performs a global search and may timeout or crash on large/obfuscated APKs.
    For safer search, consider using search_classes_by_keyword with search_in='method' instead.
    Refer to the 'search-code' prompt for best practices.

    Args:
        method_name: Method name to search for (partial matching supported).
        offset: Starting index for pagination. Default: 0
        count: Number of results to return. Default: 50, max: 200
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.search_tools.search_method_by_name(method_name, offset, count, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def batch_get_method_by_name(
    methods: list[str],
    chunk: int = 0,
    force: bool = False,
    instance_id: Optional[str] = None
) -> dict:
    """Fetch multiple method sources in a single request with intelligent size management.

    SMART BATCHING: Automatically estimates response size and provides optimization guidance.
    - Small batches (<20KB): Execute directly
    - Large batches (20-50KB): Execute with performance warning
    - Very large batches (>50KB): Returns BATCH_TOO_LARGE error with method summaries

    CHUNKING: Large responses (>8KB) are automatically chunked. If response contains
    `_chunking.has_more=true`, call again with chunk=N to get remaining content.

    TIERED STRATEGY:
    1. Continuation requests (chunk>0): Execute immediately
    2. Very large requests (>50KB estimated): Pre-flight check fails, returns optimization suggestions
    3. Large requests (20-50KB): Execute with performance warning
    4. Normal requests (<20KB): Execute directly

    Args:
        methods: List of "class_name:method_name" pairs (e.g., ['com.example.A:methodA', 'com.example.B:methodB']). Max 20.
        chunk: Chunk number for continuation (0=first request, 1-N=subsequent chunks). Default: 0
        force: Force execution even for very large requests (bypasses size check). Default: False
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        Success: {methods: [{class_name, method_name, code, found}, ...], total, found_count}
        BATCH_TOO_LARGE error: {error, estimated_size_kb, method_summaries, suggestions}
    """
    return await tools.search_tools.batch_get_method_by_name(
        methods, chunk=chunk, force=force, instance_id=instance_id
    )


@mcp.tool()
@with_busy_check
async def get_methods_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
    """List all method names in a class with Frida-friendly metadata.
    
    Returns structured JSON with is_static, is_native, overload_count for each method.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.MainActivity').
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_methods_of_class(class_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def search_classes_by_keyword(
    search_term: str,
    package: str = "",
    exclude: str = "",
    search_in: str = "code",
    offset: int = 0,
    count: int = 20,
    instance_id: Optional[str] = None,
) -> dict:
    """Search for classes containing a keyword with flexible filtering.
    
    IMPORTANT: Call get_decompile_status() first! Use search_in='class/method/field' 
    for fast searches (<100ms). Use 'code' only when cached_percentage > 20%.
    
    Args:
        search_term: Keyword to search for.
        package: Package filter (e.g., 'com.example'). Strongly recommended!
        exclude: Comma-separated package prefixes to exclude.
        search_in: Scope: class|method|field|code|comment. Default: code
        offset: Pagination offset. Default: 0
        count: Max results (max: 200). Default: 20
        instance_id: Target JADX instance name.
    
    Returns:
        dict: {classes: [...], total: int, has_more: bool}
    """
    return await tools.search_tools.search_classes_by_keyword(
        search_term, package, exclude, search_in, offset, count, instance_id=instance_id
    )


@mcp.tool()
@with_busy_check
async def get_fields_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
    """List all field names in a class with Frida-compatible type information.
    
    Returns structured JSON with type_frida field for each field.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.MainActivity').
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_fields_of_class(class_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_smali_of_class(class_name: str, chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """Fetch the smali (Dalvik bytecode) representation of a class.
    
    CHUNKING: Large Smali output (>8KB) is automatically chunked. Classes with 40+ methods
    often produce >40KB Smali. If response contains `_chunking.has_more=true`, call again
    with chunk=N to get remaining content.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.MainActivity').
        chunk: Chunk number (0=first chunk with metadata, 1-N=specific chunk). Default: 0
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_smali_of_class(class_name, chunk=chunk, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_android_manifest(chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """Retrieve and return the AndroidManifest.xml content.
    
    CHUNKING: Large manifests (>8KB) auto-chunked. If `_chunking.has_more=true`, call with chunk=N.
    
    Args:
        chunk: Chunk number (0=first chunk, 1-N=specific chunk). Default: 0
        instance_id: Target JADX instance name.
    """
    return await tools.resource_tools.get_android_manifest(chunk=chunk, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_strings(
    mode: str = "summary",
    query: Optional[str] = None,
    key: Optional[str] = None,
    locale: str = "values",
    offset: int = 0,
    limit: int = 50,
    instance_id: Optional[str] = None
) -> dict:
    """Get strings from APK with AI-friendly modes.
    
    Modes:
    - summary (default): Returns total count, sample keys, and usage hints
    - list: Paginated list of all string keys
    - search: Search strings by keyword (requires query parameter)
    - get: Get specific string value (requires key parameter)
    
    Examples:
    - Summary: get_strings() -> {total_strings: 15673, sample_keys: [...]}
    - Search: get_strings(mode="search", query="login") -> {matches: [{key, value}, ...]}
    - Get: get_strings(mode="get", key="app_name") -> {value: "MyApp"}
    - List: get_strings(mode="list", offset=0, limit=50) -> {keys: [...]}
    - Change locale: get_strings(locale="values-en")
    
    Args:
        mode: Operation mode (summary|list|search|get). Default: summary
        query: Search keyword (required for mode=search)
        key: String key name (required for mode=get)
        locale: Locale variant like "values", "values-en", "values-zh". Default: values
        offset: Pagination offset for list mode. Default: 0
        limit: Results per page (max: 200). Default: 50
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.get_strings(
        mode=mode,
        query=query,
        key=key,
        locale=locale,
        offset=offset,
        limit=limit,
        instance_id=instance_id
    )


@mcp.tool()
@with_busy_check
async def get_all_resource_file_names(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
    """Retrieve all resource file names with pagination.
    
    Args:
        offset: Pagination offset. Default: 0
        count: Max results (0=all). Default: 0
        instance_id: Target JADX instance name.
    
    Returns:
        dict: {files: [str, ...], total: int, has_more: bool}
    """
    return await tools.resource_tools.get_all_resource_file_names(offset, count, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_resource_file(resource_name: str, chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """Retrieve resource file content by name.
    
    CHUNKING: Large files (>8KB) auto-chunked. If `_chunking.has_more=true`, call with chunk=N.
    
    Args:
        resource_name: Resource file path (e.g., 'res/layout/activity_main.xml').
        chunk: Chunk number (0=first chunk, 1-N=specific chunk). Default: 0
        instance_id: Target JADX instance name.
    """
    return await tools.resource_tools.get_resource_file(resource_name, chunk=chunk, instance_id=instance_id)


# ============================================================================
# Unified Interface Tools (APK + JAR)
# ============================================================================

@mcp.tool()
@with_busy_check
async def get_file_info(instance_id: Optional[str] = None) -> dict:
    """Get unified file information for both APK and JAR files.
    
    This is the recommended first tool to call when starting analysis.
    Returns file type, class count, and recommends which tools to use.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.get_file_info(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_config_strings(
    mode: str = "summary",
    query: Optional[str] = None,
    key: Optional[str] = None,
    file: Optional[str] = None,
    instance_id: Optional[str] = None
) -> dict:
    """Get configuration strings from APK or JAR files.
    
    - APK/AAR: Info about strings.xml availability
    - JAR: Reads .properties files with search/get support
    
    Args:
        mode: "summary" | "search" | "get" | "all"
        query: Search keyword (for mode=search)
        key: Property key (for mode=get)
        file: Filter by properties file name (JAR only)
        instance_id: Optional. Target JADX instance name.
    """
    return await tools.resource_tools.get_config_strings(
        mode=mode, query=query, key=key, file=file, instance_id=instance_id
    )


@mcp.tool()
@with_busy_check
async def get_package_classes(
    package: Optional[str] = None,
    auto: bool = False,
    include_inner: bool = True,
    offset: int = 0,
    count: int = 100,
    instance_id: Optional[str] = None
) -> dict:
    """Get classes by package prefix for APK or JAR files.
    
    Use ?auto=true to auto-detect main package from manifest.
    
    Args:
        package: Package prefix (e.g., "com.example.app")
        auto: Auto-detect main package (default: False)
        include_inner: Include inner classes (default: True)
        offset: Pagination offset
        count: Max results (default: 100, max: 500)
        instance_id: Optional. Target JADX instance name.
    """
    return await tools.resource_tools.get_package_classes(
        package=package, auto=auto, include_inner=include_inner,
        offset=offset, count=count, instance_id=instance_id
    )


# ============================================================================
# JAR-specific Tools
# ============================================================================

@mcp.tool()
@with_busy_check
async def jar_get_manifest(instance_id: Optional[str] = None) -> dict:
    """Read META-INF/MANIFEST.MF from JAR files.
    
    This tool extracts structured information from JAR manifest including:
    - Main-Class: Entry point for executable JARs
    - Implementation-Title/Version: Library identification  
    - Spring Boot specific attributes
    - All custom manifest attributes
    
    NOTE: Only available for JAR files. Returns NOT_APPLICABLE for APK/AAR/DEX files.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
        
    Returns:
        dict: Structured manifest data with common and all attributes
    """
    return await tools.resource_tools.jar_get_manifest(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def jar_get_services(instance_id: Optional[str] = None) -> dict:
    """Read META-INF/services/* from JAR files to discover SPI service providers.
    
    Java SPI is used by JDBC drivers, logging frameworks, plugin architectures.
    
    NOTE: Only available for JAR files. Returns NOT_APPLICABLE for APK/AAR/DEX files.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.jar_get_services(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def jar_get_entry_points(instance_id: Optional[str] = None) -> dict:
    """Discover entry points for JAR files.
    
    Finds Main-Class, Start-Class (Spring Boot), @SpringBootApplication classes,
    and public static void main() methods.
    
    NOTE: Only available for JAR files. Returns NOT_APPLICABLE for APK/AAR/DEX files.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.jar_get_entry_points(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def jar_get_dependencies(instance_id: Optional[str] = None) -> dict:
    """Analyze dependencies embedded in JAR files.
    
    Discovers Maven coordinates, MANIFEST Class-Path, and Spring Boot BOOT-INF/lib/ dependencies.
    
    NOTE: Only available for JAR files. Returns NOT_APPLICABLE for APK/AAR/DEX files.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.jar_get_dependencies(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def jar_get_bytecode(
    class_name: str,
    instance_id: Optional[str] = None
) -> dict:
    """Get bytecode/class structure for APK or JAR classes.
    
    JAR equivalent of get_smali_of_class. Shows class structure similar to javap.
    
    Args:
        class_name: Fully qualified class name (e.g., 'com.example.Main')
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.jar_get_bytecode(class_name, instance_id=instance_id)



@mcp.tool()
@with_busy_check
async def get_main_activity_class(chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """Fetch the main activity class name from AndroidManifest.xml.

    CHUNKING: Large activity classes (>8KB) auto-chunked. If `_chunking.has_more=true`, call with chunk=N.

    Args:
        chunk: Chunk number (0=first chunk, 1-N=specific chunk). Default: 0
        instance_id: Target JADX instance name.
    """
    return await tools.class_tools.get_main_activity_class(chunk=chunk, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_class_info(class_name: str, instance_id: Optional[str] = None) -> dict:
    """Get structured information about a class including inheritance, interfaces, and members.

    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    
    Returns:
        dict with: class_name, package, super_class, interfaces, is_abstract, 
                   method_count, field_count, method_names, field_names
    """
    return await tools.class_tools.get_class_info(class_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_decompile_status(instance_id: Optional[str] = None) -> dict:
    """Get current JADX status with cache, memory, and thread metrics.
    
    **IMPORTANT: Call this BEFORE resource-intensive operations!**
    
    Use the returned metrics to make informed decisions:
    - `cached_percentage` < 20%: Avoid search_in='code', use 'class'/'method' instead
    - `memory.usage_percentage` > 85%: Reduce batch sizes, avoid smali
    - `search_lock.locked` = true: Wait and retry, another search is running
    
    Expected response time: <100ms
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    
    Returns:
        dict with:
        - total_classes: Total classes in APK
        - cached_classes: Classes with state PROCESS_COMPLETE
        - cached_percentage: Percentage of cached classes (0-100)
        - memory: {max_mb, total_mb, used_mb, free_mb, usage_percentage}
        - threads: {active_count, peak_count, daemon_count}
        - jadx_config: {threads_count, code_cache_mode}
        - search_lock: {locked, held_seconds, timeout_seconds}
    """
    return await tools.class_tools.get_decompile_status(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def rename(
    target_type: str,
    old_name: str,
    new_name: str,
    class_name: str = "",
    method_name: str = "",
    instance_id: Optional[str] = None
) -> dict:
    """Unified rename tool for classes, methods, fields, packages, and variables.

    Args:
        target_type: Type of target to rename: "class" | "method" | "field" | "package" | "variable"
        old_name: Current name (fully qualified for class/package, simple name for method/field/variable)
        new_name: New name (simple name)
        class_name: Required for method/field/variable - the class containing the member
        method_name: Required for variable - the method containing the variable
        instance_id: Target JADX instance name

    Returns:
        dict: {success: bool, message: str, renamed_count: int (for package only)}

    Examples:
        # Rename class
        rename("class", "com.example.OldClass", "NewClass")

        # Rename method
        rename("method", "oldMethod", "newMethod", class_name="com.example.MyClass")

        # Rename field
        rename("field", "oldField", "newField", class_name="com.example.MyClass")

        # Rename package
        rename("package", "com.example.old", "com.example.new")

        # Rename local variable
        rename("variable", "a", "userId", class_name="com.example.MyClass", method_name="login")

    Note:
        Triggers 30s class cache cooldown.
    """
    target_type = target_type.lower()

    if target_type == "class":
        return await tools.refactor_tools.rename_class(old_name, new_name, instance_id=instance_id)
    elif target_type == "method":
        if not class_name:
            return {"success": False, "error": "class_name required for method rename"}
        return await tools.refactor_tools.rename_method(class_name, old_name, new_name, instance_id=instance_id)
    elif target_type == "field":
        if not class_name:
            return {"success": False, "error": "class_name required for field rename"}
        return await tools.refactor_tools.rename_field(class_name, old_name, new_name, instance_id=instance_id)
    elif target_type == "package":
        return await tools.refactor_tools.rename_package(old_name, new_name, instance_id=instance_id)
    elif target_type == "variable":
        if not class_name:
            return {"success": False, "error": "class_name required for variable rename"}
        if not method_name:
            return {"success": False, "error": "method_name required for variable rename"}
        return await tools.refactor_tools.rename_variable(class_name, method_name, old_name, new_name, instance_id=instance_id)
    else:
        return {"success": False, "error": f"Invalid target_type: {target_type}. Use: class, method, field, package, variable"}


@mcp.tool()
@with_busy_check
async def get_method_signature(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
    """Get structured method signature with Frida-compatible type information.
    
    Returns frida_overload string for each method overload.
    
    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        method_name: Method name to get signature for
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.search_tools.get_method_signature(class_name, method_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_method_callees(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
    """Get methods called by the specified method (callees analysis).
    
    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        method_name: Method name to analyze
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.search_tools.get_method_callees(class_name, method_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def search_native_methods(
    package: str = "",
    offset: int = 0,
    count: int = 50,
    instance_id: Optional[str] = None
) -> dict:
    """Search for all native methods across the APK (metadata-only, fast).
    
    Native methods are the bridge between Java and native code (JNI).
    This operation does NOT trigger decompilation - it reads DEX metadata directly.
    
    Args:
        package: Optional package filter (e.g., 'com.xingin')
        offset: Pagination offset. Default: 0
        count: Max results (max: 200). Default: 50
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.search_tools.search_native_methods(package, offset, count, instance_id=instance_id)



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
    target_type = target_type.lower()
    
    if target_type == "class":
        return await tools.xrefs_tools.get_xrefs_to_class(class_name, offset, count, instance_id=instance_id)
    elif target_type == "method":
        if not member_name:
            return {"error": "member_name required for method xrefs"}
        return await tools.xrefs_tools.get_xrefs_to_method(class_name, member_name, offset, count, instance_id=instance_id)
    elif target_type == "field":
        if not member_name:
            return {"error": "member_name required for field xrefs"}
        return await tools.xrefs_tools.get_xrefs_to_field(class_name, member_name, offset, count, instance_id=instance_id)
    else:
        return {"error": f"Invalid target_type: {target_type}. Use: class, method, field"}



@mcp.tool()
@with_busy_check
async def batch_get_xrefs(targets: list[str], instance_id: Optional[str] = None) -> dict:
    """Fetch cross-references for multiple targets in a single request.
    
    Args:
        targets: List of "type:class[:member]" strings.
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.xrefs_tools.batch_get_xrefs(targets, instance_id=instance_id)




# ==================== Transfer API Tools ====================

@mcp.tool()
async def create_transfer_token(
    operation: str = "download",
    resource_type: str = "batch_classes",
    timeout_seconds: int = 120,
    params: Optional[dict] = None,
    instance_id: Optional[str] = None
) -> dict:
    """Create a transfer token for large file download bypassing MCP size limits.
    
    Use this when batch operations might exceed MCP message size limits (~16KB).
    Supports JSON and ZIP formats, with Brotli/GZIP compression.
    
    Args:
        operation: "download" (currently only download supported)
        resource_type: "batch_classes" | "batch_methods" | "project_export"
        timeout_seconds: Token validity period in seconds (default: 120)
        params: Optional request parameters
        instance_id: JADX instance ID
    
    Returns:
        dict with token, mcp_server_url, transfer_url, expires_in, etc.
    
    Python Usage Example:
        ```python
        import httpx
        
        # Step 1: Create token
        result = await create_transfer_token(
            resource_type="batch_classes",
            timeout_seconds=300
        )
        token = result["token"]
        mcp_url = result["mcp_server_url"]  # Use this, not transfer_url
        
        # Step 2: Download data via HTTP
        async with httpx.AsyncClient() as client:
            # JSON format (default)
            response = await client.get(
                f"{mcp_url}/transfer/download/batch-classes",
                params={
                    "classes": "com.example.ClassA,com.example.ClassB",
                    "token": token,
                    "format": "json"
                }
            )
            data = response.json()
            print(f"Downloaded {data['found']} classes")
            
            # ZIP format
            response = await client.get(
                f"{mcp_url}/transfer/download/batch-classes",
                params={
                    "classes": "com.example.ClassA",
                    "token": token,
                    "format": "zip"
                }
            )
            with open("classes.zip", "wb") as f:
                f.write(response.content)
        
        # Step 3: Clean up (optional, token auto-expires)
        await revoke_transfer_token(token)
        ```
    
    Supported Formats (query param 'format'):
        - json: Returns JSON data (default)
        - zip: Returns ZIP archive with .java files
    
    Supported Compressions (query param 'compression'):
        - auto: Automatic based on Accept-Encoding (default)
        - br: Brotli compression (best ratio)
        - gzip: GZIP compression
        - none: No compression
    """
    return await transfer_tools.create_transfer_token(
        operation, resource_type, timeout_seconds, params, instance_id
    )




def main():
    parser = argparse.ArgumentParser(
        "MCP Server for Jadx",
        description="JADX AI MCP Server - Connect Claude AI with JADX decompiler"
    )
    parser.add_argument(
        "--http",
        help="Serve MCP Server over HTTP stream.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--port",
        help="Port for --http (default:8651)",
        default=8651,
        type=int
    )
    parser.add_argument(
        "--host",
        help="Bind address for MCP server (default:127.0.0.1). Use 0.0.0.0 to allow external connections",
        default="127.0.0.1",
        type=str
    )
    parser.add_argument(
        "--jadx-host",
        help="JADX AI MCP Plugin host address (default:127.0.0.1)",
        default="127.0.0.1",
        type=str
    )
    parser.add_argument(
        "--jadx-port",
        help="JADX AI MCP Plugin port (default:8650)",
        default=8650,
        type=int,
    )
    parser.add_argument(
        "--auth-token",
        help="Authentication token for JADX plugin (shared across all instances)",
        default=None,
        type=str
    )
    parser.add_argument(
        "--jadx-instances",
        help="Initial JADX instances to connect: host:port[:name],host:port[:name]...",
        default=None,
        type=str
    )
    parser.add_argument(
        "--max-busy-timeout",
        help="Maximum time (seconds) an instance can be busy before auto-release (default: 300)",
        default=300,
        type=int
    )
    parser.add_argument(
        "--request-timeout",
        help="HTTP request timeout in seconds for JADX plugin requests (default: 120)",
        default=120,
        type=int
    )
    parser.add_argument(
        "--config",
        help="Path to TOML configuration file (e.g., data/config/jadx-config.toml)",
        default=None,
        type=str
    )
    parser.add_argument(
        "--mcp-auth-token",
        help="Authentication token for MCP clients connecting to this server",
        default=None,
        type=str
    )
    args = parser.parse_args()

    # ========== Load Configuration File (if provided) ==========
    from pathlib import Path
    from src.server.config_loader import ConfigLoader, set_config_loader, AppConfig
    
    loaded_config: AppConfig = None
    config_loader: ConfigLoader = None
    
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            config_loader = ConfigLoader(config_path)
            loaded_config = config_loader.load()
            set_config_loader(config_loader)
            print(f"[OK] Loaded configuration from {config_path}")
            
            # Apply config file values only when CLI uses defaults (CLI takes precedence)
            if loaded_config.server.host and args.host == parser.get_default("host"):
                args.host = loaded_config.server.host
            if loaded_config.server.port and args.port == parser.get_default("port"):
                args.port = loaded_config.server.port
            if loaded_config.defaults.request_timeout:
                args.request_timeout = loaded_config.defaults.request_timeout
            if loaded_config.defaults.busy_timeout:
                args.max_busy_timeout = loaded_config.defaults.busy_timeout
        else:
            print(f"[WARN] Config file not found: {config_path}, using CLI arguments")

    # Configure busy timeout
    InstanceBusyTracker.set_timeout(args.max_busy_timeout)
    print(f"[OK] Busy timeout set to {args.max_busy_timeout} seconds")

    # Configure request timeout
    config.set_request_timeout(args.request_timeout)
    print(f"[OK] Request timeout set to {args.request_timeout} seconds")

    # Configure JADX connection (for backward compatibility)
    config.set_jadx_config(host=args.jadx_host, port=args.jadx_port)

    # ========== Multi-User Authentication Setup ==========
    from src.server.user_auth import UserAuthManager
    
    # Get default JADX token from config or CLI
    default_jadx_token = ""
    if loaded_config and loaded_config.defaults.jadx_token:
        default_jadx_token = loaded_config.defaults.jadx_token
    if args.auth_token:  # CLI overrides config
        default_jadx_token = args.auth_token
    
    # Set shared JADX token
    if default_jadx_token:
        config.set_auth_token(default_jadx_token)
        InstanceRegistry.set_auth_token(default_jadx_token)
        print(f"[OK] Default JADX plugin token configured")
    else:
        print("[WARN] No default JADX plugin token (instances may need individual tokens)")
    
    # Configure multi-user authentication
    allow_anonymous = True  # Allow anonymous if no users configured
    if loaded_config and loaded_config.users:
        UserAuthManager.configure(
            users=loaded_config.users,
            default_jadx_token=default_jadx_token,
            allow_anonymous=False  # Require auth if users are configured
        )
        print(f"[OK] Multi-user authentication enabled ({len(loaded_config.users)} users)")
        for user in loaded_config.users:
            role = "admin" if user.is_admin else "user"
            print(f"  - {user.name} ({role})")
        allow_anonymous = False
    elif args.mcp_auth_token:
        # Single token mode (legacy)
        UserAuthManager.configure(
            users=[],
            default_jadx_token=default_jadx_token,
            allow_anonymous=True
        )
        print(f"[OK] Single-token authentication mode")
    else:
        # No authentication
        UserAuthManager.configure(
            users=[],
            default_jadx_token=default_jadx_token,
            allow_anonymous=True
        )
        print("[WARN] No MCP authentication configured")
        print("  Add [[users]] to config or use --mcp-auth-token")

    # Banner & Health Check
    try:
        print(jadx_mcp_server_banner())
    except:
        from src.banner import SERVER_VERSION
        print(
            f"[JADX AI MCP Server] v{SERVER_VERSION} | MCP: {args.host}:{args.port} | JADX: {args.jadx_host}:{args.jadx_port}"
        )

    # ========== Initialize JADX Instances ==========
    import asyncio
    
    async def init_all_instances():
        """Initialize JADX instances from config file and/or CLI"""
        instances_added = 0
        
        # 1. Load instances from config file (register as pending, health monitor will connect)
        if loaded_config and loaded_config.jadx_instances:
            print(f"\nRegistering JADX instances from config file...")
            for inst_cfg in loaded_config.jadx_instances:
                if not inst_cfg.enabled:
                    print(f"  [-] Skipped (disabled): {inst_cfg.name}")
                    continue
                
                # Register as pending - health monitor will attempt connection
                result = InstanceRegistry.register_pending_instance(
                    name=inst_cfg.name,
                    host=inst_cfg.host, 
                    port=inst_cfg.port,
                    token=inst_cfg.token if inst_cfg.token else None,
                )
                if result["success"]:
                    print(f"  [OK] Registered: {inst_cfg.name} ({inst_cfg.host}:{inst_cfg.port}) [pending]")
                    instances_added += 1
                else:
                    print(f"  [FAIL] Failed: {inst_cfg.name}: {result['message']}")
        
        # 2. Load instances from CLI --jadx-instances
        if args.jadx_instances:
            print(f"\nLoading JADX instances from CLI...")
            for inst_str in args.jadx_instances.split(","):
                parts = inst_str.strip().split(":")
                if len(parts) >= 2:
                    host = parts[0]
                    try:
                        port = int(parts[1])
                        name = parts[2] if len(parts) > 2 else None
                        result = await InstanceRegistry.add_instance(host, port, name)
                        if result["success"]:
                            print(f"  [OK] Added: {result['instance']['name']} ({host}:{port})")
                            instances_added += 1
                        else:
                            print(f"  [FAIL] Failed: {host}:{port}: {result['message']}")
                    except ValueError:
                        print(f"  [FAIL] Invalid port: {inst_str}")
                else:
                    print(f"  [FAIL] Invalid format: {inst_str}")
        
        # 3. If no instances configured, try default connection
        if instances_added == 0 and not args.jadx_instances and not (loaded_config and loaded_config.jadx_instances):
            print(f"\nTesting default JADX connection at {args.jadx_host}:{args.jadx_port}...")
            try:
                result = await InstanceRegistry.add_instance(args.jadx_host, args.jadx_port)
                if result["success"]:
                    print(f"[OK] Default JADX instance connected")
                    instances_added += 1
                else:
                    print(f"[WARN] Could not connect to default JADX: {result['message']}")
            except Exception as e:
                print(f"[WARN] Default connection failed: {e}")
        
        return instances_added
    
    try:
        instance_count = asyncio.run(init_all_instances())
        print(f"\n[OK] Total JADX instances: {instance_count}")
    except Exception as e:
        print(f"[WARN] Instance initialization error: {e}")

    # ========== Config Hot-Reload Callback ==========
    async def on_config_change(new_config: AppConfig):
        """Handle configuration file changes"""
        print(f"\n[Hot-Reload] Configuration changed, updating instances...")
        
        # Get current instance names
        current_names = {inst["name"] for inst in InstanceRegistry.list_instances()}
        
        # Get new enabled instance names from config
        new_names = {inst.name for inst in new_config.jadx_instances if inst.enabled}
        
        # Remove instances no longer in config (system-level operation)
        for name in current_names - new_names:
            result = InstanceRegistry.remove_instance(name, username="system", is_admin=True)
            print(f"  [Hot-Reload] Removed: {name}")
        
        # Add new instances from config
        for inst_cfg in new_config.jadx_instances:
            if inst_cfg.enabled and inst_cfg.name not in current_names:
                result = await InstanceRegistry.add_instance(
                    inst_cfg.host, inst_cfg.port, inst_cfg.name
                )
                if result["success"]:
                    print(f"  [Hot-Reload] Added: {inst_cfg.name}")
                else:
                    print(f"  [Hot-Reload] Failed to add {inst_cfg.name}: {result['message']}")
        
        print(f"  [Hot-Reload] Complete. Instances: {InstanceRegistry.get_instance_count()}")

    # ========== Run MCP Server ==========
    # Register instance management tools
    register_instance_tools(mcp)
    
    # Register Prompts
    register_prompts(mcp)
    
    # Register Resources (usage guide, decision matrix, benchmarks)
    register_resources(mcp)
    
    # Register authentication middleware (HTTP mode only)
    require_auth = bool(loaded_config and loaded_config.users) and not allow_anonymous
    auth_middleware = BearerAuthMiddleware(require_auth=require_auth)
    mcp.add_middleware(auth_middleware)
    if require_auth:
        print(f"[OK] Authentication middleware enabled (required)")
    else:
        print(f"[OK] Authentication middleware enabled (optional)")
    
    if args.http:
        # 设置 MCP Server URL 供 Transfer API 使用（从配置文件读取）
        if loaded_config and loaded_config.server.mcp_url:
            set_mcp_server_url_from_config(loaded_config.server.mcp_url)
            print(f"[OK] Transfer API URL: {loaded_config.server.mcp_url}")
        
        print(f"\nStarting MCP server in HTTP mode on {args.host}:{args.port}...")
        if args.mcp_auth_token or (loaded_config and loaded_config.users):
            print(f"  Clients must provide: Authorization: Bearer <token>")
        
        # Start config watcher in background (for HTTP mode only)
        if config_loader:
            config_loader.add_change_callback(on_config_change)
            # Note: Hot-reload watcher runs in the async event loop managed by FastMCP
            print(f"  Config hot-reload: enabled")
        
        # Start background health monitor for JADX instances
        health_interval = loaded_config.defaults.health_check_interval if loaded_config else 30
        HealthMonitor.configure(interval=health_interval)
        
        # Start health monitor in a background thread with its own event loop
        import threading
        import signal
        
        def run_health_monitor():
            """Run health monitor in a separate thread with its own event loop."""
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(HealthMonitor.start())
                loop.run_forever()
            except Exception as e:
                print(f"Health monitor error: {e}")
            finally:
                loop.close()
        
        health_thread = threading.Thread(target=run_health_monitor, daemon=True)
        health_thread.start()
        
        print(f"  Health monitor: enabled (interval: {health_interval}s)")
        
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        print("\nStarting MCP server in stdio mode...")
        mcp.run()


if __name__ == "__main__":
    main()

