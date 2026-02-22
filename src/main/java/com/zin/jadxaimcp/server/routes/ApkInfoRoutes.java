package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.ResourceFile;
import jadx.core.utils.android.AndroidManifestParser;
import jadx.api.JadxDecompiler;
import jadx.core.xmlgen.ResContainer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.zin.jadxaimcp.JadxAIMCP;
import com.zin.jadxaimcp.utils.FileTypeDetector;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;

/**
 * APK/JAR Info API Routes
 * 
 * Provides /apk-info endpoint that returns current loaded file metadata.
 * Supports APK, JAR, DEX, AAR, and class files.
 * Used for multi-instance management and AI guidance on available features.
 *
 * @author JADX AI MCP Team
 */
public class ApkInfoRoutes {
    private static final Logger logger = LoggerFactory.getLogger(ApkInfoRoutes.class);
    private final JadxDecompiler decompiler;
    private final JadxAIMCP plugin;

    public ApkInfoRoutes(JadxDecompiler decompiler, JadxAIMCP plugin) {
        this.decompiler = decompiler;
        this.plugin = plugin;
    }

    /**
     * GET /apk-info
     * 
     * Returns current loaded file information:
     * - instance_name: Instance name (user configured or auto-generated)
     * - file_type: Detected file type (apk/jar/dex/aar/class/unknown)
     * - android_features: Boolean indicating if Android-specific features are available
     * - smali_available: Boolean indicating if Smali generation is possible
     * - apk_package: Package name (only for APK/AAR)
     * - version_name: Version name (only for APK/AAR)
     * - version_code: Version code (only for APK/AAR)
     */
    public void handleApkInfo(Context ctx) {
        try {
            Map<String, Object> result = new HashMap<>();
            
            // Instance name
            String instanceName = plugin.getInstanceName();
            if (instanceName == null || instanceName.isEmpty()) {
                instanceName = plugin.getAutoInstanceName();
            }
            result.put("instance_name", instanceName);
            
            // Check decompiler is available
            if (decompiler == null) {
                result.put("loaded", false);
                result.put("error", "No file loaded");
                ctx.json(result);
                return;
            }

            // Detect file type
            FileTypeDetector.DetectionResult detection = FileTypeDetector.detect(decompiler);
            result.putAll(detection.toMap());
            
            // Add unavailable tools for AI guidance
            List<String> unavailableTools = detection.getUnavailableTools();
            if (!unavailableTools.isEmpty()) {
                result.put("unavailable_tools", unavailableTools);
            }
            
            // Check if we have classes loaded
            List<?> classes = decompiler.getClassesWithInners();
            if (classes == null || classes.isEmpty()) {
                result.put("loaded", false);
                result.put("error", "No classes available");
                ctx.json(result);
                return;
            }
            
            result.put("loaded", true);
            result.put("class_count", classes.size());
            
            // Try to get Android manifest info (only for APK/AAR)
            if (detection.hasAndroidFeatures()) {
                parseAndroidManifest(decompiler, result);
            }
            
            // Server info
            result.put("server_bind_address", plugin.getCurrentBindAddress());
            result.put("server_port", plugin.getCurrentPort());
            
            // Plugin version info
            result.put("plugin_version", com.zin.jadxaimcp.utils.JadxAIMCPBanner.VERSION);
            result.put("build_commit", com.zin.jadxaimcp.utils.JadxAIMCPBanner.BUILD_COMMIT);
            
            logger.debug("JADX AI MCP Plugin: File info requested, type={}", detection.getPrimaryType().getName());
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, 
                "Failed to get file info: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Parses AndroidManifest.xml to extract package and version info.
     * Only called when android_features is true.
     */
    private void parseAndroidManifest(JadxDecompiler decompiler, Map<String, Object> result) {
        try {
            List<ResourceFile> resources = decompiler.getResources();
            if (resources == null || resources.isEmpty()) {
                return;
            }
            
            ResourceFile manifestFile = AndroidManifestParser.getAndroidManifest(resources);
            if (manifestFile == null) {
                return;
            }
            
            ResContainer container = manifestFile.loadContent();
            String manifestXml = container.getText().getCodeStr();
            
            // Parse manifest using DOM
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            DocumentBuilder builder = factory.newDocumentBuilder();
            Document doc = builder.parse(new ByteArrayInputStream(manifestXml.getBytes(StandardCharsets.UTF_8)));
            
            Element manifestElement = (Element) doc.getElementsByTagName("manifest").item(0);
            if (manifestElement != null) {
                // Package name
                String packageName = manifestElement.getAttribute("package");
                if (!packageName.isEmpty()) {
                    result.put("apk_package", packageName);
                }
                
                // Version info
                String versionName = manifestElement.getAttribute("android:versionName");
                if (!versionName.isEmpty()) {
                    result.put("version_name", versionName);
                }
                
                String versionCodeStr = manifestElement.getAttribute("android:versionCode");
                if (!versionCodeStr.isEmpty()) {
                    try {
                        result.put("version_code", Integer.parseInt(versionCodeStr));
                    } catch (NumberFormatException e) {
                        result.put("version_code", versionCodeStr);
                    }
                }
            }
        } catch (Exception e) {
            logger.debug("Failed to parse AndroidManifest: {}", e.getMessage());
        }
    }
    
    /**
     * GET /file-info
     * 
     * Unified file information API that works for both APK and JAR files.
     * This is the recommended entry point for AI agents to understand file context.
     * 
     * Returns:
     * - file_type: Detected type (apk/jar/dex/aar/class)
     * - file_name: Original file name
     * - class_count: Total number of classes
     * - android_features: Boolean for Android-specific tools availability
     * - smali_available: Boolean for Smali generation support
     * 
     * For APK/AAR:
     * - package_name, version_name, version_code, main_activity
     * 
     * For JAR:
     * - main_class, implementation_title, implementation_version, spring_boot_version
     * - entry_points_available: Boolean indicating if entry points can be discovered
     */
    public void handleFileInfo(Context ctx) {
        try {
            Map<String, Object> result = new HashMap<>();
            result.put("type", "file-info");

            // Check decompiler is available
            if (decompiler == null) {
                result.put("loaded", false);
                result.put("error", "No file loaded");
                ctx.json(result);
                return;
            }

            // Detect file type
            FileTypeDetector.DetectionResult detection = FileTypeDetector.detect(decompiler);
            result.put("file_type", detection.getPrimaryType().getName());
            result.put("android_features", detection.hasAndroidFeatures());
            result.put("smali_available", detection.isSmaliAvailable());
            
            // Get file name
            List<java.io.File> inputFiles = decompiler.getArgs().getInputFiles();
            List<java.nio.file.Path> filePaths = inputFiles != null
                ? inputFiles.stream().map(java.io.File::toPath).collect(java.util.stream.Collectors.toList())
                : java.util.Collections.emptyList();
            if (!filePaths.isEmpty()) {
                result.put("file_name", filePaths.get(0).getFileName().toString());
            }
            
            // Class count
            List<?> classes = decompiler.getClassesWithInners();
            if (classes == null || classes.isEmpty()) {
                result.put("loaded", false);
                result.put("error", "No classes available");
                ctx.json(result);
                return;
            }
            result.put("loaded", true);
            result.put("class_count", classes.size());
            
            // Type-specific information
            if (detection.hasAndroidFeatures()) {
                // APK/AAR specific info
                result.put("file_category", "android");
                parseAndroidManifest(decompiler, result);
                result.put("recommended_tools", List.of(
                    "get_android_manifest",
                    "get_main_activity_class", 
                    "get_strings",
                    "get_smali_of_class"
                ));
            } else if (detection.getPrimaryType() == FileTypeDetector.FileType.JAR) {
                // JAR specific info
                result.put("file_category", "java");
                parseJarManifest(filePaths.get(0).toFile(), result);
                result.put("recommended_tools", List.of(
                    "jar_get_manifest",
                    "jar_get_entry_points",
                    "jar_get_services",
                    "get_class_source"
                ));
            } else if (detection.getPrimaryType() == FileTypeDetector.FileType.DEX) {
                // DEX specific info
                result.put("file_category", "android");
                result.put("note", "DEX file without resources. Limited to bytecode analysis.");
                result.put("recommended_tools", List.of(
                    "get_class_source",
                    "get_smali_of_class",
                    "search_classes_by_keyword"
                ));
            } else {
                result.put("file_category", "unknown");
            }
            
            // Available features summary
            Map<String, Boolean> features = new HashMap<>();
            features.put("manifest", detection.hasAndroidFeatures());
            features.put("smali", detection.isSmaliAvailable());
            features.put("strings", detection.hasAndroidFeatures());
            features.put("jar_manifest", detection.getPrimaryType() == FileTypeDetector.FileType.JAR);
            features.put("spi_services", detection.getPrimaryType() == FileTypeDetector.FileType.JAR);
            result.put("features", features);
            
            result.put("status", "success");
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, 
                "Failed to get file info: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Parse JAR MANIFEST.MF for common attributes.
     */
    private void parseJarManifest(java.io.File jarFile, Map<String, Object> result) {
        try (java.util.jar.JarFile jar = new java.util.jar.JarFile(jarFile)) {
            java.util.jar.Manifest manifest = jar.getManifest();
            if (manifest != null) {
                java.util.jar.Attributes attrs = manifest.getMainAttributes();
                
                // Common attributes
                String mainClass = attrs.getValue("Main-Class");
                if (mainClass != null) result.put("main_class", mainClass);
                
                String implTitle = attrs.getValue("Implementation-Title");
                if (implTitle != null) result.put("implementation_title", implTitle);
                
                String implVersion = attrs.getValue("Implementation-Version");
                if (implVersion != null) result.put("implementation_version", implVersion);
                
                // Spring Boot
                String startClass = attrs.getValue("Start-Class");
                if (startClass != null) result.put("start_class", startClass);
                
                String springVersion = attrs.getValue("Spring-Boot-Version");
                if (springVersion != null) result.put("spring_boot_version", springVersion);
                
                result.put("entry_points_available", mainClass != null || startClass != null);
            }
        } catch (Exception e) {
            logger.debug("Failed to parse JAR manifest: {}", e.getMessage());
        }
    }
}
