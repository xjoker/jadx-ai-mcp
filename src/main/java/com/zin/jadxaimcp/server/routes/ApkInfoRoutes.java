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
 * APK 信息 API 路由
 * 
 * 提供 /apk-info 接口，返回当前加载的 APK 元数据。
 * 用于多实例管理时识别各 JADX 实例打开的应用。
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
     * 返回当前加载的 APK 信息：
     * - instance_name: 实例名称（用户配置或自动生成）
     * - apk_package: 包名
     * - version_name: 版本名
     * - version_code: 版本号
     */
    public void handleApkInfo(Context ctx) {
        try {
            Map<String, Object> result = new HashMap<>();
            
            // 实例名称
            String instanceName = plugin.getInstanceName();
            if (instanceName == null || instanceName.isEmpty()) {
                instanceName = plugin.getAutoInstanceName();
            }
            result.put("instance_name", instanceName);
            
            // 获取 JADX Wrapper
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) {
                result.put("loaded", false);
                result.put("error", "No APK loaded");
                ctx.json(result);
                return;
            }
            
            // 获取 Manifest
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
            
            // 加载 manifest 内容
            ResContainer container = manifestFile.loadContent();
            String manifestXml = container.getText().getCodeStr();
            
            // 使用 DOM 解析 manifest
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
            
            // 服务器信息
            result.put("server_bind_address", plugin.getCurrentBindAddress());
            result.put("server_port", plugin.getCurrentPort());
            
            logger.debug("JADX AI MCP Plugin: APK info requested");
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, 
                "Failed to get APK info: " + e.getMessage(), e, logger);
        }
    }
}
