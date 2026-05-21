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
- Use `get_xrefs("class", class_name)` to find who uses this Activity.
- Use `get_xrefs("method", class_name, method_name)` for method callers.
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

**CRITICAL: Check Status First!**
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
    - Call `get_xrefs("method", class_name="{class_name}", member_name="{method_name}")`.
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

    @mcp.prompt("quick-analysis")
    def quick_analysis_prompt() -> str:
        """Guide the AI through a quick end-to-end APK analysis workflow.

        Covers: file info → APK info → main class listing → key class source.
        """
        return """You want to perform a **quick overview analysis** of the loaded APK/file.

**Step 1: File Info**
```python
info = get_file_info()
```
Check `file_type`, `file_name`, and `file_size_bytes`. Adjust strategy for large files.

**Step 2: APK Info**
```python
apk = get_apk_info()
```
Note the `package_name`, `version_name`, `min_sdk_version`, and `target_sdk_version`.
Large `total_classes` (>20 000) indicates a large APK — use targeted searches.

**Step 3: Main Class Listing**
```python
main_classes = get_main_application_classes_names()
```
These are the app's own classes (excluding third-party libraries).
If the list is long, focus on classes matching the APK package name.

**Step 4: Key Class Source**
Pick 3-5 representative classes from step 3 (e.g., Application, MainActivity, key Managers):
```python
result = batch_get_class_source(class_names=["com.example.App", "com.example.MainActivity"])
```

**Decision Rules**:
| Condition | Action |
|-----------|--------|
| `file_type` = jar | Skip APK-specific steps, go to class listing |
| `total_classes` > 50 000 | Use `search_classes_by_keyword` with package filter |
| `response_size_bytes` > 5 MB | Use pagination / reduce batch size |

**Tip**: After this overview, use `suggest_analysis_plan` with a specific goal for deeper analysis.
"""

    @mcp.prompt("security-audit")
    def security_audit_prompt() -> str:
        """Guide the AI through an Android security audit workflow.

        Covers: sensitive API search, permission review, hardcoded secrets detection.
        """
        return """You want to perform a **security audit** of the loaded APK.

**Step 1: Check Permissions**
```python
manifest = get_android_manifest()
```
Look for dangerous permissions: `INTERNET`, `READ_CONTACTS`, `ACCESS_FINE_LOCATION`,
`CAMERA`, `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE`, `RECORD_AUDIO`.

**Step 2: Search Sensitive APIs**
Run these searches (metadata mode — fast, no cache needed):
```python
# Crypto / key material
search_classes_by_keyword(search_term="SecretKey", search_in="class")
search_classes_by_keyword(search_term="KeyStore", search_in="class")
search_classes_by_keyword(search_term="Cipher", search_in="class")

# Reflection / dynamic loading
search_classes_by_keyword(search_term="DexClassLoader", search_in="class")
search_classes_by_keyword(search_term="loadClass", search_in="method")

# Native / root detection
search_classes_by_keyword(search_term="Runtime.exec", search_in="method")
search_native_methods()
```

**Step 3: Hardcoded Secret Patterns**
Use code search (requires cache — check status first):
```python
status = get_decompile_status()
if status["cached_percentage"] > 20:
    search_classes_by_keyword(search_term="password", search_in="code", count=20)
    search_classes_by_keyword(search_term="secret", search_in="code", count=20)
    search_classes_by_keyword(search_term="api_key", search_in="code", count=20)
    search_classes_by_keyword(search_term="Bearer ", search_in="code", count=20)
```

**Step 4: Network Security**
```python
# Check cleartext traffic config in manifest
# Look for network_security_config attribute in <application>

# Find HTTP (non-HTTPS) usage
search_classes_by_keyword(search_term="http://", search_in="code", count=20)
```

**Step 5: Review Findings**
For each suspicious class found, call:
```python
get_class_source(class_name="com.example.SuspiciousClass")
```

**Risk Indicators**:
| Finding | Risk |
|---------|------|
| `http://` URLs in code | Data in cleartext |
| Hardcoded `password`/`secret` fields | Credential exposure |
| `DexClassLoader` usage | Dynamic code loading |
| `Runtime.exec` calls | Command injection risk |
| Dangerous permissions without usage | Privacy concern |
"""

    @mcp.prompt("network-analysis")
    def network_analysis_prompt() -> str:
        """Guide the AI to find and analyze all network communication code.

        Covers: HTTP clients, URL patterns, OkHttp/Retrofit, WebSockets.
        """
        return """You want to analyze **all network communication** in the loaded APK.

**Step 1: Find Network Libraries**
```python
# OkHttp
search_classes_by_keyword(search_term="OkHttpClient", search_in="class")
search_classes_by_keyword(search_term="okhttp3", search_in="class")

# Retrofit
search_classes_by_keyword(search_term="Retrofit", search_in="class")
search_classes_by_keyword(search_term="@GET", search_in="code")
search_classes_by_keyword(search_term="@POST", search_in="code")

# Volley / other
search_classes_by_keyword(search_term="RequestQueue", search_in="class")

# WebSocket
search_classes_by_keyword(search_term="WebSocket", search_in="class")
```

**Step 2: Find URL/Endpoint Patterns**
```python
# Base URLs and API endpoints (requires cache)
status = get_decompile_status()
if status["cached_percentage"] > 20:
    search_classes_by_keyword(search_term="https://", search_in="code", count=30)
    search_classes_by_keyword(search_term="BASE_URL", search_in="code", count=20)
    search_classes_by_keyword(search_term="API_URL", search_in="code", count=20)
```

**Step 3: Analyze Retrofit Interface Classes**
Retrofit defines API endpoints as annotated interfaces. Find them:
```python
search_classes_by_keyword(search_term="ApiService", search_in="class")
search_classes_by_keyword(search_term="ApiInterface", search_in="class")
search_classes_by_keyword(search_term="RetrofitService", search_in="class")
```
Then get source for each: `get_class_source(class_name=...)`

**Step 4: Find Request Interceptors / Headers**
```python
search_classes_by_keyword(search_term="Interceptor", search_in="class")
search_classes_by_keyword(search_term="addHeader", search_in="method")
search_classes_by_keyword(search_term="Authorization", search_in="code", count=20)
```

**Step 5: Certificate Pinning**
```python
search_classes_by_keyword(search_term="CertificatePinner", search_in="class")
search_classes_by_keyword(search_term="TrustManager", search_in="class")
search_classes_by_keyword(search_term="checkServerTrusted", search_in="method")
```

**Analysis Tips**:
- `response_size_bytes` is injected into each tool response — large results may need pagination.
- Use `get_xrefs("class", class_name)` to trace where network classes are used.
- Check `get_android_manifest()` for `android:usesCleartextTraffic` attribute.
"""

    @mcp.prompt("entry-points")
    def entry_points_prompt() -> str:
        """Guide the AI to enumerate all Android app entry points and analyze lifecycle methods.

        Covers: Manifest → Activity/Service/Receiver/Provider → lifecycle methods.
        """
        return """You want to enumerate **all Android entry points** and their lifecycle methods.

**Step 1: Parse the Manifest**
```python
manifest = get_android_manifest()
```
Extract the following component types:
- `<activity>` — UI screens
- `<service>` — Background services
- `<receiver>` — Broadcast receivers
- `<provider>` — Content providers

Note the `android:name` attribute for each component.
Use the `package` attribute to resolve relative names (e.g., `.MainActivity` → `com.example.app.MainActivity`).

**Step 2: Analyze Activities**
For each Activity, retrieve:
```python
# Class info (inheritance, interfaces)
get_class_info(class_name="com.example.MainActivity")

# Full source
get_class_source(class_name="com.example.MainActivity")
```
Focus on lifecycle methods: `onCreate`, `onStart`, `onResume`, `onNewIntent`, `onActivityResult`.

**Step 3: Analyze Services**
Services often handle background work:
```python
get_class_source(class_name="com.example.MyService")
```
Focus on: `onStartCommand`, `onBind`, `onHandleIntent` (IntentService).

**Step 4: Analyze Broadcast Receivers**
```python
get_class_source(class_name="com.example.MyReceiver")
```
Focus on: `onReceive` — check what `Intent` actions are handled.

**Step 5: Find Exported Components**
Exported components are attack surface. Find them in manifest:
- `android:exported="true"` (explicit)
- Components with `<intent-filter>` are implicitly exported (pre-API 31)

**Step 6: Deep-Dive Key Methods**
```python
# Get specific lifecycle method
get_method_by_name(class_name="com.example.MainActivity", method_name="onCreate")

# Find who starts this Activity
get_xrefs("class", class_name="com.example.MainActivity")
```

**Efficient Batch Approach**:
```python
# Get source for multiple entry points at once
batch_get_class_source(class_names=[
    "com.example.MainActivity",
    "com.example.SplashActivity",
    "com.example.MyService",
])
```

**Risk Checklist**:
| Component | Check |
|-----------|-------|
| Activity | Intent extras validation, deeplink handling |
| Service | Permission requirements, IPC interface |
| Receiver | Exported receivers without permissions |
| Provider | `readPermission` / `writePermission` set |
"""

    @mcp.prompt("batch-operations")
    def batch_operations_prompt() -> str:
        """Guide the AI on best practices for batch operations to reduce overhead."""
        return """You want to perform multiple related operations efficiently.

**Available Batch Tools**:
| Tool | Max Items | Use Case |
|:---|:---:|:---|
| `batch_get_class_source` | 20 | Get source code for multiple classes (smart size management) |
| `batch_get_method_by_name` | 20 | Get multiple method implementations (smart size management) |
| `batch_get_xrefs` | 20 | Get cross-references for multiple targets |

**Best Practices**:
1.  **Group Related Requests**:
    - Instead of 10 individual `get_class_source` calls, use one `batch_get_class_source`.
    - This reduces network round-trips and MCP overhead.

2.  **Smart Batching with `batch_get_class_source` and `batch_get_method_by_name`**:
    - Automatically estimates response size before execution
    - Small batches (<20KB): Execute directly
    - Large batches (20-50KB): Execute with performance warning
    - Very large batches (>50KB): Returns BATCH_TOO_LARGE error with suggestions
    - Use `force=True` to bypass size checks if needed
    - Supports chunking for large responses (check `_chunking.has_more`)

3.  **Handle BATCH_TOO_LARGE Errors**:
    - Response includes `class_summaries` with metadata for each class
    - Follow suggestions: reduce batch size, use targeted tools, or add `force=True`
    - Example error response:
    ```json
    {
      "error": "BATCH_TOO_LARGE",
      "estimated_size_kb": 120.5,
      "class_summaries": [{class_name, method_count, field_count}, ...],
      "suggestions": {
        "option1": "Reduce batch size to 2-3 classes",
        "option2": "Use get_class_info + get_method_by_name",
        "option3": "Fetch individually with get_class_source",
        "option4": "Add force=True to proceed anyway"
      }
    }
    ```

4.  **Handle Partial Failures**:
    - Batch operations return results for each item with `found: true/false`.
    - Check the `error` field for individual items that failed.

5.  **Pagination for Large Results**:
    - Tools like `search_classes_by_keyword` support `offset` and `count` parameters.
    - Use `has_more` and `next_offset` to paginate through large result sets.

6.  **Chunking Support**:
    - If response contains `_chunking.has_more=true`, call again with `chunk=N`
    - Example: `batch_get_class_source(class_names=[...], chunk=2)`
    - Example: `batch_get_method_by_name(methods=["A:m1", "B:m2"], chunk=2)`

**Example 1: Analyzing a Class Hierarchy**:
```python
# Smart batch request with size management
result = batch_get_class_source(["com.example.BaseActivity", "com.example.MainActivity", "com.example.SettingsActivity"])

# Handle BATCH_TOO_LARGE error
if result.get("error") == "BATCH_TOO_LARGE":
    print(f"Estimated size: {result['estimated_size_kb']} KB")
    # Option 1: Use class summaries
    for summary in result["class_summaries"]:
        print(f"{summary['class_name']}: {summary.get('method_count', 0)} methods")

    # Option 2: Reduce batch size or force
    result = batch_get_class_source(["com.example.BaseActivity"], force=True)

# Handle normal response
for cls in result.get("classes", []):
    if cls["found"]:
        # Analyze cls["content"]
        pass

# Handle chunked response
if result.get("_chunking", {}).get("has_more"):
    next_chunk = batch_get_class_source(class_names=[...], chunk=result["_chunking"]["next_chunk"])
```

**Example 2: Analyzing Multiple Methods**:
```python
# Batch get method sources
methods = [
    "com.example.Auth:login",
    "com.example.Auth:logout",
    "com.example.Network:sendRequest"
]
result = batch_get_method_by_name(methods)

# Handle BATCH_TOO_LARGE error
if result.get("error") == "BATCH_TOO_LARGE":
    print(f"Estimated size: {result['estimated_size_kb']} KB")
    # Reduce batch or force
    result = batch_get_method_by_name(methods[:2], force=True)

# Process results
for method in result.get("methods", []):
    if method["found"]:
        print(f"Method: {method['class_name']}:{method['method_name']}")
        # Analyze method["code"]

# Handle chunking
if result.get("_chunking", {}).get("has_more"):
    next_chunk = batch_get_method_by_name(methods=methods, chunk=2)
```
"""
