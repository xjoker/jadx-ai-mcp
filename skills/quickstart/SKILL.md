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
list_packages
```

Lists all packages in the loaded file for navigation.

## APK vs JAR Tool Selection

| Analysis Target | Tool | Use Case |
|:----------------|:-----|:---------|
| Android app structure | `list_packages` | Browse package hierarchy |
| Class discovery | `search_class` | Find classes by name pattern |
| Method discovery | `search_method` | Find methods across classes |
| Code inspection | `get_class_source` | View decompiled Java source |
| String analysis | `search_code` | Find hardcoded strings/patterns |
| Resource files | `list_resources` | APK resources (layouts, strings) |
| Manifest | `get_manifest` | Android manifest analysis |

## Quick Reference

| Task | Tool | Key Parameters |
|:-----|:-----|:---------------|
| Find class by name | `search_class` | `query` (supports wildcards) |
| Get class source | `get_class_source` | `class_name` (full qualified) |
| Search in code | `search_code` | `query`, `case_sensitive` |
| List all methods | `get_class_methods` | `class_name` |
| Get method details | `get_method_source` | `class_name`, `method_name` |
| Find field usages | `search_field` | `query` |
| List resources | `list_resources` | `path` (optional filter) |
| Get resource content | `get_resource` | `path` |

## Batch Operations Best Practices

### 1. Use Pagination for Large Results

```
search_class(query="Activity", limit=50, offset=0)
search_class(query="Activity", limit=50, offset=50)
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
search_class(query="*Activity")  # Get list first
get_class_source("com.app.MainActivity")  # Fetch only what you need
```

### 4. Narrow Search Scope

| Approach | Performance |
|:---------|:------------|
| `search_code(query="password")` | Scans entire codebase |
| `search_code(query="password", package="com.app.auth")` | Scans only auth package |

## Performance Optimization Tips

### Handling Large Responses

1. **Use `limit` parameter** - Most search tools support pagination
2. **Filter by package** - Narrow scope when possible
3. **Request specific data** - Use `get_method_source` instead of full class when only one method needed

### Timeout Prevention

| Symptom | Solution |
|:--------|:---------|
| Search timeout | Add `limit` parameter, narrow package scope |
| Large class timeout | Use `get_method_source` for specific methods |
| Resource timeout | Use `list_resources` first, then `get_resource` selectively |

### Caching Behavior

- Decompiled classes are cached after first access
- `get_decompile_status` shows background decompilation progress
- Wait for decompilation to complete for faster subsequent queries

## Error Handling Guide

| Error | Cause | Solution |
|:------|:------|:---------|
| "Class not found" | Wrong class name | Use `search_class` to find correct name |
| "No file loaded" | JADX not ready | Call `get_file_info` to check status |
| "Connection refused" | Server not running | Check JADX instance is running |
| "Timeout" | Large result set | Add pagination, narrow scope |

## Common Pitfalls

- **Using short class names** - Always use fully qualified names (e.g., `com.app.MainActivity`)
- **Fetching all classes** - Use search and pagination instead of bulk retrieval
- **Ignoring decompile status** - Background decompilation may still be running
- **Broad searches** - Always add package filters when possible
