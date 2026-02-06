# Quick Start Guide Skill

A comprehensive guide for new users to get started with JADX-AI-MCP analysis.

---

## First Connection Workflow

When connecting to a new file for analysis, follow this workflow:

### Step 1: Understand the File

```
get_file_info()
```

This returns:
- File type (APK, JAR, AAR, DEX)
- Total class count
- Recommended tools for this file type

### Step 2: Check Decompilation Status

```
get_decompile_status()
```

Check the `cached_percentage` field - higher values mean faster searches:
- `< 30%`: Code search will be slow, consider waiting
- `> 70%`: Good performance for code search
- `100%`: Full cache, optimal performance

### Step 3: Get Entry Points

**For APK files:**
```
get_android_manifest()
get_main_activity_class()
get_main_application_classes_names()
```

**For JAR files:**
```
jar_get_manifest()
jar_get_entry_points()
jar_get_services()
```

---

## Project Overview Workflow

### List All Classes (Paginated)

```
get_all_classes(offset=0, count=100)
```

For large projects, use pagination:
```
get_all_classes(offset=0, count=100)    # First 100
get_all_classes(offset=100, count=100)  # Next 100
```

### Get Main Package Classes

Use `auto=true` to automatically detect the main package:

```
get_package_classes(auto=true)
```

Or specify a package prefix:

```
get_package_classes(package="com.example.app")
```

---

## Common Tool Combinations

### Finding a Feature

When searching for specific functionality:

1. **Search for keywords**
   ```
   search_classes_by_keyword(search_term="login", search_in="code")
   ```

2. **Get the class source**
   ```
   get_class_source(class_name="com.example.LoginActivity")
   ```

3. **Find cross-references**
   ```
   get_xrefs_to_class(class_name="com.example.LoginActivity")
   get_xrefs_to_method(class_name="com.example.LoginActivity", method_name="authenticate")
   ```

### Understanding a Class

For deep analysis of a specific class:

1. **Get class structure**
   ```
   get_class_info(class_name="com.example.NetworkClient")
   ```

2. **List all methods**
   ```
   get_methods_of_class(class_name="com.example.NetworkClient")
   ```

3. **Get full source code**
   ```
   get_class_source(class_name="com.example.NetworkClient")
   ```

4. **Analyze method calls**
   ```
   get_method_callees(class_name="com.example.NetworkClient", method_name="sendRequest")
   ```

### Security Analysis

For security auditing:

1. **Get manifest for permissions/components**
   ```
   get_android_manifest()
   ```

2. **Search for secrets/sensitive strings**
   ```
   search_classes_by_keyword(search_term="api_key", search_in="code")
   search_classes_by_keyword(search_term="password", search_in="code")
   search_classes_by_keyword(search_term="secret", search_in="code")
   ```

3. **Find crypto usage**
   ```
   search_classes_by_keyword(search_term="Cipher", search_in="code")
   search_classes_by_keyword(search_term="encrypt", search_in="code")
   ```

4. **Analyze findings**
   ```
   get_class_source(class_name="<suspicious_class>")
   get_xrefs_to_method(class_name="<class>", method_name="<method>")
   ```

---

## Performance Tips

### 1. Check Cache Before Code Search

```
get_decompile_status()
```

If `cached_percentage` is low, use class/method search instead of code search:
```
# Faster - searches class names only
search_classes_by_keyword(search_term="Auth", search_in="class")

# Slower - searches full code
search_classes_by_keyword(search_term="Auth", search_in="code")
```

### 2. Use Package Filter to Narrow Scope

Instead of searching all classes:
```
# Narrow to app package
search_classes_by_keyword(search_term="login", package="com.example")

# Exclude libraries
search_classes_by_keyword(search_term="login", exclude="androidx,com.google")
```

### 3. Use Batch Operations

When analyzing multiple classes:
```
# Instead of 5 individual calls
batch_get_class_source(class_names=[
    "com.example.A",
    "com.example.B",
    "com.example.C"
])
```

When analyzing multiple methods:
```
batch_get_method_by_name(methods=[
    "com.example.Auth:login",
    "com.example.Auth:logout",
    "com.example.Network:send"
])
```

When getting multiple cross-references:
```
batch_get_xrefs(targets=[
    "class:com.example.Auth",
    "method:com.example.Auth:login",
    "field:com.example.Config:API_KEY"
])
```

### 4. Handle Large Responses

Large responses are automatically chunked. Check for `_chunking` metadata:
```json
{
  "_chunking": {
    "has_more": true,
    "next_chunk": 2,
    "total_chunks": 5
  }
}
```

To get more chunks:
```
get_class_source(class_name="...", chunk=2)
```

---

## Error Handling Guide

### BATCH_TOO_LARGE Error

When batch request is too large (>50KB estimated):

```json
{
  "error": "BATCH_TOO_LARGE",
  "estimated_size_kb": 125.0,
  "suggestions": {
    "option1": "Reduce batch size to 2-3 classes",
    "option2": "Use get_class_info for targeted analysis",
    "option3": "Fetch individually with get_class_source",
    "option4": "Add force=True to proceed anyway"
  }
}
```

**Solutions:**
1. Reduce batch size
2. Use `force=True` to override
3. Fetch classes individually (supports chunking)

### NOT_APPLICABLE Response

Tool doesn't apply to this file type:
```json
{
  "status": "NOT_APPLICABLE",
  "message": "jar_get_manifest only applies to JAR files"
}
```

Check `get_file_info()` to confirm file type and use appropriate tools.

### Instance Connection Error

```json
{
  "error": "Connection failed",
  "instance": "default"
}
```

**Solutions:**
1. Check instance health: `health_check_jadx_instances()`
2. Verify JADX is running and file is loaded
3. Check network connectivity to MCP server

### Class Not Found

```json
{
  "error": "Class not found",
  "class_name": "com.example.Missing"
}
```

**Solutions:**
1. Verify class name with `search_classes_by_keyword(search_term="Missing", search_in="class")`
2. Check if class is obfuscated - may have different name
3. Use `get_all_classes()` to browse available classes

---

## File Type Reference

| File Type | Entry Point Tools | Manifest Tool |
|:----------|:------------------|:--------------|
| APK | `get_main_activity_class()`, `get_main_application_classes_names()` | `get_android_manifest()` |
| JAR | `jar_get_entry_points()`, `jar_get_services()` | `jar_get_manifest()` |
| AAR | `get_android_manifest()` | `get_android_manifest()` |
| DEX | `get_all_classes()` | N/A |

---

## Quick Reference Card

| Task | Tool |
|:-----|:-----|
| File info | `get_file_info()` |
| Check status | `get_decompile_status()` |
| List classes | `get_all_classes()`, `get_package_classes()` |
| Get source | `get_class_source()`, `get_method_by_name()` |
| Search | `search_classes_by_keyword()`, `search_method_by_name()` |
| Cross-refs | `get_xrefs_to_class()`, `get_xrefs_to_method()`, `get_xrefs_to_field()` |
| Batch ops | `batch_get_class_source()`, `batch_get_method_by_name()`, `batch_get_xrefs()` |
| APK manifest | `get_android_manifest()` |
| JAR manifest | `jar_get_manifest()` |
