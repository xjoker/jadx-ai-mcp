package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.JavaField;
import jadx.api.JavaMethod;
import jadx.core.dex.info.AccessInfo;
import jadx.core.dex.instructions.args.ArgType;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.swing.*;
import java.awt.*;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Future;
import java.util.stream.Collectors;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.JadxApiAdapter;
import com.zin.jadxaimcp.utils.SmartChunker;

/**
 * Lean navigation and class-metadata MCP endpoints.
 *
 * <p>Covers: {@code /current-class}, {@code /all-classes}, {@code /selected-text},
 * {@code /class-info}, {@code /methods-of-class}, {@code /fields-of-class},
 * {@code /package-classes}, {@code /package-tree}, {@code /jar-bytecode},
 * {@code /jar-entry-points}.</p>
 *
 * <p>Search is handled by {@link SearchRoutes}; batch and multi-class decompilation
 * by {@link BatchRoutes}; single-class source/smali by {@link DecompileRoutes}.</p>
 *
 * <p>{@link #submitWarmupTask(JavaClass)} delegates to the {@link SearchRoutes}
 * executor so {@code PluginServer.runPredecompileWarmup()} keeps working without
 * change.</p>
 */
public class ClassRoutes {
    private static final Logger logger = LoggerFactory.getLogger(ClassRoutes.class);

    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;
    private final SearchRoutes searchRoutes;

    // Known library package prefixes for is_likely_library heuristic
    private static final String[] LIBRARY_PREFIXES = {
            "androidx.", "android.support.", "com.google.", "com.android.",
            "kotlin.", "kotlinx.", "okhttp3.", "okio.", "retrofit2.",
            "com.squareup.", "io.reactivex.", "rx.", "dagger.",
            "com.facebook.", "com.amazonaws.", "org.apache.", "org.json.",
            "com.fasterxml.", "org.slf4j.", "javax.", "junit.",
            "io.netty.", "com.bumptech.glide.", "org.greenrobot.",
            "com.airbnb.", "io.realm.", "bolts.", "butterknife."
    };

    public ClassRoutes(MainWindow mainWindow, PaginationUtils paginationUtils) {
        this.mainWindow = mainWindow;
        this.paginationUtils = paginationUtils;
        this.searchRoutes = new SearchRoutes(mainWindow, paginationUtils);
    }

    /**
     * Returns the {@link SearchRoutes} instance owned by this ClassRoutes.
     * Used by {@link com.zin.jadxaimcp.server.PluginServer} to register search endpoints.
     */
    public SearchRoutes getSearchRoutes() {
        return searchRoutes;
    }

    /**
     * Shuts down the underlying search executor pool.
     * Called by {@link com.zin.jadxaimcp.server.PluginServer#stop()}.
     */
    public void shutdownSearchExecutor() {
        searchRoutes.shutdownSearchExecutor();
    }

    /**
     * Submits a single warmup decompile task to the shared search executor pool.
     * Delegates to {@link SearchRoutes#submitWarmupTask(JavaClass)} so the
     * {@code PluginServer.classRoutes.submitWarmupTask(...)} call-site compiles unchanged.
     *
     * @return a Future that completes when the class has been decompiled (or fails silently)
     */
    public Future<?> submitWarmupTask(JavaClass cls) {
        return searchRoutes.submitWarmupTask(cls);
    }

    // ------------------------------- Request Handlers --------------------------

    /**
     * Handles {@code /current-class}.
     *
     * <p>Returns the source code of the currently open/visible class in the JADX UI tab.
     * Supports chunking for large responses ({@code ?chunk=N}).</p>
     */
    public void handleCurrentClass(Context ctx) {
        try {
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

            Map<String, Object> result = SmartChunker.chunkResponse(
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
     * Handles {@code /all-classes}.
     *
     * <p>Returns all classes decompiled from the loaded APK/JAR, with pagination.</p>
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
                    cls -> {
                        Map<String, Object> classEntry = new HashMap<>();
                        classEntry.put("name", JadxApiAdapter.getClassAliasName(cls));
                        classEntry.put("raw_name", JadxApiAdapter.getClassRawName(cls));
                        return classEntry;
                    });
            ctx.json(result);
        } catch (PaginationException e) {
            JadxAIMCPPluginError.handleError(ctx, "Pagination Error: " + e.getMessage(), e, logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Failed to load class list: " + e.getMessage(), e, logger);
        }
    }

    /**
     * Handles {@code /selected-text}.
     *
     * <p>Returns the currently selected text in the JADX UI code viewer.</p>
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
     * Handles {@code /class-info}.
     *
     * <p>Returns structured metadata about a class: super class, interfaces, access
     * modifiers, method/field counts, and inner classes. Does not trigger decompilation.</p>
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
                    info.put("super_class", superClass != null ? superClass : "java.lang.Object");
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
                List<Map<String, Object>> innerClasses = new ArrayList<>();
                try {
                    for (JavaClass inner : cls.getInnerClasses()) {
                        Map<String, Object> innerEntry = new HashMap<>();
                        innerEntry.put("name", JadxApiAdapter.getClassAliasName(inner));
                        innerEntry.put("raw_name", JadxApiAdapter.getClassRawName(inner));
                        innerClasses.add(innerEntry);
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
     * Handles {@code /methods-of-class}.
     *
     * <p>Returns all methods of a class with signatures, modifiers, and return types.</p>
     */
    public void handleMethodsOfClass(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

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
     * Handles {@code /fields-of-class}.
     *
     * <p>Returns all fields of a class with types, modifiers, and Frida-compatible type strings.</p>
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

                    String typeStr = field.getType() != null ? field.getType().toString() : "unknown";
                    fieldInfo.put("type", typeStr);

                    if (field.getType() != null) {
                        fieldInfo.put("type_frida",
                            com.zin.jadxaimcp.utils.FridaTypeConverter.toFridaType(field.getType()));
                    } else {
                        fieldInfo.put("type_frida", typeStr);
                    }

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
     * Handles {@code /package-classes}.
     *
     * <p>Unified interface to get classes by package prefix. Works for both APK and JAR files.
     * Auto-detects the main package from the manifest when {@code ?auto=true} is set.</p>
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
                    try {
                        List<jadx.api.ResourceFile> resources = wrapper.getResources();
                        jadx.api.ResourceFile manifestRes = jadx.core.utils.android.AndroidManifestParser.getAndroidManifest(resources);
                        if (manifestRes != null) {
                            String manifestXml = manifestRes.loadContent().getText().getCodeStr();
                            try (java.io.InputStream xmlStream = new java.io.ByteArrayInputStream(
                                    manifestXml.getBytes(java.nio.charset.StandardCharsets.UTF_8))) {
                                org.w3c.dom.Document manifestDoc = wrapper.getArgs().getSecurity().parseXml(xmlStream);
                                manifestDoc.getDocumentElement().normalize();
                                org.w3c.dom.Element manifestElement = (org.w3c.dom.Element) manifestDoc.getElementsByTagName("manifest").item(0);
                                packagePrefix = manifestElement.getAttribute("package");
                            }
                        }
                    } catch (Exception e) {
                        logger.debug("Failed to auto-detect package from manifest: {}", e.getMessage());
                    }
                } else if (fileType.getPrimaryType() == com.zin.jadxaimcp.utils.FileTypeDetector.FileType.JAR) {
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

            if (packagePrefix == null || packagePrefix.isEmpty()) {
                ctx.status(400).json(Map.of(
                    "error", "Package prefix not specified and could not be auto-detected",
                    "hint", "Use ?package=com.example or ?auto=true"
                ));
                return;
            }

            final String pkgPrefix = packagePrefix;
            List<JavaClass> allClasses = includeInner
                ? wrapper.getIncludedClassesWithInners()
                : wrapper.getDecompiler().getClasses();

            List<JavaClass> matchedClasses = allClasses.stream()
                .filter(cls -> cls.getFullName().startsWith(pkgPrefix + ".") ||
                               cls.getFullName().equals(pkgPrefix))
                .collect(Collectors.toList());

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
     * Handles {@code /package-tree}.
     *
     * <p>Returns a flat list of all packages in the loaded APK/JAR, sorted by class count
     * (descending). Each entry includes a library-detection heuristic flag.</p>
     */
    public void handleGetPackageTree(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();

            Map<String, Integer> packageCounts = new HashMap<>();
            for (JavaClass cls : allClasses) {
                String fullName = cls.getFullName();
                int lastDot = fullName.lastIndexOf('.');
                String pkg = lastDot > 0 ? fullName.substring(0, lastDot) : "(default)";
                packageCounts.merge(pkg, 1, Integer::sum);
            }

            List<Map<String, Object>> packages = packageCounts.entrySet().stream()
                    .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                    .map(entry -> {
                        Map<String, Object> pkg = new HashMap<>();
                        pkg.put("name", entry.getKey());
                        pkg.put("class_count", entry.getValue());
                        pkg.put("is_likely_library", isLikelyLibrary(entry.getKey()));
                        return pkg;
                    })
                    .collect(Collectors.toList());

            Map<String, Object> result = new HashMap<>();
            result.put("total_classes", allClasses.size());
            result.put("total_packages", packages.size());
            result.put("packages", packages);
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error building package tree: " + e.getMessage(), e, logger);
        }
    }

    /**
     * Handles {@code /jar-entry-points}.
     *
     * <p>Intelligently discovers entry points for JAR files: Main-Class from MANIFEST.MF,
     * Spring Boot Start-Class, classes with public static void main, and SPI services.</p>
     */
    public void handleJarEntryPoints(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType =
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(wrapper);

            if (fileType.getPrimaryType() != com.zin.jadxaimcp.utils.FileTypeDetector.FileType.JAR) {
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

                    String mainClass = attrs.getValue("Main-Class");
                    if (mainClass != null && !mainClass.isEmpty()) {
                        Map<String, Object> entry = new HashMap<>();
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
            List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();
            for (JavaClass cls : allClasses) {
                try {
                    String className = cls.getFullName();
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
                if (mainMethodCount >= 10) break;
                try {
                    for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                        if (methodSnapshot.getName().equals("main")
                            && methodSnapshot.getAccessFlags() != null
                            && methodSnapshot.getAccessFlags().isStatic()
                            && methodSnapshot.getAccessFlags().isPublic()) {
                            if ("void".equals(String.valueOf(methodSnapshot.getReturnType()))) {
                                List<ArgType> args = methodSnapshot.getArgumentTypes();
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
     * Handles {@code /jar-bytecode}.
     *
     * <p>Gets the disassembled bytecode representation of a class. Works for both JAR and APK
     * files, showing class structure similar to {@code javap}.</p>
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

            StringBuilder bytecode = new StringBuilder();

            bytecode.append("// Class: ").append(targetClass.getFullName()).append("\n");
            bytecode.append("// File type: ").append(fileType.getPrimaryType().getName().toUpperCase()).append("\n\n");

            bytecode.append("// Access: ").append(classAccessFlags.rawValue())
                    .append(" (").append(classAccessFlags.toString()).append(")\n");

            String superClass = JadxApiAdapter.getSuperClass(targetClass);
            if (superClass != null) {
                bytecode.append("// Extends: ").append(superClass).append("\n");
            }

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

            bytecode.append("// Fields:\n");
            for (JadxApiAdapter.FieldInfoSnapshot fieldSnapshot : fieldSnapshots) {
                bytecode.append("  ").append(fieldSnapshot.getAccessFlags().toString())
                        .append(" ").append(fieldSnapshot.getType())
                        .append(" ").append(fieldSnapshot.getName()).append("\n");
            }
            bytecode.append("\n");

            bytecode.append("// Methods:\n");
            for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : methodSnapshots) {
                bytecode.append("  ").append(methodSnapshot.getAccessFlags().toString())
                        .append(" ").append(methodSnapshot.getReturnType())
                        .append(" ").append(methodSnapshot.getName())
                        .append("(");

                var args = methodSnapshot.getArgumentTypes();
                for (int i = 0; i < args.size(); i++) {
                    if (i > 0) bytecode.append(", ");
                    bytecode.append(args.get(i).toString());
                }
                bytecode.append(")\n");

                if (methodSnapshot.getBasicBlockCount() != null) {
                    bytecode.append("    // Basic blocks: ").append(methodSnapshot.getBasicBlockCount()).append("\n");
                }
            }

            result.put("bytecode", bytecode.toString());
            result.put("field_count", fieldSnapshots.size());
            result.put("method_count", methodSnapshots.size());
            result.put("status", "success");

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

    // ------------------------------- Helpers -----------------------------------

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

    private String getSelectedTabTitle() {
        if (mainWindow == null || mainWindow.getTabbedPane() == null)
            return null;

        int index = mainWindow.getTabbedPane().getSelectedIndex();
        if (index != -1) {
            return mainWindow.getTabbedPane().getTitleAt(index);
        }

        return null;
    }

    private String extractTextFromCurrentTab() {
        if (mainWindow == null)
            return null;

        Component component = mainWindow.getTabbedPane().getSelectedComponent();
        JTextArea textArea = findTextArea(component);

        return textArea != null ? textArea.getText() : null;
    }

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

    private boolean isLikelyLibrary(String packageName) {
        if (packageName == null) return false;
        for (String prefix : LIBRARY_PREFIXES) {
            if (packageName.startsWith(prefix)) {
                return true;
            }
        }
        return false;
    }
}
