package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.JavaMethod;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.HashMap;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;

public class MethodRoutes {
    private static final Logger logger = LoggerFactory.getLogger(MethodRoutes.class);
    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;

    public MethodRoutes(MainWindow mainWindow, PaginationUtils paginationUtils) {
        this.mainWindow = mainWindow;
        this.paginationUtils = paginationUtils;
    }

    /**
     * @return void
     * @param Context
     * 
     * This method handle the /method-by-name mcp tool call.
     * 
     * First validate the essential 'method_name' param, Then using jadxwrapper,
     * 1. if no classname is provided in http request, then search for the requested method
     * in all classes.
     *  - get list of classes
     *  - get all the methods of all classes one by one
     *  - check the if any match found and return it 
     * 2. If 'class_name' is present in http request, then 
     *  - get all the methods of that class
     *  - check if any match is found and return it
     */
    public void handleMethodByName(Context ctx) {
        String className = ctx.queryParam("class_name");

        String methodName = validateMethodParam(ctx);
        if (methodName == null) return;

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                JadxAIMCPPluginError.handleError(ctx, 500, "JadxWrapper not initialized", logger);
                return;
            }

            // Case 1: Search in all classes if no class name provided
            if (className == null || className.isEmpty()) {
                for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                    for (JavaMethod method : cls.getMethods()) {
                        if (method.getName().equalsIgnoreCase(methodName)) {
                            returnMethodResult(ctx, cls, method);
                            return;
                        }
                    }
                }
            } 
            // Case 2: Search in specific class
            else {
                for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                    if (cls.getFullName().equals(className)) {
                        for (JavaMethod method : cls.getMethods()) {
                            if (method.getName().equalsIgnoreCase(methodName)) {
                                returnMethodResult(ctx, cls, method);
                                return;
                            }
                        }
                    }
                }
            }

            // if execution reaches here, it means that method has not been found
            JadxAIMCPPluginError.handleError(ctx, 404, "Requested method " + methodName + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error occurred while retrieving method: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @return void
     * @param Context
     * 
     *         This method handles the /batch-method-by-name MCP tool call.
     *         Allows fetching multiple methods in a single request to reduce
     *         MCP interaction overhead.
     * 
     *         Request parameters:
     *         - methods (required): Comma-separated list of class_name:method_name pairs
     *           Example: com.example.A:methodA,com.example.B:methodB
     * 
     *         Returns a JSON object with:
     *         - methods: Array of objects containing class_name, method_name, found, and code/error
     *         - total: Total number of requested methods
     *         - found: Number of methods successfully found
     * 
     *         Max limit: 20 methods per request to prevent performance issues.
     */
    public void handleBatchMethodByName(Context ctx) {
        String methodsParam = ctx.queryParam("methods");
        if (methodsParam == null || methodsParam.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, 
                "Missing 'methods' parameter. Provide comma-separated class_name:method_name pairs.", logger);
            return;
        }

        String[] methodPairs = methodsParam.split(",");
        
        // Limit to prevent performance issues
        final int MAX_BATCH_SIZE = 20;
        if (methodPairs.length > MAX_BATCH_SIZE) {
            JadxAIMCPPluginError.handleError(ctx, 400, 
                "Too many methods requested. Maximum " + MAX_BATCH_SIZE + " methods per request.", logger);
            return;
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                JadxAIMCPPluginError.handleError(ctx, 500, "JadxWrapper not initialized", logger);
                return;
            }

            // Build class map for O(1) lookup
            Map<String, JavaClass> classMap = new HashMap<>();
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                classMap.put(cls.getFullName(), cls);
            }

            List<Map<String, Object>> results = new ArrayList<>();
            int foundCount = 0;

            for (String pair : methodPairs) {
                String trimmedPair = pair.trim();
                Map<String, Object> methodResult = new HashMap<>();
                
                // Parse class_name:method_name format
                int colonIndex = trimmedPair.lastIndexOf(':');
                if (colonIndex == -1) {
                    methodResult.put("input", trimmedPair);
                    methodResult.put("found", false);
                    methodResult.put("error", "Invalid format. Use class_name:method_name");
                    results.add(methodResult);
                    continue;
                }

                String className = trimmedPair.substring(0, colonIndex);
                String methodName = trimmedPair.substring(colonIndex + 1);
                
                methodResult.put("class_name", className);
                methodResult.put("method_name", methodName);

                JavaClass cls = classMap.get(className);
                if (cls == null) {
                    methodResult.put("found", false);
                    methodResult.put("error", "Class not found");
                    results.add(methodResult);
                    continue;
                }

                // Find method in class
                boolean methodFound = false;
                for (JavaMethod method : cls.getMethods()) {
                    if (method.getName().equalsIgnoreCase(methodName)) {
                        try {
                            methodResult.put("found", true);
                            methodResult.put("decl", String.valueOf(method.getCodeNodeRef()));
                            methodResult.put("code", method.getCodeStr());
                            foundCount++;
                            methodFound = true;
                        } catch (Exception e) {
                            methodResult.put("found", true);
                            methodResult.put("error", "Failed to get code: " + e.getMessage());
                        }
                        break;
                    }
                }

                if (!methodFound && !methodResult.containsKey("found")) {
                    methodResult.put("found", false);
                    methodResult.put("error", "Method not found in class");
                }
                results.add(methodResult);
            }

            Map<String, Object> response = new HashMap<>();
            response.put("methods", results);
            response.put("total", methodPairs.length);
            response.put("found", foundCount);
            ctx.json(response);

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving batch methods: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @return void
     * @param Context
     * 
     * This method handles the /search-method MCP tool call.
     * 
     * Searches for methods by name across all classes.
     * Returns structured JSON with matching method locations.
     * 
     * 1. for each java class
     *  - for each method in that class
     *      - if method name matches (case-insensitive partial match) then add to results
     * 2. return JSON results with pagination support.
     */
    public void handleSearchMethod(Context ctx) {
        String methodName = validateMethodParam(ctx);
        if (methodName == null) return;

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<Map<String, String>> results = new ArrayList<>();
            String searchTerm = methodName.toLowerCase();

            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                for (JavaMethod method : cls.getMethods()) {
                    // Match method name (case-insensitive, partial match)
                    if (method.getName().toLowerCase().contains(searchTerm)) {
                        Map<String, String> match = new HashMap<>();
                        match.put("class_name", cls.getFullName());
                        match.put("method_name", method.getName());
                        match.put("is_constructor", String.valueOf(method.isConstructor()));
                        results.add(match);
                    }
                }
            }
            
            // Return JSON response with pagination
            Map<String, Object> response = paginationUtils.handlePagination(
                ctx, results, "search-method", "methods", m -> m);
            ctx.json(response);
        } catch (PaginationException e) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Pagination error: " + e.getMessage(), logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error during method search: " + e.getMessage(), e, logger);
        }    
    }
    // Helper methods

    /**
     * @param Context
     * @return String
     * 
     * Checks if the HTTP request contains the 'method_name' param or not, if yes then returns it
     * else returns null and handles the error.
     */
    private String validateMethodParam(Context ctx) {
        String methodName = ctx.queryParam("method_name");
        if (methodName == null || methodName.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'method_name'", logger);
            return null;
        }
        return methodName;
    }

    /**
     * @return void
     * @param Context, JavaClass, JavaMethod
     * 
     * This helper method is used to build and return the found method code
     * 1. Get the method code
     * 2. Build the Map of the result.
     * 3. return json result.
     */
    private void returnMethodResult(Context ctx, JavaClass cls, JavaMethod method) {
        String codeStr;
        try {
            codeStr = method.getCodeStr();
        } catch (Exception e) {
            logger.error("JADX AI MCP ERROR: Error retrieving code: " + e.getMessage());
            codeStr = "Error retrieving code: " + e.getMessage();
        }

        Map<String, String> result = new HashMap<>();
        result.put("class_name", cls.getFullName());
        result.put("method_name", method.getName());
        result.put("decl", String.valueOf(method.getCodeNodeRef()));
        result.put("code", codeStr);
        ctx.json(result);
    }

    /**
     * @return void
     * @param Context
     * 
     * This method handles the /method-signature MCP tool call.
     * Returns structured signature information for a method including:
     * - Return type
     * - Parameter types and names
     * - Access modifiers
     * - Throws declarations
     */
    public void handleMethodSignature(Context ctx) {
        String className = ctx.queryParam("class_name");
        String methodName = validateMethodParam(ctx);
        if (methodName == null) return;
        
        if (className == null || className.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'class_name'", logger);
            return;
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                if (cls.getFullName().equals(className)) {
                    List<Map<String, Object>> signatures = new ArrayList<>();
                    
                    for (JavaMethod method : cls.getMethods()) {
                        if (method.getName().equalsIgnoreCase(methodName)) {
                            Map<String, Object> sig = new HashMap<>();
                            sig.put("method_name", method.getName());
                            sig.put("return_type", method.getReturnType() != null ? 
                                method.getReturnType().toString() : "void");
                            sig.put("access_flags", method.getAccessFlags().toString());
                            sig.put("is_constructor", method.isConstructor());
                            
                            // Parameters - iterate through argument types from MethodNode
                            List<Map<String, String>> params = new ArrayList<>();
                            try {
                                List<jadx.core.dex.instructions.args.ArgType> argTypes = 
                                    method.getMethodNode().getMethodInfo().getArgumentsTypes();
                                int idx = 0;
                                for (jadx.core.dex.instructions.args.ArgType argType : argTypes) {
                                    Map<String, String> param = new HashMap<>();
                                    param.put("name", "arg" + idx);
                                    param.put("type", argType.toString());
                                    params.add(param);
                                    idx++;
                                }
                            } catch (Exception e) {
                                logger.warn("Failed to get arguments for {}: {}", methodName, e.getMessage());
                            }
                            sig.put("parameters", params);
                            
                            // Full declaration
                            sig.put("declaration", String.valueOf(method.getCodeNodeRef()));
                            
                            signatures.add(sig);
                        }
                    }
                    
                    if (signatures.isEmpty()) {
                        JadxAIMCPPluginError.handleError(ctx, 404, 
                            "Method " + methodName + " not found in class " + className, logger);
                        return;
                    }
                    
                    Map<String, Object> response = new HashMap<>();
                    response.put("class_name", className);
                    response.put("method_name", methodName);
                    response.put("overloads", signatures.size());
                    response.put("signatures", signatures);
                    ctx.json(response);
                    return;
                }
            }
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving method signature: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @return void
     * @param Context
     * 
     * This method handles the /method-callees MCP tool call.
     * Returns a list of methods called by the specified method.
     * 
     * Uses code text parsing to identify method calls (pattern matching approach).
     * 
     * Request parameters:
     * - class_name (required): Fully qualified class name
     * - method_name (required): Method name to analyze
     * 
     * Returns JSON with list of potential callees (class.method patterns found in code).
     */
    public void handleMethodCallees(Context ctx) {
        String className = ctx.queryParam("class_name");
        String methodName = validateMethodParam(ctx);
        if (methodName == null) return;
        
        if (className == null || className.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'class_name'", logger);
            return;
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                if (cls.getFullName().equals(className)) {
                    for (JavaMethod method : cls.getMethods()) {
                        if (method.getName().equalsIgnoreCase(methodName)) {
                            String code = method.getCodeStr();
                            
                            // Parse method calls from code
                            // Pattern: identifier.methodName( or ClassName.staticMethod(
                            java.util.regex.Pattern pattern = java.util.regex.Pattern.compile(
                                "([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\.\\s*([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\("
                            );
                            java.util.regex.Matcher matcher = pattern.matcher(code);
                            
                            Set<String> calleesSet = new java.util.LinkedHashSet<>();
                            while (matcher.find()) {
                                String receiver = matcher.group(1);
                                String calledMethod = matcher.group(2);
                                // Filter out common false positives
                                if (!receiver.equals("this") && !receiver.equals("super")) {
                                    calleesSet.add(receiver + "." + calledMethod);
                                }
                            }
                            
                            // Also find new ClassName() constructor calls
                            java.util.regex.Pattern ctorPattern = java.util.regex.Pattern.compile(
                                "new\\s+([a-zA-Z_][a-zA-Z0-9_.]+)\\s*\\("
                            );
                            java.util.regex.Matcher ctorMatcher = ctorPattern.matcher(code);
                            while (ctorMatcher.find()) {
                                calleesSet.add(ctorMatcher.group(1) + ".<init>");
                            }
                            
                            List<String> callees = new ArrayList<>(calleesSet);
                            
                            Map<String, Object> response = new HashMap<>();
                            response.put("class_name", className);
                            response.put("method_name", methodName);
                            response.put("callees_count", callees.size());
                            response.put("callees", callees);
                            response.put("note", "Pattern-based analysis; may include false positives from strings/comments");
                            ctx.json(response);
                            return;
                        }
                    }
                    JadxAIMCPPluginError.handleError(ctx, 404, 
                        "Method " + methodName + " not found in class " + className, logger);
                    return;
                }
            }
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving method callees: " + e.getMessage(), e, logger);
        }
    }
}
