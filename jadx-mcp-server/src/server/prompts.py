from fastmcp import FastMCP

def register_prompts(mcp: FastMCP):
    """Register prompts for the JADX MCP server."""

    @mcp.prompt("analyze-activity")
    def analyze_activity_prompt(activity_name: str = "") -> str:
        """Guide the AI to analyze an Android Activity starting from the Manifest.
        
        Args:
            activity_name: Optional name or partial name of the activity to focus on.
        """
        return f"""You are analyzing an Android Activity{' named ' + activity_name if activity_name else ''}.
Follow this standard reverse engineering workflow:

1.  **Find the Class**:
    - Use `get_android_manifest()` to find the full class name in `AndroidManifest.xml`.
    - Look for `<activity android:name="...">` entries.
    - Note the `package` attribute in the `<manifest>` tag, as class names might be relative (e.g., `.MainActivity`).

2.  **Inspect the Code**:
    - Once you have the full class name (e.g., `com.example.app.MainActivity`), use `get_class_source()` to read its code.
    - If the class is missing or obfuscated, use `search_classes_by_keyword(search_term="...", search_in="class")` to find candidates.

3.  **Analyze Lifecycle**:
    - Focus on `onCreate`, `onStart`, or `onResume` methods to understand initialization logic.
    - Use `get_method_by_name(class_name, "onCreate")` to see specific method details.

4.  **Trace Logic**:
    - If you see interesting method calls, use `get_xrefs_to_method` or `get_method_by_name` to follow the control flow.
"""

    @mcp.prompt("search-code")
    def search_code_prompt(keyword: str) -> str:
        """Guide the AI to perform effective code searches without causing timeouts.
        
        Args:
            keyword: The term to search for.
        """
        return f"""You want to search for "{keyword}" in the codebase.
**Context**: Large codebases (or obfuscated ones) can cause timeouts or crashes if searched inefficiently.

**Recommended Strategy**:
1.  **Search for Classes First**:
    - Use `search_classes_by_keyword(search_term="{keyword}", search_in="class")`.
    - This is fast and often distinct enough to find relevant modules.

2.  **Precise Code Search**:
    - If searching for method names or field names specifically, use `search_in="method"` or `search_in="field"`.
    - AVOID `search_in="code"` (full text search) unless necessary, as it is the slowest operation and most likely to fail.

3.  **Handling Obfuscation**:
    - If results are poor, try shorter or partial keywords.
    - Look for string constants using `get_strings()` (carefully, with small limits) or searching likely string values.
"""

    @mcp.prompt("trace-method")
    def trace_method_prompt(method_signature: str) -> str:
        """Guide the AI to trace a method's usage and implementation.
        
        Args:
            method_signature: The method to trace (e.g., 'com.example.A.methodName').
        """
        parts = method_signature.rsplit('.', 1)
        if len(parts) == 2:
            class_name, method_name = parts
        else:
            class_name = "UNKNOWN_CLASS"
            method_name = method_signature

        return f"""You are tracing the method `{method_name}` in class `{class_name}`.

**Analysis Steps**:
1.  **Get Implementation**:
    - Call `get_method_by_name(class_name="{class_name}", method_name="{method_name}")`.
    - Analyze what the method does (input -> processing -> output).

2.  **Find Callers (Who calls this?)**:
    - Call `get_xrefs_to_method(class_name="{class_name}", method_name="{method_name}")`.
    - This reveals *entry points* to this logic.

3.  **Find Callees (What does this call?)**:
    - Inspect the source code from step 1.
    - Identify important calls to other methods.
    - Recurse into those methods if they look relevant to your goal.

**Tip**: If the method is overridden or part of an interface, check the class hierarchy using `get_class_source` to understand the context.
"""
