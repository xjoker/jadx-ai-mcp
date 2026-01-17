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
import jadx.core.dex.nodes.ClassNode;
import jadx.core.dex.nodes.FieldNode;
import jadx.core.dex.nodes.MethodNode;
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
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ConcurrentLinkedQueue;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.JadxSearchLock;
import com.zin.jadxaimcp.utils.ClassCacheManager;

public class ClassRoutes {
    private static final Logger logger = LoggerFactory.getLogger(ClassRoutes.class);
    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;
    
    // Thread pool for parallel batch search
    private static final ExecutorService SEARCH_EXECUTOR = Executors.newFixedThreadPool(
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

    public ClassRoutes(MainWindow mainWindow, PaginationUtils paginationUtils) {
        this.mainWindow = mainWindow;
        this.paginationUtils = paginationUtils;
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
     */
    public void handleCurrentClass(Context ctx) {
        try {
            String className = getSelectedTabTitle();
            String code = extractTextFromCurrentTab();

            Map<String, String> result = new HashMap<>();
            result.put("name", className != null ? className.replace(".java", "") : "unknown");
            result.put("type", "code/java");
            result.put("content", code != null ? code : "");

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
     */
    public void handleClassSource(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

        // Removing this line to solve issue #37 as raised and contributed by
        // github@ljt270864457
        // This solves following bug -> Bug: Inner classes with $ symbol cannot be
        // retrieved via /class-source endpoint
        // className = className.replace('$', '.');

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                if (cls.getFullName().equals(className)) {
                    ctx.result(cls.getCode());
                    return;
                }
            }
            ctx.status(404).json(Map.of("error", "Class " + className + " not found"));
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

            for (String className : classNames) {
                String trimmedName = className.trim();
                Map<String, Object> classResult = new HashMap<>();
                classResult.put("name", trimmedName);

                JavaClass cls = classMap.get(trimmedName);
                if (cls != null) {
                    try {
                        classResult.put("found", true);
                        classResult.put("content", cls.getCode());
                        foundCount++;
                    } catch (Exception e) {
                        classResult.put("found", true);
                        classResult.put("error", "Decompilation failed: " + e.getMessage());
                    }
                } else {
                    classResult.put("found", false);
                    classResult.put("error", "Class not found");
                }
                results.add(classResult);
            }

            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("classes", results);
            response.put("total", classNames.length);
            response.put("found", foundCount);
            ctx.json(response);

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
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                if (cls.getFullName().equals(className)) {
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
                        
                        // Access flags from MethodNode for accurate information
                        MethodNode methodNode = method.getMethodNode();
                        if (methodNode != null) {
                            AccessInfo accessFlags = methodNode.getAccessFlags();
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
                    response.put("class_name", className);
                    response.put("methods", methodsList);
                    response.put("count", methodsList.size());
                    
                    ctx.json(response);
                    return;
                }
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
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                if (cls.getFullName().equals(className)) {
                    List<Map<String, Object>> fieldsList = new ArrayList<>();
                    
                    for (JavaField field : cls.getFields()) {
                        Map<String, Object> fieldInfo = new HashMap<>();
                        fieldInfo.put("name", field.getName());
                        
                        // Type information
                        String typeStr = field.getType() != null ? field.getType().toString() : "unknown";
                        fieldInfo.put("type", typeStr);
                        
                        // Frida-compatible type
                        if (field.getFieldNode() != null && field.getFieldNode().getType() != null) {
                            fieldInfo.put("type_frida", 
                                com.zin.jadxaimcp.utils.FridaTypeConverter.toFridaType(field.getFieldNode().getType()));
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
                    response.put("class_name", className);
                    response.put("fields", fieldsList);
                    response.put("count", fieldsList.size());
                    
                    ctx.json(response);
                    return;
                }
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
     */
    public void handleSmaliOfClass(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

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
            
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                if (cls.getFullName().equals(className)) {
                    String smali = cls.getSmali();
                    if (smali == null || smali.isEmpty()) {
                        // Smali generation failed even though file type says it should work
                        JadxAIMCPPluginError.handleError(ctx, 404, 
                            "Smali generation returned empty for class " + className + 
                            ". This may indicate the class was loaded from a non-DEX source.", logger);
                        return;
                    }
                    ctx.result(smali);
                    return;
                }
            }
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving smali: " + e.getMessage(), e, logger);
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
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                if (cls.getFullName().equals(className)) {
                    Map<String, Object> info = new HashMap<>();
                    info.put("class_name", cls.getFullName());
                    info.put("simple_name", cls.getName());
                    info.put("package", cls.getPackage());
                    
                    // Access modifiers - use ClassNode for detailed info
                    try {
                        jadx.core.dex.nodes.ClassNode classNode = cls.getClassNode();
                        jadx.core.dex.info.AccessInfo accessInfo = classNode.getAccessFlags();
                        info.put("access_flags", accessInfo.toString());
                        info.put("is_interface", accessInfo.isInterface());
                        info.put("is_enum", accessInfo.isEnum());
                        info.put("is_abstract", accessInfo.isAbstract());
                        info.put("is_final", accessInfo.isFinal());
                    } catch (Exception e) {
                        info.put("access_flags", "unknown");
                        info.put("is_interface", false);
                        info.put("is_enum", false);
                    }
                    info.put("is_inner", cls.isInner());
                    
                    // Super class - using ClassNode to get parent info
                    try {
                        jadx.core.dex.instructions.args.ArgType superType = cls.getClassNode().getSuperClass();
                        if (superType != null) {
                            String superClass = superType.toString();
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
                        for (jadx.core.dex.instructions.args.ArgType iface : cls.getClassNode().getInterfaces()) {
                            interfaces.add(iface.toString());
                        }
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
                    
                    // Method and field counts (using ClassNode to avoid triggering decompilation)
                    jadx.core.dex.nodes.ClassNode infoClassNode = cls.getClassNode();
                    if (infoClassNode != null) {
                        info.put("methods_count", infoClassNode.getMethods().size());
                        info.put("fields_count", infoClassNode.getFields().size());
                        
                        // Method names (for quick overview)
                        List<String> methodNames = new ArrayList<>();
                        List<String> nativeMethodNames = new ArrayList<>();
                        for (jadx.core.dex.nodes.MethodNode m : infoClassNode.getMethods()) {
                            String name = m.getMethodInfo().getName();
                            methodNames.add(name);
                            // Collect native methods for security analysis
                            if (m.getAccessFlags().isNative()) {
                                nativeMethodNames.add(name);
                            }
                        }
                        info.put("method_names", methodNames);
                        info.put("native_method_names", nativeMethodNames);
                        info.put("native_count", nativeMethodNames.size());
                        
                        // Field names
                        List<String> fieldNames = new ArrayList<>();
                        for (jadx.core.dex.nodes.FieldNode f : infoClassNode.getFields()) {
                            fieldNames.add(f.getFieldInfo().getName());
                        }
                        info.put("field_names", fieldNames);
                    } else {
                        info.put("methods_count", 0);
                        info.put("fields_count", 0);
                        info.put("method_names", new ArrayList<>());
                        info.put("field_names", new ArrayList<>());
                        info.put("native_method_names", new ArrayList<>());
                        info.put("native_count", 0);
                    }

                    
                    ctx.json(info);
                    return;
                }
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
        try {
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

            ctx.json(Map.of("name", mainActivityClass.getFullName(), "type", "code/java", "content",
                    mainActivityClass.getCode()));
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error occurred while trying to get the Main Activity class code: " + e.getMessage(), e,
                    logger);
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

            // Build list of class info maps Before pagination
            List<Map<String, Object>> classInfoList = new ArrayList<>();
            for (JavaClass cls : matchedClasses) {
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

            logger.info("JADX AI MCP: Built " + classInfoList.size() + " class info objects");

            // Apply pagination to the pre-build list
            Map<String, Object> result = paginationUtils.handlePagination(
                    ctx,
                    classInfoList,
                    "application-classes",
                    "classes",
                    item -> item); // Identity function since items are already transformed

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
        Set<SearchLocation> searchLocations = parseSearchLocations(ctx.queryParam("search_in"));
        
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
            final String term = searchTerm.toLowerCase();

            // Apply package filter and exclusions first
            boolean applyPackageFilter = isValidPackageFilter(packageFilter);
            final String pkgFilter = packageFilter;
            final List<String> excludes = excludePrefixes;
            
            List<JavaClass> filteredClasses = allClasses;
            if (applyPackageFilter || !excludes.isEmpty()) {
                filteredClasses = new ArrayList<>();
                for (JavaClass cls : allClasses) {
                    if (applyPackageFilter && !matchesPackageFilter(cls, pkgFilter)) continue;
                    if (!excludes.isEmpty()) {
                        boolean excluded = false;
                        for (String prefix : excludes) {
                            if (cls.getFullName().startsWith(prefix)) {
                                excluded = true;
                                break;
                            }
                        }
                        if (excluded) continue;
                    }
                    filteredClasses.add(cls);
                }
            }

            // Try to acquire global lock
            if (!JadxSearchLock.tryAcquire()) {
                Map<String, Object> busyResponse = new HashMap<>();
                busyResponse.put("error", "Search operation in progress");
                busyResponse.put("retry_after", JadxSearchLock.RETRY_AFTER_SECONDS);
                busyResponse.put("busy", true);
                busyResponse.put("lock_held_seconds", JadxSearchLock.getLockHeldSeconds());
                ctx.status(503).json(busyResponse);
                return;
            }
            
            try {
                final int resultsNeeded = offset + count + 1; // +1 to check if has_more
                final ConcurrentLinkedQueue<String> results = new ConcurrentLinkedQueue<>();
                final AtomicInteger totalMatches = new AtomicInteger(0);
                final AtomicBoolean cancelled = new AtomicBoolean(false);
                
                long startTime = System.currentTimeMillis();
                int batchCount = 0;
                
                if (isCodeSearch && filteredClasses.size() > 100) {
                    // Use JADX's smart batching for code search
                    List<JavaClass> topClasses = new ArrayList<>();
                    for (JavaClass cls : filteredClasses) {
                        if (!cls.isInner()) {
                            topClasses.add(cls);
                        }
                    }
                    
                    List<List<JavaClass>> batches = wrapper.buildDecompileBatches(topClasses);
                    batchCount = batches.size();
                    
                    logger.info("JADX AI MCP: Code search '{}' using {} parallel batches", searchTerm, batchCount);
                    
                    // Create search tasks for each batch
                    Set<JavaClass> includedSet = new HashSet<>(filteredClasses);
                    List<Future<?>> futures = new ArrayList<>();
                    
                    for (List<JavaClass> batch : batches) {
                        Future<?> future = SEARCH_EXECUTOR.submit(() -> {
                            for (JavaClass cls : batch) {
                                if (cancelled.get()) return;
                                if (!includedSet.contains(cls) && !cls.isInner()) continue;
                                
                                try {
                                    boolean matches = false;
                                    for (SearchLocation location : searchLocations) {
                                        if (classMatchesInLocation(cls, term, location)) {
                                            matches = true;
                                            break;
                                        }
                                    }
                                    if (matches) {
                                        int total = totalMatches.incrementAndGet();
                                        results.add(cls.getFullName());
                                        // Early exit when we have enough
                                        if (total >= resultsNeeded) {
                                            cancelled.set(true);
                                        }
                                    }
                                } catch (Exception e) {
                                    // Skip failed classes
                                }
                            }
                        });
                        futures.add(future);
                    }
                    
                    // Wait for all batches with timeout
                    for (Future<?> future : futures) {
                        try {
                            long elapsed = System.currentTimeMillis() - startTime;
                            long remaining = SEARCH_TIMEOUT_SECONDS * 1000 - elapsed;
                            if (remaining > 0) {
                                future.get(remaining, TimeUnit.MILLISECONDS);
                            } else {
                                future.cancel(true);
                            }
                        } catch (TimeoutException e) {
                            future.cancel(true);
                        } catch (Exception e) {
                            // Continue with other batches
                        }
                    }
                } else {
                    // Simple sequential search for metadata search or small class sets
                    for (JavaClass cls : filteredClasses) {
                        if (cancelled.get()) break;
                        
                        boolean matches = false;
                        for (SearchLocation location : searchLocations) {
                            if (classMatchesInLocation(cls, term, location)) {
                                matches = true;
                                break;
                            }
                        }
                        if (matches) {
                            int total = totalMatches.incrementAndGet();
                            results.add(cls.getFullName());
                            if (total >= resultsNeeded) {
                                cancelled.set(true);
                            }
                        }
                    }
                }
                
                // Convert to list and apply pagination
                List<String> allResults = new ArrayList<>(results);
                int totalFound = totalMatches.get();
                
                // Apply offset/count pagination
                List<String> paginatedResults = new ArrayList<>();
                for (int i = offset; i < Math.min(offset + count, allResults.size()); i++) {
                    paginatedResults.add(allResults.get(i));
                }
                
                long elapsed = (System.currentTimeMillis() - startTime) / 1000;
                boolean timedOut = elapsed >= SEARCH_TIMEOUT_SECONDS;
                
                // Build response
                Map<String, Object> response = new HashMap<>();
                response.put("type", "class-list");
                response.put("classes", paginatedResults);
                response.put("offset", offset);
                response.put("count", paginatedResults.size());
                response.put("has_more", totalFound > offset + paginatedResults.size());
                response.put("next_offset", offset + paginatedResults.size());
                
                // Search info
                Map<String, Object> searchInfo = new HashMap<>();
                searchInfo.put("total_found", totalFound);
                searchInfo.put("total_classes", allClasses.size());
                searchInfo.put("filtered_classes", filteredClasses.size());
                searchInfo.put("elapsed_seconds", elapsed);
                searchInfo.put("timed_out", timedOut);
                searchInfo.put("parallel_batches", batchCount);
                searchInfo.put("search_locations", searchLocations.toString());
                
                response.put("search_info", searchInfo);
                
                logger.info("JADX AI MCP: Search '{}' completed in {}s - found {} matches, returned {} (batches: {})", 
                    searchTerm, elapsed, totalFound, paginatedResults.size(), batchCount);
                
                ctx.json(response);
            } finally {
                JadxSearchLock.release();
            }
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error in search: " + e.getMessage(), e, logger);
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
                    jadx.core.dex.nodes.ClassNode classNode = cls.getClassNode();
                    if (classNode == null) return false;
                    for (jadx.core.dex.nodes.MethodNode mth : classNode.getMethods()) {
                        if (mth.getMethodInfo().getName().toLowerCase().contains(term)) {
                            return true;
                        }
                    }
                    return false;
                    
                case FIELD_NAME:
                    jadx.core.dex.nodes.ClassNode fieldClassNode = cls.getClassNode();
                    if (fieldClassNode == null) return false;
                    for (jadx.core.dex.nodes.FieldNode field : fieldClassNode.getFields()) {
                        if (field.getFieldInfo().getName().toLowerCase().contains(term)) {
                            return true;
                        }
                    }
                    return false;
                    
                case CODE:
                    String code = cls.getCode();
                    return code != null && code.toLowerCase().contains(term);
                    
                case COMMENT:
                    String commentCode = cls.getCode();
                    if (commentCode == null) return false;
                    // Check for comments containing the term
                    return commentCode.contains("//" + term) || commentCode.contains("/*" + term)
                        || (commentCode.toLowerCase().contains("//") && commentCode.toLowerCase().contains(term))
                        || (commentCode.toLowerCase().contains("/*") && commentCode.toLowerCase().contains(term));
                    
                default:
                    return false;
            }
        } catch (Exception e) {
            return false;
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
                    // Use ClassNode to avoid triggering decompilation
                    jadx.core.dex.nodes.ClassNode classNode = cls.getClassNode();
                    if (classNode == null) return false;
                    
                    // Check each method in the class using MethodNode (no decompilation)
                    for (jadx.core.dex.nodes.MethodNode mth : classNode.getMethods()) {
                        String mthName = mth.getMethodInfo().getName().toLowerCase();
                        // Check method name (includes constructors <init> and static initializers <clinit>)
                        if (mthName.contains(term)) {
                            return true;
                        }

                        // Check if it's a constructor - also match against class simple name
                        if (mth.getMethodInfo().isConstructor()) {
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
                    // Use ClassNode to avoid triggering decompilation
                    jadx.core.dex.nodes.ClassNode classNode = cls.getClassNode();
                    if (classNode == null) return false;
                    
                    // Check if any field name contains the term (using FieldNode)
                    for (jadx.core.dex.nodes.FieldNode field : classNode.getFields()) {
                        if (field.getFieldInfo().getName().toLowerCase().contains(term)) {
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
                        // Check if this class is likely the main entry (has main method)
                        jadx.core.dex.nodes.ClassNode classNode = cls.getClassNode();
                        if (classNode != null) {
                            for (jadx.core.dex.nodes.MethodNode mth : classNode.getMethods()) {
                                if (mth.getMethodInfo().getName().equals("main") && 
                                    mth.getAccessFlags().isStatic() &&
                                    mth.getAccessFlags().isPublic()) {
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
                    jadx.core.dex.nodes.ClassNode classNode = cls.getClassNode();
                    if (classNode == null) continue;
                    
                    for (jadx.core.dex.nodes.MethodNode mth : classNode.getMethods()) {
                        jadx.core.dex.info.MethodInfo mthInfo = mth.getMethodInfo();
                        // Check for main method signature
                        if (mthInfo.getName().equals("main") && 
                            mth.getAccessFlags().isStatic() &&
                            mth.getAccessFlags().isPublic()) {
                            // Check return type is void
                            if (mthInfo.getReturnType().toString().equals("void")) {
                                // Check parameter is String[]
                                List<jadx.core.dex.instructions.args.ArgType> args = mthInfo.getArgumentsTypes();
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
            JavaClass targetClass = null;
            for (JavaClass cls : wrapper.getIncludedClassesWithInners()) {
                if (cls.getFullName().equals(className)) {
                    targetClass = cls;
                    break;
                }
            }
            
            if (targetClass == null) {
                ctx.status(404).json(Map.of(
                    "error", "Class not found: " + className,
                    "suggestion", "Use search_classes_by_keyword to find the correct class name"
                ));
                return;
            }
            
            Map<String, Object> result = new HashMap<>();
            result.put("type", "bytecode");
            result.put("class_name", className);
            result.put("file_type", fileType.getPrimaryType().getName());
            
            // Get the class node for bytecode access
            jadx.core.dex.nodes.ClassNode classNode = targetClass.getClassNode();
            if (classNode == null) {
                result.put("error", "Cannot access bytecode - class node not available");
                ctx.json(result);
                return;
            }
            
            // Build bytecode representation
            StringBuilder bytecode = new StringBuilder();
            
            // Class header
            bytecode.append("// Class: ").append(className).append("\n");
            bytecode.append("// File type: ").append(fileType.getPrimaryType().getName().toUpperCase()).append("\n\n");
            
            // Access flags
            bytecode.append("// Access: ").append(classNode.getAccessFlags().rawValue())
                    .append(" (").append(classNode.getAccessFlags().toString()).append(")\n");
            
            // Super class
            if (classNode.getSuperClass() != null) {
                bytecode.append("// Extends: ").append(classNode.getSuperClass().toString()).append("\n");
            }
            
            // Interfaces
            if (!classNode.getInterfaces().isEmpty()) {
                bytecode.append("// Implements: ");
                for (int i = 0; i < classNode.getInterfaces().size(); i++) {
                    if (i > 0) bytecode.append(", ");
                    bytecode.append(classNode.getInterfaces().get(i).toString());
                }
                bytecode.append("\n");
            }
            bytecode.append("\n");
            
            // Fields
            bytecode.append("// Fields:\n");
            for (jadx.core.dex.nodes.FieldNode field : classNode.getFields()) {
                bytecode.append("  ").append(field.getAccessFlags().toString())
                        .append(" ").append(field.getType().toString())
                        .append(" ").append(field.getName()).append("\n");
            }
            bytecode.append("\n");
            
            // Methods with signature
            bytecode.append("// Methods:\n");
            for (jadx.core.dex.nodes.MethodNode method : classNode.getMethods()) {
                bytecode.append("  ").append(method.getAccessFlags().toString())
                        .append(" ").append(method.getMethodInfo().getReturnType())
                        .append(" ").append(method.getName())
                        .append("(");
                
                // Parameters
                var args = method.getMethodInfo().getArgumentsTypes();
                for (int i = 0; i < args.size(); i++) {
                    if (i > 0) bytecode.append(", ");
                    bytecode.append(args.get(i).toString());
                }
                bytecode.append(")\n");
                
                // Try to get instructions count
                if (method.getBasicBlocks() != null) {
                    bytecode.append("    // Basic blocks: ").append(method.getBasicBlocks().size()).append("\n");
                }
            }
            
            result.put("bytecode", bytecode.toString());
            result.put("field_count", classNode.getFields().size());
            result.put("method_count", classNode.getMethods().size());
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
