---
name: refactoring
description: Rename and deobfuscate code elements. Use when renaming classes, methods, fields, or packages to improve code readability.
---

# Refactoring Assistant

A skill for guiding AI through code refactoring operations in JADX-AI-MCP, focusing on renaming deobfuscated code elements.

## Overview

This skill helps with systematic refactoring of decompiled Android/Java code, primarily through renaming obfuscated identifiers to meaningful names.

## Unified Rename Tool

Use the `rename` tool for all renaming operations:

### Class Renaming
```python
rename("class", "com.example.a", "com.example.MainActivity")
```

### Method Renaming
```python
rename("method", "a", "getUserProfile", class_name="com.example.UserManager")
```

### Field Renaming
```python
rename("field", "b", "mUserName", class_name="com.example.User")
```

### Package Renaming
```python
rename("package", "com.example.a", "com.example.network")
```

## Cache Invalidation

**Critical**: Rename operations trigger a 30-second cache cooldown.

### Why This Matters
- After renaming, the class source cache becomes stale
- Fetching source immediately after rename may return old content
- The 30-second window allows JADX to regenerate decompiled source

### Best Practice
1. Execute rename operation
2. Wait before fetching renamed class source (system handles this automatically)
3. Verify the rename was applied correctly

### Batch Operations
When performing multiple renames:
- Group related renames together
- Wait once after the batch completes
- Then verify all changes

## Using Cross-References (xrefs)

Always check references before and after renaming to ensure consistency.

### Before Renaming
```python
# Check all usages of a class before renaming
xrefs = get_xrefs("com.example.a")
print(f"Found {len(xrefs)} references to this class")
```

### After Renaming
```python
# Verify old name has no references (should be empty)
old_refs = get_xrefs("com.example.a")
assert len(old_refs) == 0, "Old name still has references!"

# Verify new name has all expected references
new_refs = get_xrefs("com.example.MainActivity")
print(f"New name has {len(new_refs)} references")
```

### Impact Analysis
Before renaming a widely-used class:
1. Get xrefs count
2. Review calling classes
3. Consider if rename affects public API

## Deobfuscation Best Practices

### Prioritization Order

1. **Package Names** - Establish the project structure first
2. **Class Names** - Most impactful for code understanding
3. **Method Names** - Clarify behavior
4. **Field Names** - Document state

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Package | lowercase, domain-based | `com.app.network` |
| Class | PascalCase, noun | `UserManager`, `NetworkClient` |
| Method | camelCase, verb | `getUserById`, `sendRequest` |
| Field | camelCase, prefixed | `mUserName`, `sInstance` |

### Deriving Meaningful Names

1. **Analyze Method Body**
   - Look for API calls (HTTP, database, crypto)
   - Check string literals for hints
   - Examine control flow patterns

2. **Check String Constants**
   - Log tags often reveal class purpose
   - Error messages describe functionality
   - URL paths indicate network operations

3. **Follow Data Flow**
   - Input parameters suggest purpose
   - Return types indicate output
   - Field assignments show state management

4. **Examine Inheritance**
   - Base class names provide context
   - Interface implementations reveal contracts
   - Android component types are informative

### Example Workflow

```
1. Identify obfuscated class: com.a.b.c

2. Gather context:
   - Get class source
   - Check xrefs to see usage patterns
   - Look for string literals

3. Analyze findings:
   - Extends Activity
   - Has onCreate, onResume
   - Contains "Login" in strings
   - Makes network calls to /auth endpoint

4. Apply renames:
   rename("class", "com.a.b.c", "com.app.ui.LoginActivity")
   rename("method", "a", "validateCredentials", class_name="com.app.ui.LoginActivity")
   rename("field", "b", "mEmailInput", class_name="com.app.ui.LoginActivity")

5. Verify:
   - Check xrefs for new name
   - Fetch updated source
   - Confirm no broken references
```

## Common Patterns

### Network Classes
- Look for: OkHttp, Retrofit, HttpURLConnection
- Naming: `*Client`, `*Api`, `*Service`

### Data Models
- Look for: Parcelable, Serializable, GSON annotations
- Naming: Noun matching the data type

### UI Components
- Look for: Activity, Fragment, View inheritance
- Naming: `*Activity`, `*Fragment`, `*View`

### Utilities
- Look for: Static methods, no state
- Naming: `*Utils`, `*Helper`, `*Manager`

## Troubleshooting

### Rename Not Appearing
- Wait for cache cooldown (30 seconds)
- Refresh the class source
- Check for typos in class name

### Xrefs Still Show Old Name
- Cache may not be fully invalidated
- Wait and retry
- Verify rename was successful

### Conflicting Names
- Check if target name already exists
- Use unique, descriptive names
- Consider package context
