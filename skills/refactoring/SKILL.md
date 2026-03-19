---
name: refactoring
description: Use this skill when the user wants to rename, deobfuscate, or refactor Java code in JADX. This includes renaming classes, methods, fields, or packages to meaningful names, cleaning up obfuscated code, improving code readability, or applying consistent naming conventions. Trigger words include "rename", "deobfuscate", "refactor", "meaningful names", "clean up", "improve readability", "obfuscated code", "fix names", "name cleanup".
---

# JADX Refactoring Guide

Rename and deobfuscate Java code using JADX MCP tools to improve readability and understanding.

## Unified Rename Tool

All rename operations use a single `rename` tool with a `target_type` parameter:

```
rename(
    target_type: str,      # "class" | "method" | "field" | "package"
    old_name: str,         # Current name (fully qualified for class/package)
    new_name: str,         # New name
    class_name: str = "",  # Required for method/field
    dry_run: bool = False, # Preview without executing
    instance_id: str       # JADX instance (optional)
)
```

Use `dry_run=True` to verify the target exists before renaming — this avoids triggering the 30s cache cooldown.

## Naming Conventions

| Type | Convention | Example |
|:-----|:-----------|:--------|
| Package | lowercase, dot-separated | `com.example.network` |
| Class | PascalCase, noun | `UserManager`, `HttpClient` |
| Method | camelCase, verb | `fetchData`, `parseResponse` |
| Field | camelCase, descriptive | `userName`, `isConnected` |

## Renaming Priority

Process in this order to maintain valid references:

| Priority | Type | Reason |
|:--------:|:-----|:-------|
| 1 | Package | Affects all contained classes |
| 2 | Class | Affects all methods and fields |
| 3 | Method | May affect call sites |
| 4 | Field | Least dependencies |

## Cache Invalidation

**IMPORTANT**: After renaming, JADX cache takes up to 30 seconds to refresh.

- Wait before fetching updated code
- Use `get_class_source` to verify changes applied
- If old names appear, wait and retry

## Step-by-Step Workflow

### Step 1: Analyze Obfuscated Code

```
search_classes_by_keyword(keyword="a")
get_class_source(class_name="com.example.a")
```

Review the code structure and identify patterns.

### Step 2: Identify Meaningful Names

Analyze:
- String constants and API calls
- Method signatures and return types
- Field usage patterns
- Import statements

### Step 3: Preview Before Renaming

```
rename(target_type="class", old_name="com.example.a", new_name="HttpClient", dry_run=True)
```

### Step 4: Rename Packages First

```
rename(target_type="package", old_name="com.a.b", new_name="com.example.network")
```

### Step 5: Rename Classes

```
rename(target_type="class", old_name="com.example.network.a", new_name="HttpClient")
```

### Step 6: Rename Methods and Fields

```
rename(target_type="method", old_name="a", new_name="sendRequest", class_name="com.example.network.HttpClient")

rename(target_type="field", old_name="b", new_name="responseData", class_name="com.example.network.HttpClient")
```

### Step 7: Verify Changes

```
get_class_source(class_name="com.example.network.HttpClient")
```

## Quick Reference

| Task | Command |
|:-----|:--------|
| Find classes | `search_classes_by_keyword(keyword="...")` |
| View source | `get_class_source(class_name="...")` |
| Preview rename | `rename(target_type="...", old_name="...", new_name="...", dry_run=True)` |
| Rename package | `rename(target_type="package", old_name="...", new_name="...")` |
| Rename class | `rename(target_type="class", old_name="...", new_name="...")` |
| Rename method | `rename(target_type="method", old_name="...", new_name="...", class_name="...")` |
| Rename field | `rename(target_type="field", old_name="...", new_name="...", class_name="...")` |

## Common Pitfalls

- **Renaming out of order**: Always rename packages before classes, classes before methods/fields
- **Not waiting for cache**: Changes may not appear immediately; wait 30 seconds
- **Skipping dry_run**: Always preview first to avoid wasting the cache cooldown
- **Invalid names**: Ensure new names follow Java naming rules (no spaces, no keywords)
- **Duplicate names**: Check for existing names before renaming to avoid conflicts
- **Missing context**: Always read the source code before deciding on meaningful names
