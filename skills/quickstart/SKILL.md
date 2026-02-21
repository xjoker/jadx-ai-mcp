---
name: quickstart
description: Getting started guide and performance tips for JADX-AI-MCP. Use when user asks "getting started", "how to use", "first time", "what tools", "where to start", "batch operations", "performance", "large response", "optimize", "slow", "timeout", or needs help choosing between APK and JAR analysis tools.
---

# JADX-AI-MCP Quick Start Guide

Essential workflows and performance tips for effective APK/JAR analysis.

## First Connection Workflow

### Step 1: Get File Information

```
get_file_info()
```

Returns loaded file type (APK/JAR/AAR/DEX), class count, package name, and recommended tools.

### Step 2: Check Decompile Status

```
get_decompile_status()
```

Shows cache percentage, memory usage, and whether background decompilation is still running.
- `cached_percentage < 20%`: Use `search_in="class"` or `"method"` only, avoid `"code"`
- `memory.usage_percentage > 85%`: Reduce batch sizes

### Step 3: Explore Package Structure

```
get_package_classes(auto=True)
```

Auto-detects main application package from Manifest and returns class list.

## Tool Quick Reference

| Task | Tool | Key Parameters |
|:-----|:-----|:---------------|
| Get file info | `get_file_info` | `instance_id?` |
| Find class by name | `search_classes_by_keyword` | `search_term`, `search_in="class"` |
| Get class source | `get_class_source` | `class_name` (fully qualified) |
| Search in code | `search_classes_by_keyword` | `search_term`, `search_in="code"` |
| List methods | `get_methods_of_class` | `class_name` |
| Get method source | `get_method_by_name` | `class_name`, `method_name` |
| List fields | `get_fields_of_class` | `class_name` |
| List resources | `get_all_resource_file_names` | `offset=0`, `count=0` |
| Get resource | `get_resource_file` | `resource_name` |
| Get manifest | `get_android_manifest` | — |
| Get strings | `get_strings` | `mode="summary"/"search"/"get"` |

## APK vs JAR Tool Selection

| Analysis Target | APK Tool | JAR Tool |
|:----------------|:---------|:---------|
| Entry points | `get_main_activity_class` | `jar_get_entry_points` |
| Manifest/config | `get_android_manifest` | `jar_get_manifest` |
| Dependencies | — | `jar_get_dependencies` |
| Services (SPI) | — | `jar_get_services` |
| Bytecode | `get_smali_of_class` | `jar_get_bytecode` |
| String resources | `get_strings` | `get_config_strings` |
| Classes by package | `get_main_application_classes_names` | `get_package_classes` |

## Batch Operations Best Practices

### Use Pagination for Large Results

```python
# Paginate through all classes
get_all_classes(offset=0, count=50)
get_all_classes(offset=50, count=50)

# Search with package filter (much faster)
search_classes_by_keyword(search_term="Auth", package="com.example", search_in="class")
```

### Batch Fetching

```python
# Fetch multiple classes in one call (max 20)
batch_get_class_source(class_names=["com.example.A", "com.example.B"])

# Fetch multiple methods in one call (max 20)
batch_get_method_by_name(methods=["com.example.Auth:login", "com.example.Auth:logout"])
```

### Search Scope Performance

| `search_in` value | Speed | Requires Cache |
|:-----------------|:------|:--------------|
| `"class"` | <100ms | No |
| `"method"` | <100ms | No |
| `"field"` | <100ms | No |
| `"code"` | 1-60s | Yes (>20%) |
| `"comment"` | 1-60s | Yes (>20%) |

## Handling Large Responses (Chunking)

Large responses (>8KB) are automatically split into chunks:

```python
# First call returns chunk 0 with metadata
result = get_class_source("com.example.LargeClass")

# If has_more is true, fetch remaining chunks
if result["_chunking"]["has_more"]:
    next_chunk = result["_chunking"]["next_chunk"]
    result2 = get_class_source("com.example.LargeClass", chunk=next_chunk)
```

**Tools that support chunking:** `get_class_source`, `get_smali_of_class`, `get_android_manifest`,
`fetch_current_class`, `get_main_activity_class`, `get_resource_file`,
`batch_get_class_source`, `batch_get_method_by_name`

## Error Handling Guide

| Error | Cause | Solution |
|:------|:------|:---------|
| "Class not found" | Wrong class name | Use `search_classes_by_keyword(search_in="class")` to find correct name |
| "No file loaded" | JADX not ready | Call `get_file_info()` to check status |
| "Connection refused" | Server not running | Check JADX plugin instance is running |
| "Timeout" | Large result set | Add `package` filter, reduce `count`, use `search_in="class"` |
| `BATCH_TOO_LARGE` | Batch response >50KB | Reduce batch size or add `force=True` |

## Common Pitfalls

- **Short class names**: Always use fully qualified names (e.g., `com.app.MainActivity`)
- **Fetching all classes at once**: Use search + pagination instead of `count=0` on large APKs
- **Code search before cache ready**: Check `get_decompile_status()` first — use `search_in="class"` early
- **Broad searches**: Always add `package` filter when possible to improve speed
