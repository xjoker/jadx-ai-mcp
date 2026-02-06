# Frida Hook Generation

A skill for generating Frida hooks from decompiled Android/Java code using JADX-AI-MCP.

## Overview

This skill guides AI through the process of generating accurate Frida JavaScript hooks by leveraging JADX metadata. It uses structured method and field information to produce correctly typed hooks that handle overloads, native methods, and complex type signatures.

## Key MCP Tools

### 1. get_methods_of_class

Retrieves method metadata essential for hook generation:

```python
result = get_methods_of_class("com.example.CryptoUtils")
```

**Returns:**
```json
{
  "class_name": "com.example.CryptoUtils",
  "methods": [
    {
      "name": "encrypt",
      "is_static": true,
      "is_native": false,
      "is_constructor": false,
      "is_abstract": false,
      "is_synchronized": false,
      "modifiers": ["public", "static"],
      "overload_count": 2,
      "return_type": "byte[]"
    }
  ],
  "count": 15
}
```

**Key Fields:**
- `is_static`: Determines if hook uses `this` or class reference
- `is_native`: Requires `Interceptor.attach` instead of `Java.use`
- `is_constructor`: Hook with `$init` instead of method name
- `overload_count`: If > 1, must specify `.overload()` with types

### 2. get_method_signature

Gets Frida-compatible method signatures for overload handling:

```python
result = get_method_signature("com.example.CryptoUtils", "encrypt")
```

**Returns:**
```json
{
  "class_name": "com.example.CryptoUtils",
  "method_name": "encrypt",
  "overloads": 2,
  "signatures": [
    {
      "method_name": "encrypt",
      "return_type": "byte[]",
      "access_flags": "public static",
      "is_constructor": false,
      "parameters": [
        {"name": "arg0", "type": "byte[]", "type_frida": "[B"},
        {"name": "arg1", "type": "String", "type_frida": "java.lang.String"}
      ],
      "frida_overload": "'[B', 'java.lang.String'"
    },
    {
      "method_name": "encrypt",
      "return_type": "byte[]",
      "access_flags": "public static",
      "is_constructor": false,
      "parameters": [
        {"name": "arg0", "type": "String", "type_frida": "java.lang.String"}
      ],
      "frida_overload": "'java.lang.String'"
    }
  ]
}
```

**Key Fields:**
- `frida_overload`: Ready-to-use string for `.overload()` syntax
- `type_frida`: Frida-compatible type notation (e.g., `[B` for `byte[]`)

### 3. get_fields_of_class

Gets field information for reading/writing class state:

```python
result = get_fields_of_class("com.example.Config")
```

**Returns:**
```json
{
  "class_name": "com.example.Config",
  "fields": [
    {
      "name": "API_KEY",
      "type": "String",
      "type_frida": "java.lang.String",
      "modifiers": ["private", "static", "final"],
      "is_static": true,
      "is_final": true
    },
    {
      "name": "mContext",
      "type": "Context",
      "type_frida": "android.content.Context",
      "modifiers": ["private"],
      "is_static": false,
      "is_final": false
    }
  ],
  "count": 5
}
```

**Key Fields:**
- `type_frida`: Use for casting in Frida
- `is_static`: Determines access pattern (class vs instance)

## Hook Generation Workflow

### Step 1: Gather Class Information

```python
# Get all methods with metadata
methods = get_methods_of_class("com.example.TargetClass")

# Identify hook targets
for method in methods["methods"]:
    if method["is_native"]:
        print(f"Native: {method['name']} - use Interceptor.attach")
    elif method["overload_count"] > 1:
        print(f"Overloaded: {method['name']} - need .overload() syntax")
    else:
        print(f"Simple: {method['name']} - direct hook")
```

### Step 2: Get Signatures for Overloaded Methods

```python
# For methods with overload_count > 1
sig = get_method_signature("com.example.TargetClass", "encrypt")

for overload in sig["signatures"]:
    print(f"Overload: .overload({overload['frida_overload']})")
```

### Step 3: Generate Hook Code

Use the templates below based on method characteristics.

## Frida Hook Templates

### Basic Method Hook (No Overloads)

```javascript
Java.perform(function() {
    var TargetClass = Java.use("com.example.TargetClass");

    TargetClass.methodName.implementation = function(arg0, arg1) {
        console.log("[*] methodName called");
        console.log("    arg0: " + arg0);
        console.log("    arg1: " + arg1);

        var result = this.methodName(arg0, arg1);
        console.log("    result: " + result);
        return result;
    };
});
```

### Static Method Hook

```javascript
Java.perform(function() {
    var TargetClass = Java.use("com.example.TargetClass");

    // Static methods don't use 'this', but Frida binds it anyway
    TargetClass.staticMethod.implementation = function(arg0) {
        console.log("[*] staticMethod called (static)");
        console.log("    arg0: " + arg0);

        // Call original static method
        var result = this.staticMethod(arg0);
        console.log("    result: " + result);
        return result;
    };
});
```

### Overloaded Method Hook

Use `frida_overload` from `get_method_signature`:

```javascript
Java.perform(function() {
    var CryptoUtils = Java.use("com.example.CryptoUtils");

    // Hook overload: encrypt(byte[], String)
    // frida_overload: "'[B', 'java.lang.String'"
    CryptoUtils.encrypt.overload('[B', 'java.lang.String').implementation = function(data, key) {
        console.log("[*] encrypt(byte[], String) called");
        console.log("    data length: " + data.length);
        console.log("    key: " + key);

        var result = this.encrypt(data, key);
        console.log("    result length: " + result.length);
        return result;
    };

    // Hook overload: encrypt(String)
    // frida_overload: "'java.lang.String'"
    CryptoUtils.encrypt.overload('java.lang.String').implementation = function(plaintext) {
        console.log("[*] encrypt(String) called");
        console.log("    plaintext: " + plaintext);

        var result = this.encrypt(plaintext);
        return result;
    };
});
```

### Constructor Hook

```javascript
Java.perform(function() {
    var TargetClass = Java.use("com.example.TargetClass");

    // Hook constructor using $init
    TargetClass.$init.overload('java.lang.String', 'int').implementation = function(name, id) {
        console.log("[*] TargetClass constructor called");
        console.log("    name: " + name);
        console.log("    id: " + id);

        // Call original constructor
        this.$init(name, id);

        // Access instance after construction
        console.log("    instance created: " + this);
    };
});
```

### Native Method Hook

For methods where `is_native: true`, use `Interceptor.attach`:

```javascript
// First, find the native library and function address
Interceptor.attach(Module.findExportByName("libnative.so", "Java_com_example_NativeLib_nativeMethod"), {
    onEnter: function(args) {
        console.log("[*] nativeMethod called");
        // args[0] is JNIEnv*, args[1] is jclass/jobject
        // args[2+] are actual parameters
        console.log("    JNIEnv: " + args[0]);
        console.log("    jclass: " + args[1]);
    },
    onLeave: function(retval) {
        console.log("    retval: " + retval);
    }
});
```

### Field Access Hook

Read and modify fields using `type_frida`:

```javascript
Java.perform(function() {
    var Config = Java.use("com.example.Config");

    // Read static field
    var apiKey = Config.API_KEY.value;
    console.log("[*] API_KEY: " + apiKey);

    // Modify static field
    Config.API_KEY.value = "new_api_key";

    // For instance fields, hook a method and access 'this'
    Config.init.implementation = function() {
        this.init();

        // Read instance field
        var ctx = this.mContext.value;
        console.log("[*] mContext: " + ctx);

        // Modify instance field
        // this.mContext.value = newContext;
    };
});
```

### Hooking All Overloads

When you want to hook all overloads of a method:

```javascript
Java.perform(function() {
    var TargetClass = Java.use("com.example.TargetClass");

    // Get all overloads
    var overloads = TargetClass.targetMethod.overloads;

    for (var i = 0; i < overloads.length; i++) {
        overloads[i].implementation = function() {
            console.log("[*] targetMethod overload " + i + " called");
            console.log("    arguments: " + JSON.stringify(arguments));

            // Call original with all arguments
            return this.targetMethod.apply(this, arguments);
        };
    }
});
```

## Common Frida Type Mappings

| Java Type | Frida Type (`type_frida`) |
|-----------|---------------------------|
| `byte[]` | `[B` |
| `int[]` | `[I` |
| `String[]` | `[Ljava.lang.String;` |
| `Object[]` | `[Ljava.lang.Object;` |
| `String` | `java.lang.String` |
| `int` | `int` |
| `boolean` | `boolean` |
| `long` | `long` |
| `byte` | `byte` |
| `Context` | `android.content.Context` |
| `Intent` | `android.content.Intent` |
| `Bundle` | `android.os.Bundle` |

## Complete Example: Crypto Hook Generation

### 1. Analyze the Target Class

```python
# Get methods
methods = get_methods_of_class("com.example.security.AESHelper")

# Output:
# - encrypt: is_static=True, overload_count=2
# - decrypt: is_static=True, overload_count=2
# - generateKey: is_static=True, is_native=True
```

### 2. Get Signatures

```python
encrypt_sig = get_method_signature("com.example.security.AESHelper", "encrypt")
decrypt_sig = get_method_signature("com.example.security.AESHelper", "decrypt")
```

### 3. Generated Hook

```javascript
Java.perform(function() {
    console.log("[*] Hooking AESHelper crypto operations");

    var AESHelper = Java.use("com.example.security.AESHelper");

    // Hook encrypt(byte[], byte[]) -> byte[]
    AESHelper.encrypt.overload('[B', '[B').implementation = function(data, key) {
        console.log("[ENCRYPT] data length: " + data.length);
        console.log("[ENCRYPT] key (hex): " + bytesToHex(key));

        var result = this.encrypt(data, key);
        console.log("[ENCRYPT] result (hex): " + bytesToHex(result));
        return result;
    };

    // Hook encrypt(String, String) -> String
    AESHelper.encrypt.overload('java.lang.String', 'java.lang.String').implementation = function(plaintext, key) {
        console.log("[ENCRYPT] plaintext: " + plaintext);
        console.log("[ENCRYPT] key: " + key);

        var result = this.encrypt(plaintext, key);
        console.log("[ENCRYPT] result: " + result);
        return result;
    };

    // Hook decrypt(byte[], byte[]) -> byte[]
    AESHelper.decrypt.overload('[B', '[B').implementation = function(data, key) {
        console.log("[DECRYPT] encrypted length: " + data.length);

        var result = this.decrypt(data, key);
        console.log("[DECRYPT] decrypted: " + bytesToString(result));
        return result;
    };

    // Hook native key generation
    Interceptor.attach(Module.findExportByName("libcrypto.so", "Java_com_example_security_AESHelper_generateKey"), {
        onLeave: function(retval) {
            console.log("[KEYGEN] Generated key address: " + retval);
        }
    });

    // Helper functions
    function bytesToHex(bytes) {
        var hex = [];
        for (var i = 0; i < bytes.length; i++) {
            hex.push(('0' + (bytes[i] & 0xFF).toString(16)).slice(-2));
        }
        return hex.join('');
    }

    function bytesToString(bytes) {
        var result = "";
        for (var i = 0; i < bytes.length; i++) {
            result += String.fromCharCode(bytes[i] & 0xFF);
        }
        return result;
    }
});
```

## Best Practices

### 1. Always Check Overload Count
```python
if method["overload_count"] > 1:
    # Must use get_method_signature and .overload() syntax
    sig = get_method_signature(class_name, method["name"])
```

### 2. Handle Native Methods Separately
```python
if method["is_native"]:
    # Use Interceptor.attach, not Java.use
    # Find the SO library first with search_native_methods
```

### 3. Use Frida Types Exactly
```javascript
// WRONG: Using Java syntax
.overload('byte[]', 'String')

// CORRECT: Using Frida type notation from type_frida
.overload('[B', 'java.lang.String')
```

### 4. Preserve Original Behavior
```javascript
// Always call the original method unless intentionally bypassing
var result = this.originalMethod(arg0, arg1);
return result;
```

### 5. Handle Exceptions
```javascript
try {
    var result = this.riskyMethod(arg0);
    return result;
} catch (e) {
    console.log("[ERROR] " + e);
    throw e;  // Re-throw to preserve app behavior
}
```

## Troubleshooting

### "Method not found" Error
- Check exact method name spelling
- Verify the class is loaded (use `Java.choose` for instances)
- Check if method is inherited from parent class

### Overload Mismatch
- Use `get_method_signature` to get exact `frida_overload` strings
- Ensure types match exactly (e.g., `java.lang.String` not `String`)

### Native Hook Not Triggering
- Verify SO library name with `Process.enumerateModules()`
- Check JNI naming convention: `Java_package_class_method`
- Library may load lazily - hook after `System.loadLibrary`

### Accessing Private Fields
```javascript
// Use Java reflection through Frida
var field = TargetClass.class.getDeclaredField("privateField");
field.setAccessible(true);
var value = field.get(instance);
```
