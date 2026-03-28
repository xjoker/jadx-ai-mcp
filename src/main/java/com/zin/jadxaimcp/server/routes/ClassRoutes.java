package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.JavaField;
import jadx.api.JavaMethod;
import jadx.api.ResourceFile;
import jadx.api.data.impl.JadxCodeData;
import jadx.api.metadata.ICodeNodeRef;
import jadx.api.security.IJadxSecurity;
import jadx.core.dex.info.AccessInfo;
import jadx.core.dex.instructions.args.ArgType;
import jadx.core.utils.android.AndroidManifestParser;
import jadx.core.utils.android.AppAttribute;
import jadx.core.utils.android.ApplicationParams;
import jadx.core.utils.exceptions.JadxRuntimeException;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.w3c.dom.Document;
import org.w3c.dom.Element;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.swing.*;
import java.awt.*;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.ArrayList;
import java.util.Map;
import java.util.List;
import java.util.stream.Collectors;
import java.io.InputStream;
import java.util.EnumSet;
import java.util.Set;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.regex.Pattern;
import java.util.concurrent.Callable;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ConcurrentLinkedQueue;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.JadxSearchLock;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.CodeSearchCoordinator;
import com.zin.jadxaimcp.utils.JadxApiAdapter;
import com.zin.jadxaimcp.utils.SmartChunker;

public class ClassRoutes {
    private static final Logger logger = LoggerFactory.getLogger(ClassRoutes.class);
    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;
    
    // Thread pool for parallel batch search
    private final ExecutorService searchExecutor = Executors.newFixedThreadPool(
        Math.max(2, Runtime.getRuntime().availableProcessors() - 1));

    /**
     * Enum for specifying search locations in handleSearchClassesByKeyword.
     * Supports searching in different parts of decompiled code.
     */
    public enum SearchLocation {
        CLASS_NAME, // Search classes by class name containing keyword
        METHOD_NAME, // Search classes by method name/constructor/parameter types containing keyword
        FIELD_NAME, // Search classes by field name containing keyword
        CODE, // Search code containing keyword (default)
        COMMENT // Search comments containing keyword (searches for // and /* */ patterns)
    }

    // Map lowercase search location names to enum values for URL-friendly parameter
    // parsing
    private static final Map<String, SearchLocation> SEARCH_LOCATION_MAP = new HashMap<>();
    static {
        SEARCH_LOCATION_MAP.put("class", SearchLocation.CLASS_NAME);
        SEARCH_LOCATION_MAP.put("class_name", SearchLocation.CLASS_NAME);
        SEARCH_LOCATION_MAP.put("method", SearchLocation.METHOD_NAME);
        SEARCH_LOCATION_MAP.put("method_name", SearchLocation.METHOD_NAME);
        SEARCH_LOCATION_MAP.put("field", SearchLocation.FIELD_NAME);
        SEARCH_LOCATION_MAP.put("field_name", SearchLocation.FIELD_NAME);
        SEARCH_LOCATION_MAP.put("code", SearchLocation.CODE);
        SEARCH_LOCATION_MAP.put("comment", SearchLocation.COMMENT);
    }

    // Pattern to detect jadx obfuscated package names (e.g., p000, p001, p123)
    private static final Pattern OBFUSCATED_PACKAGE_PATTERN = Pattern.compile("^p\\d+$");
    
    // Search optimization constants
    private static final int DEFAULT_RESULT_LIMIT = 50;   // Default results per page
    private static final int MAX_RESULT_LIMIT = 200;      // Maximum results per page
    private static final int SEARCH_TIMEOUT_SECONDS = 60; // Timeout for search operations
    private static final String SEARCH_DECOMPILATION_BUSY_MESSAGE = "Search/decompilation operation in progress";

    public ClassRoutes(MainWindow mainWindow, PaginationUtils paginationUtils) {
        this.mainWindow = mainWindow;
        this.paginationUtils = paginationUtils;
    }

    public void shutdownSearchExecutor() {
        searchExecutor.shutdownNow();
    }

    // ------------------------------- Request Handlers --------------------------

    /**
     * @param Context
     * @return void
     * 
     *         This handler method handle the /current-class api call,
     *         It return currently open/active/visible class code in UI in jadx.
     *         Using helper methods getSelectedTabTitle() and
     *         extractTextFromCurrentTab() it gets
     *         the title of UI component holding class code and then using that UI
     *         component extracts
     *         the text from that UI component.
     * 
     *         After getting the code it returns it.
     *         
     *         Supports chunking for large responses (>8KB).
     */
    public void handleCurrentClass(Context ctx) {
        try {
            // Parse chunk parameter
            int chunk = 0;
            String chunkParam = ctx.queryParam("chunk");
            if (chunkParam != null && !chunkParam.isEmpty()) {
                try {
                    chunk = Integer.parseInt(chunkParam.trim());
                } catch (NumberFormatException e) {
                    JadxAIMCPPluginError.handleError(ctx, 400, "Invalid chunk parameter: " + chunkParam, logger);
                    return;
                }
            }

            String className = getSelectedTabTitle();
            String code = extractTextFromCurrentTab();

            // Use SmartChunker for large responses
            Map<String, Object> result = com.zin.jadxaimcp.utils.SmartChunker.chunkResponse(
                code != null ? code : "", chunk, "content");
            
            result.put("name", className != null ? className.replace(".java", "") : "unknown");
            result.put("type", "code/java");

            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal Error while trying to fetch current class class: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @return
     * @param Context
     * 
     *                This routing method returns all classes decompiled from apk by
     *                jadx
     *                It first fetches the list of JavaClass classes using
     *                JadxWrapper.
     *                Then it combines this JavaClass list into Map and uses
     *                pagination utils to return the
     *                details of all classes.
     */
    public void handleAllClasses(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<JavaClass> classes = wrapper.getIncludedClassesWithInners();

            Map<String, Object> result = paginationUtils.handlePagination(
                    ctx,
                    classes,
                    "class-list",
                    "classes",
                    JavaClass::getFullName);
            ctx.json(result);
        } catch (PaginationException e) {
            JadxAIMCPPluginError.handleError(ctx, "Pagination Error: " + e.getMessage(), e, logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Failed to load class list: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @param Context
     * @return
     * 
     *         This routing method handles the /selected-text api call
     *         it first gets the currently selecte UI component using MainWindow's
     *         methods
     *         Then it find the text area from the currently active UI component,
     *         this text area
     *         holds the selected text.
     * 
     *         From this text area, it fetches the selected text using
     *         getSelectedText() method and
     *         returns this using Map and ctx.
     */
    public void handleSelectedText(Context ctx) {
        try {
            Component selectedComponent = mainWindow.getTabbedPane().getSelectedComponent();
            JTextArea textArea = findTextArea(selectedComponent);
            String selectedText = textArea != null ? textArea.getSelectedText() : null;

            Map<String, String> result = new HashMap<>();
            result.put("selectedText", selectedText != null ? selectedText : "");
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error while trying to fetch selected text: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @param Context
     * @return void
     * 
     *         This routing method handles the /class-source MCP tool call
     *         First it checks for request validity, the check is availability of
     *         'class' parameter in http request, then it fetches the source code of
     *         the class
     *         by fetching the classes one by one and compares it with the requested
     *         class name, if
     *         it matches returns the requested classe's code.
     *         
     *         Supports chunking for large responses:
     *         - chunk=0 or not specified: Returns first chunk with metadata
     *         - chunk=N: Returns the Nth chunk
     *         
     *         Responses larger than 8KB are automatically chunked to prevent
     *         truncation by MCP clients.
     */
    public void handleClassSource(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

        // Parse chunk parameter (0 = first chunk with metadata, N = specific chunk)
        int chunk = 0;
        String chunkParam = ctx.queryParam("chunk");
        if (chunkParam != null && !chunkParam.isEmpty()) {
            try {
                chunk = Integer.parseInt(chunkParam.trim());
            } catch (NumberFormatException e) {
                JadxAIMCPPluginError.handleError(ctx, 400, "Invalid chunk parameter: " + chunkParam, logger);
                return;
            }
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            JavaClass targetClass = findClassByName(wrapper, className);
            String cacheKey = targetClass != null ? targetClass.getFullName() : className;

            // Check decompiled code cache first (no lock needed for cache read)
            String code = ClassCacheManager.getCachedCode(cacheKey);
            if (code != null) {
                Map<String, Object> result = com.zin.jadxaimcp.utils.SmartChunker.chunkResponse(
                    code, chunk, "response");
                if (result.containsKey("error")) {
                    JadxAIMCPPluginError.handleError(ctx, 400, (String) result.get("error"), logger);
                    return;
                }
                ctx.json(result);
                return;
            }

            // Decompilation requires write lock (JADX internal state is not thread-safe)
            if (!JadxSearchLock.tryAcquire()) {
                ctx.status(503).json(Map.of(
                    "error", "Decompilation operation in progress",
                    "retry_after", JadxSearchLock.RETRY_AFTER_SECONDS
                ));
                return;
            }
            try {
                // Re-check cache after acquiring lock (another thread may have decompiled it)
                code = ClassCacheManager.getCachedCode(cacheKey);
                if (code == null) {
                    if (targetClass == null) {
                        targetClass = findClassByName(wrapper, className);
                    }
                    if (targetClass != null) {
                        code = targetClass.getCode();
                        ClassCacheManager.putCachedCode(targetClass.getFullName(), code);
                    }
                }
            } finally {
                JadxSearchLock.release();
            }

            if (code == null) {
                ctx.status(404).json(Map.of("error", "Class " + className + " not found"));
                return;
            }

            Map<String, Object> result = com.zin.jadxaimcp.utils.SmartChunker.chunkResponse(
                code, chunk, "response");
            if (result.containsKey("error")) {
                JadxAIMCPPluginError.handleError(ctx, 400, (String) result.get("error"), logger);
                return;
            }
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving class source: " + e.getMessage(), e,
                    logger);
        }
    }

    /**
     * @param Context
     * @return void
     * 
     *         This routing method handles the /batch-class-source MCP tool call.
     *         Allows fetching multiple class sources in a single request to reduce
     *         MCP interaction overhead.
     * 
     *         Request parameters:
     *         - class_names (required): Comma-separated list of fully qualified class names
     *           Example: com.example.A,com.example.B,com.example.C
     * 
     *         Returns a JSON object with:
     *         - classes: Array of objects containing name, found, and content/error
     *         - total: Total number of requested classes
     *         - found: Number of classes successfully found
     * 
     *         Max limit: 20 classes per request to prevent performance issues.
     */
    public void handleBatchClassSource(Context ctx) {
        String classNamesParam = ctx.queryParam("class_names");
        if (classNamesParam == null || classNamesParam.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing 'class_names' parameter. Provide comma-separated class names.", logger);
            return;
        }

        // Parse chunk parameter for large response handling
        int chunk = 0;
        String chunkParam = ctx.queryParam("chunk");
        if (chunkParam != null && !chunkParam.isEmpty()) {
            try {
                chunk = Integer.parseInt(chunkParam.trim());
            } catch (NumberFormatException e) {
                JadxAIMCPPluginError.handleError(ctx, 400, "Invalid chunk parameter: " + chunkParam, logger);
                return;
            }
        }

        String[] classNames = classNamesParam.split(",");
        
        // Limit to prevent performance issues
        final int MAX_BATCH_SIZE = 20;
        if (classNames.length > MAX_BATCH_SIZE) {
            JadxAIMCPPluginError.handleError(ctx, 400, 
                "Too many classes requested. Maximum " + MAX_BATCH_SIZE + " classes per request.", logger);
            return;
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            
            // Initialize cache if not already done
            if (ClassCacheManager.getStatus() == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
            }
            
            // Check cache status
            ClassCacheManager.CacheStatus status = ClassCacheManager.getStatus();
            if (status == ClassCacheManager.CacheStatus.LOADING) {
                // Return loading status with comprehensive health info
                Map<String, Object> health = ClassCacheManager.getHealthInfo();
                Map<String, Object> response = new HashMap<>();
                response.put("status", "loading");
                response.put("type", "batch-class-source");
                response.put("message", "Class cache is being loaded in background. First load takes ~30-60 seconds for large APKs.");
                response.put("retry_after", 10); // Suggest retry after 10 seconds
                response.put("health", health);
                
                // Add user-friendly guidance
                long elapsed = health.containsKey("elapsed_seconds") ? ((Number) health.get("elapsed_seconds")).longValue() : 0;
                if (elapsed > 0) {
                    response.put("estimated_remaining", "~" + Math.max(0, 40 - elapsed) + " seconds");
                }
                
                ctx.json(response);
                return;
            }
            
            // Get the cached class map
            Map<String, JavaClass> classMap = ClassCacheManager.getCache();

            List<Map<String, Object>> results = new ArrayList<>();
            int foundCount = 0;

            // Collect classes that need decompilation (cache miss)
            List<String> needDecompile = new ArrayList<>();
            Map<String, String> cachedResults = new HashMap<>();
            Map<String, JavaClass> resolvedClasses = new HashMap<>();

            for (String className : classNames) {
                String trimmedName = className.trim();
                JavaClass resolvedClass = ClassCacheManager.findClass(classMap, trimmedName);
                if (resolvedClass != null) {
                    resolvedClasses.put(trimmedName, resolvedClass);
                }

                String cacheKey = resolvedClass != null ? resolvedClass.getFullName() : trimmedName;
                String cachedCode = ClassCacheManager.getCachedCode(cacheKey);
                if (cachedCode != null) {
                    cachedResults.put(trimmedName, cachedCode);
                } else if (resolvedClass != null) {
                    needDecompile.add(trimmedName);
                }
            }

            // Decompile cache-missed classes under write lock
            Map<String, String> decompiledResults = new HashMap<>();
            if (!needDecompile.isEmpty()) {
                if (!JadxSearchLock.tryAcquire()) {
                    ctx.status(503).json(Map.of(
                        "error", "Decompilation operation in progress",
                        "retry_after", JadxSearchLock.RETRY_AFTER_SECONDS
                    ));
                    return;
                }
                try {
                    for (String name : needDecompile) {
                        // Re-check cache (another thread may have decompiled it)
                        String code = ClassCacheManager.getCachedCode(name);
                        if (code != null) {
                            decompiledResults.put(name, code);
                            continue;
                        }
                        JavaClass cls = resolvedClasses.get(name);
                        if (cls != null) {
                            try {
                                code = cls.getCode();
                                ClassCacheManager.putCachedCode(cls.getFullName(), code);
                                decompiledResults.put(name, code);
                            } catch (Exception e) {
                                logger.error("Decompilation failed for {}: {}", name, e.getMessage());
                                decompiledResults.put(name, null); // mark as failed
                            }
                        }
                    }
                } finally {
                    JadxSearchLock.release();
                }
            }

            // Build response
            for (String className : classNames) {
                String trimmedName = className.trim();
                Map<String, Object> classResult = new HashMap<>();
                classResult.put("name", trimmedName);

                if (cachedResults.containsKey(trimmedName)) {
                    classResult.put("found", true);
                    classResult.put("content", cachedResults.get(trimmedName));
                    foundCount++;
                } else if (decompiledResults.containsKey(trimmedName)) {
                    String code = decompiledResults.get(trimmedName);
                    if (code != null) {
                        classResult.put("found", true);
                        classResult.put("content", code);
                        foundCount++;
                    } else {
                        classResult.put("found", true);
                        classResult.put("error", "Decompilation failed (see server log)");
                    }
                } else if (!resolvedClasses.containsKey(trimmedName)) {
                    classResult.put("found", false);
                    classResult.put("error", "Class not found");
                } else {
                    // Class exists in classMap but was not decompiled (should not happen)
                    classResult.put("found", false);
                    classResult.put("error", "Decompilation not attempted");
                }
                results.add(classResult);
            }

            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("classes", results);
            response.put("total", classNames.length);
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

            ctx.json(chunkedResponse);

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving batch class sources: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @param Context
     * @return void
     * 
     *         This routing method handles the /methods-of-class endpoint.
     *         First it checks whether the 'class_name' parameter is present or not
     *         in http request
     *         then it iterates over each class present in jadx, and matches it for
     *         the `class_name`'s value
     *         Then once the requested class is found, it iterates over the methods
     *         of that class and gathers
     *         their details.
     * 
     *         After gathering the details it returns the methods details.
     */
     public void handleMethodsOfClass(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

        // Removing this line to solve issue #37 as raised and contributed by
        // github@ljt270864457
        // This solves following bug -> Bug: Inner classes with $ symbol cannot be
        // retrieved via /methods-of-class endpoint
        // className = className.replace('$', '.');

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            JavaClass cls = findClassByName(wrapper, className);
            if (cls != null) {
                // First pass: count overloads for each method name
                Map<String, Integer> overloadCounts = new HashMap<>();
                for (JavaMethod method : cls.getMethods()) {
                    String name = method.getName();
                    overloadCounts.put(name, overloadCounts.getOrDefault(name, 0) + 1);
                }

                // Second pass: build method info list
                List<Map<String, Object>> methodsList = new ArrayList<>();
                for (JavaMethod method : cls.getMethods()) {
                    Map<String, Object> methodInfo = new HashMap<>();
                    methodInfo.put("name", method.getName());
                    methodInfo.put("raw_name", JadxApiAdapter.getMethodRawName(method));
                    methodInfo.put("full_id", JadxApiAdapter.getMethodFullId(method));
                    methodInfo.put("raw_full_id", JadxApiAdapter.getMethodRawFullId(method));

                    AccessInfo accessFlags = method.getAccessFlags();
                    if (accessFlags != null) {
                        methodInfo.put("is_static", accessFlags.isStatic());
                        methodInfo.put("is_native", accessFlags.isNative());
                        methodInfo.put("is_abstract", accessFlags.isAbstract());
                        methodInfo.put("is_synchronized", accessFlags.isSynchronized());

                        // Access modifiers list
                        List<String> modifiers = new ArrayList<>();
                        if (accessFlags.isPublic()) modifiers.add("public");
                        if (accessFlags.isPrivate()) modifiers.add("private");
                        if (accessFlags.isProtected()) modifiers.add("protected");
                        if (accessFlags.isStatic()) modifiers.add("static");
                        if (accessFlags.isNative()) modifiers.add("native");
                        if (accessFlags.isAbstract()) modifiers.add("abstract");
                        if (accessFlags.isSynchronized()) modifiers.add("synchronized");
                        if (accessFlags.isFinal()) modifiers.add("final");
                        methodInfo.put("modifiers", modifiers);
                    } else {
                        methodInfo.put("is_static", false);
                        methodInfo.put("is_native", false);
                        methodInfo.put("is_abstract", false);
                        methodInfo.put("is_synchronized", false);
                        methodInfo.put("modifiers", new ArrayList<>());
                    }

                    methodInfo.put("is_constructor", method.isConstructor());
                    methodInfo.put("overload_count", overloadCounts.get(method.getName()));

                    // Return type
                    String returnType = method.getReturnType() != null ?
                        method.getReturnType().toString() : "void";
                    methodInfo.put("return_type", returnType);

                    methodsList.add(methodInfo);
                }

                Map<String, Object> response = new HashMap<>();
                response.put("class_name", cls.getFullName());
                response.put("raw_class_name", cls.getRawName());
                response.put("methods", methodsList);
                response.put("count", methodsList.size());

                ctx.json(response);
                return;
            }
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving methods: " + e.getMessage(), e, logger);
        }
    }


    /**
     * @param Context
     * @return void
     * 
     *         This routing method handles the /fields-of-class mcp tool call
     *         After checking for presence of 'class_name' parameter, it finds the
     *         class with
     *         'class_name' name, after finding the requested class, it fetches the
     *         fields of class
     *         starts gathering their details.
     * 
     *         Then it return these details.
     */
    public void handleFieldsOfClass(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            JavaClass cls = findClassByName(wrapper, className);
            if (cls != null) {
                List<Map<String, Object>> fieldsList = new ArrayList<>();

                for (JavaField field : cls.getFields()) {
                    Map<String, Object> fieldInfo = new HashMap<>();
                    fieldInfo.put("name", field.getName());
                    fieldInfo.put("raw_name", field.getRawName());
                    fieldInfo.put("raw_full_id", JadxApiAdapter.getFieldRawFullId(field));

                    // Type information
                    String typeStr = field.getType() != null ? field.getType().toString() : "unknown";
                    fieldInfo.put("type", typeStr);

                    // Frida-compatible type
                    if (field.getType() != null) {
                        fieldInfo.put("type_frida",
                            com.zin.jadxaimcp.utils.FridaTypeConverter.toFridaType(field.getType()));
                    } else {
                        fieldInfo.put("type_frida", typeStr);
                    }

                    // Access modifiers
                    AccessInfo accessFlags = field.getAccessFlags();
                    List<String> modifiers = new ArrayList<>();
                    if (accessFlags.isPublic()) modifiers.add("public");
                    if (accessFlags.isPrivate()) modifiers.add("private");
                    if (accessFlags.isProtected()) modifiers.add("protected");
                    if (accessFlags.isStatic()) modifiers.add("static");
                    if (accessFlags.isFinal()) modifiers.add("final");
                    if (accessFlags.isVolatile()) modifiers.add("volatile");
                    if (accessFlags.isTransient()) modifiers.add("transient");

                    fieldInfo.put("modifiers", modifiers);
                    fieldInfo.put("is_static", accessFlags.isStatic());
                    fieldInfo.put("is_final", accessFlags.isFinal());

                    fieldsList.add(fieldInfo);
                }

                Map<String, Object> response = new HashMap<>();
                response.put("class_name", cls.getFullName());
                response.put("raw_class_name", cls.getRawName());
                response.put("fields", fieldsList);
                response.put("count", fieldsList.size());

                ctx.json(response);
                return;
            }
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving fields: " + e.getMessage(), e, logger);
        }
    }


    /**
     * @param Context
     * @return void
     * 
     *         This routing method handles the /smali-of-class mcp tool call
     *         After checking for availability of 'class' parameter in request, it
     *         finds that class,
     *         After finding that class it fetch smali of that class and returns it.
     *         
     *         Note: Smali is only available for APK/DEX files, not JAR files.
     *         
     *         Supports chunking for large responses:
     *         - chunk=0 or not specified: Returns first chunk with metadata
     *         - chunk=N: Returns the Nth chunk
     *         
     *         Smali output is typically large (>8KB for classes with 10+ methods).
     *         Automatic chunking prevents truncation by MCP clients.
     */
    public void handleSmaliOfClass(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

        // Parse chunk parameter (0 = first chunk with metadata, N = specific chunk)
        int chunk = 0;
        String chunkParam = ctx.queryParam("chunk");
        if (chunkParam != null && !chunkParam.isEmpty()) {
            try {
                chunk = Integer.parseInt(chunkParam.trim());
            } catch (NumberFormatException e) {
                JadxAIMCPPluginError.handleError(ctx, 400, "Invalid chunk parameter: " + chunkParam, logger);
                return;
            }
        }

        boolean lockAcquired = false;
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            
            // Check file type - Smali only available for DEX-based files
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType = 
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(wrapper);
            if (!fileType.isSmaliAvailable()) {
                com.zin.jadxaimcp.utils.NotApplicableResponse.sendSmaliNotAvailable(
                    ctx, fileType.getPrimaryType().getName());
                return;
            }

            if (!JadxSearchLock.tryAcquire()) {
                sendSearchDecompilationBusyResponse(ctx);
                return;
            }
            lockAcquired = true;
            
            JavaClass cls = findClassByName(wrapper, className);
            if (cls != null) {
                String smali = cls.getSmali();
                if (smali == null || smali.isEmpty()) {
                    // Smali generation failed even though file type says it should work
                    JadxAIMCPPluginError.handleError(ctx, 404,
                        "Smali generation returned empty for class " + className +
                        ". This may indicate the class was loaded from a non-DEX source.", logger);
                    return;
                }

                // Use SmartChunker for automatic chunking of large Smali responses
                Map<String, Object> result = com.zin.jadxaimcp.utils.SmartChunker.chunkResponse(
                    smali, chunk, "response");

                // Check for chunking errors
                if (result.containsKey("error")) {
                    JadxAIMCPPluginError.handleError(ctx, 400, (String) result.get("error"), logger);
                    return;
                }

                ctx.json(result);
                return;
            }
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving smali: " + e.getMessage(), e, logger);
        } finally {
            if (lockAcquired) {
                JadxSearchLock.release();
            }
        }
    }

    /**
     * @param Context
     * @return void
     * 
     *         This routing method handles the /class-info MCP tool call.
     *         Returns structured information about a class including:
     *         - Super class name
     *         - Implemented interfaces
     *         - Access modifiers (public, abstract, final, etc.)
     *         - Method and field counts
     *         - Inner classes
     */
    public void handleClassInfo(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            JavaClass cls = findClassByName(wrapper, className);
            if (cls != null) {
                Map<String, Object> info = new HashMap<>();
                info.put("class_name", cls.getFullName());
                info.put("raw_class_name", cls.getRawName());
                info.put("simple_name", cls.getName());
                info.put("raw_simple_name", JadxApiAdapter.getClassRawSimpleName(cls));
                info.put("package", cls.getPackage());
                    
                // Access modifiers - metadata-only lookup via the adapter.
                try {
                    jadx.core.dex.info.AccessInfo accessInfo = JadxApiAdapter.getAccessFlags(cls);
                    if (accessInfo != null) {
                        info.put("access_flags", accessInfo.toString());
                        info.put("is_interface", accessInfo.isInterface());
                        info.put("is_enum", accessInfo.isEnum());
                        info.put("is_abstract", accessInfo.isAbstract());
                        info.put("is_final", accessInfo.isFinal());
                    } else {
                        info.put("access_flags", "unknown");
                        info.put("is_interface", false);
                        info.put("is_enum", false);
                        info.put("is_abstract", false);
                        info.put("is_final", false);
                    }
                } catch (Exception e) {
                    info.put("access_flags", "unknown");
                    info.put("is_interface", false);
                    info.put("is_enum", false);
                    info.put("is_abstract", false);
                    info.put("is_final", false);
                }
                info.put("is_inner", cls.isInner());
                    
                // Super class - metadata-only lookup via the adapter.
                try {
                    String superClass = JadxApiAdapter.getSuperClass(cls);
                    if (superClass != null) {
                        info.put("super_class", superClass);
                    } else {
                        info.put("super_class", "java.lang.Object");
                    }
                } catch (Exception e) {
                    info.put("super_class", "java.lang.Object");
                }

                // Interfaces
                List<String> interfaces = new ArrayList<>();
                try {
                    interfaces.addAll(JadxApiAdapter.getInterfaces(cls));
                } catch (Exception e) {
                    logger.warn("Failed to get interfaces for {}: {}", className, e.getMessage());
                }
                info.put("interfaces", interfaces);

                // Inner classes
                List<String> innerClasses = new ArrayList<>();
                try {
                    for (JavaClass inner : cls.getInnerClasses()) {
                        innerClasses.add(inner.getFullName());
                    }
                } catch (Exception e) {
                    logger.warn("Failed to get inner classes for {}: {}", className, e.getMessage());
                }
                info.put("inner_classes", innerClasses);

                List<JadxApiAdapter.MethodInfoSnapshot> declaredMethods =
                    JadxApiAdapter.getDeclaredMethodInfos(cls);
                List<JadxApiAdapter.FieldInfoSnapshot> declaredFields =
                    JadxApiAdapter.getDeclaredFieldInfos(cls);

                info.put("methods_count", declaredMethods.size());
                info.put("fields_count", declaredFields.size());

                List<String> methodNames = new ArrayList<>();
                List<String> rawMethodNames = new ArrayList<>();
                List<String> nativeMethodNames = new ArrayList<>();
                for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : declaredMethods) {
                    String rawName = methodSnapshot.getRawName();
                    String aliasName = methodSnapshot.getAliasName() != null
                        ? methodSnapshot.getAliasName()
                        : rawName;
                    methodNames.add(aliasName);
                    rawMethodNames.add(rawName);
                    if (methodSnapshot.getAccessFlags() != null && methodSnapshot.getAccessFlags().isNative()) {
                        nativeMethodNames.add(rawName);
                    }
                }
                info.put("method_names", methodNames);
                info.put("raw_method_names", rawMethodNames);
                info.put("native_method_names", nativeMethodNames);
                info.put("native_count", nativeMethodNames.size());

                List<String> fieldNames = new ArrayList<>();
                List<String> rawFieldNames = new ArrayList<>();
                for (JadxApiAdapter.FieldInfoSnapshot fieldSnapshot : declaredFields) {
                    fieldNames.add(fieldSnapshot.getAliasName() != null
                        ? fieldSnapshot.getAliasName()
                        : fieldSnapshot.getRawName());
                    rawFieldNames.add(fieldSnapshot.getRawName());
                }
                info.put("field_names", fieldNames);
                info.put("raw_field_names", rawFieldNames);

                ctx.json(info);
                return;
            }
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving class info: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @return void
     * @param Context
     * 
     *                This routing method handle the /main-activity mcp tool call.
     *                1. It gets the manifest file
     *                2. It gets the manifest file parser
     *                3. It parses the manifest file and fetches the name of the
     *                Main Activity class
     *                4. It gets the Main Activity class code and returns it.
     *                
     *                Note: Only available for APK/AAR files with AndroidManifest.xml
     */
    public void handleMainActivity(Context ctx) {
        boolean lockAcquired = false;
        try {
            // Parse chunk parameter
            int chunk = 0;
            String chunkParam = ctx.queryParam("chunk");
            if (chunkParam != null && !chunkParam.isEmpty()) {
                try {
                    chunk = Integer.parseInt(chunkParam.trim());
                } catch (NumberFormatException e) {
                    JadxAIMCPPluginError.handleError(ctx, 400, "Invalid chunk parameter: " + chunkParam, logger);
                    return;
                }
            }

            JadxWrapper wrapper = mainWindow.getWrapper();
            
            // Check file type - Main Activity only available for Android files
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType = 
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(wrapper);
            if (!fileType.hasAndroidFeatures()) {
                com.zin.jadxaimcp.utils.NotApplicableResponse.sendMainActivityNotAvailable(
                    ctx, fileType.getPrimaryType().getName());
                return;
            }
            
            ResourceFile manifestRes = AndroidManifestParser.getAndroidManifest(mainWindow.getWrapper().getResources());
            if (manifestRes == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "AndroidManifest.xml not found", logger);
                return;
            }

            AndroidManifestParser parser = new AndroidManifestParser(
                    manifestRes,
                    EnumSet.of(AppAttribute.MAIN_ACTIVITY),
                    wrapper.getArgs().getSecurity());

            if (!parser.isManifestFound()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "AndroidManifest.xml not found.", logger);
                return;
            }

            ApplicationParams results = parser.parse();
            if (results.getMainActivity() == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Failed to get main activity from manifest.", logger);
                return;
            }

            JavaClass mainActivityClass = results.getMainActivityJavaClass(wrapper.getDecompiler());
            if (mainActivityClass == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Failed to get activity class: " + results.getApplication(),
                        logger);
                return;
            }

            if (!JadxSearchLock.tryAcquire()) {
                sendSearchDecompilationBusyResponse(ctx);
                return;
            }
            lockAcquired = true;

            // Use SmartChunker for large responses
            String code = mainActivityClass.getCode();
            Map<String, Object> result = com.zin.jadxaimcp.utils.SmartChunker.chunkResponse(
                code, chunk, "content");
            result.put("name", mainActivityClass.getFullName());
            result.put("type", "code/java");
            
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error occurred while trying to get the Main Activity class code: " + e.getMessage(), e,
                    logger);
        } finally {
            if (lockAcquired) {
                JadxSearchLock.release();
            }
        }
    }

    /**
     * @return void
     * @param Context
     * 
     *                This method handles the /main-application-classes-names mcp
     *                tool call.
     * 
     *                First goal is to get the package name, to get this first it
     *                gets the manifest file.
     *                Then parses it and get's the package name from it. Then get
     *                all the decompiled classes and
     *                filter them under the package name of main applcaiton. After
     *                filtering classes, build a dictionary
     *                of them and return them.
     */
    public void handleMainApplicationClassesNames(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<ResourceFile> resources = wrapper.getResources();

            // get the manifest resource file
            ResourceFile manifestRes = AndroidManifestParser.getAndroidManifest(resources);
            if (manifestRes == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "AndroidManifest.xml not found.", logger);
                return;
            }

            // load manifest content and parse xml
            String manifestXml = manifestRes.loadContent()
                    .getText()
                    .getCodeStr();
            Document manifestDoc = parseManifestXml(manifestXml, wrapper.getArgs().getSecurity());

            // Extract the package name from the <manifest> tag
            Element manifestElement = (Element) manifestDoc.getElementsByTagName("manifest").item(0);
            String packageName = manifestElement.getAttribute("package");

            if (packageName.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Package name not found in AndroiManifest.xml", logger);
                return;
            }

            // Changed the getClasses() to getClassesWithInners()
            List<JavaClass> matchedClasses = wrapper.getDecompiler()
                    .getClassesWithInners()
                    .stream()
                    .filter(cls -> cls.getFullName().startsWith(packageName))
                    .collect(Collectors.toList());

            List<Map<String, Object>> classesInfo = new ArrayList<>();
            for (JavaClass cls : matchedClasses) {
                Map<String, Object> classInfo = new HashMap<>();
                classInfo.put("name", cls.getFullName());
                classesInfo.add(classInfo);
            }

            Map<String, Object> result = new HashMap<>();
            result.put("classes", classesInfo);
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error while trying to fetch all classes names: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @param Context
     * @return void
     * 
     *         This routing method handles the /main-application-classes-code MCP
     *         tool call.
     *         1. It retrieves the AndroidManifest.xml resource file
     *         2. It parses the manifest XML to extract the application's package
     *         name
     *         3. It filters all decompiled classes (including inner classes) that
     *         belong to the main package
     *         4. For each matched class, it builds a map containing:
     *         - Class full name
     *         - Content type (code/java)
     *         - Decompiled source code (or error message if decompilation fails)
     *         5. It applies pagination to the collected class information
     *         6. It returns the paginated result containing class details with
     *         their source code
     * 
     *         Note: This method handles decompilation errors gracefully by
     *         including error messages
     *         in the content field instead of failing the entire request.
     */
    public void handleMainApplicationClassesCode(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<ResourceFile> resources = wrapper.getResources();

            // get the manifest resource file
            ResourceFile manifestRes = AndroidManifestParser.getAndroidManifest(resources);
            if (manifestRes == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "AndroidManifest.xml not found.", logger);
                return;
            }

            // load manifest content and parse xml
            String manifestXml = manifestRes.loadContent()
                    .getText()
                    .getCodeStr();
            Document manifestDoc = parseManifestXml(manifestXml, wrapper.getArgs().getSecurity());

            // Extract the package name from the <manifest> tag
            Element manifestElement = (Element) manifestDoc.getElementsByTagName("manifest").item(0);
            String packageName = manifestElement.getAttribute("package");

            if (packageName.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Package name not found in AndroiManifest.xml", logger);
                return;
            }

            logger.info("JADX AI MCP: Package name: " + packageName);
            // filter classes under this package
            // Changed the getClasses() to getClassesWithInners()
            List<JavaClass> matchedClasses = wrapper.getDecompiler()
                    .getClassesWithInners()
                    .stream()
                    .filter(cls -> cls.getFullName().startsWith(packageName))
                    .collect(Collectors.toList());

            logger.info("JADX AI MCP: Found " + matchedClasses.size() + " classes in package " + packageName);
            logger.info("JADX AI MCP: Request params - offset: " + ctx.queryParam("offset") +
                    ", limit: " + ctx.queryParam("limit") +
                    ", count: " + ctx.queryParam("count"));

            PaginationWindow paginationWindow = resolvePaginationWindow(ctx, matchedClasses.size());

            // Build list of class info maps only for the requested page
            List<Map<String, Object>> classInfoList = new ArrayList<>();
            if (paginationWindow.hasResults()) {
                if (!JadxSearchLock.tryAcquire()) {
                    sendSearchDecompilationBusyResponse(ctx);
                    return;
                }

                try {
                    for (JavaClass cls : matchedClasses.subList(
                            paginationWindow.getStartIndex(),
                            paginationWindow.getEndIndex())) {
                        Map<String, Object> classInfo = new HashMap<>();
                        classInfo.put("name", cls.getFullName());
                        classInfo.put("type", "code/java");
                        try {
                            String code = cls.getCode();
                            classInfo.put("content", code);
                            logger.debug("JADX AI MCP: Successfully got code for " + cls.getFullName() +
                                    " (length: " + code.length() + ")");
                        } catch (Exception e) {
                            logger.warn("Failed to decompile class " + cls.getFullName() + ": " + e.getMessage());
                            classInfo.put("content", "// Error decompiling class: " + e.getMessage());
                        }
                        classInfoList.add(classInfo);
                    }
                } finally {
                    JadxSearchLock.release();
                }
            }

            logger.info("JADX AI MCP: Built " + classInfoList.size() + " class info objects");

            Map<String, Object> result = buildPaginatedResponse(
                    classInfoList,
                    matchedClasses.size(),
                    paginationWindow,
                    "application-classes",
                    "classes");

            ctx.json(result);
        } catch (PaginationException e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error while generating pagination result for handleMainApplicationClassesCode: "
                            + e.getMessage(),
                    e, logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error occurred while retrieving main application classes' code: " + e.getMessage(), e,
                    logger);
        }
    }

    /**
     * @return void
     * @param Context
     * 
     *                This method handles the call for /search-classes-by-keyword
     *                mcp tool.
     * 
     *                Request parameters:
     *                - search_term (required): The keyword to search for
     *                - package (optional): Limit search to specific package (e.g.,
     *                "com.example.app")
     *                Note: Package filtering is disabled for jadx obfuscated
     *                packages (p000, p001, etc.)
     *                - search_in (optional): Comma-separated list of search
     *                locations. Valid values:
     *                CLASS_NAME, METHOD_NAME, FIELD_NAME, CODE, RESOURCE, COMMENT
     *                Default: CODE
     * 
     *                The method searches for the keyword in specified locations and
     *                returns deduplicated class list.
     */
    public void handleSearchClassesByKeyword(Context ctx) {
        String searchTerm = ctx.queryParam("search_term");
        if (searchTerm == null || searchTerm.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing 'search_term' parameter.", logger);
            return;
        }

        // Parse optional package filter parameter
        String packageFilter = ctx.queryParam("package");
        String searchInParam = ctx.queryParam("search_in");
        
        // Parse optional exclude parameter
        String excludeParam = ctx.queryParam("exclude");
        List<String> excludePrefixes = new ArrayList<>();
        if (excludeParam != null && !excludeParam.isEmpty()) {
            for (String prefix : excludeParam.split(",")) {
                String trimmed = prefix.trim();
                if (!trimmed.isEmpty()) {
                    excludePrefixes.add(trimmed);
                }
            }
        }

        // Parse search locations, default to CODE if not specified
        Set<SearchLocation> searchLocations = parseSearchLocations(searchInParam);
        
        // Check if code/comment search (requires getCode() - expensive)
        boolean isCodeSearch = searchLocations.contains(SearchLocation.CODE) 
            || searchLocations.contains(SearchLocation.COMMENT);
        
        // Parse pagination parameters - limit results per page
        int offset = paginationUtils.getIntParam(ctx, "offset", 0);
        int count = paginationUtils.getIntParam(ctx, "count", DEFAULT_RESULT_LIMIT);
        count = Math.min(count, MAX_RESULT_LIMIT);

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();
            List<JavaClass> filteredClasses = filterSearchClasses(allClasses, packageFilter, excludePrefixes);

            if (isCodeSearch) {
                handleCoordinatedCodeSearch(
                    ctx,
                    wrapper,
                    allClasses,
                    filteredClasses,
                    searchTerm,
                    packageFilter,
                    excludeParam,
                    searchInParam,
                    searchLocations,
                    offset,
                    count
                );
                return;
            }

            SearchExecution searchExecution = executeSearch(
                wrapper,
                allClasses,
                filteredClasses,
                searchTerm,
                searchLocations,
                false,
                offset + count + 1
            );
            ctx.json(buildSearchResponse(searchExecution.getResult(), offset, count));
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error in search: " + e.getMessage(), e, logger);
        }
    }

    private void handleCoordinatedCodeSearch(
        Context ctx,
        JadxWrapper wrapper,
        List<JavaClass> allClasses,
        List<JavaClass> filteredClasses,
        String searchTerm,
        String packageFilter,
        String excludeParam,
        String searchInParam,
        Set<SearchLocation> searchLocations,
        int offset,
        int count
    ) throws Exception {
        CodeSearchCoordinator.SearchReservation reservation = CodeSearchCoordinator.reserve(
            wrapper,
            searchTerm,
            packageFilter,
            excludeParam,
            searchInParam
        );

        if (reservation.hasCachedResult()) {
            ctx.json(buildSearchResponse(reservation.getCachedResult(), offset, count));
            return;
        }

        if (reservation.isFollower()) {
            try {
                CodeSearchCoordinator.SearchResult result = reservation.getFuture()
                    .get(SEARCH_TIMEOUT_SECONDS, TimeUnit.SECONDS);
                ctx.json(buildSearchResponse(result, offset, count));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                sendCodeSearchBusyResponse(ctx, "Search request interrupted while waiting for in-flight result", 0.0);
            } catch (ExecutionException | TimeoutException e) {
                sendCodeSearchBusyResponse(ctx, "Search operation in progress", SEARCH_TIMEOUT_SECONDS);
            }
            return;
        }

        CompletableFuture<CodeSearchCoordinator.SearchResult> future = reservation.getFuture();
        CodeSearchCoordinator.SearchKey key = reservation.getKey();
        if (future == null || key == null) {
            sendCodeSearchBusyResponse(ctx, "Search coordinator state is unavailable", 0.0);
            return;
        }

        if (!JadxSearchLock.tryAcquire()) {
            CodeSearchCoordinator.completeFailure(
                key,
                future,
                new IllegalStateException("Search operation in progress")
            );
            sendCodeSearchBusyResponse(ctx, "Search operation in progress", 0.0);
            return;
        }

        try {
            SearchExecution execution = executeSearch(
                wrapper,
                allClasses,
                filteredClasses,
                searchTerm,
                searchLocations,
                true,
                Integer.MAX_VALUE
            );
            if (execution.isTimedOut()) {
                CodeSearchCoordinator.completeFailure(
                    key,
                    future,
                    new TimeoutException("Code search exceeded timeout window")
                );
            } else {
                CodeSearchCoordinator.completeSuccess(
                    key,
                    future,
                    execution.getResult(),
                    execution.getElapsedMs()
                );
            }
            ctx.json(buildSearchResponse(execution.getResult(), offset, count));
        } catch (Exception e) {
            CodeSearchCoordinator.completeFailure(key, future, e);
            throw e;
        } finally {
            JadxSearchLock.release();
        }
    }

    private List<JavaClass> filterSearchClasses(
        List<JavaClass> allClasses,
        String packageFilter,
        List<String> excludePrefixes
    ) {
        boolean applyPackageFilter = isValidPackageFilter(packageFilter);
        if (!applyPackageFilter && excludePrefixes.isEmpty()) {
            return allClasses;
        }

        List<JavaClass> filteredClasses = new ArrayList<>();
        for (JavaClass cls : allClasses) {
            if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                continue;
            }
            if (!excludePrefixes.isEmpty()) {
                boolean excluded = false;
                for (String prefix : excludePrefixes) {
                    if (cls.getFullName().startsWith(prefix)) {
                        excluded = true;
                        break;
                    }
                }
                if (excluded) {
                    continue;
                }
            }
            filteredClasses.add(cls);
        }
        return filteredClasses;
    }

    private SearchExecution executeSearch(
        JadxWrapper wrapper,
        List<JavaClass> allClasses,
        List<JavaClass> filteredClasses,
        String searchTerm,
        Set<SearchLocation> searchLocations,
        boolean collectAllResults,
        int resultsNeeded
    ) {
        final String term = searchTerm.toLowerCase();
        final Set<String> matchedClasses = ConcurrentHashMap.newKeySet();
        final AtomicInteger totalMatches = new AtomicInteger(0);
        final AtomicBoolean cancelled = new AtomicBoolean(false);

        long startTimeMs = System.currentTimeMillis();
        long deadlineNanos = System.nanoTime() + TimeUnit.SECONDS.toNanos(SEARCH_TIMEOUT_SECONDS);
        boolean timedOut = false;
        int batchCount = 0;
        boolean requiresContentSearch = requiresContentSearch(searchLocations);

        if (collectAllResults && filteredClasses.size() > 100) {
            List<JavaClass> topClasses = new ArrayList<>();
            for (JavaClass cls : filteredClasses) {
                if (!cls.isInner()) {
                    topClasses.add(cls);
                }
            }

            List<List<JavaClass>> batches = wrapper.buildDecompileBatches(topClasses);
            batchCount = batches.size();
            logger.info("JADX AI MCP: Code search '{}' using {} parallel batches", searchTerm, batchCount);

            Set<JavaClass> includedSet = new HashSet<>(filteredClasses);
            List<Future<?>> futures = new ArrayList<>();
            ConcurrentLinkedQueue<JavaClass> contentCandidates = new ConcurrentLinkedQueue<>();

            for (List<JavaClass> batch : batches) {
                Future<?> future = searchExecutor.submit(() -> {
                    for (JavaClass cls : batch) {
                        if (cancelled.get() || Thread.currentThread().isInterrupted()) {
                            return;
                        }
                        if (System.nanoTime() >= deadlineNanos) {
                            cancelled.set(true);
                            return;
                        }
                        if (!includedSet.contains(cls) && !cls.isInner()) {
                            continue;
                        }

                        try {
                            if (classMatchesAnyMetadataLocation(cls, term, searchLocations)) {
                                if (matchedClasses.add(cls.getFullName())) {
                                    int total = totalMatches.incrementAndGet();
                                    if (!collectAllResults && total >= resultsNeeded) {
                                        cancelled.set(true);
                                        return;
                                    }
                                }
                            } else if (requiresContentSearch) {
                                contentCandidates.add(cls);
                            }
                        } catch (Exception ignored) {
                            // Skip failed classes and continue scanning remaining classes.
                        }
                    }
                });
                futures.add(future);
            }

            for (Future<?> future : futures) {
                try {
                    long remainingNanos = deadlineNanos - System.nanoTime();
                    if (remainingNanos <= 0) {
                        timedOut = true;
                        future.cancel(true);
                        continue;
                    }
                    future.get(remainingNanos, TimeUnit.NANOSECONDS);
                } catch (TimeoutException e) {
                    timedOut = true;
                    cancelled.set(true);
                    future.cancel(true);
                } catch (Exception ignored) {
                    // Ignore individual batch failures and keep any partial matches found.
                }
            }

            if (!timedOut && requiresContentSearch) {
                for (JavaClass cls : contentCandidates) {
                    if (cancelled.get()) {
                        break;
                    }
                    if (System.nanoTime() >= deadlineNanos) {
                        timedOut = true;
                        cancelled.set(true);
                        break;
                    }
                    if (classMatchesAnyContentLocation(cls, term, searchLocations)
                            && matchedClasses.add(cls.getFullName())) {
                        int total = totalMatches.incrementAndGet();
                        if (!collectAllResults && total >= resultsNeeded) {
                            cancelled.set(true);
                            break;
                        }
                    }
                }
            }
        } else {
            for (JavaClass cls : filteredClasses) {
                if (cancelled.get()) {
                    break;
                }
                if (System.nanoTime() >= deadlineNanos) {
                    timedOut = true;
                    break;
                }
                boolean metadataMatched = classMatchesAnyMetadataLocation(cls, term, searchLocations);
                if (metadataMatched || (requiresContentSearch && classMatchesAnyContentLocation(cls, term, searchLocations))) {
                    if (matchedClasses.add(cls.getFullName())) {
                        int total = totalMatches.incrementAndGet();
                        if (!collectAllResults && total >= resultsNeeded) {
                            cancelled.set(true);
                        }
                    }
                }
            }
        }

        long elapsedMs = Math.max(0L, System.currentTimeMillis() - startTimeMs);
        Map<String, Object> searchInfo = new HashMap<>();
        searchInfo.put("total_found", totalMatches.get());
        searchInfo.put("total_classes", allClasses.size());
        searchInfo.put("filtered_classes", filteredClasses.size());
        searchInfo.put("elapsed_seconds", TimeUnit.MILLISECONDS.toSeconds(elapsedMs));
        searchInfo.put("timed_out", timedOut);
        searchInfo.put("parallel_batches", batchCount);
        searchInfo.put("search_locations", searchLocations.toString());

        CodeSearchCoordinator.SearchResult result = new CodeSearchCoordinator.SearchResult(
            buildOrderedMatchList(filteredClasses, matchedClasses),
            searchInfo
        );

        logger.info(
            "JADX AI MCP: Search '{}' completed in {}s - found {} matches (batches: {}, timed_out: {})",
            searchTerm,
            TimeUnit.MILLISECONDS.toSeconds(elapsedMs),
            totalMatches.get(),
            batchCount,
            timedOut
        );

        return new SearchExecution(result, elapsedMs, timedOut);
    }

    private boolean classMatchesAnyLocation(
        JavaClass cls,
        String term,
        Set<SearchLocation> searchLocations
    ) {
        return classMatchesAnyMetadataLocation(cls, term, searchLocations)
            || classMatchesAnyContentLocation(cls, term, searchLocations);
    }

    private Map<String, Object> buildSearchResponse(
        CodeSearchCoordinator.SearchResult result,
        int offset,
        int count
    ) {
        List<String> matches = result.getMatches();
        List<String> paginatedResults = new ArrayList<>();
        for (int i = offset; i < Math.min(offset + count, matches.size()); i++) {
            paginatedResults.add(matches.get(i));
        }

        Map<String, Object> response = new HashMap<>();
        response.put("type", "class-list");
        response.put("classes", paginatedResults);
        response.put("offset", offset);
        response.put("count", paginatedResults.size());
        response.put("has_more", matches.size() > offset + paginatedResults.size());
        response.put("next_offset", offset + paginatedResults.size());
        response.put("search_info", result.getSearchInfo());
        return response;
    }

    private void sendCodeSearchBusyResponse(Context ctx, String message, double waitedSeconds) {
        Map<String, Object> busyResponse = new HashMap<>();
        busyResponse.put("error", message);
        busyResponse.put("retry_after", JadxSearchLock.RETRY_AFTER_SECONDS);
        busyResponse.put("busy", true);
        busyResponse.put("lock_held_seconds", JadxSearchLock.getLockHeldSeconds());
        if (waitedSeconds > 0.0) {
            busyResponse.put("waited_seconds", waitedSeconds);
        }
        ctx.status(503).json(busyResponse);
    }

    private void sendSearchDecompilationBusyResponse(Context ctx) {
        ctx.status(503).json(Map.of(
            "error", SEARCH_DECOMPILATION_BUSY_MESSAGE,
            "retry_after", JadxSearchLock.RETRY_AFTER_SECONDS
        ));
    }

    private static final class SearchExecution {
        private final CodeSearchCoordinator.SearchResult result;
        private final long elapsedMs;
        private final boolean timedOut;

        private SearchExecution(
            CodeSearchCoordinator.SearchResult result,
            long elapsedMs,
            boolean timedOut
        ) {
            this.result = result;
            this.elapsedMs = elapsedMs;
            this.timedOut = timedOut;
        }

        public CodeSearchCoordinator.SearchResult getResult() {
            return result;
        }

        public long getElapsedMs() {
            return elapsedMs;
        }

        public boolean isTimedOut() {
            return timedOut;
        }
    }
    
    /**
     * Check if a class matches the search term in the specified location.
     * For CODE and COMMENT, this triggers decompilation.
     */
    private boolean classMatchesInLocation(JavaClass cls, String term, SearchLocation location) {
        try {
            switch (location) {
                case CLASS_NAME:
                    return cls.getName().toLowerCase().contains(term);
                    
                case METHOD_NAME:
                    for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                        if (methodSnapshot.getName().toLowerCase().contains(term)) {
                            return true;
                        }
                    }
                    return false;
                    
                case FIELD_NAME:
                    for (JadxApiAdapter.FieldInfoSnapshot fieldSnapshot : JadxApiAdapter.getDeclaredFieldInfos(cls)) {
                        if (fieldSnapshot.getName().toLowerCase().contains(term)) {
                            return true;
                        }
                    }
                    return false;
                    
                default:
                    return false;
            }
        } catch (Exception e) {
            return false;
        }
    }

    private boolean classMatchesAnyMetadataLocation(
        JavaClass cls,
        String term,
        Set<SearchLocation> searchLocations
    ) {
        for (SearchLocation location : searchLocations) {
            if (location == SearchLocation.CODE || location == SearchLocation.COMMENT) {
                continue;
            }
            if (classMatchesInLocation(cls, term, location)) {
                return true;
            }
        }
        return false;
    }

    private boolean classMatchesAnyContentLocation(
        JavaClass cls,
        String term,
        Set<SearchLocation> searchLocations
    ) {
        if (!requiresContentSearch(searchLocations)) {
            return false;
        }

        try {
            String code = cls.getCode();
            if (code == null) {
                return false;
            }

            String normalizedCode = code.toLowerCase();
            if (searchLocations.contains(SearchLocation.CODE) && normalizedCode.contains(term)) {
                return true;
            }
            return searchLocations.contains(SearchLocation.COMMENT) && matchesCommentSearch(normalizedCode, term);
        } catch (Exception e) {
            return false;
        }
    }

    private boolean matchesCommentSearch(String normalizedCode, String term) {
        return normalizedCode.contains("//" + term)
            || normalizedCode.contains("/*" + term)
            || (normalizedCode.contains("//") && normalizedCode.contains(term))
            || (normalizedCode.contains("/*") && normalizedCode.contains(term));
    }

    private boolean requiresContentSearch(Set<SearchLocation> searchLocations) {
        return searchLocations.contains(SearchLocation.CODE)
            || searchLocations.contains(SearchLocation.COMMENT);
    }

    private List<String> buildOrderedMatchList(List<JavaClass> filteredClasses, Set<String> matchedClasses) {
        List<String> orderedMatches = new ArrayList<>();
        for (JavaClass cls : filteredClasses) {
            String fullName = cls.getFullName();
            if (matchedClasses.contains(fullName)) {
                orderedMatches.add(fullName);
            }
        }
        return orderedMatches;
    }

    private PaginationWindow resolvePaginationWindow(Context ctx, int totalItems) throws PaginationException {
        String offsetParam = ctx.queryParam("offset");
        String limitParam = ctx.queryParam("limit");
        String countParam = ctx.queryParam("count");
        String pageSizeParam = limitParam != null ? limitParam : countParam;

        int offset = 0;
        int requestedLimit = 0;
        boolean hasCustomLimit = pageSizeParam != null && !pageSizeParam.isEmpty();

        if (offsetParam != null && !offsetParam.isEmpty()) {
            try {
                offset = Integer.parseInt(offsetParam.trim());
                if (offset < 0) {
                    throw paginationUtils.new PaginationException("Offset must be non-negative, got: " + offset);
                }
                if (offset > paginationUtils.MAX_OFFSET) {
                    throw paginationUtils.new PaginationException(
                        "Offset too large, maximum: " + paginationUtils.MAX_OFFSET);
                }
            } catch (NumberFormatException e) {
                throw paginationUtils.new PaginationException("Invalid offset format: '" + offsetParam + "'");
            }
        }

        if (hasCustomLimit) {
            try {
                requestedLimit = Integer.parseInt(pageSizeParam.trim());
                if (requestedLimit < 0) {
                    throw paginationUtils.new PaginationException(
                        "Limit must be non-negative, got: " + requestedLimit);
                }
                if (requestedLimit > paginationUtils.MAX_PAGE_SIZE) {
                    throw paginationUtils.new PaginationException(
                        "Limit too large, maximum: " + paginationUtils.MAX_PAGE_SIZE);
                }
            } catch (NumberFormatException e) {
                throw paginationUtils.new PaginationException("Invalid limit format: '" + pageSizeParam + "'");
            }
        }

        int effectiveLimit;
        if (hasCustomLimit) {
            effectiveLimit = requestedLimit == 0 ? Math.max(0, totalItems - offset) : requestedLimit;
        } else {
            effectiveLimit = Math.min(paginationUtils.DEFAULT_PAGE_SIZE, Math.max(0, totalItems - offset));
        }
        effectiveLimit = Math.max(0, Math.min(effectiveLimit, totalItems - offset));

        if (offset >= totalItems) {
            return new PaginationWindow(offset, effectiveLimit, requestedLimit, 0, 0, false, totalItems);
        }

        int startIndex = offset;
        int endIndex = Math.min(startIndex + effectiveLimit, totalItems);
        boolean hasMore = endIndex < totalItems;
        int nextOffset = hasMore ? endIndex : -1;

        return new PaginationWindow(offset, effectiveLimit, requestedLimit, startIndex, endIndex, hasMore, nextOffset);
    }

    private Map<String, Object> buildPaginatedResponse(
        List<?> data,
        int totalItems,
        PaginationWindow window,
        String dataType,
        String itemsKey
    ) {
        Map<String, Object> result = new HashMap<>();
        result.put("type", dataType);
        result.put(itemsKey, data);

        Map<String, Object> pagination = new HashMap<>();
        pagination.put("total", totalItems);
        pagination.put("offset", window.getOffset());
        pagination.put("limit", window.getLimit());
        pagination.put("count", data.size());
        pagination.put("has_more", window.hasMore());

        if (window.hasMore()) {
            pagination.put("next_offset", window.getNextOffset());
        }

        if (window.getOffset() > 0) {
            int prevOffset = Math.max(0, window.getOffset() - window.getLimit());
            pagination.put("prev_offset", prevOffset);
        }

        if (window.getLimit() > 0) {
            int currentPage = (window.getOffset() / window.getLimit()) + 1;
            int totalPages = (int) Math.ceil((double) totalItems / window.getLimit());
            pagination.put("current_page", currentPage);
            pagination.put("total_pages", totalPages);
            pagination.put("page_size", window.getLimit());
        }

        result.put("requested_count", window.getRequestedLimit());
        result.put("pagination", pagination);
        return result;
    }

    private static final class PaginationWindow {
        private final int offset;
        private final int limit;
        private final int requestedLimit;
        private final int startIndex;
        private final int endIndex;
        private final boolean hasMore;
        private final int nextOffset;

        private PaginationWindow(
            int offset,
            int limit,
            int requestedLimit,
            int startIndex,
            int endIndex,
            boolean hasMore,
            int nextOffset
        ) {
            this.offset = offset;
            this.limit = limit;
            this.requestedLimit = requestedLimit;
            this.startIndex = startIndex;
            this.endIndex = endIndex;
            this.hasMore = hasMore;
            this.nextOffset = nextOffset;
        }

        public int getOffset() {
            return offset;
        }

        public int getLimit() {
            return limit;
        }

        public int getRequestedLimit() {
            return requestedLimit;
        }

        public int getStartIndex() {
            return startIndex;
        }

        public int getEndIndex() {
            return endIndex;
        }

        public boolean hasMore() {
            return hasMore;
        }

        public int getNextOffset() {
            return nextOffset;
        }

        public boolean hasResults() {
            return endIndex > startIndex;
        }
    }

    /**
     * Parse the search_in parameter into a set of SearchLocation enums.
     * Accepts lowercase values like "class,method,code" for URL-friendly usage.
     * 
     * @param searchIn Comma-separated string of search locations (e.g.,
     *                 "class,method,code")
     * @return Set of SearchLocation enums, defaults to {CODE} if null or empty
     */
    private Set<SearchLocation> parseSearchLocations(String searchIn) {
        Set<SearchLocation> locations = EnumSet.noneOf(SearchLocation.class);

        if (searchIn == null || searchIn.trim().isEmpty()) {
            // Default to CODE search if not specified
            locations.add(SearchLocation.CODE);
            return locations;
        }

        // Parse comma-separated values using lowercase mapping
        String[] parts = searchIn.toLowerCase().split(",");
        for (String part : parts) {
            String trimmed = part.trim();
            SearchLocation loc = SEARCH_LOCATION_MAP.get(trimmed);
            if (loc != null) {
                locations.add(loc);
            } else {
                logger.warn("JADX AI MCP: Invalid search location '{}', ignoring. Valid values: {}",
                        trimmed, SEARCH_LOCATION_MAP.keySet());
            }
        }

        // If no valid locations parsed, default to CODE
        if (locations.isEmpty()) {
            locations.add(SearchLocation.CODE);
        }

        return locations;
    }

    /**
     * Check if package filter is valid and should be applied.
     * Returns false for jadx obfuscated package names (p000, p001, etc.)
     * 
     * @param packageFilter The package filter string
     * @return true if package filter should be applied, false otherwise
     */
    private boolean isValidPackageFilter(String packageFilter) {
        if (packageFilter == null || packageFilter.trim().isEmpty()) {
            return false;
        }
        // defpackage is the default package name for jadx obfuscated classes
        if (packageFilter.equals("defpackage")) {
            return false;
        }

        // Check if the package filter matches jadx obfuscated pattern
        // Jadx uses patterns like "p000", "p001" for obfuscated packages
        String firstPart = packageFilter.split("\\.")[0];
        if (OBFUSCATED_PACKAGE_PATTERN.matcher(firstPart).matches()) {
            return false;
        }

        return true;
    }

    /**
     * Check if a class belongs to the specified package.
     * 
     * @param cls           The JavaClass to check
     * @param packageFilter The package prefix to match
     * @return true if class belongs to the package
     */
    private boolean matchesPackageFilter(JavaClass cls, String packageFilter) {
        if (packageFilter == null || packageFilter.trim().isEmpty()) {
            return true;
        }
        String fullName = cls.getFullName();
        // Match if the class full name starts with package filter
        return fullName.startsWith(packageFilter + ".") || fullName.equals(packageFilter);
    }

    /**
     * Search for keyword in the specified location.
     * 
     * @param allClasses         List of all classes to search
     * @param term               Search term (lowercase)
     * @param location           SearchLocation to search in
     * @param packageFilter      Package filter string
     * @param applyPackageFilter Whether to apply package filtering
     * @return Set of matching JavaClasses
     */
    private Set<JavaClass> searchInLocation(List<JavaClass> allClasses,
            String term, SearchLocation location,
            String packageFilter, boolean applyPackageFilter) {
        switch (location) {
            case CLASS_NAME:
                return searchByClassName(allClasses, term, packageFilter, applyPackageFilter);
            case METHOD_NAME:
                return searchByMethodName(allClasses, term, packageFilter, applyPackageFilter);
            case FIELD_NAME:
                return searchByFieldName(allClasses, term, packageFilter, applyPackageFilter);
            case CODE:
                return searchByCode(allClasses, term, packageFilter, applyPackageFilter);
            case COMMENT:
                return searchByComment(allClasses, term, packageFilter, applyPackageFilter);
            default:
                return new HashSet<>();
        }
    }

    /**
     * Search classes by class name containing the keyword.
     */
    private Set<JavaClass> searchByClassName(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        return allClasses.parallelStream()
                .filter(cls -> {
                    // Apply package filter if enabled
                    if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                        return false;
                    }
                    // Check if class name contains the term
                    String className = cls.getName().toLowerCase();
                    return className.contains(term);
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    /**
     * Search classes by method name, constructor name, or parameter types
     * containing the keyword.
     * This matches jadx's search behavior which searches:
     * - Method names
     * - Constructor names (methods named <init> or <clinit>)
     * - Method parameter types
     */
    private Set<JavaClass> searchByMethodName(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        return allClasses.parallelStream()
                .filter(cls -> {
                    // Apply package filter if enabled
                    if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                        return false;
                    }
                    for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                        String mthName = methodSnapshot.getName().toLowerCase();
                        // Check method name (includes constructors <init> and static initializers <clinit>)
                        if (mthName.contains(term)) {
                            return true;
                        }

                        // Check if it's a constructor - also match against class simple name
                        if (methodSnapshot.isConstructor()) {
                            String classSimpleName = cls.getName().toLowerCase();
                            if (classSimpleName.contains(term)) {
                                return true;
                            }
                        }
                    }
                    return false;
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    /**
     * Search classes by field name containing the keyword.
     */
    private Set<JavaClass> searchByFieldName(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        return allClasses.parallelStream()
                .filter(cls -> {
                    // Apply package filter if enabled
                    if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                        return false;
                    }
                    for (JadxApiAdapter.FieldInfoSnapshot fieldSnapshot : JadxApiAdapter.getDeclaredFieldInfos(cls)) {
                        if (fieldSnapshot.getName().toLowerCase().contains(term)) {
                            return true;
                        }
                    }
                    return false;
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    /**
     * Search classes by code containing the keyword.
     * 
     * WARNING: This is the most expensive search as it requires full decompilation.
     * Uses sequential stream to avoid JADX internal state race conditions.
     */
    private Set<JavaClass> searchByCode(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        // Use sequential stream to avoid race conditions in JADX decompilation
        // parallelStream can cause intermittent empty results due to internal state conflicts
        return allClasses.stream()
                .filter(cls -> {
                    try {
                        // Apply package filter if enabled
                        if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                            return false;
                        }
                        // This triggers decompilation
                        String code = cls.getCode();
                        return code != null && code.toLowerCase().contains(term);
                    } catch (Exception e) {
                        return false;
                    }
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    /**
     * Search classes by comments containing the keyword.
     * Comments include both single-line (//) and multi-line comments.
     */
    private Set<JavaClass> searchByComment(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        // Pattern to match Java comments: // single line or /* multi line */
        Pattern singleLineComment = Pattern.compile("//.*?" + Pattern.quote(term) + ".*", Pattern.CASE_INSENSITIVE);
        Pattern multiLineComment = Pattern.compile("/\\*[^*]*\\*+(?:[^/*][^*]*\\*+)*/", Pattern.DOTALL);

        return allClasses.parallelStream()
                .filter(cls -> {
                    try {
                        // Apply package filter if enabled
                        if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                            return false;
                        }
                        String code = cls.getCode();
                        if (code == null)
                            return false;

                        // Search for keyword in single-line comments
                        if (singleLineComment.matcher(code).find()) {
                            return true;
                        }

                        // Search for keyword in multi-line comments
                        java.util.regex.Matcher matcher = multiLineComment.matcher(code);
                        while (matcher.find()) {
                            String comment = matcher.group();
                            if (comment.toLowerCase().contains(term)) {
                                return true;
                            }
                        }
                        return false;
                    } catch (Exception e) {
                        return false;
                    }
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    // -------------------------------- Helper methods ----------------------------

    /**
     * @param Context
     * @return String
     * 
     *         Checks if the HTTP request contains the 'class_name' param or not, if
     *         yes then returns it,
     *         else returns null
     */
    private String checkClassParam(Context ctx) {
        String className = ctx.queryParam("class_name");
        if (className == null || className.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required parameter 'class_name'", logger);
            return null;
        }
        return className;
    }

    private JavaClass findClassByName(JadxWrapper wrapper, String className) {
        if (wrapper == null || className == null || className.isEmpty()) {
            return null;
        }

        try {
            ClassCacheManager.CacheStatus status = ClassCacheManager.getStatus();
            if (status == ClassCacheManager.CacheStatus.NOT_INITIALIZED) {
                ClassCacheManager.initCache(wrapper);
                status = ClassCacheManager.getStatus();
            }
            if (status == ClassCacheManager.CacheStatus.READY) {
                JavaClass cachedClass = ClassCacheManager.findClass(ClassCacheManager.getCache(), className);
                if (cachedClass != null) {
                    return cachedClass;
                }
            }
        } catch (Exception e) {
            logger.debug("Failed to resolve class '{}' from cache: {}", className, e.getMessage());
        }

        for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
            if (JadxApiAdapter.matchesClassName(cls, className)) {
                return cls;
            }
        }
        return null;
    }

    /**
     * @param
     * @return String
     * 
     *         This helper method extracts the selected(currently open class's UI
     *         tab)'s
     *         title. First it checks whether the mainWindow is null or not if it is
     *         null then
     *         return null.
     * 
     *         Then first it gets's the index of TabbedPane if it is -1 then it is
     *         not valid/ there
     *         is no selected class UI. Else it extracts title of tab using it's
     *         index and returns it
     *         as String.
     */
    private String getSelectedTabTitle() {
        if (mainWindow == null || mainWindow.getTabbedPane() == null)
            return null;

        int index = mainWindow.getTabbedPane().getSelectedIndex();
        if (index != -1) {
            return mainWindow.getTabbedPane().getTitleAt(index);
        }

        return null;
    }

    /**
     * @param
     * @return String
     * 
     *         This helper method extracts the text from current tab (active tab in
     *         UI) in other
     *         words, UI where we see class code.
     * 
     *         After checking for mainWindow's state for `null`, it first creates
     *         the Component object
     *         to store the current tab ( UI where we see class code ), Then using
     *         findTextArea() it
     *         extracts all text (class code) from it and return it via
     *         textArea.getText() method after
     *         checking for null.
     */
    private String extractTextFromCurrentTab() {
        if (mainWindow == null)
            return null;

        Component component = mainWindow.getTabbedPane().getSelectedComponent();
        JTextArea textArea = findTextArea(component);

        return textArea != null ? textArea.getText() : null;
    }

    /**
     * @return JTextArea
     * @param Component
     *                  Recursively searches for a JTextArea (or compatible
     *                  component) inside the given container.
     * 
     *                  This helper method is used in extractTextFromCurrentTab()
     *                  method. It takes the UI component
     *                  and recursively check if there is any JTextArea in that UI
     *                  compoenet, if yes then return it
     *                  else return null
     */
    private JTextArea findTextArea(Component component) {
        if (component instanceof JTextArea) {
            return (JTextArea) component;
        }

        if (component instanceof Container) {
            for (Component child : ((Container) component).getComponents()) {
                JTextArea found = findTextArea(child);
                if (found != null) {
                    return found;
                }
            }
        }
        return null;
    }

    /**
     * @param String, IJadxSecurity
     * @return Document
     * 
     *         reusing jadx's secure xml parsing logic for parsing manifest xml file
     *         this code is taken from jadx -
     *         https://github.com/skylot/jadx/blob/47647bbb9a9a3cd3150705e09cc1f84a5e9f0be6/jadx-core/src/main/java/jadx/core/utils/android/AndroidManifestParser.java#L214
     */
    private Document parseManifestXml(String xmlContent, IJadxSecurity security) {
        try (InputStream xmlStream = new ByteArrayInputStream(xmlContent.getBytes(StandardCharsets.UTF_8))) {
            Document doc = security.parseXml(xmlStream);
            doc.getDocumentElement().normalize();
            return doc;
        } catch (Exception e) {
            throw new JadxRuntimeException("Failed to parse AndroidManifest.xml", e);
        }
    }

    /**
     * Handle the /jar-entry-points MCP tool call.
     * 
     * Intelligently discovers entry points for JAR files:
     * 1. Main-Class from MANIFEST.MF
     * 2. Start-Class for Spring Boot (actual application class)
     * 3. Classes with @SpringBootApplication annotation
     * 4. Classes with public static void main(String[]) method
     * 5. SPI services (from META-INF/services)
     * 
     * Only available for JAR files.
     */
    public void handleJarEntryPoints(Context ctx) {
        try {
            // Check file type
            JadxWrapper wrapper = mainWindow.getWrapper();
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType = 
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(wrapper);
            
            if (fileType.getPrimaryType() != com.zin.jadxaimcp.utils.FileTypeDetector.FileType.JAR) {
                // Not a JAR file - return NOT_APPLICABLE with APK alternative
                Map<String, Object> response = new HashMap<>();
                response.put("status", "NOT_APPLICABLE");
                response.put("reason", "JAR entry points detection is only for JAR files. This is a " + 
                    fileType.getPrimaryType().getName().toUpperCase() + " file.");
                response.put("file_type", fileType.getPrimaryType().getName());
                response.put("alternatives", List.of(
                    Map.of("tool", "get_main_activity_class", "description", "Get MainActivity for APK files")
                ));
                ctx.json(response);
                return;
            }
            
            // Get the loaded JAR file
            java.nio.file.Path jarPath = wrapper.getProject().getFilePaths().isEmpty() ? null 
                : wrapper.getProject().getFilePaths().get(0);
            if (jarPath == null || !jarPath.toFile().exists()) {
                ctx.status(404).json(Map.of("error", "No JAR file loaded"));
                return;
            }
            
            Map<String, Object> result = new HashMap<>();
            result.put("type", "jar-entry-points");
            result.put("file_name", jarPath.getFileName().toString());
            
            List<Map<String, Object>> entryPoints = new ArrayList<>();
            String primaryEntry = null;
            
            // 1. Read MANIFEST.MF for Main-Class and Start-Class
            try (java.util.jar.JarFile jar = new java.util.jar.JarFile(jarPath.toFile())) {
                java.util.jar.Manifest manifest = jar.getManifest();
                if (manifest != null) {
                    java.util.jar.Attributes attrs = manifest.getMainAttributes();
                    
                    // Check Start-Class first (Spring Boot actual entry point)
                    String startClass = attrs.getValue("Start-Class");
                    if (startClass != null && !startClass.isEmpty()) {
                        Map<String, Object> entry = new HashMap<>();
                        entry.put("type", "spring_boot_start_class");
                        entry.put("class", startClass);
                        entry.put("source", "MANIFEST.MF Start-Class");
                        entry.put("priority", 1);
                        entryPoints.add(entry);
                        primaryEntry = startClass;
                    }
                    
                    // Check Main-Class
                    String mainClass = attrs.getValue("Main-Class");
                    if (mainClass != null && !mainClass.isEmpty()) {
                        Map<String, Object> entry = new HashMap<>();
                        // Check if it's a Spring Boot launcher
                        boolean isSpringBootLauncher = mainClass.contains("springframework.boot.loader");
                        entry.put("type", isSpringBootLauncher ? "spring_boot_launcher" : "main_class");
                        entry.put("class", mainClass);
                        entry.put("source", "MANIFEST.MF Main-Class");
                        entry.put("priority", isSpringBootLauncher ? 3 : 1);
                        if (isSpringBootLauncher) {
                            entry.put("note", "This is Spring Boot launcher. Use Start-Class for actual app.");
                        }
                        entryPoints.add(entry);
                        if (primaryEntry == null && !isSpringBootLauncher) {
                            primaryEntry = mainClass;
                        }
                    }
                }
            } catch (Exception e) {
                logger.debug("Failed to read manifest for entry points: " + e.getMessage());
            }
            
            // 2. Search for Spring Boot application classes by class name pattern
            // Note: Full annotation detection requires decompilation, skipped for performance
            List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();
            for (JavaClass cls : allClasses) {
                try {
                    String className = cls.getFullName();
                    // Look for common Spring Boot application class naming patterns
                    if (className.endsWith("Application") || 
                        className.contains(".Application$") ||
                        className.endsWith("App") ||
                        className.contains(".bootstrap.")) {
                        for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                            if (methodSnapshot.getName().equals("main")
                                && methodSnapshot.getAccessFlags() != null
                                && methodSnapshot.getAccessFlags().isStatic()
                                && methodSnapshot.getAccessFlags().isPublic()) {
                                Map<String, Object> entry = new HashMap<>();
                                entry.put("type", "application_class");
                                entry.put("class", className);
                                entry.put("source", "naming_pattern");
                                entry.put("priority", 2);
                                entryPoints.add(entry);
                                break;
                            }
                        }
                    }
                } catch (Exception e) {
                    // Skip classes that can't be analyzed
                }
            }
            
            // 3. Search for public static void main(String[]) methods
            int mainMethodCount = 0;
            for (JavaClass cls : allClasses) {
                if (mainMethodCount >= 10) break; // Limit to first 10
                try {
                    for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                        // Check for main method signature
                        if (methodSnapshot.getName().equals("main")
                            && methodSnapshot.getAccessFlags() != null
                            && methodSnapshot.getAccessFlags().isStatic()
                            && methodSnapshot.getAccessFlags().isPublic()) {
                            // Check return type is void
                            if ("void".equals(String.valueOf(methodSnapshot.getReturnType()))) {
                                // Check parameter is String[]
                                List<jadx.core.dex.instructions.args.ArgType> args = methodSnapshot.getArgumentTypes();
                                if (args.size() == 1 && args.get(0).toString().contains("String[]")) {
                                    Map<String, Object> entry = new HashMap<>();
                                    entry.put("type", "main_method");
                                    entry.put("class", cls.getFullName());
                                    entry.put("method", "main(String[])");
                                    entry.put("source", "method_signature");
                                    entry.put("priority", 4);
                                    entryPoints.add(entry);
                                    mainMethodCount++;
                                    break;
                                }
                            }
                        }
                    }
                } catch (Exception e) {
                    // Skip
                }
            }
            
            result.put("status", "success");
            result.put("entry_points", entryPoints);
            result.put("total_found", entryPoints.size());
            if (primaryEntry != null) {
                result.put("primary_entry", primaryEntry);
            }
            
            if (entryPoints.isEmpty()) {
                result.put("note", "No entry points found. This may be a library JAR without executable entry.");
            }
            
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Error finding JAR entry points: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Handle the /package-classes MCP tool call.
     * 
     * Unified interface to get classes by package prefix. Works for both APK and JAR files.
     * 
     * Parameters:
     * - package: Package prefix to filter classes (required unless using auto-detect)
     * - auto: If "true", auto-detect main package from manifest (APK) or manifest (JAR)
     * - include_inner: Include inner classes (default: true)
     * - offset/count: Pagination parameters
     */
    public void handlePackageClasses(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType = 
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(wrapper);
            
            String packagePrefix = ctx.queryParam("package");
            boolean autoDetect = "true".equalsIgnoreCase(ctx.queryParam("auto"));
            boolean includeInner = !"false".equalsIgnoreCase(ctx.queryParam("include_inner"));
            
            // Auto-detect package from manifest
            if (autoDetect || packagePrefix == null || packagePrefix.isEmpty()) {
                if (fileType.hasAndroidFeatures()) {
                    // APK/AAR: Get package from AndroidManifest.xml
                    try {
                        List<ResourceFile> resources = wrapper.getResources();
                        ResourceFile manifestRes = AndroidManifestParser.getAndroidManifest(resources);
                        if (manifestRes != null) {
                            String manifestXml = manifestRes.loadContent().getText().getCodeStr();
                            Document manifestDoc = parseManifestXml(manifestXml, wrapper.getArgs().getSecurity());
                            Element manifestElement = (Element) manifestDoc.getElementsByTagName("manifest").item(0);
                            packagePrefix = manifestElement.getAttribute("package");
                        }
                    } catch (Exception e) {
                        logger.debug("Failed to auto-detect package from manifest: {}", e.getMessage());
                    }
                } else if (fileType.getPrimaryType() == com.zin.jadxaimcp.utils.FileTypeDetector.FileType.JAR) {
                    // JAR: Try to detect main package from manifest or top-level classes
                    try {
                        java.nio.file.Path jarPath = wrapper.getProject().getFilePaths().get(0);
                        try (java.util.jar.JarFile jar = new java.util.jar.JarFile(jarPath.toFile())) {
                            java.util.jar.Manifest manifest = jar.getManifest();
                            if (manifest != null) {
                                String startClass = manifest.getMainAttributes().getValue("Start-Class");
                                if (startClass == null) {
                                    startClass = manifest.getMainAttributes().getValue("Main-Class");
                                }
                                if (startClass != null && startClass.contains(".")) {
                                    // Get package from class name (e.g., com.example.App -> com.example)
                                    int lastDot = startClass.lastIndexOf('.');
                                    packagePrefix = startClass.substring(0, lastDot);
                                }
                            }
                        }
                    } catch (Exception e) {
                        logger.debug("Failed to auto-detect package from JAR manifest: {}", e.getMessage());
                    }
                }
            }
            
            // Validate package prefix
            if (packagePrefix == null || packagePrefix.isEmpty()) {
                ctx.status(400).json(Map.of(
                    "error", "Package prefix not specified and could not be auto-detected",
                    "hint", "Use ?package=com.example or ?auto=true"
                ));
                return;
            }
            
            // Filter classes
            final String pkgPrefix = packagePrefix;
            List<JavaClass> allClasses = includeInner 
                ? wrapper.getIncludedClassesWithInners()
                : wrapper.getDecompiler().getClasses();
                
            List<JavaClass> matchedClasses = allClasses.stream()
                .filter(cls -> cls.getFullName().startsWith(pkgPrefix + ".") || 
                               cls.getFullName().equals(pkgPrefix))
                .collect(Collectors.toList());
            
            // Apply pagination
            int offset = paginationUtils.getIntParam(ctx, "offset", 0);
            int count = paginationUtils.getIntParam(ctx, "count", 100);
            count = Math.min(count, 500);
            
            List<Map<String, Object>> classesInfo = new ArrayList<>();
            for (int i = offset; i < Math.min(offset + count, matchedClasses.size()); i++) {
                JavaClass cls = matchedClasses.get(i);
                Map<String, Object> classInfo = new HashMap<>();
                classInfo.put("name", cls.getFullName());
                classInfo.put("is_inner", cls.isInner());
                classesInfo.add(classInfo);
            }
            
            Map<String, Object> result = new HashMap<>();
            result.put("type", "package-classes");
            result.put("file_type", fileType.getPrimaryType().getName());
            result.put("package", packagePrefix);
            result.put("classes", classesInfo);
            result.put("offset", offset);
            result.put("count", classesInfo.size());
            result.put("total_matched", matchedClasses.size());
            result.put("has_more", matchedClasses.size() > offset + classesInfo.size());
            result.put("status", "success");
            
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Error getting package classes: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Handle the /jar-bytecode MCP tool call.
     * 
     * Gets the disassembled bytecode representation of a JAR class.
     * This is the JAR equivalent of get_smali_of_class for APK files.
     * 
     * For JAR files, JADX can provide disassembled output similar to javap.
     * For APK files, this returns Dalvik bytecode (smali).
     * 
     * Parameters:
     * - class_name: Fully qualified class name (required)
     */
    public void handleJarBytecode(Context ctx) {
        try {
            String className = ctx.queryParam("class_name");
            if (className == null || className.isEmpty()) {
                ctx.status(400).json(Map.of("error", "class_name parameter is required"));
                return;
            }
            
            JadxWrapper wrapper = mainWindow.getWrapper();
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType = 
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(wrapper);
            
            // Find the class
            JavaClass targetClass = findClassByName(wrapper, className);
            
            if (targetClass == null) {
                ctx.status(404).json(Map.of(
                    "error", "Class not found: " + className,
                    "suggestion", "Use search_classes_by_keyword to find the correct class name"
                ));
                return;
            }
            
            Map<String, Object> result = new HashMap<>();
            result.put("type", "bytecode");
            result.put("class_name", targetClass.getFullName());
            result.put("raw_class_name", targetClass.getRawName());
            result.put("file_type", fileType.getPrimaryType().getName());
            
            AccessInfo classAccessFlags = JadxApiAdapter.getAccessFlags(targetClass);
            List<JadxApiAdapter.FieldInfoSnapshot> fieldSnapshots = JadxApiAdapter.getDeclaredFieldInfos(targetClass);
            List<JadxApiAdapter.MethodInfoSnapshot> methodSnapshots = JadxApiAdapter.getDeclaredMethodInfos(targetClass);
            if (classAccessFlags == null) {
                result.put("error", "Cannot access bytecode - class node not available");
                ctx.json(result);
                return;
            }
            
            // Build bytecode representation
            StringBuilder bytecode = new StringBuilder();
            
            // Class header
            bytecode.append("// Class: ").append(targetClass.getFullName()).append("\n");
            bytecode.append("// File type: ").append(fileType.getPrimaryType().getName().toUpperCase()).append("\n\n");
            
            // Access flags
            bytecode.append("// Access: ").append(classAccessFlags.rawValue())
                    .append(" (").append(classAccessFlags.toString()).append(")\n");
            
            // Super class
            String superClass = JadxApiAdapter.getSuperClass(targetClass);
            if (superClass != null) {
                bytecode.append("// Extends: ").append(superClass).append("\n");
            }
            
            // Interfaces
            List<String> interfaces = JadxApiAdapter.getInterfaces(targetClass);
            if (!interfaces.isEmpty()) {
                bytecode.append("// Implements: ");
                for (int i = 0; i < interfaces.size(); i++) {
                    if (i > 0) bytecode.append(", ");
                    bytecode.append(interfaces.get(i));
                }
                bytecode.append("\n");
            }
            bytecode.append("\n");
            
            // Fields
            bytecode.append("// Fields:\n");
            for (JadxApiAdapter.FieldInfoSnapshot fieldSnapshot : fieldSnapshots) {
                bytecode.append("  ").append(fieldSnapshot.getAccessFlags().toString())
                        .append(" ").append(fieldSnapshot.getType())
                        .append(" ").append(fieldSnapshot.getName()).append("\n");
            }
            bytecode.append("\n");
            
            // Methods with signature
            bytecode.append("// Methods:\n");
            for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : methodSnapshots) {
                bytecode.append("  ").append(methodSnapshot.getAccessFlags().toString())
                        .append(" ").append(methodSnapshot.getReturnType())
                        .append(" ").append(methodSnapshot.getName())
                        .append("(");
                
                // Parameters
                var args = methodSnapshot.getArgumentTypes();
                for (int i = 0; i < args.size(); i++) {
                    if (i > 0) bytecode.append(", ");
                    bytecode.append(args.get(i).toString());
                }
                bytecode.append(")\n");
                
                // Try to get instructions count
                if (methodSnapshot.getBasicBlockCount() != null) {
                    bytecode.append("    // Basic blocks: ").append(methodSnapshot.getBasicBlockCount()).append("\n");
                }
            }
            
            result.put("bytecode", bytecode.toString());
            result.put("field_count", fieldSnapshots.size());
            result.put("method_count", methodSnapshots.size());
            result.put("status", "success");
            
            // Add note about smali availability
            if (fileType.isSmaliAvailable()) {
                result.put("smali_available", true);
                result.put("note", "Use get_smali_of_class for full Dalvik bytecode (APK/DEX files)");
            } else {
                result.put("smali_available", false);
                result.put("note", "JAR files use JVM bytecode. This shows class structure similar to javap.");
            }
            
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Error getting bytecode: " + e.getMessage(), e, logger);
        }
    }
}
