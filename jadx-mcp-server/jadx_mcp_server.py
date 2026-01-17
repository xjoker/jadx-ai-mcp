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

For detailed guidance, use the 'status-check' or 'search-code' prompts.
"""

mcp = FastMCP(
    "JADX-AI-MCP Plugin Reverse Engineering Server", 
    stateless_http=True,
    instructions=MCP_INSTRUCTIONS
)

# Import and register ALL tools using correct FastMCP pattern
from src.server.tools.class_tools import (
    fetch_current_class, get_selected_text, get_class_source, batch_get_class_source,
    get_all_classes, get_methods_of_class, get_fields_of_class, get_smali_of_class,
    get_main_application_classes_names, get_main_application_classes_code, get_main_activity_class,
    get_class_info
)
from src.server.tools.search_tools import (
    get_method_by_name, search_method_by_name, batch_get_method_by_name, search_classes_by_keyword,
    get_method_signature, get_method_callees, search_native_methods
)

from src.server.tools.resource_tools import (
    get_android_manifest, get_strings, get_all_resource_file_names,
    get_resource_file, jar_get_manifest, jar_get_services, jar_get_entry_points
)
from src.server.tools.refactor_tools import (
    rename_class, rename_method, rename_field, rename_package
)
from src.server.tools.debug_tools import (
    debug_get_stack_frames, debug_get_threads, debug_get_variables
)
from src.server.tools.xrefs_tools import (
    get_xrefs_to_class, get_xrefs_to_method, get_xrefs_to_field, batch_get_xrefs
)
from src.server.prompts import register_prompts
from src.server.resources import register_resources
from src.server.tools.instance_tools import register_instance_tools
from src.server.instance_registry import InstanceRegistry
from src.server.busy_tracker import with_busy_check, InstanceBusyTracker
from src.server.auth_middleware import BearerAuthMiddleware
from src.server.health_monitor import HealthMonitor
from src.server.logging_config import configure_logging, get_logger

logger = get_logger("main")


# CORRECT REGISTRATION PATTERN for FastMCP
# All tools support optional instance_id for multi-instance targeting
from typing import Optional


@mcp.tool()
@with_busy_check
async def fetch_current_class(instance_id: Optional[str] = None) -> dict:
    """Fetch the currently selected class and its code from the JADX-GUI plugin.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.fetch_current_class(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_selected_text(instance_id: Optional[str] = None) -> dict:
    """Returns the currently selected text in the decompiled code view.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_selected_text(instance_id=instance_id)


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
async def get_class_source(class_name: str, instance_id: Optional[str] = None) -> dict:
    """Fetch the Java source of a specific class.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.MainActivity').
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_class_source(class_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def batch_get_class_source(class_names: list[str], instance_id: Optional[str] = None) -> dict:
    """Fetch multiple class sources in a single request. Maximum 20 classes.
    
    Reduces MCP interaction overhead when analyzing multiple related classes.

    Args:
        class_names: List of fully qualified class names (e.g., ['com.example.A', 'com.example.B']).
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.batch_get_class_source(class_names, instance_id=instance_id)


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
async def batch_get_method_by_name(methods: list[str], instance_id: Optional[str] = None) -> dict:
    """Fetch multiple method sources in a single request. Maximum 20 methods.
    
    Reduces MCP interaction overhead when analyzing multiple methods.

    Args:
        methods: List of "class_name:method_name" pairs (e.g., ['com.example.A:methodA', 'com.example.B:methodB']).
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.search_tools.batch_get_method_by_name(methods, instance_id=instance_id)


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
    """Search for classes containing a specific keyword with flexible filtering options.
    
    **PERFORMANCE CHARACTERISTICS:**
    | search_in | Expected Time | Requires Cache | Notes |
    |-----------|--------------|----------------|-------|
    | class     | <100ms       | No             | Fastest, searches class names |
    | method    | <100ms       | No             | Fast, searches method names |
    | field     | <100ms       | No             | Fast, searches field names |
    | code      | 1-60s        | Yes            | Slow! May timeout on uncached APKs |
    | comment   | 1-60s        | Yes            | Slow! Searches code comments |
    
    **DECISION GUIDE:**
    - Check `get_decompile_status()` first!
    - If `cached_percentage` < 20%: Use 'class', 'method', or 'field' only
    - If `search_lock.locked` = true: Wait and retry
    - Use `package` filter to reduce scope and improve performance
    
    Args:
        search_term: The keyword or string to search for.
        package: Package name to limit search scope (e.g., 'com.example'). Strongly recommended!
        exclude: Comma-separated package prefixes to exclude.
        search_in: Search scope: class, method, field, code, comment. Default: code
        offset: Starting index for result pagination. Default: 0
        count: Maximum number of results (max: 200). Default: 20
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
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
async def get_smali_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
    """Fetch the smali (Dalvik bytecode) representation of a class.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.MainActivity').
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_smali_of_class(class_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_android_manifest(instance_id: Optional[str] = None) -> dict:
    """Retrieve and return the AndroidManifest.xml content.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.get_android_manifest(instance_id=instance_id)


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
    """Retrieve all resource files names.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.get_all_resource_file_names(offset, count, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_resource_file(resource_name: str, instance_id: Optional[str] = None) -> dict:
    """Retrieve resource file content.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.get_resource_file(resource_name, instance_id=instance_id)


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
async def get_main_application_classes_names(instance_id: Optional[str] = None) -> dict:
    """Fetch main application classes' names from Manifest package.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_main_application_classes_names(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_main_application_classes_code(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
    """Fetch main application classes' code with pagination.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_main_application_classes_code(offset, count, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_main_activity_class(instance_id: Optional[str] = None) -> dict:
    """Fetch the main activity class from AndroidManifest.xml.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.class_tools.get_main_activity_class(instance_id=instance_id)


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
async def rename_class(class_name: str, new_name: str, instance_id: Optional[str] = None) -> dict:
    """Renames a specific class.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.refactor_tools.rename_class(class_name, new_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def rename_method(method_name: str, new_name: str, instance_id: Optional[str] = None) -> dict:
    """Renames a specific method.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.refactor_tools.rename_method(method_name, new_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def rename_field(class_name: str, field_name: str, new_name: str, instance_id: Optional[str] = None) -> dict:
    """Renames a specific field.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.refactor_tools.rename_field(class_name, field_name, new_name, instance_id=instance_id)


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
async def rename_package(old_package_name: str, new_package_name: str, instance_id: Optional[str] = None) -> dict:
    """Renames a package and all its classes.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.refactor_tools.rename_package(old_package_name, new_package_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def debug_get_stack_frames(instance_id: Optional[str] = None) -> dict:
    """Get current stack frames (call stack).
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.debug_tools.debug_get_stack_frames(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def debug_get_threads(instance_id: Optional[str] = None) -> dict:
    """Get all threads in the debugged process.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.debug_tools.debug_get_threads(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def debug_get_variables(instance_id: Optional[str] = None) -> dict:
    """Get current variables when process is suspended.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.debug_tools.debug_get_variables(instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_xrefs_to_class(class_name: str, offset: int = 0, count: int = 20, instance_id: Optional[str] = None) -> dict:
    """Find all cross-references (xrefs) to a class.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.Helper').
        offset: Starting index for pagination (default: 0).
        count: Maximum results to return (default: 20).
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.xrefs_tools.get_xrefs_to_class(class_name, offset, count, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_xrefs_to_method(
    class_name: str, method_name: str, offset: int = 0, count: int = 20, instance_id: Optional[str] = None
) -> dict:
    """Find all references to a method.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.xrefs_tools.get_xrefs_to_method(
        class_name, method_name, offset, count, instance_id=instance_id
    )


@mcp.tool()
@with_busy_check
async def get_xrefs_to_field(
    class_name: str, field_name: str, offset: int = 0, count: int = 20, instance_id: Optional[str] = None
) -> dict:
    """Find all references to a field.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.xrefs_tools.get_xrefs_to_field(
        class_name, field_name, offset, count, instance_id=instance_id
    )


@mcp.tool()
@with_busy_check
async def batch_get_xrefs(targets: list[str], instance_id: Optional[str] = None) -> dict:
    """Fetch cross-references for multiple targets in a single request.
    
    Args:
        targets: List of "type:class[:member]" strings.
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.xrefs_tools.batch_get_xrefs(targets, instance_id=instance_id)


@mcp.tool()
async def check_instance_status(instance_name: str = None) -> dict:
    """Query the busy status of JADX instances.
    
    Use this to check if an instance is available before making requests.
    If an instance is busy, the response will include what operation is running.
    
    Args:
        instance_name: Optional. Specific instance to check. If not provided, returns all instances status.
    
    Returns:
        Single instance: {"instance": "name", "available": true/false, "current_operation": "..."}
        All instances: {"busy_instances": [...], "count": N}
    """
    return await InstanceBusyTracker.get_status(instance_name)


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
            print(f"✓ Loaded configuration from {config_path}")
            
            # Override CLI args with config file values (config file takes precedence)
            if loaded_config.server.host and args.host == "127.0.0.1":
                args.host = loaded_config.server.host
            if loaded_config.server.port and args.port == 8651:
                args.port = loaded_config.server.port
            if loaded_config.defaults.request_timeout:
                args.request_timeout = loaded_config.defaults.request_timeout
            if loaded_config.defaults.busy_timeout:
                args.max_busy_timeout = loaded_config.defaults.busy_timeout
        else:
            print(f"⚠ Config file not found: {config_path}, using CLI arguments")

    # Configure busy timeout
    InstanceBusyTracker.set_timeout(args.max_busy_timeout)
    print(f"✓ Busy timeout set to {args.max_busy_timeout} seconds")

    # Configure request timeout
    config.set_request_timeout(args.request_timeout)
    print(f"✓ Request timeout set to {args.request_timeout} seconds")

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
        print(f"✓ Default JADX plugin token configured")
    else:
        print("⚠ No default JADX plugin token (instances may need individual tokens)")
    
    # Configure multi-user authentication
    allow_anonymous = True  # Allow anonymous if no users configured
    if loaded_config and loaded_config.users:
        UserAuthManager.configure(
            users=loaded_config.users,
            default_jadx_token=default_jadx_token,
            allow_anonymous=False  # Require auth if users are configured
        )
        print(f"✓ Multi-user authentication enabled ({len(loaded_config.users)} users)")
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
        print(f"✓ Single-token authentication mode")
    else:
        # No authentication
        UserAuthManager.configure(
            users=[],
            default_jadx_token=default_jadx_token,
            allow_anonymous=True
        )
        print("⚠ No MCP authentication configured")
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
                    print(f"  ⊘ Skipped (disabled): {inst_cfg.name}")
                    continue
                
                # Register as pending - health monitor will attempt connection
                result = InstanceRegistry.register_pending_instance(
                    name=inst_cfg.name,
                    host=inst_cfg.host, 
                    port=inst_cfg.port,
                    token=inst_cfg.token if inst_cfg.token else None,
                )
                if result["success"]:
                    print(f"  ✓ Registered: {inst_cfg.name} ({inst_cfg.host}:{inst_cfg.port}) [pending]")
                    instances_added += 1
                else:
                    print(f"  ✗ Failed: {inst_cfg.name}: {result['message']}")
        
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
                            print(f"  ✓ Added: {result['instance']['name']} ({host}:{port})")
                            instances_added += 1
                        else:
                            print(f"  ✗ Failed: {host}:{port}: {result['message']}")
                    except ValueError:
                        print(f"  ✗ Invalid port: {inst_str}")
                else:
                    print(f"  ✗ Invalid format: {inst_str}")
        
        # 3. If no instances configured, try default connection
        if instances_added == 0 and not args.jadx_instances and not (loaded_config and loaded_config.jadx_instances):
            print(f"\nTesting default JADX connection at {args.jadx_host}:{args.jadx_port}...")
            try:
                result = await InstanceRegistry.add_instance(args.jadx_host, args.jadx_port)
                if result["success"]:
                    print(f"✓ Default JADX instance connected")
                    instances_added += 1
                else:
                    print(f"⚠ Could not connect to default JADX: {result['message']}")
            except Exception as e:
                print(f"⚠ Default connection failed: {e}")
        
        return instances_added
    
    try:
        instance_count = asyncio.run(init_all_instances())
        print(f"\n✓ Total JADX instances: {instance_count}")
    except Exception as e:
        print(f"⚠ Instance initialization error: {e}")

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
        print(f"✓ Authentication middleware enabled (required)")
    else:
        print(f"✓ Authentication middleware enabled (optional)")
    
    if args.http:
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

