---
name: refactoring
description: Use this skill when the user wants to rename, deobfuscate, or refactor Java code in JADX. This includes renaming classes, methods, fields, packages, or local variables to meaningful names, cleaning up obfuscated code, improving code readability, or applying consistent naming conventions. Trigger words include "rename", "deobfuscate", "refactor", "meaningful names", "clean up", "improve readability", "obfuscated code", "fix names", "name cleanup".
---

# JADX Refactoring Guide

Rename and deobfuscate Java code using JADX MCP tools to improve readability and understanding.

## Rename Tools

Each rename operation has a dedicated tool. Choose the right one by what you are renaming:

| Task | Tool | Key Parameters |
|:-----|:-----|:---------------|
| Rename a class | `rename_class` | `class_name`, `new_name` |
| Rename a method | `rename_method` | `class_name`, `method_name`, `new_name` |
| Rename a field | `rename_field` | `class_name`, `field_name`, `new_name` |
| Rename a package | `rename_package` | `old_package_name`, `new_package_name` |
| Rename a local variable | `rename_variable` | `class_name`, `method_name`, `variable_name`, `new_name` |

All rename operations trigger a **30-second ClassCacheManager cooldown**. Wait before fetching updated source.

## Naming Conventions

| Type | Convention | Example |
|:-----|:-----------|:--------|
| Package | lowercase, dot-separated | `com.example.network` |
| Class | PascalCase, noun | `UserManager`, `HttpClient` |
| Method | camelCase, verb | `fetchData`, `parseResponse` |
| Field | camelCase, descriptive | `userName`, `isConnected` |
| Variable | camelCase, descriptive | `userId`, `tokenStr`, `retryCount` |

## Renaming Priority

Process in this order to maintain valid references:

| Priority | Type | Reason |
|:--------:|:-----|:-------|
| 1 | Package | Affects all contained classes |
| 2 | Class | Affects all methods and fields |
| 3 | Method | May affect call sites |
| 4 | Field | Fewer dependencies |
| 5 | Variable | Scoped to method body, safest last |

## Cache Invalidation

**IMPORTANT**: After renaming, JADX cache takes up to 30 seconds to refresh.

- Wait before fetching updated code
- Use `get_class_source` to verify changes applied
- If old names appear, wait and retry

## Step-by-Step Workflow

### Step 1: Analyze Obfuscated Code

```
search_classes_by_keyword(search_term="a", search_in="class")
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
rename_package(
    old_package_name="com.a.b",
    new_package_name="com.example.network"
)
```

### Step 4: Rename Classes

```
rename_class(
    class_name="com.example.network.a",
    new_name="HttpClient"
)
```

### Step 5: Rename Methods and Fields

```
rename_method(
    class_name="com.example.network.HttpClient",
    method_name="a",
    new_name="sendRequest"
)

rename_field(
    class_name="com.example.network.HttpClient",
    field_name="b",
    new_name="responseData"
)
```

### Step 6: Rename Local Variables (Optional)

For heavily obfuscated methods with single-letter variables:

```
rename_variable(
    class_name="com.example.network.HttpClient",
    method_name="sendRequest",
    variable_name="a",
    new_name="requestUrl"
)
```

### Step 7: Verify Changes

```
get_class_source(class_name="com.example.network.HttpClient")
```

## Common Pitfalls

- **Renaming out of order**: Always rename packages before classes, classes before methods/fields
- **Not waiting for cache**: Changes may not appear immediately; wait 30 seconds
- **Invalid names**: Ensure new names follow Java naming rules (no spaces, no keywords)
- **Duplicate names**: Check for existing names before renaming to avoid conflicts
- **Missing context**: Always read the source code before deciding on meaningful names
