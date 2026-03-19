---
name: logic-tracing
description: Trace code logic, call chains, and data flow in decompiled Android apps. Use when asked "how does this work", "call chain", "trace flow", "where is this called", "how is this implemented", "find callers", "understand logic", "API flow", "data flow", or when analyzing method invocations, understanding feature implementations, or tracing data through the codebase.
---

# Logic Tracing Guide

Understand code execution paths, method call chains, and data flow in decompiled Android applications using JADX-AI-MCP tools.

## When to Use This Skill

- Understanding how a specific feature or API is implemented
- Tracing method call chains (who calls what)
- Finding all callers of a method (reverse tracing)
- Following data flow through the application
- Analyzing entry points (Activities, Services, Receivers)
- Understanding callback and listener patterns

## Core Tools

| Tool | Purpose | Use Case |
|:-----|:--------|:---------|
| `get_xrefs_to_method` | Find all callers | Reverse tracing - "where is this called?" |
| `get_method_callees` | Find all callees | Forward tracing - "what does this call?" |
| `get_class_source` | Read full source | Understand implementation details |
| `search_method_by_name` | Find methods | Locate entry points by name pattern |
| `search_classes_by_keyword` | Find classes | Locate components by name |

## Tracing Patterns

### Pattern 1: Forward Tracing (Entry Point → Implementation)

Start from a known entry point and trace what it calls.

```
1. Identify entry point (Activity.onCreate, Service.onStartCommand, etc.)
2. Use get_class_source to read the entry point
3. Use get_method_callees to find what methods it invokes
4. Recursively trace interesting callees
5. Document the call chain
```

**Example: Trace login flow**
```
Entry: LoginActivity.onCreate()
  → LoginActivity.onLoginClicked()
    → AuthManager.login()
      → ApiClient.postRequest()
        → OkHttpClient.newCall()
```

### Pattern 2: Reverse Tracing (Method → All Callers)

Start from a method and find everything that calls it.

```
1. Identify target method (e.g., sensitive API call)
2. Use get_xrefs_to_method to find all callers
3. For each caller, trace upward to find entry points
4. Build reverse call graph
```

**Example: Find all encryption uses**
```
Target: CryptoUtils.encrypt()
Callers:
  ← UserDataManager.saveCredentials()
    ← LoginActivity.onLoginSuccess()
  ← PaymentHandler.processCard()
    ← CheckoutActivity.submitPayment()
```

### Pattern 3: Data Flow Tracing

Follow how data moves through the application.

```
1. Identify data source (user input, API response, file read)
2. Trace method calls that pass the data
3. Identify transformations (encoding, encryption, parsing)
4. Find data sinks (network, storage, display)
```

**Key data flow points:**
- Sources: EditText.getText(), Intent.getStringExtra(), SharedPreferences.getString()
- Sinks: HttpURLConnection.write(), SQLiteDatabase.insert(), Log.d()

## Step-by-Step Workflow

### Step 1: Identify Starting Point

```python
# Find entry points by component type
search_classes_by_keyword(keyword="Activity")    # UI entry points
search_classes_by_keyword(keyword="Service")     # Background entry points
search_classes_by_keyword(keyword="Receiver")    # Broadcast entry points

# Find by functionality
search_method_by_name(method_name="login")
search_method_by_name(method_name="encrypt")
search_method_by_name(method_name="sendRequest")
```

### Step 2: Read Source Code

```python
# Get full class implementation
get_class_source("com.example.app.LoginActivity")

# Look for:
# - onCreate, onStart, onResume (Activity lifecycle)
# - onClick handlers and listeners
# - Method parameters and return types
```

### Step 3: Trace Outward (Forward)

```python
# Find what a method calls
get_method_callees("com.example.app.AuthManager", "login")

# Returns list of invoked methods
# Follow interesting ones deeper
```

### Step 4: Trace Inward (Reverse)

```python
# Find all callers of a method
get_xrefs_to_method("com.example.app.CryptoUtils", "encrypt")

# Returns all locations that invoke this method
# Trace each caller to its entry point
```

### Step 5: Document Call Chain

Build a clear representation:

```
[Entry Point]
  LoginActivity.onCreate()
    ↓
  LoginActivity.setupListeners()
    ↓
  [User Action: Click Login]
    ↓
  LoginActivity.onLoginClicked()
    ↓
  AuthManager.login(username, password)
    ↓
  ApiClient.post("/api/login", credentials)
    ↓
  [Network Call]
```

## Quick Reference

| Task | Tool | Example |
|:-----|:-----|:--------|
| Find method callers | `get_xrefs_to_method` | Who calls `sendSMS()`? |
| Find method callees | `get_method_callees` | What does `processPayment()` call? |
| Read implementation | `get_class_source` | Full source of AuthManager |
| Find by name | `search_method_by_name` | Methods containing "encrypt" |
| Find components | `search_classes_by_keyword` | Classes ending in "Activity" |

## Best Practices

1. **Start broad, then narrow**: Begin with class-level understanding before diving into specific methods
2. **Trace both directions**: Combine forward and reverse tracing for complete picture
3. **Follow the data**: Track parameters and return values through call chains
4. **Note callbacks**: Android uses many callback patterns; trace listener registrations
5. **Check for obfuscation**: Method names like `a()`, `b()` indicate obfuscation; focus on string literals and API calls
6. **Document as you go**: Build call chain diagrams to avoid getting lost

## Common Entry Points

| Component | Entry Methods |
|:----------|:-------------|
| Activity | `onCreate`, `onResume`, `onClick` handlers |
| Service | `onStartCommand`, `onBind` |
| BroadcastReceiver | `onReceive` |
| ContentProvider | `query`, `insert`, `update`, `delete` |
| Fragment | `onCreateView`, `onViewCreated` |

## Common Pitfalls

- **Missing indirect calls**: Reflection, dynamic proxies, and event buses hide call relationships
- **Ignoring async**: AsyncTask, Handler, and coroutines break direct call chains
- **Stopping too early**: Important logic often lives several layers deep
- **Forgetting interfaces**: Implementations may be in unexpected classes
