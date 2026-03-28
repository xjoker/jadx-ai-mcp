package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.JavaField;
import jadx.api.JavaMethod;
import jadx.core.dex.instructions.args.ArgType;
import jadx.core.dex.nodes.MethodNode;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.zin.jadxaimcp.utils.FridaTypeConverter;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.JadxApiAdapter;

/**
 * HTTP route handler — Frida hook script auto-generation
 *
 * Endpoints:
 *   GET /generate-frida-hook   — Generate a Frida hook script for a specific method
 *   GET /generate-frida-trace  — Generate a Frida script to trace all methods of a class
 *   GET /generate-frida-enum   — Generate a Frida script to enumerate enum instances, static methods, and fields
 */
public class FridaRoutes {
    private static final Logger logger = LoggerFactory.getLogger(FridaRoutes.class);
    private final MainWindow mainWindow;

    public FridaRoutes(MainWindow mainWindow) {
        this.mainWindow = mainWindow;
    }

    // -------------------------------------------------------------------------
    // GET /generate-frida-hook
    // -------------------------------------------------------------------------

    /**
     * Generate a Frida hook script.
     *
     * Query parameters:
     *   class_name   (required) Fully qualified class name
     *   method_name  (optional) Method name; defaults to hook_type=all_methods if omitted
     *   hook_type    (optional) method_enter | method_exit | both | constructor | all_methods
     *                      Default: both
     */
    public void handleGenerateFridaHook(Context ctx) {
        String className = ctx.queryParam("class_name");
        if (className == null || className.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter: class_name", logger);
            return;
        }

        String methodName = ctx.queryParam("method_name");
        String hookTypeStr = ctx.queryParam("hook_type");
        if (hookTypeStr == null || hookTypeStr.isEmpty()) {
            hookTypeStr = (methodName == null || methodName.isEmpty()) ? "all_methods" : "both";
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                JadxAIMCPPluginError.handleError(ctx, 500, "JadxWrapper not initialized", logger);
                return;
            }

            JavaClass targetClass = findClass(wrapper, className);
            if (targetClass == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Class not found: " + className, logger);
                return;
            }

            String rawClassName = JadxApiAdapter.getClassRawName(targetClass);
            if (rawClassName == null) {
                rawClassName = className;
            }
            String aliasClassName = JadxApiAdapter.getClassAliasName(targetClass);
            if (aliasClassName == null) {
                aliasClassName = className;
            }

            String script;
            if ("all_methods".equalsIgnoreCase(hookTypeStr)) {
                script = generateAllMethodsHook(targetClass, rawClassName, aliasClassName);
            } else if ("constructor".equalsIgnoreCase(hookTypeStr)) {
                script = generateConstructorHook(targetClass, rawClassName, aliasClassName);
            } else {
                if (methodName == null || methodName.isEmpty()) {
                    JadxAIMCPPluginError.handleError(ctx, 400,
                        "method_name is required for hook_type: " + hookTypeStr, logger);
                    return;
                }
                script = generateMethodHook(targetClass, rawClassName, aliasClassName, methodName, hookTypeStr);
            }

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("class_name", aliasClassName);
            response.put("raw_class_name", rawClassName);
            response.put("method_name", methodName != null ? methodName : "(all)");
            response.put("hook_type", hookTypeStr);
            response.put("script", script);
            ctx.json(response);

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                "Error generating Frida hook: " + e.getMessage(), e, logger);
        }
    }

    // -------------------------------------------------------------------------
    // GET /generate-frida-trace
    // -------------------------------------------------------------------------

    /**
     * Generate a Frida script to trace all method calls of a class.
     *
     * Query parameters:
     *   class_name          (required)
     *   include_subclasses  (optional) true/false, default false
     */
    public void handleGenerateFridaTrace(Context ctx) {
        String className = ctx.queryParam("class_name");
        if (className == null || className.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter: class_name", logger);
            return;
        }

        String includeSubStr = ctx.queryParam("include_subclasses");
        boolean includeSubclasses = "true".equalsIgnoreCase(includeSubStr);

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                JadxAIMCPPluginError.handleError(ctx, 500, "JadxWrapper not initialized", logger);
                return;
            }

            JavaClass targetClass = findClass(wrapper, className);
            if (targetClass == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Class not found: " + className, logger);
                return;
            }

            String rawClassName = JadxApiAdapter.getClassRawName(targetClass);
            if (rawClassName == null) {
                rawClassName = className;
            }
            String aliasClassName = JadxApiAdapter.getClassAliasName(targetClass);
            if (aliasClassName == null) {
                aliasClassName = className;
            }

            String script = generateTraceScript(wrapper, targetClass, rawClassName, aliasClassName, includeSubclasses);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("class_name", aliasClassName);
            response.put("raw_class_name", rawClassName);
            response.put("include_subclasses", includeSubclasses);
            response.put("script", script);
            ctx.json(response);

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                "Error generating Frida trace: " + e.getMessage(), e, logger);
        }
    }

    // -------------------------------------------------------------------------
    // GET /generate-frida-enum
    // -------------------------------------------------------------------------

    /**
     * Generate a Frida script to enumerate class instances, call static methods, and read fields.
     *
     * Query parameters:
     *   class_name (required)
     */
    public void handleGenerateFridaEnum(Context ctx) {
        String className = ctx.queryParam("class_name");
        if (className == null || className.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter: class_name", logger);
            return;
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                JadxAIMCPPluginError.handleError(ctx, 500, "JadxWrapper not initialized", logger);
                return;
            }

            JavaClass targetClass = findClass(wrapper, className);
            if (targetClass == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Class not found: " + className, logger);
                return;
            }

            String rawClassName = JadxApiAdapter.getClassRawName(targetClass);
            if (rawClassName == null) {
                rawClassName = className;
            }
            String aliasClassName = JadxApiAdapter.getClassAliasName(targetClass);
            if (aliasClassName == null) {
                aliasClassName = className;
            }

            String script = generateEnumScript(targetClass, rawClassName, aliasClassName);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("class_name", aliasClassName);
            response.put("raw_class_name", rawClassName);
            response.put("script", script);
            ctx.json(response);

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                "Error generating Frida enum script: " + e.getMessage(), e, logger);
        }
    }

    // =========================================================================
    // Script generation logic
    // =========================================================================

    /** Generate a hook script for the specified method (handles overloads) */
    private String generateMethodHook(JavaClass cls, String rawClassName, String aliasClassName,
                                      String methodName, String hookType) {
        List<JavaMethod> overloads = new ArrayList<>();
        for (JavaMethod m : cls.getMethods()) {
            // Match by alias name or raw name
            String rawMName = JadxApiAdapter.getMethodRawName(m);
            String aliasMName = JadxApiAdapter.getMethodAliasName(m);
            if (methodName.equals(aliasMName) || methodName.equals(rawMName)) {
                overloads.add(m);
            }
        }

        StringBuilder sb = new StringBuilder();
        sb.append(fridaHeader(rawClassName, aliasClassName));

        if (overloads.isEmpty()) {
            // Generate a comment placeholder when the method is not found
            sb.append("    // WARNING: method '").append(methodName)
              .append("' not found in ").append(rawClassName).append("\n");
        } else {
            for (JavaMethod method : overloads) {
                appendMethodHookBlock(sb, rawClassName, method, hookType, "    ");
            }
        }

        sb.append("});\n");
        return sb.toString();
    }

    /** Generate hooks for all methods in the class */
    private String generateAllMethodsHook(JavaClass cls, String rawClassName, String aliasClassName) {
        StringBuilder sb = new StringBuilder();
        sb.append(fridaHeader(rawClassName, aliasClassName));

        for (JavaMethod method : cls.getMethods()) {
            appendMethodHookBlock(sb, rawClassName, method, "both", "    ");
        }

        sb.append("});\n");
        return sb.toString();
    }

    /** Generate hooks for all constructors */
    private String generateConstructorHook(JavaClass cls, String rawClassName, String aliasClassName) {
        StringBuilder sb = new StringBuilder();
        sb.append(fridaHeader(rawClassName, aliasClassName));

        boolean found = false;
        for (JavaMethod method : cls.getMethods()) {
            if (method.isConstructor()) {
                appendMethodHookBlock(sb, rawClassName, method, "both", "    ");
                found = true;
            }
        }

        if (!found) {
            sb.append("    // No constructors found in ").append(rawClassName).append("\n");
        }

        sb.append("});\n");
        return sb.toString();
    }

    /** Append a hook code block for a single method to the StringBuilder */
    private void appendMethodHookBlock(StringBuilder sb, String rawClassName,
                                       JavaMethod method, String hookType, String indent) {
        // Use raw name for actual hook; constructor maps to $init in Frida
        String rawMName = method.isConstructor() ? "$init" : JadxApiAdapter.getMethodRawName(method);
        if (rawMName == null) {
            rawMName = method.isConstructor() ? "$init" : JadxApiAdapter.getMethodAliasName(method);
        }
        String aliasMName = method.isConstructor() ? "$init" : JadxApiAdapter.getMethodAliasName(method);
        if (aliasMName == null) {
            aliasMName = rawMName;
        }

        List<ArgType> argTypes = getArgTypes(method);
        String overloadStr = FridaTypeConverter.toFridaOverloadString(argTypes);
        ArgType retType = getReturnType(method);
        String retTypeFrida = FridaTypeConverter.toFridaType(retType);

        // Build argument name list
        List<String> argNames = buildArgNames(argTypes);
        String argsDecl = String.join(", ", argNames);

        // Comment shows alias name for readability
        sb.append(indent).append("// Hook: ").append(rawMName);
        if (!rawMName.equals(aliasMName)) {
            sb.append(" /* alias: ").append(aliasMName).append(" */");
        }
        if (!argTypes.isEmpty()) {
            sb.append("(").append(overloadStr).append(")");
        }
        sb.append(" -> ").append(retTypeFrida).append("\n");

        // clazz.method[.overload(...)] call chain — use raw name
        sb.append(indent).append("clazz.").append(rawMName);
        if (argTypes.size() > 0) {
            sb.append(".overload(").append(overloadStr).append(")");
        }
        sb.append(".implementation = function(").append(argsDecl).append(") {\n");

        if ("method_enter".equalsIgnoreCase(hookType) || "both".equalsIgnoreCase(hookType)) {
            sb.append(indent).append("    console.log('[+] ").append(rawClassName)
              .append(".").append(rawMName).append(" called');\n");
            for (String arg : argNames) {
                sb.append(indent).append("    console.log('  arg ")
                  .append(arg).append(" = ' + ").append(arg).append(");\n");
            }
        }

        // Call the original implementation — use raw name
        sb.append(indent).append("    var ret = this.").append(rawMName).append(".call(this");
        if (!argNames.isEmpty()) {
            sb.append(", ").append(String.join(", ", argNames));
        }
        sb.append(");\n");

        if ("method_exit".equalsIgnoreCase(hookType) || "both".equalsIgnoreCase(hookType)) {
            sb.append(indent).append("    console.log('[+] ").append(rawClassName)
              .append(".").append(rawMName).append(" returned: ' + ret);\n");
        }

        sb.append(indent).append("    return ret;\n");
        sb.append(indent).append("};\n\n");
    }

    /** Generate trace script */
    private String generateTraceScript(JadxWrapper wrapper, JavaClass cls,
                                       String rawClassName, String aliasClassName,
                                       boolean includeSubclasses) {
        StringBuilder sb = new StringBuilder();
        sb.append("'use strict';\n\n");
        sb.append("// Frida Trace Script — generated by JADX AI MCP\n");
        sb.append("// Target: ").append(rawClassName);
        if (!rawClassName.equals(aliasClassName)) {
            sb.append(" /* alias: ").append(aliasClassName).append(" */");
        }
        sb.append("\n\n");

        sb.append("Java.perform(function () {\n");
        sb.append("    try {\n");

        // Trace the main class — use raw name for Java.use()
        appendTraceClass(sb, rawClassName, cls, "        ");

        // Trace subclasses (filtered by superclass match)
        if (includeSubclasses) {
            for (JavaClass candidate : wrapper.getIncludedClassesWithInners()) {
                if (candidate.equals(cls)) continue;
                try {
                    String superClass = JadxApiAdapter.getSuperClass(candidate);
                    // Match superclass against both raw and alias name of current class
                    if (rawClassName.equals(superClass) || aliasClassName.equals(superClass)) {
                        String subRawName = JadxApiAdapter.getClassRawName(candidate);
                        if (subRawName == null) {
                            subRawName = candidate.getFullName();
                        }
                        String subAliasName = JadxApiAdapter.getClassAliasName(candidate);
                        sb.append("\n        // Subclass: ").append(subRawName);
                        if (!subRawName.equals(subAliasName) && subAliasName != null) {
                            sb.append(" /* alias: ").append(subAliasName).append(" */");
                        }
                        sb.append("\n");
                        appendTraceClass(sb, subRawName, candidate, "        ");
                    }
                } catch (Exception ignored) {
                    // Skip classes whose superclass info cannot be read
                }
            }
        }

        sb.append("    } catch (e) {\n");
        sb.append("        console.error('[-] Trace setup error: ' + e.message);\n");
        sb.append("    }\n");
        sb.append("});\n");
        return sb.toString();
    }

    private void appendTraceClass(StringBuilder sb, String rawClassName, JavaClass cls, String indent) {
        // Use raw class name in Java.use() — Frida hooks JVM runtime names
        sb.append(indent).append("var clazz = Java.use('").append(rawClassName).append("');\n");
        for (JavaMethod method : cls.getMethods()) {
            // Use raw method name for actual hook
            String rawMName = method.isConstructor() ? "$init" : JadxApiAdapter.getMethodRawName(method);
            if (rawMName == null) {
                rawMName = method.isConstructor() ? "$init" : JadxApiAdapter.getMethodAliasName(method);
            }
            String aliasMName = method.isConstructor() ? "$init" : JadxApiAdapter.getMethodAliasName(method);

            List<ArgType> argTypes = getArgTypes(method);
            String overloadStr = FridaTypeConverter.toFridaOverloadString(argTypes);
            List<String> argNames = buildArgNames(argTypes);
            String argsDecl = String.join(", ", argNames);

            sb.append(indent).append("clazz.").append(rawMName);
            if (!argTypes.isEmpty()) {
                sb.append(".overload(").append(overloadStr).append(")");
            }
            sb.append(".implementation = function(").append(argsDecl).append(") {\n");
            sb.append(indent).append("    var tag = '[TRACE] ").append(rawClassName)
              .append(".").append(rawMName);
            if (aliasMName != null && !rawMName.equals(aliasMName)) {
                sb.append(" /* alias: ").append(aliasMName).append(" */");
            }
            sb.append("';\n");
            sb.append(indent).append("    console.log(tag + ' enter');");

            for (int i = 0; i < argNames.size(); i++) {
                sb.append("\n").append(indent).append("    console.log(tag + '  arg")
                  .append(i).append("=' + ").append(argNames.get(i)).append(");");
            }
            sb.append("\n");

            sb.append(indent).append("    var ret = this.").append(rawMName).append(".call(this");
            if (!argNames.isEmpty()) {
                sb.append(", ").append(String.join(", ", argNames));
            }
            sb.append(");\n");
            sb.append(indent).append("    console.log(tag + ' exit => ' + ret);\n");
            sb.append(indent).append("    return ret;\n");
            sb.append(indent).append("};\n");
        }
    }

    /** Generate enum/instance enumeration script */
    private String generateEnumScript(JavaClass cls, String rawClassName, String aliasClassName) {
        StringBuilder sb = new StringBuilder();
        sb.append("'use strict';\n\n");
        sb.append("// Frida Enum Script — generated by JADX AI MCP\n");
        sb.append("// Target: ").append(rawClassName);
        if (!rawClassName.equals(aliasClassName)) {
            sb.append(" /* alias: ").append(aliasClassName).append(" */");
        }
        sb.append("\n\n");

        sb.append("Java.perform(function () {\n");
        sb.append("    try {\n");
        // Use raw class name in Java.use() — Frida hooks JVM runtime names
        sb.append("        var clazz = Java.use('").append(rawClassName).append("');\n\n");

        // Enumerate static fields (enum constants + regular static fields)
        sb.append("        // --- Static Fields ---\n");
        for (JavaField field : cls.getFields()) {
            try {
                if (field.getFieldNode().getAccessFlags().isStatic()) {
                    String rawFName = JadxApiAdapter.getFieldRawName(field);
                    if (rawFName == null) {
                        rawFName = JadxApiAdapter.getFieldAliasName(field);
                    }
                    String aliasFName = JadxApiAdapter.getFieldAliasName(field);
                    sb.append("        try {\n");
                    // Use raw field name; show alias in comment if different
                    if (aliasFName != null && !rawFName.equals(aliasFName)) {
                        sb.append("            // alias: ").append(aliasFName).append("\n");
                    }
                    sb.append("            console.log('[+] ").append(rawFName)
                      .append(" = ' + clazz.").append(rawFName).append(".value);\n");
                    sb.append("        } catch (e) {\n");
                    sb.append("            console.log('[-] Cannot read ").append(rawFName)
                      .append(": ' + e.message);\n");
                    sb.append("        }\n");
                }
            } catch (Exception ignored) {
                // Skip fields that cannot be accessed
            }
        }

        // Enumerate static methods
        sb.append("\n        // --- Static Methods ---\n");
        for (JavaMethod method : cls.getMethods()) {
            try {
                MethodNode mn = method.getMethodNode();
                if (mn.getAccessFlags().isStatic() && !method.isConstructor()) {
                    String rawMName = JadxApiAdapter.getMethodRawName(method);
                    if (rawMName == null) {
                        rawMName = JadxApiAdapter.getMethodAliasName(method);
                    }
                    String aliasMName = JadxApiAdapter.getMethodAliasName(method);
                    List<ArgType> argTypes = getArgTypes(method);
                    String overloadStr = FridaTypeConverter.toFridaOverloadString(argTypes);
                    // Use raw method name in the actual call
                    String call = argTypes.isEmpty()
                        ? "clazz." + rawMName + "()"
                        : "/* clazz." + rawMName + ".overload(" + overloadStr + ")(...) */";

                    sb.append("        try {\n");
                    // Show alias in comment if different
                    if (aliasMName != null && !rawMName.equals(aliasMName)) {
                        sb.append("            // alias: ").append(aliasMName).append("\n");
                    }
                    sb.append("            var result_").append(sanitize(rawMName))
                      .append(" = ").append(call).append(";\n");
                    sb.append("            console.log('[+] ").append(rawMName)
                      .append("() = ' + result_").append(sanitize(rawMName)).append(");\n");
                    sb.append("        } catch (e) {\n");
                    sb.append("            console.log('[-] ").append(rawMName)
                      .append("() error: ' + e.message);\n");
                    sb.append("        }\n");
                }
            } catch (Exception ignored) {
                // Skip methods whose access flags cannot be read
            }
        }

        // Try to enumerate instances (if the class is an enum)
        sb.append("\n        // --- Enum Instances (if enum class) ---\n");
        sb.append("        try {\n");
        sb.append("            var enumValues = clazz.values();\n");
        sb.append("            for (var i = 0; i < enumValues.length; i++) {\n");
        sb.append("                console.log('[+] enum[' + i + '] = ' + enumValues[i]);\n");
        sb.append("            }\n");
        sb.append("        } catch (e) {\n");
        sb.append("            console.log('[-] Not an enum or values() failed: ' + e.message);\n");
        sb.append("        }\n\n");

        // Enumerate live instances via Java.choose — use raw class name
        sb.append("        // --- Enumerate Live Instances (Java.choose) ---\n");
        sb.append("        Java.choose('").append(rawClassName).append("', {\n");
        sb.append("            onMatch: function (instance) {\n");
        sb.append("                console.log('[+] Instance: ' + instance);\n");
        // Read instance fields — use raw field names
        for (JavaField field : cls.getFields()) {
            try {
                if (!field.getFieldNode().getAccessFlags().isStatic()) {
                    String rawFName = JadxApiAdapter.getFieldRawName(field);
                    if (rawFName == null) {
                        rawFName = JadxApiAdapter.getFieldAliasName(field);
                    }
                    String aliasFName = JadxApiAdapter.getFieldAliasName(field);
                    String aliasComment = (aliasFName != null && !rawFName.equals(aliasFName))
                        ? " /* alias: " + aliasFName + " */" : "";
                    sb.append("                try { console.log('    .").append(rawFName)
                      .append(aliasComment)
                      .append(" = ' + instance.").append(rawFName).append(".value); } catch(e){}\n");
                }
            } catch (Exception ignored) {
                // Skip
            }
        }
        sb.append("            },\n");
        sb.append("            onComplete: function () {\n");
        sb.append("                console.log('[+] Instance enumeration complete');\n");
        sb.append("            }\n");
        sb.append("        });\n\n");

        sb.append("    } catch (e) {\n");
        sb.append("        console.error('[-] Enum script error: ' + e.message);\n");
        sb.append("    }\n");
        sb.append("});\n");
        return sb.toString();
    }

    // =========================================================================
    // Utility methods
    // =========================================================================

    private String fridaHeader(String rawClassName, String aliasClassName) {
        String aliasComment = (aliasClassName != null && !rawClassName.equals(aliasClassName))
            ? " /* alias: " + aliasClassName + " */" : "";
        return "'use strict';\n\n" +
               "// Frida Hook Script — generated by JADX AI MCP\n" +
               "// Target: " + rawClassName + aliasComment + "\n\n" +
               "Java.perform(function () {\n" +
               "    try {\n" +
               // Use raw class name in Java.use() — Frida hooks JVM runtime names
               "        var clazz = Java.use('" + rawClassName + "');\n\n";
    }

    private JavaClass findClass(JadxWrapper wrapper, String className) {
        for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
            if (JadxApiAdapter.matchesClassName(cls, className)) {
                return cls;
            }
        }
        return null;
    }

    private List<ArgType> getArgTypes(JavaMethod method) {
        List<ArgType> result = new ArrayList<>();
        try {
            MethodNode mn = method.getMethodNode();
            for (ArgType t : mn.getMethodInfo().getArgumentsTypes()) {
                result.add(t);
            }
        } catch (Exception e) {
            // Return empty list if argument types cannot be retrieved
        }
        return result;
    }

    private ArgType getReturnType(JavaMethod method) {
        try {
            return method.getMethodNode().getMethodInfo().getReturnType();
        } catch (Exception e) {
            return null;
        }
    }

    private List<String> buildArgNames(List<ArgType> types) {
        List<String> names = new ArrayList<>();
        for (int i = 0; i < types.size(); i++) {
            names.add("arg" + i);
        }
        return names;
    }

    private String packageOf(String className) {
        int dot = className.lastIndexOf('.');
        return dot > 0 ? className.substring(0, dot) : "";
    }

    /** Convert a method name to a valid JS identifier (replace illegal characters) */
    private String sanitize(String name) {
        return name.replaceAll("[^a-zA-Z0-9_$]", "_");
    }
}
