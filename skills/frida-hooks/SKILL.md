---
name: frida-hooks
description: Generate Frida hook scripts for Android/Java runtime instrumentation. Use when user asks to "hook", "intercept", "instrument", "trace method", "bypass", "frida script", "runtime analysis", "dynamic analysis", or wants to monitor/modify app behavior at runtime.
---

# Frida Hook Script Generation

Generate production-ready Frida scripts for Android/Java method hooking using JADX decompiled code analysis.

## Key MCP Tools

| Tool | Purpose | When to Use |
|:-----|:--------|:------------|
| `get_methods_of_class` | List all methods with signatures | Find target methods to hook |
| `get_method_signature` | Get exact parameter/return types | Build correct overload syntax |
| `get_fields_of_class` | List class fields | Access/modify instance data |
| `get_class_source` | Full decompiled source | Understand method logic |

## Java to Frida Type Mapping

| Java Type | Frida Type |
|:----------|:-----------|
| `int` | `'int'` |
| `boolean` | `'boolean'` |
| `byte` | `'byte'` |
| `char` | `'char'` |
| `short` | `'short'` |
| `long` | `'long'` |
| `float` | `'float'` |
| `double` | `'double'` |
| `String` | `'java.lang.String'` |
| `int[]` | `'[I'` |
| `byte[]` | `'[B'` |
| `Object[]` | `'[Ljava.lang.Object;'` |
| `List<T>` | `'java.util.List'` |
| `Context` | `'android.content.Context'` |

## Hook Templates

### Basic Instance Method

```javascript
Java.perform(function() {
    var TargetClass = Java.use('com.example.TargetClass');

    TargetClass.targetMethod.implementation = function(arg1, arg2) {
        console.log('[*] targetMethod called');
        console.log('    arg1: ' + arg1);
        console.log('    arg2: ' + arg2);

        var result = this.targetMethod(arg1, arg2);
        console.log('    result: ' + result);
        return result;
    };
});
```

### Overloaded Method

```javascript
Java.perform(function() {
    var TargetClass = Java.use('com.example.TargetClass');

    // Hook specific overload
    TargetClass.process.overload('java.lang.String', 'int').implementation = function(str, num) {
        console.log('[*] process(String, int) called');
        return this.process(str, num);
    };

    // Hook all overloads
    var overloads = TargetClass.process.overloads;
    overloads.forEach(function(overload) {
        overload.implementation = function() {
            console.log('[*] process called with ' + arguments.length + ' args');
            return this.process.apply(this, arguments);
        };
    });
});
```

### Static Method

```javascript
Java.perform(function() {
    var TargetClass = Java.use('com.example.TargetClass');

    TargetClass.staticMethod.implementation = function(arg) {
        console.log('[*] staticMethod called: ' + arg);
        // Modify argument
        var result = this.staticMethod('modified_' + arg);
        return result;
    };
});
```

### Constructor

```javascript
Java.perform(function() {
    var TargetClass = Java.use('com.example.TargetClass');

    TargetClass.$init.overload('java.lang.String').implementation = function(arg) {
        console.log('[*] Constructor called: ' + arg);
        this.$init(arg);
    };
});
```

### Native Method

```javascript
Interceptor.attach(Module.findExportByName('libnative.so', 'native_function'), {
    onEnter: function(args) {
        console.log('[*] native_function called');
        console.log('    arg0: ' + args[0]);
        console.log('    arg1: ' + Memory.readUtf8String(args[1]));
    },
    onLeave: function(retval) {
        console.log('    retval: ' + retval);
    }
});
```

### Field Access

```javascript
Java.perform(function() {
    var TargetClass = Java.use('com.example.TargetClass');

    TargetClass.someMethod.implementation = function() {
        // Read field
        var fieldValue = this.secretField.value;
        console.log('[*] secretField: ' + fieldValue);

        // Modify field
        this.secretField.value = 'new_value';

        return this.someMethod();
    };
});
```

## Generation Workflow

1. **Identify Target Class**
   - Use `get_class_source` to understand the class structure
   - Identify the method(s) to hook

2. **Get Method Signature**
   - Use `get_method_signature` for exact parameter types
   - Note return type and modifiers (static, native)

3. **Check for Overloads**
   - Use `get_methods_of_class` to find all method variants
   - If overloaded, use `.overload()` with exact types

4. **Map Types**
   - Convert Java types to Frida type strings
   - Use full package names for objects

5. **Generate Script**
   - Select appropriate template
   - Fill in class name, method name, types
   - Add logging for arguments and return value

## Common Pitfalls

| Problem | Cause | Solution |
|:--------|:------|:---------|
| `Method not found` | Missing overload specification | Use `.overload('type1', 'type2')` |
| `Cannot find class` | Inner class naming | Use `OuterClass$InnerClass` |
| `Type mismatch` | Wrong array syntax | Use `'[B'` for `byte[]`, `'[Ljava.lang.String;'` for `String[]` |
| `null reference` | Hook before class loaded | Wrap in `Java.performNow` or delay hook |
| `Native crash` | Wrong argument parsing | Check native function signature with IDA/Ghidra |

## Best Practices

1. **Always log before calling original** - Helps debug crashes
2. **Use try-catch** - Prevent script termination on errors
3. **Check for null** - Arguments may be null
4. **Use `Java.scheduleOnMainThread`** - For UI-related hooks
5. **Enumerate loaded classes first** - When class name is obfuscated
