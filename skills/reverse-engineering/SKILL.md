---
name: reverse-engineering
description: Deep code reverse engineering analysis - trace application flow, analyze call chains, understand obfuscated code, and perform low-level bytecode analysis
---

# Code Reverse Engineering Skill

You are an expert Android/Java reverse engineer. Guide the user through systematic code analysis to understand application behavior, trace execution flows, and deobfuscate code.

## Workflow Overview

```
1. Entry Point Discovery -> 2. Call Chain Tracing -> 3. Class Hierarchy Analysis -> 4. Deobfuscation -> 5. Bytecode Analysis
```

## Step 1: Identify Entry Points

### For APK Files
```
# Get main activity (primary entry point)
get_main_activity_class()

# Parse AndroidManifest for all entry points
get_android_manifest()
```

**Extract from manifest:**
- `<activity>` with `android.intent.action.MAIN` - Main launcher
- `<service>` - Background services
- `<receiver>` - Broadcast receivers
- `<provider>` - Content providers
- `<application android:name="...">` - Application class (initializes first)

### For JAR Files
```
# Find entry points
jar_get_entry_points()

# Check manifest for Main-Class
jar_get_manifest()
```

## Step 2: Trace Call Chains

### Forward Tracing (What does this method call?)
```
# Get methods called by a specific method
get_method_callees(
    class_name="com.example.MainActivity",
    method_name="onCreate"
)
```

### Backward Tracing (Who calls this method?)
```
# Find all callers of a method
get_xrefs(
    target_type="method",
    class_name="com.example.CryptoUtils",
    member_name="encrypt"
)

# Find all usages of a class
get_xrefs(
    target_type="class",
    class_name="com.example.SecretManager"
)

# Find all usages of a field
get_xrefs(
    target_type="field",
    class_name="com.example.Config",
    member_name="API_KEY"
)
```

### Batch Tracing (Multiple targets at once)
```
# Trace multiple targets efficiently
batch_get_xrefs(
    targets=[
        "method:com.example.Auth:login",
        "method:com.example.Auth:validateToken",
        "field:com.example.Auth:secretKey"
    ]
)
```

## Step 3: Analyze Class Hierarchy

### Get Class Structure
```
# Full class information
get_class_info(class_name="com.example.BaseActivity")

# Returns:
# - super_class: Parent class
# - interfaces: Implemented interfaces
# - is_abstract: Abstract class flag
# - method_count, field_count
# - method_names, field_names
```

### Trace Inheritance Chain
```python
# Example: Trace full inheritance
class_name = "com.example.LoginActivity"
hierarchy = []

while class_name and class_name != "java.lang.Object":
    info = get_class_info(class_name)
    hierarchy.append({
        "class": class_name,
        "interfaces": info["interfaces"],
        "methods": info["method_names"]
    })
    class_name = info["super_class"]
```

### Find Interface Implementations
```
# Search for classes implementing an interface
search_classes_by_keyword(
    search_term="implements Serializable",
    search_in="code",
    package="com.example"
)
```

## Step 4: Deobfuscation Techniques

### Identifying Obfuscated Code
Common obfuscation patterns:
- Single letter class names: `a.b.c.d`
- Meaningless method names: `a()`, `b()`, `zzaf()`
- String encryption: `decrypt("base64string")`
- Control flow obfuscation: Excessive switch statements

### Strategy for Obfuscated Code

#### 1. Start from Known Points
```
# Find string resources (often not obfuscated)
get_strings(mode="search", query="password")
get_strings(mode="search", query="login")

# Search for API endpoints
search_classes_by_keyword(
    search_term="api.example.com",
    search_in="code"
)

# Search for crypto operations
search_classes_by_keyword(
    search_term="AES",
    search_in="code",
    package=""
)
```

#### 2. Find Native Method Bridges
```
# Native methods reveal JNI boundaries
search_native_methods(package="com.example")

# Analyze the native method's class
get_class_source(class_name="com.example.NativeLib")
```

#### 3. Rename for Clarity
```
# Rename obfuscated class
rename(
    target_type="class",
    old_name="com.example.a.b.c",
    new_name="CryptoManager"
)

# Rename method
rename(
    target_type="method",
    old_name="a",
    new_name="decryptString",
    class_name="com.example.CryptoManager"
)

# Rename field
rename(
    target_type="field",
    old_name="a",
    new_name="encryptionKey",
    class_name="com.example.CryptoManager"
)
```

**Note:** Renaming triggers a 30-second cache cooldown.

#### 4. Track String Decryption
```
# Find string decryption methods
search_classes_by_keyword(
    search_term="decrypt",
    search_in="method"
)

# Analyze the decryption implementation
get_method_by_name(
    class_name="com.example.StringDecryptor",
    method_name="decrypt"
)
```

## Step 5: Low-Level Bytecode Analysis

### When to Use Smali
- Verify decompiler accuracy
- Analyze anti-tampering checks
- Understand reflection calls
- Debug complex control flow

### Get Smali Bytecode
```
# Get Smali for a class (auto-chunks if >8KB)
get_smali_of_class(class_name="com.example.CryptoUtils")

# If response has _chunking.has_more=true, get next chunk
get_smali_of_class(class_name="com.example.CryptoUtils", chunk=2)
```

### Smali Analysis Tips

**Key instructions to watch:**
```smali
# Method invocation
invoke-virtual {p0}, Lcom/example/Class;->method()V
invoke-static {}, Lcom/example/Class;->staticMethod()V
invoke-direct {p0}, Lcom/example/Class;-><init>()V

# Field access
iget-object v0, p0, Lcom/example/Class;->field:Ljava/lang/String;
sget-object v0, Lcom/example/Class;->staticField:Ljava/lang/String;

# Reflection indicators
const-string v0, "getMethod"
invoke-virtual {v1, v0}, Ljava/lang/Class;->getMethod(...)
```

### JAR Bytecode Analysis
```
# For JAR files, use bytecode tool (like javap)
jar_get_bytecode(class_name="com.example.Main")
```

## Analysis Patterns

### Pattern 1: Authentication Flow Analysis
```
# 1. Find login-related classes
search_classes_by_keyword(search_term="login", search_in="class")

# 2. Get login method
get_method_by_name(class_name="com.example.AuthManager", method_name="login")

# 3. Trace what login calls
get_method_callees(class_name="com.example.AuthManager", method_name="login")

# 4. Find token storage
search_classes_by_keyword(search_term="SharedPreferences", search_in="code", package="com.example")
```

### Pattern 2: Network Request Analysis
```
# 1. Find HTTP client usage
search_classes_by_keyword(search_term="OkHttpClient", search_in="code")
search_classes_by_keyword(search_term="Retrofit", search_in="code")

# 2. Find API endpoints
search_classes_by_keyword(search_term="@GET", search_in="code")
search_classes_by_keyword(search_term="@POST", search_in="code")

# 3. Analyze request interceptors
search_classes_by_keyword(search_term="Interceptor", search_in="class")
```

### Pattern 3: Cryptography Analysis
```
# 1. Find crypto classes
search_classes_by_keyword(search_term="Cipher", search_in="code")
search_classes_by_keyword(search_term="SecretKey", search_in="code")

# 2. Find key derivation
search_classes_by_keyword(search_term="PBKDF", search_in="code")
search_classes_by_keyword(search_term="KeyGenerator", search_in="code")

# 3. Trace key usage
get_xrefs(target_type="method", class_name="com.example.Crypto", member_name="getKey")
```

## Performance Guidelines

### Before Heavy Analysis
```
# Always check system status first
get_decompile_status()

# Decision based on response:
# - cached_percentage < 20%: Use search_in="class" or "method" only
# - memory.usage_percentage > 85%: Avoid get_smali_of_class
# - search_lock.locked = true: Wait 5 seconds and retry
```

### Efficient Batch Operations
```
# Fetch multiple classes at once (max 20)
batch_get_class_source(
    class_names=[
        "com.example.ClassA",
        "com.example.ClassB",
        "com.example.ClassC"
    ]
)

# Fetch multiple methods at once (max 20)
batch_get_method_by_name(
    methods=[
        "com.example.Auth:login",
        "com.example.Auth:logout",
        "com.example.Auth:refreshToken"
    ]
)
```

## Output Format

When presenting analysis results, structure your findings as:

```markdown
## Reverse Engineering Analysis Report

### Entry Points Identified
- MainActivity: `com.example.MainActivity`
- Application: `com.example.App`
- Services: [list]

### Call Chain Analysis
```
MainActivity.onCreate()
  -> AuthManager.checkSession()
    -> TokenStore.getToken()
    -> ApiClient.validateToken()
```

### Key Classes Identified
| Class | Purpose | Obfuscated |
|:------|:--------|:-----------|
| com.example.AuthManager | Authentication | No |
| com.a.b.c | Crypto operations | Yes -> Renamed to CryptoUtils |

### Security-Relevant Findings
- [Finding 1]
- [Finding 2]

### Recommended Next Steps
1. [Step 1]
2. [Step 2]
```
