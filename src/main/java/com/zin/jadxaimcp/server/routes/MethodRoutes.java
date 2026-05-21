package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.JavaMethod;
import jadx.api.plugins.input.data.IMethodRef;
import jadx.core.dex.info.MethodInfo;
import jadx.core.dex.instructions.BaseInvokeNode;
import jadx.core.dex.instructions.args.InsnArg;
import jadx.core.dex.instructions.args.InsnWrapArg;
import jadx.core.dex.nodes.InsnNode;
import jadx.core.dex.nodes.MethodNode;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.HashMap;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.JadxSearchLock;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.JadxApiAdapter;
import com.zin.jadxaimcp.utils.SmartChunker;

public class MethodRoutes {
    private static final Logger logger = LoggerFactory.getLogger(MethodRoutes.class);
    private static final java.lang.reflect.Method JAVA_METHOD_GET_USED = findOptionalMethod(JavaMethod.class, "getUsed");
    private static final java.lang.reflect.Method JAVA_METHOD_GET_UNRESOLVED_USED =
        findOptionalMethod(JavaMethod.class, "getUnresolvedUsed");
    private static final java.lang.reflect.Method METHOD_NODE_GET_USED = findOptionalMethod(MethodNode.class, "getUsed");
    private static final java.lang.reflect.Method METHOD_NODE_GET_UNRESOLVED_USED =
        findOptionalMethod(MethodNode.class, "getUnresolvedUsed");
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
        // Optional JVM short-descriptor to disambiguate overloads, e.g. "foo(I)V"
        String methodSignature = ctx.queryParam("method_signature");
        if (methodSignature != null && methodSignature.isBlank()) {
            methodSignature = null;
        }

        String methodName = validateMethodParam(ctx);
        if (methodName == null) return;

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                JadxAIMCPPluginError.handleError(ctx, 500, "JadxWrapper not initialized", logger);
                return;
            }

            if (!tryAcquireDecompileLock(ctx)) {
                return;
            }
            try {
                // Case 1: Search in all classes if no class name provided
                // Use adapter-backed metadata lookup to avoid triggering decompilation.
                if (className == null || className.isEmpty()) {
                    for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                        for (JadxApiAdapter.MethodInfoSnapshot methodInfo : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                            if (matchesMethodName(methodInfo, methodName)) {
                                JavaMethod method = findMethodByNameAndDescriptor(cls, methodName, methodSignature);
                                if (method != null) {
                                    returnMethodResult(ctx, cls, method);
                                    return;
                                }
                            }
                        }
                    }
                }
                // Case 2: Search in specific class
                else {
                    for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                        if (JadxApiAdapter.matchesClassName(cls, className)) {
                            // Collect all name-matching methods to detect overloads
                            List<JavaMethod> candidates = findMethodsByName(cls, methodName);
                            if (candidates.isEmpty()) {
                                break; // class found, method not found
                            }

                            // Descriptor provided: find the exact overload
                            if (methodSignature != null) {
                                for (JavaMethod candidate : candidates) {
                                    if (JadxApiAdapter.matchesMethodDescriptor(candidate, methodSignature)) {
                                        returnMethodResult(ctx, cls, candidate);
                                        return;
                                    }
                                }
                                // Descriptor supplied but no match
                                List<String> available = collectDescriptors(candidates);
                                Map<String, Object> err = new HashMap<>();
                                err.put("error", "No overload of " + methodName + " matches descriptor '"
                                    + methodSignature + "' in class " + cls.getFullName());
                                err.put("available_descriptors", available);
                                ctx.status(404).json(err);
                                return;
                            }

                            // No descriptor: if exactly one match, return it; otherwise require disambiguation
                            if (candidates.size() == 1) {
                                returnMethodResult(ctx, cls, candidates.get(0));
                                return;
                            }

                            // Multiple overloads — tell the caller which descriptors are available
                            List<String> available = collectDescriptors(candidates);
                            Map<String, Object> err = new HashMap<>();
                            err.put("error", "Method " + methodName + " in class " + cls.getFullName()
                                + " has " + candidates.size()
                                + " overloads. Provide 'method_signature' to select one.");
                            err.put("available_descriptors", available);
                            ctx.status(300).json(err);
                            return;
                        }
                    }
                }
            } finally {
                JadxSearchLock.release();
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

        // Parse chunk parameter for large response handling
        String chunkParam = ctx.queryParam("chunk");
        int chunk = 0;
        if (chunkParam != null) {
            try {
                chunk = Integer.parseInt(chunkParam);
            } catch (NumberFormatException e) {
                JadxAIMCPPluginError.handleError(ctx, 400, "Invalid 'chunk' parameter: must be an integer", logger);
                return;
            }
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

            // Initialize cache if not already done
            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }
            
            // Check cache status
            ClassCacheManager.CacheStatus status = ClassCacheManager.getStatus();
            if (status == ClassCacheManager.CacheStatus.LOADING) {
                Map<String, Object> health = ClassCacheManager.getHealthInfo();
                Map<String, Object> response = new HashMap<>();
                response.put("status", "loading");
                response.put("type", "batch-method-by-name");
                response.put("message", "Class cache is being loaded in background. First load takes ~30-60 seconds for large APKs.");
                response.put("retry_after", 10);
                response.put("health", health);
                
                long elapsed = health.containsKey("elapsed_seconds") ? ((Number) health.get("elapsed_seconds")).longValue() : 0;
                if (elapsed > 0) {
                    response.put("estimated_remaining", "~" + Math.max(0, 40 - elapsed) + " seconds");
                }
                
                ctx.json(response);
                return;
            }

            if (!tryAcquireDecompileLock(ctx)) {
                return;
            }
            try {
                // Get the cached class map
                Map<String, JavaClass> classMap = ClassCacheManager.getCache();

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

                    JavaClass cls = ClassCacheManager.findClass(classMap, className);
                    if (cls == null) {
                        methodResult.put("found", false);
                        methodResult.put("error", "Class not found");
                        results.add(methodResult);
                        continue;
                    }

                    // Find method in class
                    boolean methodFound = false;
                    JavaMethod method = findMethodByName(cls, methodName);
                    if (method != null) {
                        try {
                            methodResult.put("class_name", cls.getFullName());
                            methodResult.put("raw_class_name", cls.getRawName());
                            methodResult.put("method_name", method.getName());
                            methodResult.put("raw_method_name", JadxApiAdapter.getMethodRawName(method));
                            methodResult.put("raw_method_full_id", JadxApiAdapter.getMethodRawFullId(method));
                            methodResult.put("found", true);
                            methodResult.put("decl", String.valueOf(method.getCodeNodeRef()));
                            methodResult.put("code", method.getCodeStr());
                            foundCount++;
                            methodFound = true;
                        } catch (Exception e) {
                            methodResult.put("found", true);
                            methodResult.put("error", "Failed to get code: " + e.getMessage());
                            methodFound = true;
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

                // Serialize and apply SmartChunker to prevent large response truncation
                com.google.gson.Gson gson = new com.google.gson.Gson();
                String responseJson = gson.toJson(response);

                // Apply chunking (auto-chunks if response > 8KB)
                Map<String, Object> chunkedResponse = SmartChunker.chunkResponse(
                    responseJson,
                    chunk,
                    "batch_result"
                );

                if (chunkedResponse.containsKey("error")) {
                    ctx.status(400).json(chunkedResponse);
                    return;
                }

                ctx.json(chunkedResponse);
            } finally {
                JadxSearchLock.release();
            }
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

        // Pagination parameters
        int offset = paginationUtils.getIntParam(ctx, "offset", 0);
        int count = paginationUtils.getIntParam(ctx, "count", 50);
        final int MAX_COUNT = 200;  // Max per request
        final int TIMEOUT_SECONDS = 30; // Timeout for search
        count = Math.min(count, MAX_COUNT);

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<Map<String, String>> results = new ArrayList<>();
            String searchTerm = methodName.toLowerCase();
            
            int totalMatches = 0;
            int skipped = 0;
            int collected = 0;
            int classesProcessed = 0;
            boolean timedOut = false;
            long startTime = System.currentTimeMillis();

            // Method-name search only reads ClassNode metadata and does not decompile code.
            // Acquire read lock to allow concurrent metadata queries while blocking during
            // exclusive decompilation (write lock) operations.
            if (!JadxSearchLock.tryAcquireRead()) {
                Map<String, Object> busyResponse = new HashMap<>();
                busyResponse.put("error", "Decompilation operation in progress");
                busyResponse.put("retry_after", JadxSearchLock.RETRY_AFTER_SECONDS);
                busyResponse.put("busy", true);
                ctx.status(503).json(busyResponse);
                return;
            }
            try {
            List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();
            int resultsNeeded = offset + count + 1; // +1 to check has_more

            outerLoop:
            for (JavaClass cls : allClasses) {
                // Timeout check every 100 classes
                if (classesProcessed % 100 == 0) {
                    long elapsed = (System.currentTimeMillis() - startTime) / 1000;
                    if (elapsed > TIMEOUT_SECONDS) {
                        timedOut = true;
                        break;
                    }
                }

                for (JadxApiAdapter.MethodInfoSnapshot methodInfo : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                    String mthName = methodInfo.getName();

                    if (mthName.toLowerCase().contains(searchTerm)) {
                        totalMatches++;

                        if (skipped < offset) {
                            skipped++;
                            continue;
                        }

                        if (collected < count) {
                            Map<String, String> match = new HashMap<>();
                            match.put("class_name", cls.getFullName());
                            match.put("raw_class_name", cls.getRawName());
                            match.put("method_name", mthName);
                            match.put("raw_method_name", mthName);
                            match.put("is_constructor", String.valueOf(methodInfo.isConstructor()));
                            results.add(match);
                            collected++;
                        }

                        // Early exit when we have enough
                        if (totalMatches >= resultsNeeded) {
                            break outerLoop;
                        }
                    }
                }
                classesProcessed++;
            }
            } finally {
                JadxSearchLock.releaseRead();
            }
            
            long elapsed = (System.currentTimeMillis() - startTime) / 1000;
            
            // Build response with pagination info
            Map<String, Object> response = new HashMap<>();
            response.put("type", "search-method");
            response.put("methods", results);
            response.put("offset", offset);
            response.put("count", collected);
            response.put("has_more", totalMatches > offset + collected);
            response.put("next_offset", offset + collected);
            
            // Search info
            Map<String, Object> searchInfo = new HashMap<>();
            searchInfo.put("total_found", totalMatches);
            searchInfo.put("classes_processed", classesProcessed);
            searchInfo.put("elapsed_seconds", elapsed);
            searchInfo.put("timed_out", timedOut);
            response.put("search_info", searchInfo);
            
            ctx.json(response);
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

    private JavaMethod findMethodByName(JavaClass cls, String methodName) {
        for (JavaMethod method : cls.getMethods()) {
            if (JadxApiAdapter.matchesMethodName(method, methodName)) {
                return method;
            }
        }
        return null;
    }

    /** Returns all methods in {@code cls} whose name matches {@code methodName}. */
    private List<JavaMethod> findMethodsByName(JavaClass cls, String methodName) {
        List<JavaMethod> result = new ArrayList<>();
        for (JavaMethod method : cls.getMethods()) {
            if (JadxApiAdapter.matchesMethodName(method, methodName)) {
                result.add(method);
            }
        }
        return result;
    }

    /**
     * Returns the first method in {@code cls} whose name matches {@code methodName} AND whose
     * JVM short descriptor matches {@code descriptor}.  When {@code descriptor} is {@code null}
     * the descriptor check is skipped and the first name-match is returned (legacy behaviour).
     */
    private JavaMethod findMethodByNameAndDescriptor(JavaClass cls, String methodName, String descriptor) {
        for (JavaMethod method : cls.getMethods()) {
            if (JadxApiAdapter.matchesMethodName(method, methodName)
                    && JadxApiAdapter.matchesMethodDescriptor(method, descriptor)) {
                return method;
            }
        }
        return null;
    }

    /** Collects the JVM short descriptor (e.g. {@code "foo(I)V"}) for each method in the list. */
    private List<String> collectDescriptors(List<JavaMethod> methods) {
        List<String> descriptors = new ArrayList<>(methods.size());
        for (JavaMethod m : methods) {
            String shortId = JadxApiAdapter.getMethodInfo(m) != null
                ? JadxApiAdapter.getMethodInfo(m).getShortId()
                : null;
            if (shortId != null) {
                descriptors.add(shortId);
            }
        }
        return descriptors;
    }

    private boolean matchesMethodName(JadxApiAdapter.MethodInfoSnapshot methodInfo, String methodName) {
        if (methodInfo == null || methodName == null || methodName.isEmpty()) {
            return false;
        }
        return methodName.equalsIgnoreCase(methodInfo.getRawName())
            || (methodInfo.getAliasName() != null && methodName.equalsIgnoreCase(methodInfo.getAliasName()))
            || (methodInfo.getFullId() != null && methodName.equalsIgnoreCase(methodInfo.getFullId()))
            || (methodInfo.getRawFullId() != null && methodName.equalsIgnoreCase(methodInfo.getRawFullId()));
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
        result.put("raw_class_name", cls.getRawName());
        result.put("method_name", method.getName());
        result.put("raw_method_name", JadxApiAdapter.getMethodRawName(method));
        result.put("method_full_id", JadxApiAdapter.getMethodFullId(method));
        result.put("raw_method_full_id", JadxApiAdapter.getMethodRawFullId(method));
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
     * - Frida-compatible overload string
     * - Frida hook template
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
                if (JadxApiAdapter.matchesClassName(cls, className)) {
                    List<Map<String, Object>> signatures = new ArrayList<>();
                    
                    for (JavaMethod method : cls.getMethods()) {
                        if (JadxApiAdapter.matchesMethodName(method, methodName)) {
                            Map<String, Object> sig = new HashMap<>();
                            sig.put("method_name", method.getName());
                            sig.put("raw_method_name", JadxApiAdapter.getMethodRawName(method));
                            sig.put("return_type", method.getReturnType() != null ? 
                                method.getReturnType().toString() : "void");
                            sig.put("access_flags", method.getAccessFlags().toString());
                            sig.put("is_constructor", method.isConstructor());
                            
                            // Parameters - JavaMethod exposes argument types via the public API in JADX 1.5.5.
                            List<Map<String, String>> params = new ArrayList<>();
                            List<jadx.core.dex.instructions.args.ArgType> argTypes = new ArrayList<>();
                            
                            try {
                                argTypes = new ArrayList<>(method.getArguments());
                                int idx = 0;
                                for (jadx.core.dex.instructions.args.ArgType argType : argTypes) {
                                    Map<String, String> param = new HashMap<>();
                                    param.put("name", "arg" + idx);
                                    param.put("type", argType.toString());
                                    param.put("type_frida", 
                                        com.zin.jadxaimcp.utils.FridaTypeConverter.toFridaType(argType));
                                    params.add(param);
                                    idx++;
                                }
                            } catch (Exception e) {
                                logger.warn("Failed to get arguments for {}: {}", methodName, e.getMessage());
                            }
                            sig.put("parameters", params);
                            
                            // Frida-compatible overload string
                            String fridaOverload = com.zin.jadxaimcp.utils.FridaTypeConverter
                                .toFridaOverloadString(argTypes);
                            sig.put("frida_overload", fridaOverload);
                            
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
                    response.put("class_name", cls.getFullName());
                    response.put("raw_class_name", cls.getRawName());
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
     * Request parameters:
     * - class_name (required): Fully qualified class name
     * - method_name (required): Method name to analyze
     * 
     * Returns JSON with semantic callee data split into resolved and unresolved groups.
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
            
            // Initialize cache if not already done
            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }
            
            // Get from cache
            Map<String, JavaClass> classMap = ClassCacheManager.getCache();
            JavaClass cls = ClassCacheManager.findClass(classMap, className);
            
            if (cls != null) {
                if (!tryAcquireDecompileLock(ctx)) {
                    return;
                }
                try {
                    JavaMethod method = findMethodByName(cls, methodName);
                    if (method != null) {
                        CalleeAnalysisResult analysis = analyzeMethodCallees(method);

                        Map<String, Object> response = new HashMap<>();
                        response.put("class_name", cls.getFullName());
                        response.put("raw_class_name", cls.getRawName());
                        response.put("method_name", method.getName());
                        response.put("raw_method_name", JadxApiAdapter.getMethodRawName(method));
                        response.put("callees_count", analysis.getAllCallees().size());
                        response.put("callees", analysis.getAllCallees());
                        response.put("resolved_callees_count", analysis.getResolvedCallees().size());
                        response.put("resolved_callees", analysis.getResolvedCallees());
                        response.put("unresolved_callees_count", analysis.getUnresolvedCallees().size());
                        response.put("unresolved_callees", analysis.getUnresolvedCallees());
                        response.put("analysis_mode", analysis.getAnalysisMode());
                        response.put("note", analysis.getNote());
                        ctx.json(response);
                        return;
                    }
                } finally {
                    JadxSearchLock.release();
                }

                JadxAIMCPPluginError.handleError(ctx, 404,
                    "Method " + methodName + " not found in class " + className, logger);
                return;
            }
            
            // Class not found
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving method callees: " + e.getMessage(), e, logger);
        }
    }

    private CalleeAnalysisResult analyzeMethodCallees(JavaMethod method) {
        CalleeAnalysisResult publicApiResult = analyzeMethodCalleesWithJavaMethodApi(method);
        if (publicApiResult != null) {
            return publicApiResult;
        }

        CalleeAnalysisResult internalApiResult = analyzeMethodCalleesWithMethodNodeApi(method);
        if (internalApiResult != null) {
            return internalApiResult;
        }

        // TODO: Replace this fallback with the upstream semantic usage API directly once the
        // JADX runtime we compile against exposes JavaMethod#getUsed/getUnresolvedUsed.
        return analyzeMethodCalleesFromInstructions(method);
    }

    private CalleeAnalysisResult analyzeMethodCalleesWithJavaMethodApi(JavaMethod method) {
        if (JAVA_METHOD_GET_USED == null || JAVA_METHOD_GET_UNRESOLVED_USED == null) {
            return null;
        }
        try {
            CalleeAnalysisResult result = new CalleeAnalysisResult(
                "semantic-public-api",
                "Collected callees via JavaMethod.getUsed()/getUnresolvedUsed()."
            );
            addResolvedCallees(result, invokeNodeCollection(JAVA_METHOD_GET_USED, method));
            addUnresolvedCallees(result, invokeMethodRefCollection(JAVA_METHOD_GET_UNRESOLVED_USED, method));
            return result;
        } catch (ReflectiveOperationException e) {
            logger.warn("Failed to use JavaMethod semantic callee API, falling back: {}", e.getMessage());
            return null;
        }
    }

    private CalleeAnalysisResult analyzeMethodCalleesWithMethodNodeApi(JavaMethod method) {
        if (METHOD_NODE_GET_USED == null || METHOD_NODE_GET_UNRESOLVED_USED == null) {
            return null;
        }
        MethodNode methodNode = JadxApiAdapter.getInternalMethodNode(method);
        if (methodNode == null) {
            return null;
        }
        try {
            CalleeAnalysisResult result = new CalleeAnalysisResult(
                "semantic-internal-api",
                "Collected callees via internal MethodNode usage API."
            );
            addResolvedCallees(result, invokeNodeCollection(METHOD_NODE_GET_USED, methodNode));
            addUnresolvedCallees(result, invokeMethodRefCollection(METHOD_NODE_GET_UNRESOLVED_USED, methodNode));
            return result;
        } catch (ReflectiveOperationException e) {
            logger.warn("Failed to use MethodNode semantic callee API, falling back: {}", e.getMessage());
            return null;
        }
    }

    private CalleeAnalysisResult analyzeMethodCalleesFromInstructions(JavaMethod method) {
        CalleeAnalysisResult result = new CalleeAnalysisResult(
            "semantic-instruction-fallback",
            "JavaMethod.getUsed()/getUnresolvedUsed() are unavailable in jadx-all 1.5.5; "
                + "using MethodNode instruction analysis without source regex."
        );

        MethodNode methodNode = JadxApiAdapter.getInternalMethodNode(method);
        if (methodNode == null) {
            return result;
        }

        InsnNode[] instructions = methodNode.getInstructions();
        if (instructions == null) {
            return result;
        }

        for (InsnNode instruction : instructions) {
            collectInvokeCallees(methodNode, instruction, result);
        }
        return result;
    }

    private void collectInvokeCallees(MethodNode callerMethod, InsnNode instruction, CalleeAnalysisResult result) {
        if (instruction == null) {
            return;
        }

        if (instruction instanceof BaseInvokeNode) {
            MethodInfo calledMethod = ((BaseInvokeNode) instruction).getCallMth();
            if (calledMethod != null) {
                MethodNode resolvedMethod = callerMethod.root().resolveMethod(calledMethod);
                if (resolvedMethod != null) {
                    result.addResolved(buildResolvedCalleeInfo(resolvedMethod));
                } else {
                    result.addUnresolved(buildUnresolvedCalleeInfo(calledMethod));
                }
            }
        }

        for (InsnArg argument : instruction.getArguments()) {
            if (argument.isInsnWrap()) {
                collectInvokeCallees(callerMethod, ((InsnWrapArg) argument).getWrapInsn(), result);
            }
        }
    }

    private void addResolvedCallees(CalleeAnalysisResult result, Collection<?> usedNodes) {
        for (Object usedNode : usedNodes) {
            if (usedNode instanceof JavaMethod) {
                result.addResolved(buildResolvedCalleeInfo((JavaMethod) usedNode));
            } else if (usedNode instanceof MethodNode) {
                result.addResolved(buildResolvedCalleeInfo((MethodNode) usedNode));
            }
        }
    }

    private void addUnresolvedCallees(CalleeAnalysisResult result, Collection<IMethodRef> unresolvedRefs) {
        for (IMethodRef unresolvedRef : unresolvedRefs) {
            result.addUnresolved(buildUnresolvedCalleeInfo(unresolvedRef));
        }
    }

    private Collection<?> invokeNodeCollection(java.lang.reflect.Method apiMethod, Object target)
            throws ReflectiveOperationException {
        Object value = apiMethod.invoke(target);
        if (value instanceof Collection<?>) {
            return (Collection<?>) value;
        }
        return Collections.emptyList();
    }

    private Collection<IMethodRef> invokeMethodRefCollection(java.lang.reflect.Method apiMethod, Object target)
            throws ReflectiveOperationException {
        Object value = apiMethod.invoke(target);
        if (!(value instanceof Collection<?>)) {
            return Collections.emptyList();
        }

        List<IMethodRef> methodRefs = new ArrayList<>();
        for (Object item : (Collection<?>) value) {
            if (item instanceof IMethodRef) {
                methodRefs.add((IMethodRef) item);
            }
        }
        return methodRefs;
    }

    private Map<String, Object> buildResolvedCalleeInfo(JavaMethod calleeMethod) {
        return buildResolvedCalleeInfo(JadxApiAdapter.getMethodInfo(calleeMethod));
    }

    private Map<String, Object> buildResolvedCalleeInfo(MethodNode calleeMethod) {
        return buildResolvedCalleeInfo(JadxApiAdapter.getMethodInfo(calleeMethod));
    }

    private Map<String, Object> buildResolvedCalleeInfo(JadxApiAdapter.MethodInfoSnapshot calleeMethodInfo) {
        Map<String, Object> info = new LinkedHashMap<>();
        if (calleeMethodInfo == null) {
            info.put("class_name", "");
            info.put("method_name", "");
            info.put("raw_method_name", "");
            info.put("full_name", "");
            info.put("raw_full_id", "");
            info.put("short_id", "");
            info.put("display_name", "");
            return info;
        }
        String fullName = calleeMethodInfo.getFullName();
        String aliasFullName = calleeMethodInfo.getAliasFullName();
        String className = calleeMethodInfo.getDeclaringClassName();
        info.put("class_name", className);
        info.put("method_name", calleeMethodInfo.getAliasName() != null
            ? calleeMethodInfo.getAliasName()
            : calleeMethodInfo.getRawName());
        info.put("raw_method_name", calleeMethodInfo.getRawName());
        info.put("full_name", fullName);
        info.put("alias_full_name", aliasFullName);
        info.put("raw_full_id", calleeMethodInfo.getRawFullId());
        info.put("short_id", calleeMethodInfo.getShortId());
        info.put("display_name", aliasFullName != null ? aliasFullName : fullName);
        return info;
    }

    private Map<String, Object> buildUnresolvedCalleeInfo(MethodInfo unresolvedMethod) {
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("class_name", unresolvedMethod.getDeclClass().getFullName());
        info.put("method_name", unresolvedMethod.getName());
        info.put("raw_method_name", unresolvedMethod.getName());
        info.put("full_name", unresolvedMethod.getFullName());
        info.put("raw_full_id", unresolvedMethod.getRawFullId());
        info.put("short_id", unresolvedMethod.getShortId());
        info.put("display_name", unresolvedMethod.getFullName());
        return info;
    }

    private Map<String, Object> buildUnresolvedCalleeInfo(IMethodRef unresolvedMethod) {
        Map<String, Object> info = new LinkedHashMap<>();
        String className = normalizeTypeName(unresolvedMethod.getParentClassType());
        info.put("class_name", className);
        info.put("method_name", unresolvedMethod.getName());
        info.put("full_name", className + "." + unresolvedMethod.getName());
        info.put("arg_types", new ArrayList<>(unresolvedMethod.getArgTypes()));
        info.put("return_type", unresolvedMethod.getReturnType());
        info.put("display_name", className + "." + unresolvedMethod.getName());
        return info;
    }

    private static java.lang.reflect.Method findOptionalMethod(Class<?> type, String methodName) {
        try {
            return type.getMethod(methodName);
        } catch (NoSuchMethodException e) {
            return null;
        }
    }

    private String normalizeTypeName(String typeName) {
        if (typeName == null || typeName.isEmpty()) {
            return "";
        }
        if (typeName.startsWith("L") && typeName.endsWith(";")) {
            return typeName.substring(1, typeName.length() - 1).replace('/', '.');
        }
        return typeName.replace('/', '.');
    }

    private static final class CalleeAnalysisResult {
        private final LinkedHashMap<String, Map<String, Object>> resolved = new LinkedHashMap<>();
        private final LinkedHashMap<String, Map<String, Object>> unresolved = new LinkedHashMap<>();
        private final String analysisMode;
        private final String note;

        private CalleeAnalysisResult(String analysisMode, String note) {
            this.analysisMode = analysisMode;
            this.note = note;
        }

        private void addResolved(Map<String, Object> callee) {
            resolved.putIfAbsent(String.valueOf(callee.get("full_name")) + "#" + String.valueOf(callee.get("short_id")), callee);
        }

        private void addUnresolved(Map<String, Object> callee) {
            String unresolvedKey = String.valueOf(callee.get("full_name")) + "#"
                + String.valueOf(callee.getOrDefault("short_id", callee.getOrDefault("arg_types", "")));
            unresolved.putIfAbsent(unresolvedKey, callee);
        }

        private List<String> getAllCallees() {
            Set<String> combined = new LinkedHashSet<>();
            for (Map<String, Object> callee : resolved.values()) {
                combined.add(String.valueOf(callee.get("display_name")));
            }
            for (Map<String, Object> callee : unresolved.values()) {
                combined.add(String.valueOf(callee.get("display_name")));
            }
            return new ArrayList<>(combined);
        }

        private List<Map<String, Object>> getResolvedCallees() {
            return new ArrayList<>(resolved.values());
        }

        private List<Map<String, Object>> getUnresolvedCallees() {
            return new ArrayList<>(unresolved.values());
        }

        private String getAnalysisMode() {
            return analysisMode;
        }

        private String getNote() {
            return note;
        }
    }

    /**
     * Search for all native methods across the APK.
     * 
     * This is a metadata-only operation that does NOT trigger decompilation.
     * Uses adapter-backed metadata access which reads from DEX metadata directly.
     * 
     * Query params:
     * - package: Optional package filter (e.g., "com.xingin")
     * - offset: Pagination offset (default: 0)
     * - count: Max results (default: 50, max: 200)
     */
    public void handleSearchNativeMethods(Context ctx) {
        String packageFilter = ctx.queryParam("package");
        int offset = 0;
        int count = 50;
        
        try {
            String offsetStr = ctx.queryParam("offset");
            if (offsetStr != null) offset = Integer.parseInt(offsetStr);
        } catch (NumberFormatException e) {
            // Use default
        }
        
        try {
            String countStr = ctx.queryParam("count");
            if (countStr != null) count = Math.min(Integer.parseInt(countStr), 200);
        } catch (NumberFormatException e) {
            // Use default
        }
        
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                JadxAIMCPPluginError.handleError(ctx, 500, "JadxWrapper not initialized", logger);
                return;
            }
            
            List<Map<String, Object>> nativeMethods = new ArrayList<>();
            int totalFound = 0;
            int skipped = 0;

            // Metadata-only operation: acquire read lock to allow concurrent metadata queries
            // while blocking during exclusive decompilation (write lock) operations.
            if (!JadxSearchLock.tryAcquireRead()) {
                Map<String, Object> busyResponse = new HashMap<>();
                busyResponse.put("error", "Decompilation operation in progress");
                busyResponse.put("retry_after", JadxSearchLock.RETRY_AFTER_SECONDS);
                busyResponse.put("busy", true);
                ctx.status(503).json(busyResponse);
                return;
            }
            try {
            // Iterate through all classes - only accessing metadata, no decompilation
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                String className = cls.getFullName();

                // Apply package filter if provided
                if (packageFilter != null && !packageFilter.isEmpty()) {
                    if (!className.startsWith(packageFilter)) {
                        continue;
                    }
                }

                for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                    if (methodSnapshot.getAccessFlags() != null && methodSnapshot.getAccessFlags().isNative()) {
                        totalFound++;

                        // Apply pagination
                        if (skipped < offset) {
                            skipped++;
                            continue;
                        }

                        if (nativeMethods.size() >= count) {
                            continue; // Keep counting total but don't add more
                        }

                        Map<String, Object> nativeMethodInfo = new HashMap<>();
                        nativeMethodInfo.put("class_name", className);
                        nativeMethodInfo.put("raw_class_name", JadxApiAdapter.getClassRawName(cls));
                        String methodAliasName = methodSnapshot.getAliasName() != null
                            ? methodSnapshot.getAliasName()
                            : methodSnapshot.getName();
                        nativeMethodInfo.put("method_name", methodAliasName);
                        nativeMethodInfo.put("raw_method_name", methodSnapshot.getName());
                        nativeMethodInfo.put("short_id", methodSnapshot.getShortId());

                        // Get parameter types for Frida overload
                        List<String> paramTypes = new ArrayList<>();
                        for (jadx.core.dex.instructions.args.ArgType argType : methodSnapshot.getArgumentTypes()) {
                            paramTypes.add(com.zin.jadxaimcp.utils.FridaTypeConverter.toFridaType(argType));
                        }
                        nativeMethodInfo.put("param_types_frida", paramTypes);

                        nativeMethods.add(nativeMethodInfo);
                    }
                }
            }
            } finally {
                JadxSearchLock.releaseRead();
            }
            
            Map<String, Object> response = new HashMap<>();
            response.put("native_methods", nativeMethods);
            response.put("count", nativeMethods.size());
            response.put("total_found", totalFound);
            response.put("offset", offset);
            response.put("has_more", totalFound > offset + nativeMethods.size());
            if (packageFilter != null && !packageFilter.isEmpty()) {
                response.put("package_filter", packageFilter);
            }
            
            ctx.json(response);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error searching native methods: " + e.getMessage(), e, logger);
        }
    }

    private boolean tryAcquireDecompileLock(Context ctx) {
        if (JadxSearchLock.tryAcquire()) {
            return true;
        }

        Map<String, Object> busyResponse = new HashMap<>();
        busyResponse.put("error", "Decompilation operation in progress");
        busyResponse.put("retry_after", JadxSearchLock.RETRY_AFTER_SECONDS);
        busyResponse.put("busy", true);
        ctx.status(503).json(busyResponse);
        return false;
    }

}
