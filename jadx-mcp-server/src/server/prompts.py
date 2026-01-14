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
        """Guide the AI to perform effective code searches with retry handling.
        
        Args:
            keyword: The term to search for.
        """
        return f"""You want to search for "{keyword}" in the codebase.

**Search Modes** (from fastest to slowest):
| Mode | Use Case | Speed |
|:---|:---|:---:|
| `search_in="class"` | Find class names | ⚡ Fast |
| `search_in="method"` | Find method names | ⚡ Fast |
| `search_in="field"` | Find field names | ⚡ Fast |
| `search_in="code"` | Full-text search in decompiled code | 🐢 Slow |

**Recommended Strategy**:
1.  **Start with metadata search**:
    - `search_classes_by_keyword(search_term="{keyword}", search_in="class")` for class names.
    - `search_classes_by_keyword(search_term="{keyword}", search_in="method")` for methods.

2.  **Use `search_in="code"` with filters**:
    - Add `package` filter to narrow scope: `package="com.example"`.
    - Use pagination: `count=20, offset=0` then check `has_more` and `next_offset`.

3.  **Handle 503 Busy Response**:
    - If you receive `{{"busy": true, "retry_after": 10}}`, wait 10 seconds and retry.
    - Only one search can run at a time (serialized for stability).

4.  **Obfuscated Code Tips**:
    - Try shorter keywords or string constants.
    - Use `get_strings(count=50)` carefully to find relevant strings.
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

    @mcp.prompt("warm-up-package")
    def warm_up_package_prompt(package_name: str) -> str:
        """Guide the AI to pre-warm decompilation cache for a package.
        
        Args:
            package_name: The package prefix to warm up (e.g., 'com.example.app').
        """
        return f"""You want to pre-warm the decompilation cache for package `{package_name}`.

**Why Warm Up?**
Large APKs have lazy decompilation - classes are only decompiled when first accessed.
By pre-loading key classes, subsequent searches and analysis will be faster.

**Strategy**:
1.  **List Classes in Package**:
    - Use `get_all_classes(count=100)` and filter for `{package_name}` prefix.
    - Or use `search_classes_by_keyword(search_term="{package_name}", search_in="class", count=50)`.

2.  **Load Key Classes**:
    - For each class found, call `get_class_source(class_name)` to trigger decompilation.
    - Focus on core classes (Activities, Managers, Utils) rather than inner classes.

3.  **Batch Loading**:
    - Use `batch_get_class_source(class_names=[...])` for up to 20 classes at once.
    - This is more efficient than individual calls.

**Note**: This creates cache entries that persist until JADX restarts. If using Docker with cache volume, they persist across restarts.
"""

    @mcp.prompt("batch-operations")
    def batch_operations_prompt() -> str:
        """Guide the AI on best practices for batch operations to reduce overhead."""
        return """You want to perform multiple related operations efficiently.

**Available Batch Tools**:
| Tool | Max Items | Use Case |
|:---|:---:|:---|
| `batch_get_class_source` | 20 | Get source code for multiple classes |
| `batch_get_method_by_name` | 20 | Get multiple method implementations |
| `batch_get_xrefs` | 20 | Get cross-references for multiple targets |

**Best Practices**:
1.  **Group Related Requests**:
    - Instead of 10 individual `get_class_source` calls, use one `batch_get_class_source`.
    - This reduces network round-trips and MCP overhead.

2.  **Handle Partial Failures**:
    - Batch operations return results for each item with `found: true/false`.
    - Check the `error` field for individual items that failed.

3.  **Pagination for Large Results**:
    - Tools like `search_method_by_name` support `offset` and `count` parameters.
    - Use `has_more` and `next_offset` to paginate through large result sets.

4.  **Avoid Overloading**:
    - Requesting too many items at once can still cause timeouts.
    - If batch operations fail, try smaller batches (e.g., 5-10 items).

**Example: Analyzing a Class Hierarchy**:
```python
# Get info for multiple related classes at once
result = batch_get_class_source(["com.example.BaseActivity", "com.example.MainActivity", "com.example.SettingsActivity"])
for cls in result["classes"]:
    if cls["found"]:
        # Analyze cls["content"]
        pass
```
"""
