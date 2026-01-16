from fastmcp import FastMCP

def register_prompts(mcp: FastMCP):
    """Register prompts for the JADX MCP server."""

    @mcp.prompt("status-check")
    def status_check_prompt() -> str:
        """Guide the AI to check JADX status before performing resource-intensive operations.
        
        This prompt helps AI make informed decisions based on real-time JADX metrics.
        """
        return """**Before performing resource-intensive operations, check JADX status.**

Call `get_decompile_status()` first and interpret the results:

## Response Fields and Decision Rules

### 1. Class Cache Status
| Field | Description | Decision |
|-------|-------------|----------|
| `cached_percentage` | % of classes already decompiled | If <20%, avoid `search_in=code` |
| `cached_classes` | Number of cached classes | Low number = expect slow code search |
| `total_classes` | Total classes in APK | Large APK (>100k) = use smaller batches |

### 2. Memory Status  
| Field | Warning Threshold | Action |
|-------|-------------------|--------|
| `memory.usage_percentage` | >85% | Reduce batch size, avoid smali |
| `memory.free_mb` | <200MB | Wait or use smaller requests |

### 3. Thread Status
| Field | Warning Threshold | Action |
|-------|-------------------|--------|
| `threads.active_count` | >50 | JADX is busy, wait before heavy ops |

### 4. Search Lock
| Field | Meaning | Action |
|-------|---------|--------|
| `search_lock.locked=true` | Search in progress | Wait, don't start new search |
| `search_lock.held_seconds` | How long held | If >30s, may timeout soon |

## Decision Matrix

| Scenario | Recommended Action |
|----------|-------------------|
| cached_percentage < 10% | Use `search_in=class/method/field` only |
| cached_percentage > 50% | `search_in=code` is viable |
| memory.usage_percentage > 90% | Reduce count to 10, avoid batch ops |
| search_lock.locked = true | Wait and retry after 5 seconds |
| threads.active_count > 100 | JADX overloaded, pause operations |

## Example Workflow
```python
# 1. Check status first
status = get_decompile_status()

# 2. Make informed decision
if status["cached_percentage"] < 20:
    # Use fast metadata search
    results = search_classes_by_keyword(search_term="login", search_in="class")
else:
    # Code search is viable
    results = search_classes_by_keyword(search_term="login", search_in="code")

# 3. Monitor memory for batch operations
if status["memory"]["usage_percentage"] > 80:
    batch_size = 5  # Smaller batches
else:
    batch_size = 20  # Full batch
```

**Core Principle**: Always check status before heavy operations. React to real metrics, don't guess.
"""

    @mcp.prompt("analyze-activity")
    def analyze_activity_prompt(activity_name: str = "") -> str:
        """Guide the AI to analyze an Android Activity starting from the Manifest.
        
        Args:
            activity_name: Optional name or partial name of the activity to focus on.
        """
        return f"""You are analyzing an Android Activity{' named ' + activity_name if activity_name else ''}.

**Step 0: Check System Status** (Important!)
- Call `get_decompile_status()` to check cache and memory status.
- If `cached_percentage` < 10%, expect slow code analysis.

**Step 1: Find the Class**
- Use `get_android_manifest()` to find the full class name.
- Look for `<activity android:name="...">` entries.
- Note the `package` attribute for relative class names (e.g., `.MainActivity`).

**Step 2: Get Class Info**
- Use `get_class_info(class_name)` to see inheritance, methods, and fields.
- Expected time: <1s

**Step 3: Inspect the Code**
- Use `get_class_source(class_name)` to read the full source.
- Expected time: <1s (cached), may be slower first time.

**Step 4: Analyze Lifecycle**
- Focus on `onCreate`, `onStart`, `onResume` methods.
- Use `get_method_by_name(class_name, "onCreate")` for specific methods.
- Expected time: <1s

**Step 5: Trace Cross-References**
- Use `get_xrefs_to_class(class_name)` to find who uses this Activity.
- Use `get_xrefs_to_method(class_name, method_name)` for method callers.
- Expected time: <1s with pagination.

**Performance Tips**:
- If analyzing multiple classes, use `batch_get_class_source()` for efficiency.
- Check `memory.usage_percentage` before batch operations.
"""

    @mcp.prompt("search-code")
    def search_code_prompt(keyword: str) -> str:
        """Guide the AI to perform effective code searches with status-aware decision making.
        
        Args:
            keyword: The term to search for.
        """
        return f"""You want to search for "{keyword}" in the codebase.

**⚠️ CRITICAL: Check Status First!**
```python
status = get_decompile_status()
```

**Decision Matrix Based on Status:**

| Condition | Recommended `search_in` | Reason |
|-----------|------------------------|--------|
| `cached_percentage` < 20% | `class`, `method`, `field` | Code search will timeout |
| `cached_percentage` > 50% | `code` is viable | Enough classes cached |
| `memory.usage_percentage` > 85% | Use count=10 | Reduce memory pressure |
| `search_lock.locked` = true | Wait 5s, retry | Another search running |

**Search Modes** (fastest to slowest):
| Mode | Expected Time | Triggers Decompilation |
|------|--------------|------------------------|
| `search_in="class"` | <100ms | No |
| `search_in="method"` | <100ms | No |
| `search_in="field"` | <100ms | No |
| `search_in="code"` | 1-60s | Yes |
| `search_in="comment"` | 1-60s | Yes |

**Recommended Workflow:**
1. **Always check status first** - Don't skip this!
2. **Start with metadata search** - Fast and reliable:
   - `search_classes_by_keyword(search_term="{keyword}", search_in="class")`
   - `search_classes_by_keyword(search_term="{keyword}", search_in="method")`
3. **Use package filter** to narrow scope:
   - `package="com.example"` reduces classes to search
4. **For code search**, check cache first:
   - If `cached_percentage` < 30%, avoid or use small `count`
5. **Handle timeout gracefully**:
   - `search_info.timed_out=true` means partial results returned
   - Results are still valid, just incomplete

**Efficient API/URL Search Workflow:**
```python
# 1. Fast metadata search first
results = search_classes_by_keyword(search_term="Http", search_in="class")

# 2. Get source for candidate classes
for cls in results["classes"][:10]:
    source = get_class_source(cls)
    # Analyze in your context

# 3. Only if needed, use code search with package filter
if not found:
    results = search_classes_by_keyword(
        search_term="{keyword}", 
        search_in="code",
        package="com.example.network"  # Narrow scope!
    )
```
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
