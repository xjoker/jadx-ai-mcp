package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TimeZone;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

import com.zin.jadxaimcp.JadxAIMCP;
import com.zin.jadxaimcp.utils.FileTypeDetector;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.ManifestInfoService;

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
    private final MainWindow mainWindow;
    private final JadxAIMCP plugin;
    private final ManifestInfoService manifestInfoService = ManifestInfoService.getInstance();

    public ApkInfoRoutes(MainWindow mainWindow, JadxAIMCP plugin) {
        this.mainWindow = mainWindow;
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
            
            // Get JADX Wrapper
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                result.put("loaded", false);
                result.put("error", "No file loaded");
                ctx.json(result);
                return;
            }
            
            // Detect file type
            FileTypeDetector.DetectionResult detection = FileTypeDetector.detect(wrapper);
            result.putAll(detection.toMap());
            
            // Add unavailable tools for AI guidance
            List<String> unavailableTools = detection.getUnavailableTools();
            if (!unavailableTools.isEmpty()) {
                result.put("unavailable_tools", unavailableTools);
            }
            
            // Check if we have classes loaded
            List<?> classes = wrapper.getIncludedClassesWithInners();
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
                parseAndroidManifest(wrapper, result);
            }

            // DEX count and total classes (always available when classes loaded)
            result.put("total_classes", classes.size());

            // APK-specific enrichment: signatures, native libs, DEX count
            if (detection.hasAndroidFeatures()) {
                enrichApkMetadata(wrapper, result);
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
    private void parseAndroidManifest(JadxWrapper wrapper, Map<String, Object> result) {
        try {
            String packageName = manifestInfoService.getPackageName(wrapper);
            if (packageName != null) {
                result.put("apk_package", packageName);
            }

            String versionName = manifestInfoService.getVersionName(wrapper);
            if (versionName != null) {
                result.put("version_name", versionName);
            }

            String versionCode = manifestInfoService.getVersionCode(wrapper);
            if (versionCode != null) {
                try {
                    result.put("version_code", Integer.parseInt(versionCode));
                } catch (NumberFormatException e) {
                    result.put("version_code", versionCode);
                }
            }

            String appLabel = manifestInfoService.getApplicationLabel(wrapper);
            if (appLabel != null) {
                if (appLabel.startsWith("@string/")) {
                    result.put("app_name_ref", appLabel);
                } else {
                    result.put("app_name", appLabel);
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
            
            // Get JADX Wrapper
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                result.put("loaded", false);
                result.put("error", "No file loaded");
                ctx.json(result);
                return;
            }
            
            // Detect file type
            FileTypeDetector.DetectionResult detection = FileTypeDetector.detect(wrapper);
            result.put("file_type", detection.getPrimaryType().getName());
            result.put("android_features", detection.hasAndroidFeatures());
            result.put("smali_available", detection.isSmaliAvailable());
            
            // Get file name
            List<java.nio.file.Path> filePaths = wrapper.getProject().getFilePaths();
            if (!filePaths.isEmpty()) {
                result.put("file_name", filePaths.get(0).getFileName().toString());
            }
            
            // Class count
            List<?> classes = wrapper.getIncludedClassesWithInners();
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
                parseAndroidManifest(wrapper, result);
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
     * Enriches the APK info response with signature certificate, native libraries,
     * and DEX count. Failures in any sub-section are caught and set to null to
     * avoid breaking the rest of the response.
     */
    private void enrichApkMetadata(JadxWrapper wrapper, Map<String, Object> result) {
        // Resolve APK file path
        java.io.File apkFile = null;
        try {
            List<java.nio.file.Path> filePaths = wrapper.getProject().getFilePaths();
            if (!filePaths.isEmpty()) {
                apkFile = filePaths.get(0).toFile();
            }
        } catch (Exception e) {
            logger.debug("Could not resolve APK file path: {}", e.getMessage());
        }

        if (apkFile == null || !apkFile.exists()) {
            result.put("signing_certificate", null);
            result.put("native_libraries", null);
            result.put("dex_count", null);
            return;
        }

        try (ZipFile zip = new ZipFile(apkFile)) {
            // --- Signature certificate (v1: META-INF/*.RSA / *.DSA / *.EC) ---
            Map<String, Object> certInfo = null;
            try {
                Enumeration<? extends ZipEntry> entries = zip.entries();
                while (entries.hasMoreElements()) {
                    ZipEntry entry = entries.nextElement();
                    String name = entry.getName();
                    if (name.startsWith("META-INF/") && (name.endsWith(".RSA") || name.endsWith(".DSA") || name.endsWith(".EC"))) {
                        try (InputStream is = zip.getInputStream(entry)) {
                            CertificateFactory cf = CertificateFactory.getInstance("X.509");
                            Certificate cert = cf.generateCertificate(is);
                            if (cert instanceof X509Certificate) {
                                X509Certificate x509 = (X509Certificate) cert;
                                certInfo = new LinkedHashMap<>();
                                certInfo.put("subject", x509.getSubjectDN().getName());
                                certInfo.put("algorithm", x509.getSigAlgName());

                                // SHA-256 fingerprint
                                byte[] encoded = x509.getEncoded();
                                MessageDigest md = MessageDigest.getInstance("SHA-256");
                                byte[] digest = md.digest(encoded);
                                StringBuilder hexSb = new StringBuilder();
                                for (byte b : digest) {
                                    hexSb.append(String.format("%02X", b));
                                }
                                certInfo.put("sha256", hexSb.toString().toLowerCase());

                                SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'");
                                sdf.setTimeZone(TimeZone.getTimeZone("UTC"));
                                certInfo.put("valid_from", sdf.format(x509.getNotBefore()));
                                certInfo.put("valid_until", sdf.format(x509.getNotAfter()));
                            }
                        } catch (Exception ex) {
                            logger.debug("Failed to parse signing cert entry {}: {}", name, ex.getMessage());
                        }
                        if (certInfo != null) break; // use first found cert
                    }
                }
            } catch (Exception ex) {
                logger.debug("Failed to enumerate APK entries for cert: {}", ex.getMessage());
            }
            result.put("signing_certificate", certInfo);

            // --- Native libraries: lib/<abi>/*.so ---
            List<Map<String, Object>> nativeLibs = new ArrayList<>();
            int dexCount = 0;
            try {
                Enumeration<? extends ZipEntry> allEntries = zip.entries();
                while (allEntries.hasMoreElements()) {
                    ZipEntry entry = allEntries.nextElement();
                    String name = entry.getName();

                    if (name.endsWith(".dex")) {
                        dexCount++;
                    }

                    if (name.startsWith("lib/") && name.endsWith(".so") && !entry.isDirectory()) {
                        // lib/<abi>/libfoo.so
                        String[] parts = name.split("/");
                        if (parts.length >= 3) {
                            String abi = parts[1];
                            String soName = parts[parts.length - 1];
                            Map<String, Object> libEntry = new LinkedHashMap<>();
                            libEntry.put("path", name);
                            libEntry.put("abi", abi);
                            libEntry.put("name", soName);
                            nativeLibs.add(libEntry);
                        }
                    }
                }
            } catch (Exception ex) {
                logger.debug("Failed to enumerate APK entries for native libs/dex: {}", ex.getMessage());
            }
            result.put("native_libraries", nativeLibs);
            result.put("dex_count", dexCount);

        } catch (Exception e) {
            logger.debug("Failed to open APK as ZIP for metadata enrichment: {}", e.getMessage());
            result.put("signing_certificate", null);
            result.put("native_libraries", null);
            result.put("dex_count", null);
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
