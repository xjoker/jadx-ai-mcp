package com.zin.jadxaimcp.server.routes;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.JavaField;
import jadx.api.JavaMethod;
import jadx.api.metadata.ICodeNodeRef;
import jadx.api.plugins.events.types.NodeRenamedByUser;
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

        if (validateParams(ctx, methodName, newName)) return;

        // Strip method signature if present
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
                for (JavaMethod method : cls.getMethods()) {
                    if (JadxApiAdapter.matchesMethodName(method, simpleMethodName)) {
                        ICodeNodeRef nodeRef = method.getCodeNodeRef();
                        NodeRenamedByUser event = new NodeRenamedByUser(nodeRef, method.getName(), newName);
                        event.setRenameNode(nodeRef);
                        event.setResetName(newName.isEmpty());
                        mainWindow.events().send(event);

                        // Invalidate decompiled code cache — class source changed after method rename
                        invalidateCodeForClass(cls, className);

                        logger.info("Renaming method {} to {}", method.getName(), newName);
                        ctx.json(Map.of("result", "Rename method " + method.getName() + " to " + newName));
                        return;
                    }
                }
                JadxAIMCPPluginError.handleError(ctx, 404, "Method " + simpleMethodName + " not found in class " + className, logger);
                return;
            }
            
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error while trying to rename the method: " + e.getMessage(), e, logger);
        }
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
