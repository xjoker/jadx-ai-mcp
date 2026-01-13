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

# Initialize MCP Server
mcp = FastMCP("JADX-AI-MCP Plugin Reverse Engineering Server")

# Import and register ALL tools using correct FastMCP pattern
from src.server.tools.class_tools import (
    fetch_current_class, get_selected_text, get_class_source,
    get_all_classes, get_methods_of_class, get_fields_of_class, get_smali_of_class,
    get_main_application_classes_names, get_main_application_classes_code, get_main_activity_class
)
from src.server.tools.search_tools import (
    get_method_by_name, search_method_by_name, search_classes_by_keyword
)
from src.server.tools.resource_tools import (
    get_android_manifest, get_strings, get_all_resource_file_names,
    get_resource_file
)
from src.server.tools.refactor_tools import (
    rename_class, rename_method, rename_field, rename_package
)
from src.server.tools.debug_tools import (
    debug_get_stack_frames, debug_get_threads, debug_get_variables
)
from src.server.tools.xrefs_tools import (
    get_xrefs_to_class, get_xrefs_to_method, get_xrefs_to_field
)
from src.server.tools.instance_tools import register_instance_tools
from src.server.instance_registry import InstanceRegistry
from src.server.busy_tracker import with_busy_check, InstanceBusyTracker


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
async def search_method_by_name(method_name: str, instance_id: Optional[str] = None) -> dict:
    """Search for a method name across all classes in the APK.

    Args:
        method_name: Method name to search for (partial matching supported).
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.search_tools.search_method_by_name(method_name, instance_id=instance_id)


@mcp.tool()
@with_busy_check
async def get_methods_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
    """List all method names in a class (useful for seeing overloaded methods).

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
    search_in: str = "code",
    offset: int = 0,
    count: int = 20,
    instance_id: Optional[str] = None,
) -> dict:
    """Search for classes containing a specific keyword with flexible filtering options.

    Args:
        search_term: The keyword or string to search for.
        package: Package name to limit search scope (optional).
        search_in: Comma-separated search scopes: class,method,field,code,comment. Default: code
        offset: Starting index for pagination. Default: 0
        count: Maximum number of results. Default: 20
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.search_tools.search_classes_by_keyword(
        search_term, package, search_in, offset, count, instance_id=instance_id
    )


@mcp.tool()
@with_busy_check
async def get_fields_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
    """List all field names in a class.

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
async def get_strings(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
    """Retrieve contents of strings.xml files.
    
    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.
    """
    return await tools.resource_tools.get_strings(offset, count, instance_id=instance_id)


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
    args = parser.parse_args()

    # Configure busy timeout
    InstanceBusyTracker.set_timeout(args.max_busy_timeout)
    print(f"✓ Busy timeout set to {args.max_busy_timeout} seconds")

    # Configure request timeout
    config.set_request_timeout(args.request_timeout)
    print(f"✓ Request timeout set to {args.request_timeout} seconds")

    # Configure JADX connection (for backward compatibility)
    config.set_jadx_config(host=args.jadx_host, port=args.jadx_port)

    # Configure authentication (shared across all instances)
    if args.auth_token:
        config.set_auth_token(args.auth_token)
        InstanceRegistry.set_auth_token(args.auth_token)
        print(f"✓ Authentication enabled (token configured for all instances)")
    else:
        print("⚠ Authentication disabled (no token provided)")
        print("  If JADX plugin has auth enabled, use --auth-token parameter")

    # Banner & Health Check
    try:
        print(jadx_mcp_server_banner())
    except:
        from src.banner import SERVER_VERSION
        print(
            f"[JADX AI MCP Server] v{SERVER_VERSION} | MCP: {args.host}:{args.port} | JADX: {args.jadx_host}:{args.jadx_port}"
        )

    # Process initial JADX instances from command line
    # Format: host:port[:name],host:port[:name],...
    if args.jadx_instances:
        import asyncio
        print(f"\nInitializing JADX instances from command line...")
        instances_str = args.jadx_instances.split(",")
        
        async def init_instances():
            for inst_str in instances_str:
                parts = inst_str.strip().split(":")
                if len(parts) >= 2:
                    host = parts[0]
                    try:
                        port = int(parts[1])
                        name = parts[2] if len(parts) > 2 else None
                        result = await InstanceRegistry.add_instance(host, port, name)
                        if result["success"]:
                            print(f"  ✓ Added: {result['instance']['name']} ({host}:{port})")
                        else:
                            print(f"  ✗ Failed to add {host}:{port}: {result['message']}")
                    except ValueError:
                        print(f"  ✗ Invalid port in: {inst_str}")
                else:
                    print(f"  ✗ Invalid format: {inst_str} (expected host:port[:name])")
        
        asyncio.run(init_instances())
        print(f"Initialized {InstanceRegistry.get_instance_count()} instance(s)")
    else:
        # Add default instance from --jadx-host/--jadx-port
        print(f"\nTesting JADX AI MCP Plugin connectivity at {args.jadx_host}:{args.jadx_port}...")
        result = config.health_ping()
        print(f"Health check result: {result}")

        if isinstance(result, dict) and "error" in result:
            print("⚠ Warning: Could not connect to JADX plugin. Make sure:")
            print("  1. JADX GUI is running")
            print("  2. JADX AI MCP Plugin is installed and active")
            print("  3. Plugin is listening on the configured host and port")
            print("  4. If using non-default host, use --jadx-host parameter")
            print("  5. If auth is enabled, provide --auth-token parameter")
        else:
            # Auto-add the default instance
            import asyncio
            async def add_default():
                await InstanceRegistry.add_instance(args.jadx_host, args.jadx_port)
            try:
                asyncio.run(add_default())
                print(f"✓ Default JADX instance registered")
            except Exception as e:
                print(f"⚠ Could not auto-register default instance: {e}")

    # Run Server
    if args.http:
        print(f"Starting MCP server in HTTP mode on {args.host}:{args.port}...")
        # Register instance management tools before running
        register_instance_tools(mcp)
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        print("Starting MCP server in stdio mode...")
        # Register instance management tools before running
        register_instance_tools(mcp)
        mcp.run()


if __name__ == "__main__":
    main()
