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
 * HTTP 路由处理器 — Frida Hook 脚本自动生成
 *
 * 端点：
 *   GET /generate-frida-hook   — 生成指定方法的 Frida hook 脚本
 *   GET /generate-frida-trace  — 生成追踪类所有方法的 Frida 脚本
 *   GET /generate-frida-enum   — 生成枚举类实例/静态方法/字段的 Frida 脚本
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
     * 生成 Frida hook 脚本。
     *
     * 查询参数：
     *   class_name   (必填) 完全限定类名
     *   method_name  (可选) 方法名；缺失时按 hook_type=all_methods 处理
     *   hook_type    (可选) method_enter | method_exit | both | constructor | all_methods
     *                      默认：both
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

            String script;
            if ("all_methods".equalsIgnoreCase(hookTypeStr)) {
                script = generateAllMethodsHook(targetClass, className);
            } else if ("constructor".equalsIgnoreCase(hookTypeStr)) {
                script = generateConstructorHook(targetClass, className);
            } else {
                if (methodName == null || methodName.isEmpty()) {
                    JadxAIMCPPluginError.handleError(ctx, 400,
                        "method_name is required for hook_type: " + hookTypeStr, logger);
                    return;
                }
                script = generateMethodHook(targetClass, className, methodName, hookTypeStr);
            }

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("class_name", className);
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
     * 生成追踪类所有方法调用的 Frida 脚本。
     *
     * 查询参数：
     *   class_name          (必填)
     *   include_subclasses  (可选) true/false，默认 false
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

            String script = generateTraceScript(wrapper, targetClass, className, includeSubclasses);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("class_name", className);
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
     * 生成枚举类实例、调用静态方法、读取字段的 Frida 脚本。
     *
     * 查询参数：
     *   class_name (必填)
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

            String script = generateEnumScript(targetClass, className);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("class_name", className);
            response.put("script", script);
            ctx.json(response);

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                "Error generating Frida enum script: " + e.getMessage(), e, logger);
        }
    }

    // =========================================================================
    // 脚本生成逻辑
    // =========================================================================

    /** 为指定方法（可能有多个重载）生成 hook 脚本 */
    private String generateMethodHook(JavaClass cls, String className,
                                      String methodName, String hookType) {
        List<JavaMethod> overloads = new ArrayList<>();
        for (JavaMethod m : cls.getMethods()) {
            if (m.getName().equals(methodName)) {
                overloads.add(m);
            }
        }

        StringBuilder sb = new StringBuilder();
        sb.append(fridaHeader(className));

        if (overloads.isEmpty()) {
            // 方法未找到时生成注释占位符
            sb.append("    // WARNING: method '").append(methodName)
              .append("' not found in ").append(className).append("\n");
        } else {
            for (JavaMethod method : overloads) {
                appendMethodHookBlock(sb, className, method, hookType, "    ");
            }
        }

        sb.append("});\n");
        return sb.toString();
    }

    /** 为类中所有方法生成 hook */
    private String generateAllMethodsHook(JavaClass cls, String className) {
        StringBuilder sb = new StringBuilder();
        sb.append(fridaHeader(className));

        for (JavaMethod method : cls.getMethods()) {
            appendMethodHookBlock(sb, className, method, "both", "    ");
        }

        sb.append("});\n");
        return sb.toString();
    }

    /** 为所有构造方法生成 hook */
    private String generateConstructorHook(JavaClass cls, String className) {
        StringBuilder sb = new StringBuilder();
        sb.append(fridaHeader(className));

        boolean found = false;
        for (JavaMethod method : cls.getMethods()) {
            if (method.isConstructor()) {
                appendMethodHookBlock(sb, className, method, "both", "    ");
                found = true;
            }
        }

        if (!found) {
            sb.append("    // No constructors found in ").append(className).append("\n");
        }

        sb.append("});\n");
        return sb.toString();
    }

    /** 向 StringBuilder 中追加单个方法的 hook 代码块 */
    private void appendMethodHookBlock(StringBuilder sb, String className,
                                       JavaMethod method, String hookType, String indent) {
        String mName = method.isConstructor() ? "$init" : method.getName();
        List<ArgType> argTypes = getArgTypes(method);
        String overloadStr = FridaTypeConverter.toFridaOverloadString(argTypes);
        ArgType retType = getReturnType(method);
        String retTypeFrida = FridaTypeConverter.toFridaType(retType);

        // 参数名列表
        List<String> argNames = buildArgNames(argTypes);
        String argsDecl = String.join(", ", argNames);

        sb.append(indent).append("// Hook: ").append(mName);
        if (!argTypes.isEmpty()) {
            sb.append("(").append(overloadStr).append(")");
        }
        sb.append(" -> ").append(retTypeFrida).append("\n");

        // clazz.method[.overload(...)]
        sb.append(indent).append("clazz.").append(mName);
        if (argTypes.size() > 0) {
            sb.append(".overload(").append(overloadStr).append(")");
        }
        sb.append(".implementation = function(").append(argsDecl).append(") {\n");

        if ("method_enter".equalsIgnoreCase(hookType) || "both".equalsIgnoreCase(hookType)) {
            sb.append(indent).append("    console.log('[+] ").append(className)
              .append(".").append(mName).append(" called');\n");
            for (String arg : argNames) {
                sb.append(indent).append("    console.log('  arg ")
                  .append(arg).append(" = ' + ").append(arg).append(");\n");
            }
        }

        // 调用原始实现
        sb.append(indent).append("    var ret = this.").append(mName).append(".call(this");
        if (!argNames.isEmpty()) {
            sb.append(", ").append(String.join(", ", argNames));
        }
        sb.append(");\n");

        if ("method_exit".equalsIgnoreCase(hookType) || "both".equalsIgnoreCase(hookType)) {
            sb.append(indent).append("    console.log('[+] ").append(className)
              .append(".").append(mName).append(" returned: ' + ret);\n");
        }

        sb.append(indent).append("    return ret;\n");
        sb.append(indent).append("};\n\n");
    }

    /** 生成追踪脚本 */
    private String generateTraceScript(JadxWrapper wrapper, JavaClass cls,
                                       String className, boolean includeSubclasses) {
        StringBuilder sb = new StringBuilder();
        sb.append("'use strict';\n\n");
        sb.append("// Frida Trace Script — generated by JADX AI MCP\n");
        sb.append("// Target: ").append(className).append("\n\n");

        sb.append("Java.perform(function () {\n");
        sb.append("    try {\n");

        // 追踪主类
        appendTraceClass(sb, className, cls, "        ");

        // 追踪子类（包名前缀过滤）
        if (includeSubclasses) {
            for (JavaClass candidate : wrapper.getIncludedClassesWithInners()) {
                if (candidate.equals(cls)) continue;
                try {
                    String superClass = JadxApiAdapter.getSuperClass(candidate);
                    if (className.equals(superClass)) {
                        String subName = candidate.getFullName();
                        sb.append("\n        // Subclass: ").append(subName).append("\n");
                        appendTraceClass(sb, subName, candidate, "        ");
                    }
                } catch (Exception ignored) {
                    // 跳过无法读取超类信息的类
                }
            }
        }

        sb.append("    } catch (e) {\n");
        sb.append("        console.error('[-] Trace setup error: ' + e.message);\n");
        sb.append("    }\n");
        sb.append("});\n");
        return sb.toString();
    }

    private void appendTraceClass(StringBuilder sb, String className, JavaClass cls, String indent) {
        sb.append(indent).append("var clazz = Java.use('").append(className).append("');\n");
        for (JavaMethod method : cls.getMethods()) {
            String mName = method.isConstructor() ? "$init" : method.getName();
            List<ArgType> argTypes = getArgTypes(method);
            String overloadStr = FridaTypeConverter.toFridaOverloadString(argTypes);
            List<String> argNames = buildArgNames(argTypes);
            String argsDecl = String.join(", ", argNames);

            sb.append(indent).append("clazz.").append(mName);
            if (!argTypes.isEmpty()) {
                sb.append(".overload(").append(overloadStr).append(")");
            }
            sb.append(".implementation = function(").append(argsDecl).append(") {\n");
            sb.append(indent).append("    var tag = '[TRACE] ").append(className)
              .append(".").append(mName).append("';\n");
            sb.append(indent).append("    console.log(tag + ' enter');");

            for (int i = 0; i < argNames.size(); i++) {
                sb.append("\n").append(indent).append("    console.log(tag + '  arg")
                  .append(i).append("=' + ").append(argNames.get(i)).append(");");
            }
            sb.append("\n");

            sb.append(indent).append("    var ret = this.").append(mName).append(".call(this");
            if (!argNames.isEmpty()) {
                sb.append(", ").append(String.join(", ", argNames));
            }
            sb.append(");\n");
            sb.append(indent).append("    console.log(tag + ' exit => ' + ret);\n");
            sb.append(indent).append("    return ret;\n");
            sb.append(indent).append("};\n");
        }
    }

    /** 生成枚举/实例枚举脚本 */
    private String generateEnumScript(JavaClass cls, String className) {
        StringBuilder sb = new StringBuilder();
        sb.append("'use strict';\n\n");
        sb.append("// Frida Enum Script — generated by JADX AI MCP\n");
        sb.append("// Target: ").append(className).append("\n\n");

        sb.append("Java.perform(function () {\n");
        sb.append("    try {\n");
        sb.append("        var clazz = Java.use('").append(className).append("');\n\n");

        // 枚举静态字段（enum 常量 + 普通 static 字段）
        sb.append("        // --- Static Fields ---\n");
        for (JavaField field : cls.getFields()) {
            try {
                if (field.getFieldNode().getAccessFlags().isStatic()) {
                    sb.append("        try {\n");
                    sb.append("            console.log('[+] ").append(field.getName())
                      .append(" = ' + clazz.").append(field.getName()).append(".value);\n");
                    sb.append("        } catch (e) {\n");
                    sb.append("            console.log('[-] Cannot read ").append(field.getName())
                      .append(": ' + e.message);\n");
                    sb.append("        }\n");
                }
            } catch (Exception ignored) {
                // 字段访问异常时跳过
            }
        }

        // 枚举静态方法
        sb.append("\n        // --- Static Methods ---\n");
        for (JavaMethod method : cls.getMethods()) {
            try {
                MethodNode mn = method.getMethodNode();
                if (mn.getAccessFlags().isStatic() && !method.isConstructor()) {
                    List<ArgType> argTypes = getArgTypes(method);
                    String overloadStr = FridaTypeConverter.toFridaOverloadString(argTypes);
                    String call = argTypes.isEmpty()
                        ? "clazz." + method.getName() + "()"
                        : "/* clazz." + method.getName() + ".overload(" + overloadStr + ")(...) */";

                    sb.append("        try {\n");
                    sb.append("            var result_").append(sanitize(method.getName()))
                      .append(" = ").append(call).append(";\n");
                    sb.append("            console.log('[+] ").append(method.getName())
                      .append("() = ' + result_").append(sanitize(method.getName())).append(");\n");
                    sb.append("        } catch (e) {\n");
                    sb.append("            console.log('[-] ").append(method.getName())
                      .append("() error: ' + e.message);\n");
                    sb.append("        }\n");
                }
            } catch (Exception ignored) {
                // 跳过无法读取访问标志的方法
            }
        }

        // 尝试枚举实例（如果是 enum 类型）
        sb.append("\n        // --- Enum Instances (if enum class) ---\n");
        sb.append("        try {\n");
        sb.append("            var enumValues = clazz.values();\n");
        sb.append("            for (var i = 0; i < enumValues.length; i++) {\n");
        sb.append("                console.log('[+] enum[' + i + '] = ' + enumValues[i]);\n");
        sb.append("            }\n");
        sb.append("        } catch (e) {\n");
        sb.append("            console.log('[-] Not an enum or values() failed: ' + e.message);\n");
        sb.append("        }\n\n");

        // 实例方法通过 Java.choose 枚举
        sb.append("        // --- Enumerate Live Instances (Java.choose) ---\n");
        sb.append("        Java.choose('").append(className).append("', {\n");
        sb.append("            onMatch: function (instance) {\n");
        sb.append("                console.log('[+] Instance: ' + instance);\n");
        // 实例字段读取
        for (JavaField field : cls.getFields()) {
            try {
                if (!field.getFieldNode().getAccessFlags().isStatic()) {
                    sb.append("                try { console.log('    .").append(field.getName())
                      .append(" = ' + instance.").append(field.getName()).append(".value); } catch(e){}\n");
                }
            } catch (Exception ignored) {
                // 跳过
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
    // 工具方法
    // =========================================================================

    private String fridaHeader(String className) {
        return "'use strict';\n\n" +
               "// Frida Hook Script — generated by JADX AI MCP\n" +
               "// Target: " + className + "\n\n" +
               "Java.perform(function () {\n" +
               "    try {\n" +
               "        var clazz = Java.use('" + className + "');\n\n";
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
            // 无法获取参数类型时返回空列表
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

    /** 将方法名转换为合法 JS 变量名（替换非法字符） */
    private String sanitize(String name) {
        return name.replaceAll("[^a-zA-Z0-9_$]", "_");
    }
}
