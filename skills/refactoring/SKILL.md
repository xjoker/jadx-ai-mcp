---
name: refactoring
description: Use this skill when the user wants to rename, deobfuscate, or refactor Java code in JADX. This includes renaming classes, methods, fields, or packages to meaningful names, cleaning up obfuscated code, improving code readability, or applying consistent naming conventions. Trigger words include "rename", "deobfuscate", "refactor", "meaningful names", "clean up", "improve readability", "obfuscated code", "fix names", "name cleanup".
---

# JADX Refactoring Guide

Rename and deobfuscate Java code using JADX MCP tools to improve readability and understanding.

## Rename Tools

Each identifier type has its own dedicated rename tool:

| Tool | Purpose | Key Parameters |
|:-----|:--------|:---------------|
| `rename_package` | Rename a package | `original_name`, `new_name` |
| `rename_class` | Rename a class | `original_name`, `new_name` |
| `rename_method` | Rename a method | `original_name`, `new_name` |
| `rename_field` | Rename a field | `original_name`, `new_name` |

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

### Step 3: Rename Packages First

```
rename_package(original_name="com.a.b", new_name="com.example.network")
```

### Step 4: Rename Classes

```
rename_class(original_name="com.example.network.a", new_name="HttpClient")
```

### Step 5: Rename Methods and Fields

```
rename_method(original_name="a", new_name="sendRequest")

rename_field(original_name="b", new_name="responseData")
```

### Step 6: Verify Changes

```
get_class_source(class_name="com.example.network.HttpClient")
```

## Quick Reference

| Task | Tool |
|:-----|:-----|
| Find classes | `search_classes_by_keyword` |
| View source | `get_class_source` |
| Rename package | `rename_package` |
| Rename class | `rename_class` |
| Rename method | `rename_method` |
| Rename field | `rename_field` |

## Common Pitfalls

- **Renaming out of order**: Always rename packages before classes, classes before methods/fields
- **Not waiting for cache**: Changes may not appear immediately; wait 30 seconds
- **Invalid names**: Ensure new names follow Java naming rules (no spaces, no keywords)
- **Duplicate names**: Check for existing names before renaming to avoid conflicts
- **Missing context**: Always read the source code before deciding on meaningful names
