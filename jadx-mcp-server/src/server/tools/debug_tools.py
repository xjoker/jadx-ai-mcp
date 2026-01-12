"""
JADX MCP Server - Debugging Tools

This module provides MCP tools for runtime debugging of Android applications
through JADX, enabling inspection of execution state, threads, and variables.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

from typing import Optional
from src.server.config import get_from_jadx


async def debug_get_stack_frames(instance_id: Optional[str] = None) -> dict:
    """
    Get current stack frames (call stack).

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Current execution stack trace when process is suspended

    MCP Tool: debug_get_stack_frames
    Description: Inspects call stack during debugging sessions
    """
    return await get_from_jadx("debug/stack-frames", instance_id=instance_id)


async def debug_get_threads(instance_id: Optional[str] = None) -> dict:
    """
    Get all threads in the debugged process.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: List of all active threads with their states

    MCP Tool: debug_get_threads
    Description: Enumerates all threads in the running application
    """
    return await get_from_jadx("debug/threads", instance_id=instance_id)


async def debug_get_variables(instance_id: Optional[str] = None) -> dict:
    """
    Get current variables when process is suspended.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Local and instance variables at current breakpoint

    MCP Tool: debug_get_variables
    Description: Inspects variable values during debugging pause
    """
    return await get_from_jadx("debug/variables", instance_id=instance_id)
