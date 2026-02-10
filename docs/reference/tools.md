# MCP Tools Reference

**English** | [简体中文](tools.zh-cn.md)

---

## 📊 Tool Availability Matrix

> ✅ Full support | ⚠️ Partial | ❌ Not available | 🔄 Returns NOT_APPLICABLE

| Tool | APK | JAR | AAR | DEX | Description |
|:-----|:---:|:---:|:---:|:---:|:------------|
| **Universal Analysis Tools** |
| `get_file_info` | ✅ | ✅ | ✅ | ✅ | Recommended first call, auto-detect file type |
| `get_class_source` | ✅ | ✅ | ✅ | ✅ | Get class source code |
| `get_method_by_name` | ✅ | ✅ | ✅ | ✅ | Get method source code |
| `get_class_info` | ✅ | ✅ | ✅ | ✅ | Class structure (inheritance, interfaces, members) |
| `get_method_signature` | ✅ | ✅ | ✅ | ✅ | Method signature (Frida-compatible) |
| `get_methods_of_class` | ✅ | ✅ | ✅ | ✅ | List all methods in class |
| `get_fields_of_class` | ✅ | ✅ | ✅ | ✅ | List all fields in class |
| `get_method_callees` | ✅ | ✅ | ✅ | ✅ | Methods called by a method |
| `get_all_classes` | ✅ | ✅ | ✅ | ✅ | List all classes (paginated) |
| `get_package_classes` | ✅ | ✅ | ✅ | ✅ | Get classes by package prefix |
| `fetch_current_class` | ✅ | ✅ | ✅ | ✅ | Get currently selected class |
| `get_selected_text` | ✅ | ✅ | ✅ | ✅ | Get selected text |
| **Search Tools** |
| `search_classes_by_keyword` | ✅ | ✅ | ✅ | ✅ | Search classes by keyword |
| `search_method_by_name` | ✅ | ✅ | ✅ | ✅ | Search method by name |
| `search_native_methods` | ✅ | ❌ | ✅ | ✅ | Search native methods (JNI) |
| **Cross-Reference Tools** |
| `get_xrefs_to_class` | ✅ | ✅ | ✅ | ✅ | Find class references |
| `get_xrefs_to_method` | ✅ | ✅ | ✅ | ✅ | Find method references |
| `get_xrefs_to_field` | ✅ | ✅ | ✅ | ✅ | Find field references |
| **Batch Tools** |
| `batch_get_class_source` | ✅ | ✅ | ✅ | ✅ | Batch get class sources (max 20) |
| `batch_get_method_by_name` | ✅ | ✅ | ✅ | ✅ | Batch get methods (max 20) |
| `batch_get_xrefs` | ✅ | ✅ | ✅ | ✅ | Batch find references (max 10) |
| **Android-Specific Tools** |
| `get_android_manifest` | ✅ | 🔄 | ✅ | ❌ | Get AndroidManifest.xml |
| `get_main_activity_class` | ✅ | 🔄 | ✅ | ❌ | Get main Activity |
| `get_main_application_classes_names` | ✅ | 🔄 | ✅ | ❌ | Main app class names |
| `get_main_application_classes_code` | ✅ | 🔄 | ✅ | ❌ | Main app class sources |
| `get_strings` | ✅ | 🔄 | ✅ | ❌ | String resources (strings.xml) |
| `get_smali_of_class` | ✅ | ❌ | ✅ | ✅ | Smali bytecode |
| **JAR-Specific Tools** |
| `jar_get_manifest` | 🔄 | ✅ | 🔄 | 🔄 | Read MANIFEST.MF |
| `jar_get_services` | 🔄 | ✅ | 🔄 | 🔄 | Read SPI services |
| `jar_get_entry_points` | 🔄 | ✅ | 🔄 | 🔄 | Discover entry points |
| `jar_get_dependencies` | 🔄 | ✅ | 🔄 | 🔄 | Analyze embedded dependencies |
| `jar_get_bytecode` | ✅ | ✅ | ✅ | ✅ | Class bytecode (like javap) |
| **Unified Config Tools** |
| `get_config_strings` | ✅ | ✅ | ✅ | ❌ | APK: strings.xml summary, JAR: properties files |
| **Resource Tools** |
| `get_all_resource_file_names` | ✅ | ✅ | ✅ | ❌ | List all resource files |
| `get_resource_file` | ✅ | ✅ | ✅ | ❌ | Get resource file content |
| **Rename Tools** |
| `rename_class` | ✅ | ✅ | ✅ | ✅ | Rename class |
| `rename_method` | ✅ | ✅ | ✅ | ✅ | Rename method |
| `rename_field` | ✅ | ✅ | ✅ | ✅ | Rename field |
| `rename_package` | ✅ | ✅ | ✅ | ✅ | Rename package |
| **Debug Tools** |
| `debug_get_stack_frames` | ✅ | ❌ | ✅ | ✅ | Get stack frames |
| `debug_get_threads` | ✅ | ❌ | ✅ | ✅ | Get thread info |
| `debug_get_variables` | ✅ | ❌ | ✅ | ✅ | Get variables |
| **Instance Management Tools** |
| `list_jadx_instances` | ✅ | ✅ | ✅ | ✅ | List all instances |
| `add_jadx_instance` | ✅ | ✅ | ✅ | ✅ | Add new instance |
| `remove_jadx_instance` | ✅ | ✅ | ✅ | ✅ | Remove instance |
| `set_default_jadx_instance` | ✅ | ✅ | ✅ | ✅ | Set default instance |
| `get_jadx_instance_info` | ✅ | ✅ | ✅ | ✅ | Get instance details |
| `health_check_jadx_instances` | ✅ | ✅ | ✅ | ✅ | Health check |
| `check_instance_status` | ✅ | ✅ | ✅ | ✅ | Check instance busy status |
| `clear_class_cache` | ✅ | ✅ | ✅ | ✅ | Clear class cache |
| **Status Monitor Tools** |
| `get_decompile_status` | ✅ | ✅ | ✅ | ✅ | Get decompile status and metrics |

---

## 🔍 Tool Details

### Universal Analysis Tools

| Tool | Parameters | Description |
|:-----|:-----------|:------------|
| `get_file_info()` | `instance_id?` | **Recommended first call**. Returns file type, class count, recommended tools |
| `get_class_source(class_name)` | `class_name`, `chunk=0`, `instance_id?` | Get full class source. **Auto-chunks >8KB responses** |
| `get_method_by_name(class_name, method_name)` | `class_name`, `method_name`, `instance_id?` | Get method source |
| `get_class_info(class_name)` | `class_name`, `instance_id?` | Class structure: inheritance, interfaces, method/field count, native methods |
| `get_method_signature(class_name, method_name)` | `class_name`, `method_name`, `instance_id?` | Returns Frida-compatible signature (`frida_overload`) |
| `get_methods_of_class(class_name)` | `class_name`, `instance_id?` | Returns JSON: `is_static`, `is_native`, `overload_count` |
| `get_fields_of_class(class_name)` | `class_name`, `instance_id?` | Returns JSON with `type_frida` field |
| `get_method_callees(class_name, method_name)` | `class_name`, `method_name`, `instance_id?` | All methods called by this method |
| `get_all_classes(offset, count)` | `offset=0`, `count=0`, `instance_id?` | Paginated list of all classes |
| `get_package_classes(package, auto)` | `package?`, `auto=false`, `include_inner=true`, `offset=0`, `count=100`, `instance_id?` | `auto=true` auto-detects main package |

### Search Tools

| Tool | Parameters | Description |
|:-----|:-----------|:------------|
| `search_classes_by_keyword(keyword)` | `search_term`, `package=""`, `exclude=""`, `search_in="code"`, `offset=0`, `count=20`, `instance_id?` | `search_in`: `class`/`method`/`field`/`code`/`comment` |
| `search_method_by_name(method_name)` | `method_name`, `offset=0`, `count=50`, `instance_id?` | Global method search |
| `search_native_methods(package)` | `package=""`, `offset=0`, `count=50`, `instance_id?` | Search JNI native methods |

### Batch Tools

| Tool | Parameters | Description |
|:-----|:-----------|:------------|
| `batch_get_class_source(class_names)` | `class_names[]`, `chunk=0`, `force=False`, `instance_id?` | Max 20 classes. Smart size management with chunking support |
| `batch_get_method_by_name(methods)` | `methods[]` (format: `class:method`), `chunk=0`, `force=False`, `instance_id?` | Max 20 methods. Smart size management with chunking support |
| `batch_get_xrefs(targets)` | `targets[]` (format: `type:class:member`), `instance_id?` | Max 10 targets |

### JAR-Specific Tools

| Tool | Parameters | Description |
|:-----|:-----------|:------------|
| `jar_get_manifest()` | `instance_id?` | Read META-INF/MANIFEST.MF, returns Main-Class, version etc |
| `jar_get_services()` | `instance_id?` | Read META-INF/services/*, discover SPI services |
| `jar_get_entry_points()` | `instance_id?` | Discover entry points: Main-Class, @SpringBootApplication, main() |
| `jar_get_dependencies()` | `instance_id?` | Analyze dependencies: pom.properties, Class-Path, BOOT-INF/lib |
| `jar_get_bytecode(class_name)` | `class_name`, `instance_id?` | Class bytecode structure (like javap) |

### Android-Specific Tools

| Tool | Parameters | Description |
|:-----|:-----------|:------------|
| `get_android_manifest()` | `instance_id?` | Get AndroidManifest.xml |
| `get_main_activity_class()` | `instance_id?` | Get main Activity from Manifest |
| `get_strings(mode, query, key)` | `mode="summary"`, `query?`, `key?`, `locale="values"`, `offset=0`, `limit=50`, `instance_id?` | Modes: `summary`/`list`/`search`/`get` |
| `get_smali_of_class(class_name)` | `class_name`, `chunk=0`, `instance_id?` | Dalvik bytecode. **Auto-chunks >8KB responses** |

### Rename Tools

| Tool | Parameters | Description |
|:-----|:-----------|:------------|
| `rename_class(class_name, new_name)` | `class_name`, `new_name`, `instance_id?` | Rename class |
| `rename_method(method_name, new_name)` | `method_name`, `new_name`, `instance_id?` | Rename method |
| `rename_field(class_name, field_name, new_name)` | `class_name`, `field_name`, `new_name`, `instance_id?` | Rename field |
| `rename_package(old_name, new_name)` | `old_package_name`, `new_package_name`, `instance_id?` | Rename package |

### Instance Management Tools

| Tool | Parameters | Description |
|:-----|:-----------|:------------|
| `list_jadx_instances()` | - | List all connected instances |
| `add_jadx_instance(host, port)` | `host`, `port`, `name?`, `token?` | Dynamically add instance |
| `remove_jadx_instance(name)` | `name` | Remove instance |
| `set_default_jadx_instance(name)` | `name` | Set default instance |
| `get_jadx_instance_info(name)` | `name` | Get instance details |
| `health_check_jadx_instances()` | - | Check all instances health |
| `check_instance_status(instance_name)` | `instance_name?` | Check if instance is busy |
| `clear_class_cache()` | `instance_id?` | Clear class cache (30s cooldown) |
| `get_decompile_status()` | `instance_id?` | Get cache, memory, thread metrics |

---

## ⚡ Performance Tips

| Scenario | Recommendation |
|:---------|:---------------|
| First analysis | Call `get_file_info()` first to understand file type |
| Code search | Prefer `search_in="class"` or `"method"`, avoid `"code"` |
| Many classes | Use `batch_get_class_source` to reduce request count |
| Check status | Call `get_decompile_status()` to check cache hit rate |

---

## 🧩 Response Chunking

Large responses (>8KB) are automatically chunked to prevent MCP client truncation.

| Scenario | Behavior |
|:---------|:---------|
| Response ≤8KB | Returns full content directly |
| Response >8KB | Returns first chunk + `_chunking` metadata |

**Chunking Metadata Example:**
```json
{
  "content": "...first 8KB...",
  "_chunking": {
    "enabled": true,
    "total_size": 45000,
    "total_chunks": 6,
    "current_chunk": 1,
    "has_more": true,
    "next_chunk": 2
  }
}
```

**To get remaining chunks:**
```python
# If _chunking.has_more == true, call again with chunk=N
result = get_smali_of_class(class_name="...", chunk=2)
result = batch_get_class_source(class_names=["..."], chunk=2)
```

**Affected Tools:** `get_class_source`, `get_smali_of_class`, `get_android_manifest`, `fetch_current_class`, `get_main_activity_class`, `get_resource_file`, `batch_get_class_source`, `batch_get_method_by_name`

---

## 🚦 Smart Batch Size Management

`batch_get_class_source` and `batch_get_method_by_name` include intelligent size management to prevent oversized responses.

### Tiered Strategy

| Response Size | Behavior | Action |
|:--------------|:---------|:-------|
| <20KB | Execute directly | No warnings |
| 20-50KB | Execute with warning | Returns `_performance_warning` field |
| >50KB | Pre-flight check fails | Returns `BATCH_TOO_LARGE` error |

### BATCH_TOO_LARGE Error Response

When a batch request is too large, you'll receive:

**For `batch_get_class_source`:**
```json
{
  "error": "BATCH_TOO_LARGE",
  "estimated_size_bytes": 128000,
  "estimated_size_kb": 125.0,
  "classes_count": 15,
  "class_summaries": [
    {
      "class_name": "com.example.LargeClass",
      "method_count": 150,
      "field_count": 80,
      "is_abstract": false
    }
  ],
  "suggestions": {
    "option1": "Reduce batch size to 2-3 classes maximum",
    "option2": "Use get_class_info + get_method_by_name for targeted analysis",
    "option3": "Fetch classes individually with get_class_source (supports chunking)",
    "option4": "Add force=True to proceed anyway: batch_get_class_source(class_names=['...'], force=True)"
  }
}
```

**For `batch_get_method_by_name`:**
```json
{
  "error": "BATCH_TOO_LARGE",
  "estimated_size_bytes": 95000,
  "estimated_size_kb": 92.8,
  "methods_count": 12,
  "method_summaries": [
    {
      "class_name": "com.example.Service",
      "method_name": "processData",
      "line_count": 450
    }
  ],
  "suggestions": {
    "option1": "Reduce batch size to 2-3 methods maximum",
    "option2": "Fetch methods individually with get_method_by_name",
    "option3": "Add force=True to proceed anyway: batch_get_method_by_name(methods=['...'], force=True)"
  }
}
```

### Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `class_names` | list[str] | required | List of class names (max 20) |
| `chunk` | int | 0 | Chunk number for continuation (0=first request) |
| `force` | bool | False | Bypass size check and force execution |
| `instance_id` | str | None | Target JADX instance |

### Usage Examples

**Example 1: Batch Get Classes**
```python
# Normal batch request
result = batch_get_class_source(["com.example.A", "com.example.B"])

# Handle BATCH_TOO_LARGE error
result = batch_get_class_source(["Large1", "Large2", "Large3"])
if result.get("error") == "BATCH_TOO_LARGE":
    # Option 1: Review class summaries
    for summary in result["class_summaries"]:
        print(f"{summary['class_name']}: {summary['method_count']} methods")

    # Option 2: Reduce batch size
    result = batch_get_class_source(["Large1"])

    # Option 3: Force execution
    result = batch_get_class_source(["Large1", "Large2"], force=True)

# Handle chunked response
if result.get("_chunking", {}).get("has_more"):
    next_result = batch_get_class_source(
        class_names=["com.example.A"],
        chunk=result["_chunking"]["next_chunk"]
    )
```

**Example 2: Batch Get Methods**
```python
# Batch request for multiple methods
methods = [
    "com.example.Auth:login",
    "com.example.Auth:logout",
    "com.example.Network:sendRequest"
]
result = batch_get_method_by_name(methods)

# Handle BATCH_TOO_LARGE error
if result.get("error") == "BATCH_TOO_LARGE":
    print(f"Estimated size: {result['estimated_size_kb']} KB")
    # Reduce batch or force execution
    result = batch_get_method_by_name(methods[:2], force=True)

# Process results
for method in result.get("methods", []):
    if method["found"]:
        print(f"{method['class_name']}:{method['method_name']}")
        # Analyze method["code"]

# Handle chunking
if result.get("_chunking", {}).get("has_more"):
    next_result = batch_get_method_by_name(
        methods=methods,
        chunk=result["_chunking"]["next_chunk"]
    )
```

---

## 🔗 Related Documentation

- [Quick Start Guide](../getting-started/quickstart.md)
- [AI Client Configuration](../guides/ai-clients.md)
- [Common Issues / Troubleshooting](../troubleshooting/common-issues.md)
- [Docker Deployment](../deployment/docker.md)
