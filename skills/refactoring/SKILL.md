---
name: refactoring
description: Use this skill when the user wants to rename, deobfuscate, or refactor Java code in JADX. This includes renaming classes, methods, fields, or packages to meaningful names, cleaning up obfuscated code, improving code readability, or applying consistent naming conventions. Trigger words include "rename", "deobfuscate", "refactor", "meaningful names", "clean up", "improve readability", "obfuscated code", "fix names", "name cleanup".
---

# JADX Refactoring Guide

Rename and deobfuscate Java code using JADX MCP tools to improve readability and understanding.

## Unified Rename Interface

All rename operations use the same tool with a `type` parameter:

```
mcp__jadx__rename_identifier(
    original_name: str,      # Current name (e.g., "a", "com.example.a")
    new_name: str,           # New meaningful name
    type: str,               # "package" | "class" | "method" | "field"
    instance_name: str       # JADX instance (default: "local")
)
```

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
mcp__jadx__search_class(query="a")
mcp__jadx__get_class_source(class_name="com.example.a")
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
mcp__jadx__rename_identifier(
    original_name="com.a.b",
    new_name="com.example.network",
    type="package"
)
```

### Step 4: Rename Classes

```
mcp__jadx__rename_identifier(
    original_name="com.example.network.a",
    new_name="HttpClient",
    type="class"
)
```

### Step 5: Rename Methods and Fields

```
mcp__jadx__rename_identifier(
    original_name="a",
    new_name="sendRequest",
    type="method"
)

mcp__jadx__rename_identifier(
    original_name="b",
    new_name="responseData",
    type="field"
)
```

### Step 6: Verify Changes

```
mcp__jadx__get_class_source(class_name="com.example.network.HttpClient")
```

## Quick Reference

| Task | Tool | Parameters |
|:-----|:-----|:-----------|
| Find classes | `search_class` | `query` |
| View source | `get_class_source` | `class_name` |
| Rename package | `rename_identifier` | `type="package"` |
| Rename class | `rename_identifier` | `type="class"` |
| Rename method | `rename_identifier` | `type="method"` |
| Rename field | `rename_identifier` | `type="field"` |

## Common Pitfalls

- **Renaming out of order**: Always rename packages before classes, classes before methods/fields
- **Not waiting for cache**: Changes may not appear immediately; wait 30 seconds
- **Invalid names**: Ensure new names follow Java naming rules (no spaces, no keywords)
- **Duplicate names**: Check for existing names before renaming to avoid conflicts
- **Missing context**: Always read the source code before deciding on meaningful names
