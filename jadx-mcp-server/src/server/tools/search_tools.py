"""
JADX MCP Server - Code Search Tools

This module provides MCP tools for searching through decompiled Android code,
enabling discovery of classes, methods, and keywords across the entire APK.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

from typing import Optional
from src.PaginationUtils import PaginationUtils
from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("search_tools")


async def get_method_by_name(
    class_name: str,
    method_name: str,
    method_signature: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Fetch the source code of a method from a specific class.

    When the class contains overloaded methods with the same name, supply
    ``method_signature`` (the JVM short descriptor) to select the exact overload.
    If you omit it and multiple overloads exist, the server returns HTTP 300 with
    an ``available_descriptors`` list — call this function again with one of those
    values to get the code you need.

    Args:
        class_name: Fully qualified class name (e.g. ``"com.example.MainActivity"``).
        method_name: Method name (e.g. ``"process"``).
        method_signature: Optional JVM short descriptor to disambiguate overloads,
            e.g. ``"process(Ljava/lang/String;I)Z"`` or ``"process(I)V"``.
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Method source code and metadata, or an error dict with
        ``available_descriptors`` when multiple overloads exist.

    MCP Tool: get_method_by_name
    Description: Retrieves specific method implementation from a known class
    """
    logger.info(
        f"get_method_by_name: class={class_name}, method={method_name}, "
        f"method_signature={method_signature}, instance={instance_id}"
    )
    params: dict = {"class_name": class_name, "method_name": method_name}
    if method_signature:
        params["method_signature"] = method_signature
    result = await get_from_jadx("method-by-name", params, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"get_method_by_name failed: {result.get('error')}")
    return result


async def search_method_by_name(
    method_name: str,
    offset: int = 0,
    count: int = 50,
    instance_id: Optional[str] = None
) -> dict:
    """
    Search for a method name across all classes with pagination.

    Args:
        method_name: Method name to search for (partial matching supported)
        offset: Starting index for pagination (default: 0)
        count: Number of results to return (default: 50, max: 200)
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Paginated list of methods with has_more, next_offset for continuation

    MCP Tool: search_method_by_name
    Description: Finds all occurrences of a method name across the APK with pagination
    """
    logger.info(f"search_method_by_name: method={method_name}, offset={offset}, count={count}, instance={instance_id}")
    try:
        result = await get_from_jadx(
            "search-method", 
            {"method_name": method_name, "offset": offset, "count": count}, 
            instance_id=instance_id
        )
        if "error" in result:
            logger.warning(f"search_method_by_name error response: {result.get('error')}")
            # Add recovery hints to error response
            result["suggested_prompt"] = "search-code"
            result["recovery_hint"] = (
                "This global search may have timed out or crashed. "
                "Try using search_classes_by_keyword(search_term='%s', search_in='method') instead." % method_name
            )
        else:
            match_count = len(result.get("methods", result.get("classes", [])))
            logger.info(f"search_method_by_name: found {match_count} matches, has_more={result.get('has_more')}")
        return result
    except Exception as e:
        logger.error(f"search_method_by_name exception: {type(e).__name__}: {e}")
        return {
            "error": f"Unexpected error: {e}",
            "suggested_prompt": "search-code",
            "recovery_hint": (
                "This global search failed. Consider using the safer alternative: "
                "search_classes_by_keyword(search_term='%s', search_in='method')." % method_name
            ),
        }


async def _execute_batch_method_request(methods: list[str], chunk: int, instance_id: Optional[str]) -> dict:
    """Execute the actual batch method request"""
    params = {"methods": ",".join(methods)}
    if chunk > 0:
        params["chunk"] = str(chunk)

    result = await get_from_jadx("batch-method-by-name", params, instance_id=instance_id)

    # If chunking metadata is present, add AI-friendly instruction
    if "_chunking" in result and result["_chunking"].get("has_more"):
        chunk_info = result["_chunking"]
        result["_ai_instruction"] = (
            f"Response chunked ({chunk_info['current_chunk']}/{chunk_info['total_chunks']}). "
            f"Call batch_get_method_by_name(methods={methods}, chunk={chunk_info['next_chunk']}) to get next chunk."
        )

    return result


async def batch_get_method_by_name(
    methods: list[str],
    chunk: int = 0,
    force: bool = False,
    instance_id: Optional[str] = None
) -> dict:
    """
    Smart batch retrieval of method source code (with automatic chunking and size warnings)

    Tiered strategy:
    1. Continuation requests (chunk>0) -> Execute directly
    2. Very large requests (estimated >50KB) -> Pre-flight check fails, return optimization suggestions
    3. Large requests (estimated 20-50KB) -> Execute + warning
    4. Normal requests (<20KB) -> Execute directly

    Args:
        methods: List of "class_name:method_name" pairs (e.g., ["com.example.A:methodA", "com.example.B:methodB"])
        chunk: Chunk number for continuation (0=first request)
        force: Force execution even for very large requests
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Contains 'methods' array with class_name, method_name, found status, and code/error for each,
              plus 'total' and 'found' counts

    MCP Tool: batch_get_method_by_name
    Description: Batch retrieval of method sources using class:method format with intelligent size management
    """
    logger.info(f"batch_get_method_by_name: methods={methods}, chunk={chunk}, force={force}")

    # Continuation request: execute directly
    if chunk > 0:
        return await _execute_batch_method_request(methods, chunk, instance_id)

    # Estimate response size (approximately 3KB per method)
    estimated_size = len(methods) * 3000

    # Strategy 1: Very large request (>50KB)
    if estimated_size > 50000 and not force:
        return {
            "error": "BATCH_TOO_LARGE",
            "estimated_size_bytes": estimated_size,
            "estimated_size_kb": round(estimated_size / 1024, 1),
            "methods_count": len(methods),
            "suggestions": {
                "option1": "Reduce batch size to 5-10 methods maximum",
                "option2": "Fetch methods individually with get_method_by_name",
                "option3": f"Add force=True to proceed: batch_get_method_by_name(methods={methods[:5]}, force=True)"
            }
        }

    # Strategy 2 & 3: Execute request
    result = await _execute_batch_method_request(methods, chunk, instance_id)

    # Add performance warning for large requests
    if estimated_size > 20000:
        result["_performance_warning"] = {
            "estimated_size_kb": round(estimated_size / 1024, 1),
            "message": "Large batch request. Response may be chunked.",
            "optimization_tip": "Consider fetching methods individually if only specific ones are needed"
        }

    return result


async def search_classes_by_keyword(
    search_term: str,
    package: str = "",
    exclude: str = "",
    search_in: str = "code",
    offset: int = 0,
    count: int = 20,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Search for classes containing a specific keyword with flexible filtering options.

    BEST PRACTICE:
    - Use search_in='class' for finding class names (fastest, most reliable).
    - Use search_in='method' or 'field' for specific member searches.
    - AVOID search_in='code' on large APKs as full-text search may timeout or crash.
    Refer to the 'search-code' prompt for detailed guidance.

    Args:
        search_term: The keyword or string to search for.
        package: Package name to limit search scope (optional).
        exclude: Comma-separated package prefixes to exclude (optional).
        search_in: Comma-separated search scopes: class,method,field,code,comment. Default: code
        offset: Starting index for pagination. Default: 0
        count: Maximum number of results. Default: 20
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Paginated list of classes containing the search term, with search_info metadata

    MCP Tool: search_classes_by_keyword
    Description: Advanced search tool that finds classes matching a keyword with filtering
    """
    params = {
        "search_term": search_term,
        "package": package,
        "exclude": exclude,
        "search_in": search_in,
        "offset": offset,
        "count": count,
    }
    return await get_from_jadx("search-classes-by-keyword", params, instance_id=instance_id)


async def get_method_signature(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Get structured method signature with Frida-compatible type information.

    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        method_name: Method name to get signature for
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Structured method signature containing:
            - class_name: Containing class name
            - method_name: Method name
            - overloads: Number of overloaded versions
            - signatures: List of signature objects with:
                - method_name: Method name
                - return_type: Return type as string
                - access_flags: Access modifiers string
                - is_constructor: Whether this is a constructor
                - parameters: List of parameter objects with:
                    - name: Parameter name (arg0, arg1, ...)
                    - type: Java type as string
                    - type_frida: Frida-compatible type string (e.g., '[B' for byte[])
                - frida_overload: Frida .overload() string (e.g., "'[B', 'int'")

    MCP Tool: get_method_signature
    Description: Retrieves structured method signature with Frida-compatible types
    """

    logger.info(f"get_method_signature: class={class_name}, method={method_name}, instance={instance_id}")
    result = await get_from_jadx(
        "method-signature", {"class_name": class_name, "method_name": method_name}, instance_id=instance_id
    )
    if "error" in result:
        logger.warning(f"get_method_signature error: {result.get('error')}")
    return result



async def get_method_callees(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
    """
    Get methods called by the specified method (callees analysis).

    Args:
        class_name: Fully qualified class name (e.g., com.example.MainActivity)
        method_name: Method name to analyze
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Analysis result containing:
            - class_name: Containing class name
            - method_name: Method name
            - callees_count: Number of potential callees found
            - callees: List of "receiver.method" patterns found in code
            - note: Warning about pattern-based analysis accuracy

    MCP Tool: get_method_callees
    Description: Analyzes method code to identify called methods (pattern-based)
    """
    logger.info(f"get_method_callees: class={class_name}, method={method_name}, instance={instance_id}")
    result = await get_from_jadx(
        "method-callees", {"class_name": class_name, "method_name": method_name}, instance_id=instance_id
    )
    if "error" in result:
        logger.warning(f"get_method_callees error: {result.get('error')}")
    return result


async def search_native_methods(
    package: str = "",
    offset: int = 0,
    count: int = 50,
    instance_id: Optional[str] = None
) -> dict:
    """
    Search for all native methods across the APK (metadata-only, fast).

    This is a high-performance operation that reads DEX metadata without triggering decompilation.
    Native methods are the bridge between Java and native code (JNI), crucial for:
    - Security analysis (encryption, signing, verification in SO libraries)
    - Finding Frida Native Hook targets
    - Identifying SO library entry points

    Args:
        package: Optional package filter (e.g., 'com.xingin')
        offset: Pagination offset. Default: 0
        count: Max results (max: 200). Default: 50
        instance_id: Optional. Target JADX instance name. Uses default if not specified.

    Returns:
        dict: Search results containing:
            - native_methods: List of native method objects with:
                - class_name: Containing class
                - method_name: Native method name
                - short_id: Method signature ID
                - param_types_frida: Frida-compatible parameter types
            - total_found: Total native methods matching filter
            - count: Number of results returned
            - offset: Current offset
            - has_more: Whether more results available

    MCP Tool: search_native_methods
    Description: Finds all native methods for JNI/SO security analysis
    """
    logger.info(f"search_native_methods: package={package}, offset={offset}, count={count}, instance={instance_id}")
    params = {"offset": offset, "count": count}
    if package:
        params["package"] = package
    result = await get_from_jadx("search-native-methods", params, instance_id=instance_id)
    if "error" in result:
        logger.warning(f"search_native_methods error: {result.get('error')}")
    return result


def register_search_tools(mcp, with_busy_check):
    """Register search-related tools to MCP Server"""

    @mcp.tool(name="get_method_by_name")
    @with_busy_check
    async def get_method_by_name_tool(
        class_name: str,
        method_name: str,
        method_signature: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Fetch source code of a specific method. Use method_signature (JVM descriptor) to pick an overload.

        Args:
            class_name: Fully qualified class name. method_name: Method name.
            method_signature: JVM short descriptor, e.g. 'process(Ljava/lang/String;I)Z' (optional).
            instance_id: Target JADX instance name.
        Returns:
            dict: {code: str} or {available_descriptors: [...]} if overloads exist.
        """
        return await get_method_by_name(
            class_name, method_name, method_signature=method_signature, instance_id=instance_id
        )

    @mcp.tool(name="search_method_by_name")
    @with_busy_check
    async def search_method_by_name_tool(
        method_name: str,
        offset: int = 0,
        count: int = 50,
        instance_id: Optional[str] = None
    ) -> dict:
        """Global method-name search across all classes. Prefer search_classes_by_keyword(search_in='method') — faster and safer.

        Args:
            method_name: Method name (partial match supported). offset: Pagination start.
            count: Max results (default 50, max 200). instance_id: Target JADX instance name.
        Returns:
            dict: {methods: [...], has_more: bool}
        """
        return await search_method_by_name(method_name, offset, count, instance_id=instance_id)

    @mcp.tool(name="batch_get_method_by_name")
    @with_busy_check
    async def batch_get_method_by_name_tool(
        methods: list[str],
        chunk: int = 0,
        force: bool = False,
        instance_id: Optional[str] = None
    ) -> dict:
        """Fetch multiple method sources in one request using "class:method" format. Auto size-managed.

        Args:
            methods: List of "class_name:method_name" strings (max 20). chunk: 0=first, N=continue.
            force: Bypass size guard. instance_id: Target JADX instance name.
        Returns:
            dict: {methods: [{class_name, method_name, code, found}]} or BATCH_TOO_LARGE error.
        """
        return await batch_get_method_by_name(
            methods, chunk=chunk, force=force, instance_id=instance_id
        )

    @mcp.tool(name="search_classes_by_keyword")
    @with_busy_check
    async def search_classes_by_keyword_tool(
        search_term: str,
        package: str = "",
        exclude: str = "",
        search_in: str = "code",
        offset: int = 0,
        count: int = 20,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Search classes by keyword across class/method/field/code/comment scopes.

        Args:
            search_term: Keyword. package: Package filter (recommended). exclude: Comma-separated exclusions.
            search_in: class|method|field|code|comment (class/method/field fast; code needs cache). count: Max results.
            instance_id: Target JADX instance name.
        Returns:
            dict: {classes: [...], total: int, has_more: bool}
        """
        return await search_classes_by_keyword(
            search_term, package, exclude, search_in, offset, count, instance_id=instance_id
        )

    @mcp.tool(name="get_method_signature")
    @with_busy_check
    async def get_method_signature_tool(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
        """Get structured method signatures with Frida-compatible types and frida_overload strings.

        Args:
            class_name: Fully qualified class name. method_name: Method name.
            instance_id: Target JADX instance name.
        Returns:
            dict: {signatures: [{return_type, parameters, frida_overload, ...}], overloads: int}
        """
        return await get_method_signature(class_name, method_name, instance_id=instance_id)

    @mcp.tool(name="get_method_callees")
    @with_busy_check
    async def get_method_callees_tool(class_name: str, method_name: str, instance_id: Optional[str] = None) -> dict:
        """Get methods called by the specified method (pattern-based callee analysis).

        Args:
            class_name: Fully qualified class name. method_name: Method name.
            instance_id: Target JADX instance name.
        Returns:
            dict: {callees: [str, ...], callees_count: int}
        """
        return await get_method_callees(class_name, method_name, instance_id=instance_id)

    @mcp.tool(name="search_native_methods")
    @with_busy_check
    async def search_native_methods_tool(
        package: str = "",
        offset: int = 0,
        count: int = 50,
        instance_id: Optional[str] = None
    ) -> dict:
        """Find all native (JNI) methods across the APK — reads DEX metadata, no decompilation needed.

        Args:
            package: Optional package filter. offset: Pagination start.
            count: Max results (max 200, default 50). instance_id: Target JADX instance name.
        Returns:
            dict: {native_methods: [{class_name, method_name, param_types_frida}], has_more: bool}
        """
        return await search_native_methods(package, offset, count, instance_id=instance_id)
