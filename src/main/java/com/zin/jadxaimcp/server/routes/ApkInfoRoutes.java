package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.ResourceFile;
import jadx.core.utils.android.AndroidManifestParser;
import jadx.core.xmlgen.ResContainer;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

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
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;

/**
 * APK Info API Routes
 * 
 * Provides /apk-info endpoint that returns current loaded APK metadata.
 * Used for multi-instance management to identify which app each JADX instance has opened.
 *
 * @author JADX AI MCP Team
 */
public class ApkInfoRoutes {
    private static final Logger logger = LoggerFactory.getLogger(ApkInfoRoutes.class);
    private final MainWindow mainWindow;
    private final JadxAIMCP plugin;

    public ApkInfoRoutes(MainWindow mainWindow, JadxAIMCP plugin) {
        this.mainWindow = mainWindow;
        this.plugin = plugin;
    }

    /**
     * GET /apk-info
     * 
     * Returns current loaded APK information:
     * - instance_name: Instance name (user configured or auto-generated)
     * - apk_package: Package name
     * - version_name: Version name
     * - version_code: Version code
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
                result.put("error", "No APK loaded");
                ctx.json(result);
                return;
            }
            
            // Get Manifest
            List<ResourceFile> resources = wrapper.getResources();
            if (resources == null || resources.isEmpty()) {
                result.put("loaded", false);
                result.put("error", "No resources available");
                ctx.json(result);
                return;
            }
            
            ResourceFile manifestFile = AndroidManifestParser.getAndroidManifest(resources);
            if (manifestFile == null) {
                result.put("loaded", false);
                result.put("error", "AndroidManifest.xml not found");
                ctx.json(result);
                return;
            }
            
            result.put("loaded", true);
            
            // Load manifest content
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
            
            // Server info
            result.put("server_bind_address", plugin.getCurrentBindAddress());
            result.put("server_port", plugin.getCurrentPort());
            
            // Plugin version info
            result.put("plugin_version", com.zin.jadxaimcp.utils.JadxAIMCPBanner.VERSION);
            result.put("build_commit", com.zin.jadxaimcp.utils.JadxAIMCPBanner.BUILD_COMMIT);
            
            logger.debug("JADX AI MCP Plugin: APK info requested");
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, 
                "Failed to get APK info: " + e.getMessage(), e, logger);
        }
    }
}
