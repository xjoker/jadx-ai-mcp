---
name: quickstart
description: Getting started guide and performance tips for JADX-AI-MCP. Use when user asks "getting started", "how to use", "first time", "what tools", "where to start", "batch operations", "performance", "large response", "optimize", "slow", "timeout", or needs help choosing between APK and JAR analysis tools.
---

# JADX-AI-MCP Quick Start Guide

Essential workflows and performance tips for effective APK/JAR analysis.

## First Connection Workflow

### Step 1: Get File Information

```
get_file_info
```

Returns loaded file type, package count, class count, and analysis status.

### Step 2: Check Decompile Status

```
get_decompile_status
```

Shows decompilation progress and whether background processing is complete.

### Step 3: Explore Package Structure

```
get_all_classes
```

Lists all classes in the loaded file for navigation.

## APK vs JAR Tool Selection

| Analysis Target | Tool | Use Case |
|:----------------|:-----|:---------|
| All classes | `get_all_classes` | Browse full class list |
| Class discovery | `search_classes_by_keyword` | Find classes by name pattern |
| Method discovery | `search_method_by_name` | Find methods across classes |
| Code inspection | `get_class_source` | View decompiled Java source |
| String analysis | `get_strings` | Find hardcoded strings |
| Resource files | `get_all_resource_file_names` | APK resources (layouts, strings) |
| Manifest | `get_android_manifest` | Android manifest analysis |

## Quick Reference

| Task | Tool | Key Parameters |
|:-----|:-----|:---------------|
| Find class by name | `search_classes_by_keyword` | `keyword` |
| Get class source | `get_class_source` | `class_name` (full qualified) |
| List all methods | `get_methods_of_class` | `class_name` |
| Get method details | `get_method_by_name` | `class_name`, `method_name` |
| List fields | `get_fields_of_class` | `class_name` |
| List resources | `get_all_resource_file_names` | |
| Get resource content | `get_resource_file` | `file_name` |

## Batch Operations Best Practices

### 1. Use Pagination for Large Results

```
search_classes_by_keyword(keyword="Activity", limit=50, offset=0)
search_classes_by_keyword(keyword="Activity", limit=50, offset=50)
```

### 2. Check Cache Before Repeated Calls

The server caches decompiled results. Repeated calls to the same class are fast.

### 3. Batch Related Queries

Instead of multiple single queries:

```
# Inefficient
get_class_source("com.app.MainActivity")
get_class_source("com.app.BaseActivity")
get_class_source("com.app.LoginActivity")
```

Use search first, then fetch selectively:

```
# Efficient
search_classes_by_keyword(keyword="Activity")  # Get list first
get_class_source("com.app.MainActivity")  # Fetch only what you need
```

### 4. Narrow Search Scope

Use specific class or method search instead of broad queries when possible.

## Performance Optimization Tips

### Handling Large Responses

1. **Use `limit` parameter** - Most search tools support pagination
2. **Filter by package** - Narrow scope when possible
3. **Request specific data** - Use `get_method_by_name` instead of full class when only one method needed

### Timeout Prevention

| Symptom | Solution |
|:--------|:---------|
| Search timeout | Add `limit` parameter, narrow scope |
| Large class timeout | Use `get_method_by_name` for specific methods |
| Resource timeout | Use `get_all_resource_file_names` first, then `get_resource_file` selectively |

### Caching Behavior

- Decompiled classes are cached after first access
- `get_decompile_status` shows background decompilation progress
- Wait for decompilation to complete for faster subsequent queries

## Error Handling Guide

| Error | Cause | Solution |
|:------|:------|:---------|
| "Class not found" | Wrong class name | Use `search_classes_by_keyword` to find correct name |
| "No file loaded" | JADX not ready | Call `get_file_info` to check status |
| "Connection refused" | Server not running | Check JADX instance is running |
| "Timeout" | Large result set | Add pagination, narrow scope |

## Common Pitfalls

- **Using short class names** - Always use fully qualified names (e.g., `com.app.MainActivity`)
- **Fetching all classes** - Use search and pagination instead of bulk retrieval
- **Ignoring decompile status** - Background decompilation may still be running
- **Broad searches** - Always add package filters when possible
