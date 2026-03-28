"""
JADX MCP Server - Frida Hook Generation Tools

This module provides MCP tools for automatically generating Frida hook scripts, supporting:
  - Hook scripts for single methods / constructors / all methods
  - Class-level tracing scripts (with optional subclass inclusion)
  - Enumeration scripts for class instances, static methods, and fields

Author: JADX AI MCP
License: See LICENSE file
"""

from typing import Optional
from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("frida_tools")


async def generate_frida_hook(
    class_name: str,
    method_name: Optional[str] = None,
    hook_type: str = "both",
    instance_id: Optional[str] = None,
) -> dict:
    """
    Generate a ready-to-run Frida hook script for the specified class/method.

    Supports overloaded methods (automatically generates .overload() calls for each overload).
    Uses FridaTypeConverter to ensure parameter type strings are correctly formatted.

    Args:
        class_name: Fully qualified class name (e.g. com.example.MainActivity)
        method_name: Method name (optional). If omitted, hook_type is automatically upgraded to all_methods.
        hook_type: Hook type, available values:
            - method_enter  — Print arguments at method entry only
            - method_exit   — Print return value at method return only
            - both          — Entry + return value (default)
            - constructor   — Hook all constructors
            - all_methods   — Hook all methods in the class
        instance_id: Optional. Target JADX instance name.

    Returns:
        dict:
            - class_name: Target class name
            - method_name: Target method name (or "(all)")
            - hook_type: The hook type used
            - script: Generated Frida JavaScript script

    MCP Tool: generate_frida_hook
    Description: Automatically generate ready-to-run Frida hook scripts with overload support and correct type conversion
    """
    params: dict = {"class_name": class_name, "hook_type": hook_type}
    if method_name:
        params["method_name"] = method_name

    result = await get_from_jadx("generate-frida-hook", params, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"generate_frida_hook error: {result.get('error')}")
    else:
        logger.info(f"generate_frida_hook: class={class_name}, method={method_name}, type={hook_type}")
    return result


async def generate_frida_trace(
    class_name: str,
    include_subclasses: bool = False,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Generate a Frida script that traces all method calls on the specified class.

    Each method call will print entry arguments and return values with a timestamp label,
    making it easy to quickly locate call chains in frida-trace / frida CLI.

    Args:
        class_name: Fully qualified class name (e.g. com.example.NetworkManager)
        include_subclasses: Whether to also trace direct subclasses in the same package. Default: False.
        instance_id: Optional. Target JADX instance name.

    Returns:
        dict:
            - class_name: Target class name
            - include_subclasses: Whether subclasses are included
            - script: Generated Frida JavaScript tracing script

    MCP Tool: generate_frida_trace
    Description: Generate a class-level Frida tracing script that records entry arguments and return values for all method calls
    """
    params: dict = {
        "class_name": class_name,
        "include_subclasses": "true" if include_subclasses else "false",
    }

    result = await get_from_jadx("generate-frida-trace", params, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"generate_frida_trace error: {result.get('error')}")
    else:
        logger.info(f"generate_frida_trace: class={class_name}, subclasses={include_subclasses}")
    return result


async def generate_frida_enum(
    class_name: str,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Generate a Frida script for enumerating class instances, calling static methods, and reading fields.

    Generated content:
    1. Read all static field values
    2. Call no-argument static methods and print results
    3. For enum classes, call values() to enumerate all constants
    4. Use Java.choose() to enumerate active instances in memory and read instance fields

    Args:
        class_name: Fully qualified class name (e.g. com.example.Config)
        instance_id: Optional. Target JADX instance name.

    Returns:
        dict:
            - class_name: Target class name
            - script: Generated Frida JavaScript enumeration script

    MCP Tool: generate_frida_enum
    Description: Generate a Frida script for enumerating class instances and static members, suitable for extracting runtime configuration and constants
    """
    params: dict = {"class_name": class_name}

    result = await get_from_jadx("generate-frida-enum", params, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"generate_frida_enum error: {result.get('error')}")
    else:
        logger.info(f"generate_frida_enum: class={class_name}")
    return result


# Save module-level function references to prevent shadowing by same-named functions inside register_frida_tools
_generate_frida_hook = generate_frida_hook
_generate_frida_trace = generate_frida_trace
_generate_frida_enum = generate_frida_enum


def register_frida_tools(mcp, with_busy_check):
    """Register Frida script generation tools with the MCP Server"""

    @mcp.tool()
    @with_busy_check
    async def generate_frida_hook(
        class_name: str,
        method_name: Optional[str] = None,
        hook_type: str = "both",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Generate a ready-to-run Frida hook script with overload support and correct type conversion.

        Available hook_type values:
          - method_enter  — Record entry arguments only
          - method_exit   — Record return value only
          - both          — Entry + return value (default)
          - constructor   — Hook all constructors
          - all_methods   — Hook all methods in the class

        Args:
            class_name: Fully qualified class name (e.g. 'com.example.MainActivity')
            method_name: Method name; if omitted, all_methods mode is used automatically
            hook_type: Hook type (see above), default 'both'
            instance_id: Optional. Target JADX instance name
        """
        return await _generate_frida_hook(
            class_name,
            method_name=method_name,
            hook_type=hook_type,
            instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def generate_frida_trace(
        class_name: str,
        include_subclasses: bool = False,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Generate a class-level Frida tracing script that records entry arguments and return values for all method calls.

        Args:
            class_name: Fully qualified class name (e.g. 'com.example.NetworkManager')
            include_subclasses: Whether to also trace direct subclasses. Default: False
            instance_id: Optional. Target JADX instance name
        """
        return await _generate_frida_trace(
            class_name,
            include_subclasses=include_subclasses,
            instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def generate_frida_enum(
        class_name: str,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Generate a Frida script for enumerating class instances and static members, suitable for extracting runtime configuration and constants.

        Generated content: static field reads, static method calls, enum values(), Java.choose() instance enumeration.

        Args:
            class_name: Fully qualified class name (e.g. 'com.example.Config')
            instance_id: Optional. Target JADX instance name
        """
        return await _generate_frida_enum(class_name, instance_id=instance_id)
