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


async def fetch_current_class(chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """
    Retrieves the currently opened class in JADX-GUI.

    CHUNKING SUPPORT: Large classes (>8KB) are automatically chunked.
    - If response contains `_chunking.has_more=true`, call again with chunk=N to get remaining content.

    Args:
        chunk: Chunk number (0=first chunk with metadata, 1-N=specific chunk). Default: 0
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains:
            - content: Current class source code (or chunk of it)
            - _chunking: (only for large responses) {enabled, total_chunks, current_chunk, has_more}

    MCP Tool: fetch_current_class
    Description: Gets code from the active JADX tab for context-aware analysis
    """
    params = {}
    if chunk > 0:
        params["chunk"] = str(chunk)
    
    result = await get_from_jadx("current-class", params, instance_id=instance_id)
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


async def get_class_source(class_name: str, chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """
    Fetch the Java source of a specific class.

    CHUNKING SUPPORT: Large classes (>8KB) are automatically chunked.
    - If response contains `_chunking.has_more=true`, call again with chunk=N to get remaining content.
    - Small classes are returned in full (no chunking).

    WARNING: Very large classes (e.g., R.class) may require multiple chunk calls.
    For large classes, consider using get_method_by_name to fetch specific methods,
    or get_class_info to get class structure first.

    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        chunk: Chunk number (0=first chunk with metadata, 1-N=specific chunk). Default: 0
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains:
            - response: Java source code (or chunk of it)
            - _chunking: (only for large responses) {enabled, total_chunks, current_chunk, has_more}

    MCP Tool: get_class_source
    Description: Retrieves decompiled Java source for any class in the APK
    """
    params = {"class_name": class_name}
    if chunk > 0:
        params["chunk"] = str(chunk)
    return await get_from_jadx("class-source", params, instance_id=instance_id)


async def _estimate_batch_size(class_names: list[str], instance_id: Optional[str]) -> int:
    """基于class_info快速估算批量请求的响应大小"""
    total_estimate = 0
    for class_name in class_names:
        try:
            info = await get_class_info(class_name, instance_id)
            if "error" not in info:
                estimate = (
                    info.get("methods_count", 0) * 200 +  # 每个方法约200字节
                    info.get("fields_count", 0) * 50 +    # 每个字段约50字节
                    500  # 类头部
                )
                total_estimate += estimate
        except:
            total_estimate += 5000  # 估算失败时假设中等大小
    return total_estimate


async def _execute_batch_request(class_names: list[str], chunk: int, instance_id: Optional[str]) -> dict:
    """执行实际的批量请求"""
    params = {"class_names": ",".join(class_names)}
    if chunk > 0:
        params["chunk"] = str(chunk)

    result = await get_from_jadx("batch-class-source", params, instance_id=instance_id)

    # 如果有chunking元数据，添加AI友好提示
    if "_chunking" in result and result["_chunking"].get("has_more"):
        chunk_info = result["_chunking"]
        result["_ai_instruction"] = (
            f"Response chunked ({chunk_info['current_chunk']}/{chunk_info['total_chunks']}). "
            f"Call batch_get_class_source(class_names={class_names}, chunk={chunk_info['next_chunk']}) to get next chunk."
        )

    return result


async def batch_get_class_source(
    class_names: list[str],
    chunk: int = 0,
    force: bool = False,
    instance_id: Optional[str] = None
) -> dict:
    """
    智能批量获取类源码（支持自动分块和大小预警）

    分层策略：
    1. 续传请求（chunk>0）→ 直接执行
    2. 超大请求（预估>50KB）→ 预检失败，返回优化建议
    3. 大请求（预估20-50KB）→ 执行 + 警告
    4. 正常请求（<20KB）→ 直接执行

    Args:
        class_names: List of fully qualified class names (max 20)
        chunk: Chunk number for continuation (0=first request)
        force: Force execution even for very large requests
        instance_id: Optional JADX instance name

    Returns:
        dict: Response with classes data and optional chunking metadata

    MCP Tool: batch_get_class_source
    Description: Batch retrieval of decompiled Java sources for multiple classes with intelligent size management
    """
    logger.info(f"batch_get_class_source: classes={class_names}, chunk={chunk}, force={force}")

    # Validate batch size
    if len(class_names) > 20:
        return {
            "error": "TOO_MANY_CLASSES",
            "message": "Maximum 20 classes per request",
            "requested": len(class_names),
            "maximum": 20
        }

    # 续传请求：直接执行
    if chunk > 0:
        return await _execute_batch_request(class_names, chunk, instance_id)

    # 预估响应大小
    try:
        estimated_size = await _estimate_batch_size(class_names, instance_id)
    except Exception as e:
        logger.error(f"Size estimation failed: {e}, using conservative fallback")
        estimated_size = len(class_names) * 5000  # Conservative estimate

    # 策略1：超大请求（>50KB）
    if estimated_size > 50000 and not force:
        class_infos = []
        for class_name in class_names:
            try:
                info = await get_class_info(class_name, instance_id)
                class_infos.append(info)
            except:
                class_infos.append({"class_name": class_name, "error": "Failed to get info"})

        return {
            "error": "BATCH_TOO_LARGE",
            "estimated_size_bytes": estimated_size,
            "estimated_size_kb": round(estimated_size / 1024, 1),
            "classes_count": len(class_names),
            "class_summaries": class_infos,
            "suggestions": {
                "option1": "Reduce batch size to 2-3 classes maximum",
                "option2": "Use get_class_info + get_method_by_name for targeted analysis",
                "option3": "Fetch classes individually with get_class_source (supports chunking)",
                "option4": f"Add force=True to proceed anyway: batch_get_class_source(class_names={class_names[:2]}, force=True)"
            }
        }

    # 策略2 & 3：执行请求
    result = await _execute_batch_request(class_names, chunk, instance_id)

    # 大请求添加性能警告
    if estimated_size > 20000:
        result["_performance_warning"] = {
            "estimated_size_kb": round(estimated_size / 1024, 1),
            "message": "Large batch request. Response may be chunked.",
            "optimization_tip": "Consider using get_class_info first to check if you really need full source code"
        }

    return result


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
    List all method names in a class (useful for seeing overloaded methods).

    Returns structured JSON with Frida-friendly metadata for each method.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.MainActivity')
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Structured method information containing:
            - class_name: Full class name
            - methods: List of method objects, each with:
                - name: Method name
                - is_static: Boolean indicating static method
                - is_native: Boolean indicating native method
                - is_constructor: Boolean indicating constructor
                - is_abstract: Boolean indicating abstract method
                - is_synchronized: Boolean indicating synchronized method
                - modifiers: List of modifier strings (e.g., ['public', 'static'])
                - overload_count: Number of overloads for this method name
                - return_type: Return type as string
            - count: Total number of methods

    MCP Tool: get_methods_of_class
    Description: Extracts all method declarations with Frida-friendly metadata
    """
    return await get_from_jadx("methods-of-class", {"class_name": class_name}, instance_id=instance_id)


async def get_fields_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
    """
    List all field names in a class.

    Returns structured JSON with Frida-friendly metadata for each field.

    Args:
        class_name: Fully qualified class name (e.g., 'com.example.MainActivity')
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Structured field information containing:
            - class_name: Full class name
            - fields: List of field objects, each with:
                - name: Field name
                - type: Java type as string
                - type_frida: Frida-compatible type string for hooks
                - modifiers: List of modifier strings (e.g., ['public', 'static', 'final'])
                - is_static: Boolean indicating static field
                - is_final: Boolean indicating final field
            - count: Total number of fields

    MCP Tool: get_fields_of_class
    Description: Extracts all field variables with Frida-compatible type information
    """
    return await get_from_jadx("fields-of-class", {"class_name": class_name}, instance_id=instance_id)


async def get_smali_of_class(class_name: str, chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """
    Fetch the smali representation of a class.

    CHUNKING SUPPORT: Large Smali output (>8KB, typical for classes with 10+ methods)
    is automatically chunked to prevent MCP client truncation.
    - If response contains `_chunking.has_more=true`, call again with chunk=N to get remaining content.
    - Small classes are returned in full (no chunking).

    IMPORTANT: Classes with 40+ methods often produce Smali >40KB, requiring 5+ chunk calls.
    Consider using get_method_by_name for specific methods if only partial analysis is needed.

    Args:
        class_name: Fully qualified class name (for inner classes use $ syntax: OuterClass$InnerClass)
        chunk: Chunk number (0=first chunk with metadata, 1-N=specific chunk). Default: 0
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains:
            - response: Smali/Dalvik bytecode (or chunk of it)
            - _chunking: (only for large responses) {enabled, total_chunks, current_chunk, has_more, warning}

    MCP Tool: get_smali_of_class
    Description: Retrieves low-level smali bytecode for advanced analysis
    """
    normalized_name = class_name
    logger.info(f"get_smali_of_class: class={class_name}, chunk={chunk}, instance={instance_id}")
    
    params = {"class_name": normalized_name}
    if chunk > 0:
        params["chunk"] = str(chunk)
    
    result = await get_from_jadx("smali-of-class", params, instance_id=instance_id)
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

    WARNING: Large responses may cause timeout. Use small count values (1-5) to avoid timeout.
    For exploring, use get_main_application_classes_names first to identify target classes,
    then use get_class_source for specific classes.

    Args:
        offset: Starting index for pagination (default: 0)
        count: Number of classes to return (0 = all, default: 0). Recommended: 1-5 to avoid timeout.
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


async def get_main_activity_class(chunk: int = 0, instance_id: Optional[str] = None) -> dict:
    """
    Fetch the main activity class as defined in the AndroidManifest.xml.

    CHUNKING SUPPORT: Large activity classes (>8KB) are automatically chunked.
    - If response contains `_chunking.has_more=true`, call again with chunk=N to get remaining content.

    Args:
        chunk: Chunk number (0=first chunk with metadata, 1-N=specific chunk). Default: 0
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains:
            - content: Main activity class source code (or chunk of it)
            - _chunking: (only for large responses) {enabled, total_chunks, current_chunk, has_more}

    MCP Tool: get_main_activity_class
    Description: Identifies and retrieves the app's entry point activity
    """
    params = {}
    if chunk > 0:
        params["chunk"] = str(chunk)
    return await get_from_jadx("main-activity", params, instance_id=instance_id)


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
            - native_method_names: List of native method names (for JNI/SO analysis)
            - native_count: Number of native methods

    MCP Tool: get_class_info
    Description: Retrieves structured class metadata including native methods for security analysis
    """

    logger.info(f"get_class_info: class={class_name}, instance={instance_id}")
    result = await get_from_jadx("class-info", {"class_name": class_name}, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"get_class_info error: {result.get('error')}")
    return result


async def get_decompile_status(instance_id: Optional[str] = None) -> dict:
    """
    Get the current decompilation status of the JADX instance.
    
    Use this to check if JADX has finished decompiling all classes before
    using search_in='code' which requires decompilation.

    Args:
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Decompilation status containing:
            - status: "ready" or "loading"
            - processed_classes: Number of classes already decompiled
            - total_classes: Total number of classes
            - percentage: Progress percentage (0-100)
            - recommendation: Suggested action based on status
            - search_lock: Current search lock status

    MCP Tool: get_decompile_status
    Description: Check if JADX is ready for code search (decompilation complete)
    """
    logger.info(f"get_decompile_status: instance={instance_id}")
    result = await get_from_jadx("decompile-status", instance_id=instance_id)
    if "error" in result:
        logger.warning(f"get_decompile_status error: {result.get('error')}")
    else:
        status = result.get("status", "unknown")
        pct = result.get("percentage", 0)
        logger.info(f"get_decompile_status: {status} ({pct}%)")
    return result


# Save references to module-level functions before they get shadowed
# by tool wrapper functions inside register_class_tools
_get_all_classes = get_all_classes
_get_class_source = get_class_source
_batch_get_class_source = batch_get_class_source
_get_methods_of_class = get_methods_of_class
_get_fields_of_class = get_fields_of_class
_get_smali_of_class = get_smali_of_class
_get_main_activity_class = get_main_activity_class
_get_class_info = get_class_info
_get_decompile_status = get_decompile_status


def register_class_tools(mcp, with_busy_check):
    """Register class analysis tools to MCP Server"""

    @mcp.tool()
    @with_busy_check
    async def get_all_classes(offset: int = 0, count: int = 0, instance_id: Optional[str] = None) -> dict:
        """Returns a list of all classes in the project with pagination support.

        Args:
            instance_id: Optional. Target JADX instance name. Uses default if not specified.
        """
        return await _get_all_classes(offset, count, instance_id=instance_id)

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
        return await _get_class_source(class_name, chunk=chunk, instance_id=instance_id)

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
        return await _batch_get_class_source(
            class_names, chunk=chunk, force=force, instance_id=instance_id
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
        return await _get_methods_of_class(class_name, instance_id=instance_id)

    @mcp.tool()
    @with_busy_check
    async def get_fields_of_class(class_name: str, instance_id: Optional[str] = None) -> dict:
        """List all field names in a class with Frida-compatible type information.

        Returns structured JSON with type_frida field for each field.

        Args:
            class_name: Fully qualified class name (e.g., 'com.example.MainActivity').
            instance_id: Optional. Target JADX instance name. Uses default if not specified.
        """
        return await _get_fields_of_class(class_name, instance_id=instance_id)

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
        return await _get_smali_of_class(class_name, chunk=chunk, instance_id=instance_id)

    @mcp.tool()
    @with_busy_check
    async def get_main_activity_class(chunk: int = 0, instance_id: Optional[str] = None) -> dict:
        """Fetch the main activity class name from AndroidManifest.xml.

        CHUNKING: Large activity classes (>8KB) auto-chunked. If `_chunking.has_more=true`, call with chunk=N.

        Args:
            chunk: Chunk number (0=first chunk, 1-N=specific chunk). Default: 0
            instance_id: Target JADX instance name.
        """
        return await _get_main_activity_class(chunk=chunk, instance_id=instance_id)

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
        return await _get_class_info(class_name, instance_id=instance_id)

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
        return await _get_decompile_status(instance_id=instance_id)
