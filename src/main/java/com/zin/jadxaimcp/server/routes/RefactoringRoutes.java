package com.zin.jadxaimcp.server.routes;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.JavaField;
import jadx.api.JavaMethod;
import jadx.api.metadata.ICodeNodeRef;
import jadx.api.metadata.annotations.VarNode;
import jadx.api.plugins.events.types.NodeRenamedByUser;
import jadx.core.dex.nodes.MethodNode;
import jadx.core.dex.instructions.args.SSAVar;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.JadxApiAdapter;

public class RefactoringRoutes {
    private static final Logger logger = LoggerFactory.getLogger(RefactoringRoutes.class);
    private static final Gson GSON = new Gson();
    private final MainWindow mainWindow;
    
    public RefactoringRoutes(MainWindow mainWindow) {
        this.mainWindow = mainWindow;
    }

    /**
     * @return void
     * @param Context
     * 
     * This routing method handle the /rename-class mcp tool call's http request, After validating the 
     * required http params, it tries to find the class which has to be renamed. If it is found
     * then it renames it using NodeRenamedByUser class' events methods 'setRenameNode' and 'setResetName'.
     * Then it sends these events using MainWindows's send() method.
     */
    public void handleRenameClass(Context ctx) {
        JsonObject requestBody = parseJsonBody(ctx);
        if (requestBody == null) return;

        String className = getBodyString(requestBody, "class_name");
        String newName = getBodyString(requestBody, "new_name");

        if (validateParams(ctx, className, newName)) return;

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            
            // Initialize cache if needed
            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }
            
            // Use cache for fast lookup
            Map<String, JavaClass> classMap = ClassCacheManager.getCache();
            JavaClass cls = ClassCacheManager.findClass(classMap, className);
            
            if (cls != null) {
                ICodeNodeRef nodeRef = cls.getCodeNodeRef();
                NodeRenamedByUser event = new NodeRenamedByUser(nodeRef, cls.getName(), newName);
                event.setRenameNode(nodeRef);
                event.setResetName(newName.isEmpty());
                mainWindow.events().send(event);

                // Invalidate decompiled code cache — renamed class code is stale
                invalidateCodeForClass(cls, className);

                logger.info("Renaming Class {} to {}", cls.getName(), newName);
                ctx.json(Map.of("result", "Renamed Class " + cls.getName() + " to " + newName));
                return;
            }

            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error while trying to rename the class: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @param
     * @return
     * 
     * This routing method handle the /rename-method mcp tool call's http request, After validating the 
     * required http params, it tries to find the class whose method has to be renamed. If it is found
     * then it renames it using NodeRenamedByUser class' events methods 'setRenameNode' and 'setResetName'.
     * Then it sends these events using MainWindows's send() method.
     * 
     */
    public void handleRenameMethod(Context ctx) {
        JsonObject requestBody = parseJsonBody(ctx);
        if (requestBody == null) return;

        String methodName = getBodyString(requestBody, "method_name");
        String newName = getBodyString(requestBody, "new_name");
        String className = getBodyString(requestBody, "class_name");
        // Optional JVM short-descriptor (e.g. "foo(I)V") to pinpoint a specific overload
        String methodSignature = getBodyString(requestBody, "method_signature");
        if (methodSignature != null && methodSignature.isBlank()) {
            methodSignature = null;
        }

        if (validateParams(ctx, methodName, newName)) return;

        // Strip method signature if present in the method_name itself (legacy usage)
        if (methodName.contains("(")) {
            methodName = methodName.substring(0, methodName.indexOf('('));
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();

            // Initialize cache if needed
            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }

            // Extract class name from method_name (format: com.example.Class:methodName or com.example.Class.methodName)
            String simpleMethodName = methodName;

            if ((className == null || className.isEmpty()) && methodName.contains(":")) {
                int colonIdx = methodName.lastIndexOf(':');
                className = methodName.substring(0, colonIdx);
                simpleMethodName = methodName.substring(colonIdx + 1);
            } else if ((className == null || className.isEmpty()) && methodName.contains(".")) {
                int lastDot = methodName.lastIndexOf('.');
                className = methodName.substring(0, lastDot);
                simpleMethodName = methodName.substring(lastDot + 1);
            }

            if (className == null || className.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'class_name'", logger);
                return;
            }

            // Use cache for fast lookup
            Map<String, JavaClass> classMap = ClassCacheManager.getCache();
            JavaClass cls = ClassCacheManager.findClass(classMap, className);

            if (cls != null) {
                // Collect all name-matching candidates to detect overloads
                List<JavaMethod> candidates = new ArrayList<>();
                for (JavaMethod method : cls.getMethods()) {
                    if (JadxApiAdapter.matchesMethodName(method, simpleMethodName)) {
                        candidates.add(method);
                    }
                }

                if (candidates.isEmpty()) {
                    JadxAIMCPPluginError.handleError(ctx, 404,
                        "Method " + simpleMethodName + " not found in class " + className, logger);
                    return;
                }

                // Descriptor supplied: find the exact overload
                if (methodSignature != null) {
                    for (JavaMethod method : candidates) {
                        if (JadxApiAdapter.matchesMethodDescriptor(method, methodSignature)) {
                            doRenameMethod(ctx, cls, method, newName, className);
                            return;
                        }
                    }
                    // Descriptor supplied but no overload matched — list available ones
                    List<String> available = collectMethodDescriptors(candidates);
                    Map<String, Object> err = new HashMap<>();
                    err.put("error", "No overload of " + simpleMethodName + " matches descriptor '"
                        + methodSignature + "' in class " + className);
                    err.put("available_descriptors", available);
                    ctx.status(404).json(err);
                    return;
                }

                // No descriptor: single match → rename; multiple → require disambiguation
                if (candidates.size() == 1) {
                    doRenameMethod(ctx, cls, candidates.get(0), newName, className);
                    return;
                }

                List<String> available = collectMethodDescriptors(candidates);
                Map<String, Object> err = new HashMap<>();
                err.put("error", "Method " + simpleMethodName + " in class " + className
                    + " has " + candidates.size()
                    + " overloads. Provide 'method_signature' to select one.");
                err.put("available_descriptors", available);
                ctx.status(300).json(err);
                return;
            }

            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error while trying to rename the method: " + e.getMessage(), e, logger);
        }
    }

    /** Performs the actual rename event dispatch and cache invalidation for a single method. */
    private void doRenameMethod(Context ctx, JavaClass cls, JavaMethod method, String newName, String className) {
        ICodeNodeRef nodeRef = method.getCodeNodeRef();
        NodeRenamedByUser event = new NodeRenamedByUser(nodeRef, method.getName(), newName);
        event.setRenameNode(nodeRef);
        event.setResetName(newName.isEmpty());
        mainWindow.events().send(event);
        invalidateCodeForClass(cls, className);
        logger.info("Renaming method {} to {}", method.getName(), newName);
        ctx.json(Map.of("result", "Rename method " + method.getName() + " to " + newName));
    }

    /** Collects JVM short descriptors (e.g. {@code "foo(I)V"}) for a list of methods. */
    private List<String> collectMethodDescriptors(List<JavaMethod> methods) {
        List<String> descriptors = new ArrayList<>(methods.size());
        for (JavaMethod m : methods) {
            JadxApiAdapter.MethodInfoSnapshot info = JadxApiAdapter.getMethodInfo(m);
            if (info != null && info.getShortId() != null) {
                descriptors.add(info.getShortId());
            }
        }
        return descriptors;
    }

    /**
     * 
     * @param ctx
     * @return
     * 
     * This routing method handle the /rename-field mcp tool call's http request, After validating the 
     * required http params, it tries to find the class whose method has to be renamed. If it is found
     * then it renames it using NodeRenamedByUser class' events methods 'setRenameNode' and 'setResetName'.
     * Then it sends these events using MainWindows's send() method.
     */
    public void handleRenameField(Context ctx) {
        JsonObject requestBody = parseJsonBody(ctx);
        if (requestBody == null) return;

        String className = getBodyString(requestBody, "class_name");
        String oldFieldName = getBodyString(requestBody, "field_name");
        String newFieldName = getBodyString(requestBody, "new_field_name");

        if (validateParams(ctx, className, oldFieldName, newFieldName)) return;

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            
            // Initialize cache if needed
            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }
            
            // Use cache for fast lookup
            Map<String, JavaClass> classMap = ClassCacheManager.getCache();
            JavaClass cls = ClassCacheManager.findClass(classMap, className);
            
            if (cls != null) {
                for (JavaField field : cls.getFields()) {
                    if (JadxApiAdapter.matchesFieldName(field, oldFieldName)) {
                        ICodeNodeRef nodeRef = field.getCodeNodeRef();
                        NodeRenamedByUser event = new NodeRenamedByUser(nodeRef, field.getName(), newFieldName);
                        event.setRenameNode(nodeRef);
                        event.setResetName(newFieldName.isEmpty());
                        mainWindow.events().send(event);

                        // Invalidate decompiled code cache — class source changed after field rename
                        invalidateCodeForClass(cls, className);

                        logger.info("Renaming field {} to {}", field.getName(), newFieldName);
                        ctx.json(Map.of("result", "Renamed field " + field.getName() + " to " + newFieldName));
                        return;
                    }
                }
                JadxAIMCPPluginError.handleError(ctx, 404, "Field " + oldFieldName + " not found in class " + className, logger);
                return;
            }
            
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error while trying to rename the field: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @return void
     * @param Context
     * 
     * This routing method handle the /rename-package mcp tool call's http request, After validating the 
     * required http params, It iterates over list of class one by one under the oldpackage and 
     * then it renames it using NodeRenamedByUser class' events methods 'setRenameNode' and 'setResetName'.
     * Then it sends these events using MainWindows's send() method.
     */
    public void handleRenamePackage(Context ctx) {
        JsonObject requestBody = parseJsonBody(ctx);
        if (requestBody == null) return;

        String oldPackage = getBodyString(requestBody, "old_package_name");
        String newPackage = getBodyString(requestBody, "new_package_name");

        if (validateParams(ctx, oldPackage, newPackage)) return;

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<String> errors = new ArrayList<>();
            int count = 0;
            int total = 0;

            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                String fullName = cls.getFullName();
                if (fullName.startsWith(oldPackage + ".") || fullName.equals(oldPackage)) {
                    total++;
                    try {
                        String relativePath = fullName.substring(oldPackage.length());
                        String newFullName = newPackage + relativePath;

                        NodeRenamedByUser event = new NodeRenamedByUser(cls.getCodeNodeRef(), cls.getName(), newFullName);
                        event.setRenameNode(cls.getCodeNodeRef());
                        event.setResetName(false);
                        mainWindow.events().send(event);
                        count++;
                    } catch (Exception e) {
                        errors.add("Failed to rename " + fullName + ": " + e.getMessage());
                    }
                }
            }

            // Invalidate all decompiled code cache — package rename affects many classes
            if (count > 0) {
                ClassCacheManager.clearCodeCache();
            }

            Map<String, Object> result = new HashMap<>();
            result.put("renamed", count);
            result.put("total", total);
            result.put("errors", errors);
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error occurred while trying to rename the package: " + e.getMessage(), e, logger);
        }
    }

    /**
     * GET /export-rename-mappings
     *
     * Iterates over all renamed classes/methods/fields, collects raw name vs alias differences,
     * and returns a JSON array: [{type, original_name, new_name, class_context}]
     */
    public void handleExportRenameMappings(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();

            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }

            List<Map<String, String>> mappings = new ArrayList<>();

            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                String rawName = cls.getRawName();
                String aliasName = cls.getFullName();

                // Class was renamed: rawName differs from aliasName
                if (rawName != null && aliasName != null && !rawName.equals(aliasName)) {
                    Map<String, String> entry = new HashMap<>();
                    entry.put("type", "class");
                    entry.put("original_name", rawName);
                    entry.put("new_name", aliasName);
                    entry.put("class_context", "");
                    mappings.add(entry);
                }

                // Field renames
                for (JavaField field : cls.getFields()) {
                    String rawFieldName = field.getRawName();
                    String aliasFieldName = field.getName();
                    if (rawFieldName != null && aliasFieldName != null && !rawFieldName.equals(aliasFieldName)) {
                        Map<String, String> fEntry = new HashMap<>();
                        fEntry.put("type", "field");
                        fEntry.put("original_name", rawFieldName);
                        fEntry.put("new_name", aliasFieldName);
                        fEntry.put("class_context", cls.getFullName());
                        mappings.add(fEntry);
                    }
                }

                // Method renames
                for (JavaMethod method : cls.getMethods()) {
                    String rawMethodName = JadxApiAdapter.getMethodRawName(method);
                    String aliasMethodName = JadxApiAdapter.getMethodAliasName(method);
                    if (rawMethodName != null && aliasMethodName != null && !rawMethodName.equals(aliasMethodName)) {
                        Map<String, String> mEntry = new HashMap<>();
                        mEntry.put("type", "method");
                        mEntry.put("original_name", rawMethodName);
                        mEntry.put("new_name", aliasMethodName);
                        mEntry.put("class_context", cls.getFullName());
                        mappings.add(mEntry);
                    }
                }
            }

            Map<String, Object> result = new HashMap<>();
            result.put("mappings", mappings);
            result.put("total", mappings.size());
            logger.info("[JAI] Exported {} rename mappings", mappings.size());
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Failed to export rename mappings: " + e.getMessage(), e, logger);
        }
    }

    /**
     * POST /import-rename-mappings
     *
     * Accepts a JSON body: {"mappings": [{type, original_name, new_name, class_context}]}
     * Applies each rename in order and returns success/failure counts.
     */
    public void handleImportRenameMappings(Context ctx) {
        JsonObject requestBody = parseJsonBody(ctx);
        if (requestBody == null) return;

        if (!requestBody.has("mappings") || !requestBody.get("mappings").isJsonArray()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing or invalid 'mappings' array in request body", logger);
            return;
        }

        JsonArray mappingsArray = requestBody.getAsJsonArray("mappings");

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();

            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }

            Map<String, JavaClass> classMap = ClassCacheManager.getCache();
            int successCount = 0;
            int failCount = 0;
            List<String> errors = new ArrayList<>();

            for (JsonElement element : mappingsArray) {
                if (!element.isJsonObject()) {
                    failCount++;
                    errors.add("Skipped non-object element");
                    continue;
                }

                JsonObject entry = element.getAsJsonObject();
                String type = getStringFromJson(entry, "type");
                String originalName = getStringFromJson(entry, "original_name");
                String newName = getStringFromJson(entry, "new_name");
                String classContext = getStringFromJson(entry, "class_context");

                if (type == null || originalName == null || newName == null) {
                    failCount++;
                    errors.add("Missing required fields (type/original_name/new_name) in entry: " + entry);
                    continue;
                }

                try {
                    switch (type.toLowerCase()) {
                        case "class": {
                            JavaClass cls = ClassCacheManager.findClass(classMap, originalName);
                            if (cls == null) {
                                failCount++;
                                errors.add("Class not found: " + originalName);
                                continue;
                            }
                            ICodeNodeRef nodeRef = cls.getCodeNodeRef();
                            NodeRenamedByUser event = new NodeRenamedByUser(nodeRef, cls.getName(), newName);
                            event.setRenameNode(nodeRef);
                            event.setResetName(false);
                            mainWindow.events().send(event);
                            invalidateCodeForClass(cls, originalName);
                            successCount++;
                            break;
                        }
                        case "method": {
                            if (classContext == null || classContext.isEmpty()) {
                                failCount++;
                                errors.add("class_context required for method: " + originalName);
                                continue;
                            }
                            JavaClass cls = ClassCacheManager.findClass(classMap, classContext);
                            if (cls == null) {
                                failCount++;
                                errors.add("Class not found for method: " + classContext);
                                continue;
                            }
                            boolean found = false;
                            for (JavaMethod method : cls.getMethods()) {
                                if (JadxApiAdapter.matchesMethodName(method, originalName)) {
                                    ICodeNodeRef nodeRef = method.getCodeNodeRef();
                                    NodeRenamedByUser event = new NodeRenamedByUser(nodeRef, method.getName(), newName);
                                    event.setRenameNode(nodeRef);
                                    event.setResetName(false);
                                    mainWindow.events().send(event);
                                    invalidateCodeForClass(cls, classContext);
                                    found = true;
                                    successCount++;
                                    break;
                                }
                            }
                            if (!found) {
                                failCount++;
                                errors.add("Method not found: " + originalName + " in " + classContext);
                            }
                            break;
                        }
                        case "field": {
                            if (classContext == null || classContext.isEmpty()) {
                                failCount++;
                                errors.add("class_context required for field: " + originalName);
                                continue;
                            }
                            JavaClass cls = ClassCacheManager.findClass(classMap, classContext);
                            if (cls == null) {
                                failCount++;
                                errors.add("Class not found for field: " + classContext);
                                continue;
                            }
                            boolean found = false;
                            for (JavaField field : cls.getFields()) {
                                if (JadxApiAdapter.matchesFieldName(field, originalName)) {
                                    ICodeNodeRef nodeRef = field.getCodeNodeRef();
                                    NodeRenamedByUser event = new NodeRenamedByUser(nodeRef, field.getName(), newName);
                                    event.setRenameNode(nodeRef);
                                    event.setResetName(false);
                                    mainWindow.events().send(event);
                                    invalidateCodeForClass(cls, classContext);
                                    found = true;
                                    successCount++;
                                    break;
                                }
                            }
                            if (!found) {
                                failCount++;
                                errors.add("Field not found: " + originalName + " in " + classContext);
                            }
                            break;
                        }
                        default:
                            failCount++;
                            errors.add("Unknown type '" + type + "' for entry: " + originalName);
                    }
                } catch (Exception e) {
                    failCount++;
                    errors.add("Error processing " + type + " '" + originalName + "': " + e.getMessage());
                }
            }

            Map<String, Object> result = new HashMap<>();
            result.put("success", failCount == 0);
            result.put("total", mappingsArray.size());
            result.put("applied", successCount);
            result.put("failed", failCount);
            result.put("errors", errors);
            logger.info("[JAI] Import rename mappings: applied={}, failed={}", successCount, failCount);
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Failed to import rename mappings: " + e.getMessage(), e, logger);
        }
    }

    /**
     * POST /apply-proguard-mapping
     *
     * Accepts a ProGuard mapping.txt body:
     *   {"mapping_content": "com.example.Original -> a.b.c:\n ..."}
     *
     * Parses class-level mappings only (original -> obfuscated format).
     * Builds a rename list where obfuscated name (current APK name) is renamed
     * back to the original name, then delegates to import-rename-mappings logic.
     *
     * Response: {"applied":N,"failed":M,"errors":[...],"total":T,"format":"proguard"}
     */
    public void handleApplyProguardMapping(Context ctx) {
        JsonObject requestBody = parseJsonBody(ctx);
        if (requestBody == null) return;

        String mappingContent = getBodyString(requestBody, "mapping_content");
        if (mappingContent == null || mappingContent.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'mapping_content'", logger);
            return;
        }

        // Parse ProGuard mapping: lines matching "original.Name -> obfuscated.Name:"
        // (class-level only; method/field lines start with whitespace — skip them)
        java.util.regex.Pattern classLinePattern =
            java.util.regex.Pattern.compile("^([\\w.$]+)\\s*->\\s*([\\w.$]+)\\s*:.*$");

        JsonArray mappingsArray = new JsonArray();
        List<String> parseErrors = new ArrayList<>();

        try (java.io.BufferedReader reader = new java.io.BufferedReader(
                new java.io.StringReader(mappingContent))) {
            String line;
            while ((line = reader.readLine()) != null) {
                // Skip blank lines and comment lines (#)
                String trimmed = line.trim();
                if (trimmed.isEmpty() || trimmed.startsWith("#")) continue;
                // Member lines (method/field) are indented — skip
                if (line.startsWith(" ") || line.startsWith("\t")) continue;

                java.util.regex.Matcher m = classLinePattern.matcher(trimmed);
                if (!m.matches()) continue;

                String originalName = m.group(1).trim();
                String obfuscatedName = m.group(2).trim();

                // In the APK the obfuscated name is the current name;
                // we rename it back to the original.
                JsonObject entry = new JsonObject();
                entry.addProperty("type", "class");
                entry.addProperty("original_name", obfuscatedName);   // current name in APK
                entry.addProperty("new_name", originalName);           // target (readable) name
                entry.addProperty("class_context", "");
                mappingsArray.add(entry);
            }
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                "Failed to parse ProGuard mapping content: " + e.getMessage(), e, logger);
            return;
        }

        if (mappingsArray.size() == 0) {
            Map<String, Object> result = new HashMap<>();
            result.put("applied", 0);
            result.put("failed", 0);
            result.put("errors", parseErrors);
            result.put("total", 0);
            result.put("format", "proguard");
            ctx.json(result);
            return;
        }

        // Delegate to existing import logic
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();

            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }

            Map<String, JavaClass> classMap = ClassCacheManager.getCache();
            int successCount = 0;
            int failCount = 0;
            List<String> errors = new ArrayList<>(parseErrors);

            for (JsonElement element : mappingsArray) {
                if (!element.isJsonObject()) {
                    failCount++;
                    continue;
                }
                JsonObject entry = element.getAsJsonObject();
                String originalName = getStringFromJson(entry, "original_name");
                String newName = getStringFromJson(entry, "new_name");
                if (originalName == null || newName == null) {
                    failCount++;
                    continue;
                }

                try {
                    JavaClass cls = ClassCacheManager.findClass(classMap, originalName);
                    if (cls == null) {
                        failCount++;
                        errors.add("Class not found: " + originalName);
                        continue;
                    }
                    ICodeNodeRef nodeRef = cls.getCodeNodeRef();
                    NodeRenamedByUser event = new NodeRenamedByUser(nodeRef, cls.getName(), newName);
                    event.setRenameNode(nodeRef);
                    event.setResetName(false);
                    mainWindow.events().send(event);
                    invalidateCodeForClass(cls, originalName);
                    successCount++;
                } catch (Exception e) {
                    failCount++;
                    errors.add("Error renaming '" + originalName + "': " + e.getMessage());
                }
            }

            Map<String, Object> result = new HashMap<>();
            result.put("applied", successCount);
            result.put("failed", failCount);
            result.put("errors", errors);
            result.put("total", mappingsArray.size());
            result.put("format", "proguard");
            logger.info("[JAI] Apply ProGuard mapping: applied={}, failed={}", successCount, failCount);
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                "Failed to apply ProGuard mapping: " + e.getMessage(), e, logger);
        }
    }

    /**
     * POST /rename-variable
     *
     * Renames a local variable inside a method using SSA variable tracking.
     * Required params: class_name, method_name, variable_name, new_name.
     * Optional params: reg (register number), ssa (SSA version) for disambiguation.
     *
     * If no SSA variables are found for the method on the first try, the class is
     * unloaded and force-processed to populate SSA state, then retried once.
     */
    public void handleRenameVariable(Context ctx) {
        JsonObject requestBody = parseJsonBody(ctx);
        if (requestBody == null) return;

        String className = getBodyString(requestBody, "class_name");
        String methodName = getBodyString(requestBody, "method_name");
        String variableName = getBodyString(requestBody, "variable_name");
        String newName = getBodyString(requestBody, "new_name");

        // Optional params for disambiguation when multiple SSA vars share a name
        String regStr = getBodyString(requestBody, "reg");
        String ssaStr = getBodyString(requestBody, "ssa");

        if (validateParams(ctx, className, methodName, variableName, newName)) return;

        // Strip method signature if present (e.g. "doSomething(int, String)" -> "doSomething")
        if (methodName.contains("(")) {
            methodName = methodName.substring(0, methodName.indexOf('('));
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();

            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                if (cls.getFullName().equals(className)) {
                    for (JavaMethod method : cls.getMethods()) {
                        String fullMethodName = cls.getFullName() + "." + method.getName();
                        if (method.getName().equals(methodName) || fullMethodName.equalsIgnoreCase(methodName)) {
                            MethodNode methodNode = method.getMethodNode();
                            if (methodNode == null) continue;

                            List<SSAVar> sVars = methodNode.getSVars();

                            // Ensure class is processed to populate SSA variables
                            if (sVars.isEmpty()) {
                                logger.info("SSA variables empty for method {}, forcing class reload and processing...", method.getName());
                                try {
                                    cls.getClassNode().unload();
                                    cls.getClassNode().root().getProcessClasses().forceProcess(cls.getClassNode());

                                    // Re-fetch method node and sVars after processing
                                    MethodNode newMethodNode = cls.getClassNode().searchMethodByShortName(method.getName());
                                    if (newMethodNode != null) {
                                        methodNode = newMethodNode;
                                        sVars = methodNode.getSVars();
                                        logger.info("Class reloaded. New SSA variables count: {}", sVars != null ? sVars.size() : "null");
                                    } else {
                                        logger.error("Failed to find method {} after reload", method.getName());
                                    }
                                } catch (Exception e) {
                                    logger.error("Failed to force process class {}", cls.getName(), e);
                                }
                            }

                            if (sVars == null || sVars.isEmpty()) continue;

                            for (SSAVar sVar : sVars) {
                                boolean nameMatch = variableName.equals(sVar.getName());
                                boolean regMatch = regStr == null || regStr.isEmpty() || String.valueOf(sVar.getRegNum()).equals(regStr);
                                boolean ssaMatch = ssaStr == null || ssaStr.isEmpty() || String.valueOf(sVar.getVersion()).equals(ssaStr);

                                if (nameMatch && regMatch && ssaMatch) {
                                    VarNode varNode = VarNode.get(methodNode, sVar);
                                    if (varNode != null) {
                                        NodeRenamedByUser event = new NodeRenamedByUser(varNode, variableName, newName);
                                        event.setRenameNode(varNode);
                                        event.setResetName(newName.isEmpty());
                                        mainWindow.events().send(event);

                                        logger.info("Renamed variable {} to {} in method {}", variableName, newName, method.getName());
                                        ctx.json(Map.of("result", "Renamed variable " + variableName + " to " + newName));
                                        return;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            JadxAIMCPPluginError.handleError(ctx, 404, "Variable " + variableName + " not found in method " + methodName, logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error while trying to rename the variable: " + e.getMessage(), e, logger);
        }
    }

    private String getStringFromJson(JsonObject obj, String key) {
        if (!obj.has(key) || obj.get(key).isJsonNull()) return null;
        JsonElement el = obj.get(key);
        return el.isJsonPrimitive() ? el.getAsString().trim() : null;
    }

    // Helper methods

    private JsonObject parseJsonBody(Context ctx) {
        try {
            String rawBody = ctx.body();
            if (rawBody == null || rawBody.isBlank()) {
                JadxAIMCPPluginError.handleError(ctx, 400, "Missing JSON request body", logger);
                return null;
            }

            JsonObject body = GSON.fromJson(rawBody, JsonObject.class);
            if (body == null) {
                JadxAIMCPPluginError.handleError(ctx, 400, "Missing JSON request body", logger);
                return null;
            }
            return body;
        } catch (JsonParseException e) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Invalid JSON request body", logger);
            return null;
        }
    }

    private String getBodyString(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull() || !body.get(key).isJsonPrimitive()) {
            return null;
        }
        String value = body.get(key).getAsString();
        return value == null ? null : value.trim();
    }

    /**
     * @param Context, String, String
     * @return boolean
     * 
     * This method is used to validate the availability of required http params in RefactoringRoutes
     * MCP tool's HTTP requests. If params are ok return true else return false.
     */
    private boolean validateParams(Context ctx, String p1, String p2) {
        if (p1 == null || p1.isEmpty() || p2 == null || p2.isEmpty()) {
            //ctx.status(400).json(Map.of("error", "Missing required parameters."));
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameters", logger);
            return true;
        }
        return false;
    }

    /**
     * @param Context, String, String, String
     * @return boolean
     * 
     * This method is used to validate the availability of required http params in RefactoringRoutes
     * MCP tool's HTTP requests. If params are ok return true else return false.
     */
    private boolean validateParams(Context ctx, String p1, String p2, String p3) {
        if (p1 == null || p1.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'class_name'", logger);
            return true;
        }
        if (p2 == null || p2.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'field_name'", logger);
            return true;
        }
        if (p3 == null || p3.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'new_field_name'", logger);
            return true;
        }
        return false;
    }

    /**
     * @param Context, String, String, String, String
     * @return boolean
     *
     * Validates four required parameters. Returns true (and sends 400) if any is null/empty.
     */
    private boolean validateParams(Context ctx, String p1, String p2, String p3, String p4) {
        if (p1 == null || p1.isEmpty() || p2 == null || p2.isEmpty()
                || p3 == null || p3.isEmpty() || p4 == null || p4.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameters", logger);
            return true;
        }
        return false;
    }

    private void invalidateCodeForClass(JavaClass cls, String requestedClassName) {
        if (requestedClassName != null && !requestedClassName.isEmpty()) {
            ClassCacheManager.invalidateCode(requestedClassName);
        }
        if (cls != null) {
            ClassCacheManager.invalidateCode(cls.getFullName());
            ClassCacheManager.invalidateCode(cls.getRawName());
        }
    }

}
