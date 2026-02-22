package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.ResourceFile;
import jadx.api.security.IJadxSecurity;
import jadx.core.utils.android.AndroidManifestParser;
import jadx.core.utils.android.AppAttribute;
import jadx.core.utils.android.ApplicationParams;
import jadx.core.utils.exceptions.JadxRuntimeException;
import jadx.core.xmlgen.ResContainer;
import jadx.api.JadxDecompiler;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.xml.sax.InputSource;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.io.StringReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.ArrayList;
import java.util.Map;
import java.util.List;
import java.util.stream.Collectors;
import java.io.InputStream;
import java.util.concurrent.CompletableFuture;
import javax.swing.JFrame;
import javax.swing.JTabbedPane;
import javax.swing.JTextArea;
import javax.swing.SwingUtilities;
import java.awt.Component;
import java.awt.Container;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.ResourceCacheManager;


public class ResourceRoutes {
    private static final Logger logger = LoggerFactory.getLogger(ResourceRoutes.class);
    private final JadxDecompiler decompiler;
    private final JFrame ownerFrame;
    private final PaginationUtils paginationUtils;
    
    // Dedicated single-thread executor for resource loading
    // Daemon thread to not prevent JVM shutdown
    private static final java.util.concurrent.ExecutorService resourceExecutor = 
        java.util.concurrent.Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "ResourceLoader");
            t.setDaemon(true);
            return t;
        });

    public ResourceRoutes(JadxDecompiler decompiler, JFrame ownerFrame) {
        this.decompiler = decompiler;
        this.ownerFrame = ownerFrame;
        this.paginationUtils = new PaginationUtils();
    }
    
    /**
     * Clear the resource cache (call when APK changes).
     * Delegates to unified ResourceCacheManager.
     */
    public static void clearStringsCache() {
        ResourceCacheManager.clearCache();
    }

    /**
     * @return void
     * @param Context
     * 
     * This route method handles /manifest http MCP tool call. 
     * First it tries to get the manifest file using getManifestFile() method
     * and assigns it to object named manifest. If this object is null then it returns,
     * else it loads the contents of manifest file in ResContainer object and from it fetches 
     * the content in String and returns this content.
     * 
     * Note: Only available for APK/AAR files with AndroidManifest.xml
     */
    public void handleManifest(Context ctx) {
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

            // Check file type - Manifest only available for Android files
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType =
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(decompiler);
            if (!fileType.hasAndroidFeatures()) {
                com.zin.jadxaimcp.utils.NotApplicableResponse.sendManifestNotAvailable(
                    ctx, fileType.getPrimaryType().getName());
                return;
            }

            ResourceFile manifest = getManifestFile();
            if (manifest == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "AndroidManifest.xml not found.", logger);
                return;
            }
            ResContainer container = manifest.loadContent();
            String content = container.getText().getCodeStr();
            
            // Use SmartChunker for large manifests
            Map<String, Object> result = com.zin.jadxaimcp.utils.SmartChunker.chunkResponse(
                content, chunk, "content");
            result.put("name", manifest.getOriginalName());
            result.put("type", "manifest/xml");
            
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error occurred while trying to fetch the AndroidManifest.xml file: " + e.getMessage(), e, logger);
        }
    }

    /**
     * Handle the /strings MCP tool call with AI-friendly modes.
     * 
     * Modes:
     * - summary (default): Returns stats and sample keys
     * - list: Paginated list of all string keys
     * - search: Search for strings containing a keyword
     * - get: Get a specific string by key name
     * 
     * Parameters:
     * - mode: summary|list|search|get (default: summary)
     * - query: Search keyword (for mode=search)
     * - key: String key name (for mode=get)
     * - locale: Locale variant like "values", "values-en" (default: values)
     * - offset: Pagination offset (default: 0)
     * - limit: Results per page (default: 50, max: 200)
     * 
     * Note: Only available for APK/AAR files with Android resources
     */
    public void handleStrings(Context ctx) {
        try {
            // Check file type - Strings only available for Android files
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType =
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(decompiler);
            if (!fileType.hasAndroidFeatures()) {
                com.zin.jadxaimcp.utils.NotApplicableResponse.sendStringsNotAvailable(
                    ctx, fileType.getPrimaryType().getName());
                return;
            }
            
            Map<String, Object> result = new HashMap<>();
            result.put("type", "resource/strings");
            
            // Check cache status first
            ResourceCacheManager.CacheStatus cacheStatus = ResourceCacheManager.getStatus();
            logger.info("handleStrings: cache status = {}", cacheStatus);
            
            if (cacheStatus != ResourceCacheManager.CacheStatus.READY) {
                handleStringsCacheNotReady(ctx, result, cacheStatus);
                return;
            }
            
            // Get parameters
            String mode = ctx.queryParam("mode") != null ? ctx.queryParam("mode") : "summary";
            String locale = ctx.queryParam("locale") != null ? ctx.queryParam("locale") : "values";
            int offset = ctx.queryParam("offset") != null ? Integer.parseInt(ctx.queryParam("offset")) : 0;
            int limit = ctx.queryParam("limit") != null ? Math.min(200, Integer.parseInt(ctx.queryParam("limit"))) : 50;
            
            // Find the target strings file
            String targetFile = "res/" + locale + "/strings.xml";
            ResContainer stringsFile = null;
            List<String> availableLocales = new ArrayList<>();
            
            for (ResContainer file : ResourceCacheManager.getStringsFiles()) {
                String fileName = file.getFileName();
                // Extract locale from path like "res/values-en/strings.xml"
                if (fileName.contains("/strings.xml")) {
                    String loc = fileName.replace("res/", "").replace("/strings.xml", "");
                    availableLocales.add(loc);
                    if (fileName.equals(targetFile)) {
                        stringsFile = file;
                    }
                }
            }
            
            if (stringsFile == null) {
                result.put("status", "not_found");
                result.put("message", "Locale '" + locale + "' not found");
                result.put("available_locales", availableLocales);
                ctx.json(result);
                return;
            }
            
            // Parse strings.xml into key-value map
            Map<String, String> strings = parseStringsXml(ResourceCacheManager.getContent(stringsFile));
            List<String> allKeys = new ArrayList<>(strings.keySet());
            java.util.Collections.sort(allKeys);
            
            result.put("locale", locale);
            result.put("available_locales", availableLocales);
            
            switch (mode) {
                case "summary":
                    // Return summary with sample keys
                    result.put("status", "success");
                    result.put("mode", "summary");
                    result.put("total_strings", strings.size());
                    result.put("sample_keys", allKeys.subList(0, Math.min(10, allKeys.size())));
                    result.put("usage", Map.of(
                        "list_keys", "?mode=list&offset=0&limit=50",
                        "search", "?mode=search&query=login",
                        "get_specific", "?mode=get&key=app_name",
                        "change_locale", "?locale=values-en"
                    ));
                    break;
                    
                case "list":
                    // Paginated list of keys
                    int endIndex = Math.min(offset + limit, allKeys.size());
                    List<String> pageKeys = allKeys.subList(offset, endIndex);
                    
                    result.put("status", "success");
                    result.put("mode", "list");
                    result.put("total", allKeys.size());
                    result.put("offset", offset);
                    result.put("limit", limit);
                    result.put("keys", pageKeys);
                    result.put("has_more", endIndex < allKeys.size());
                    break;
                    
                case "search":
                    // Search for strings containing keyword
                    String query = ctx.queryParam("query");
                    if (query == null || query.isEmpty()) {
                        result.put("status", "error");
                        result.put("error", "Missing 'query' parameter for search mode");
                        ctx.status(400).json(result);
                        return;
                    }
                    
                    String queryLower = query.toLowerCase();
                    List<Map<String, String>> matches = new ArrayList<>();
                    
                    for (Map.Entry<String, String> entry : strings.entrySet()) {
                        if (entry.getKey().toLowerCase().contains(queryLower) || 
                            entry.getValue().toLowerCase().contains(queryLower)) {
                            if (matches.size() >= limit) break;
                            matches.add(Map.of("key", entry.getKey(), "value", entry.getValue()));
                        }
                    }
                    
                    result.put("status", "success");
                    result.put("mode", "search");
                    result.put("query", query);
                    result.put("matches", matches);
                    result.put("count", matches.size());
                    break;
                    
                case "get":
                    // Get specific string by key
                    String key = ctx.queryParam("key");
                    if (key == null || key.isEmpty()) {
                        result.put("status", "error");
                        result.put("error", "Missing 'key' parameter for get mode");
                        ctx.status(400).json(result);
                        return;
                    }
                    
                    String value = strings.get(key);
                    if (value != null) {
                        result.put("status", "success");
                        result.put("mode", "get");
                        result.put("key", key);
                        result.put("value", value);
                    } else {
                        result.put("status", "not_found");
                        result.put("mode", "get");
                        result.put("key", key);
                        result.put("message", "String key not found");
                        
                        // Suggest similar keys
                        String keyLower = key.toLowerCase();
                        List<String> suggestions = allKeys.stream()
                            .filter(k -> k.toLowerCase().contains(keyLower))
                            .limit(5)
                            .collect(Collectors.toList());
                        if (!suggestions.isEmpty()) {
                            result.put("suggestions", suggestions);
                        }
                    }
                    break;
                    
                default:
                    result.put("status", "error");
                    result.put("error", "Unknown mode: " + mode);
                    result.put("valid_modes", List.of("summary", "list", "search", "get"));
                    ctx.status(400).json(result);
                    return;
            }
            
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Error in handleStrings: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Handle cache not ready states.
     */
    private void handleStringsCacheNotReady(Context ctx, Map<String, Object> result, 
                                            ResourceCacheManager.CacheStatus status) {
        switch (status) {
            case LOADING:
                result.put("status", "loading");
                result.put("message", "Resource cache is loading in background");
                result.put("health", ResourceCacheManager.getHealthInfo());
                result.put("retry_after", 3);
                ctx.status(202).json(result);
                break;
                
            case NOT_INITIALIZED:
                boolean started = ResourceCacheManager.initCache(decompiler);
                result.put("status", "loading_started");
                result.put("message", started ? "Resource cache loading started" : "Cache initialization pending");
                result.put("health", ResourceCacheManager.getHealthInfo());
                result.put("retry_after", 5);
                ctx.status(202).json(result);
                break;
                
            case ERROR:
                result.put("status", "error");
                result.put("error", ResourceCacheManager.getErrorMessage());
                result.put("message", "Resource loading failed. Try restarting JADX.");
                ctx.status(500).json(result);
                break;
                
            default:
                result.put("status", "error");
                result.put("error", "Unknown cache status: " + status);
                ctx.status(500).json(result);
        }
    }
    
    /**
     * Parse strings.xml content into a key-value map.
     * 
     * @param xmlContent The XML content of strings.xml
     * @return Map of string name to value
     */
    private Map<String, String> parseStringsXml(String xmlContent) {
        Map<String, String> strings = new HashMap<>();
        
        if (xmlContent == null || xmlContent.isEmpty()) {
            return strings;
        }
        
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
            DocumentBuilder builder = factory.newDocumentBuilder();
            Document doc = builder.parse(new InputSource(new StringReader(xmlContent)));
            
            var stringNodes = doc.getElementsByTagName("string");
            for (int i = 0; i < stringNodes.getLength(); i++) {
                Element elem = (Element) stringNodes.item(i);
                String name = elem.getAttribute("name");
                String value = elem.getTextContent();
                if (name != null && !name.isEmpty()) {
                    strings.put(name, value);
                }
            }
        } catch (Exception e) {
            logger.warn("Error parsing strings.xml: {}", e.getMessage());
        }
        
        return strings;
    }
    
    /**
     * Get content from all opened tabs that match the given filename pattern.
     * This reads from JTextArea components in the GUI, avoiding loadContent().
     */
    private List<Map<String, String>> getOpenedResourceTabs(String filenamePattern) {
        List<Map<String, String>> results = new ArrayList<>();
        
        jadx.gui.ui.MainWindow mw = ownerFrame instanceof jadx.gui.ui.MainWindow
            ? (jadx.gui.ui.MainWindow) ownerFrame : null;
        if (mw == null) {
            logger.debug("getOpenedResourceTabs: MainWindow not available");
            return results;
        }

        try {
            JTabbedPane tabbedPane = mw.getTabbedPane();
            if (tabbedPane == null) {
                logger.debug("getOpenedResourceTabs: tabbedPane is null");
                return results;
            }
            
            int tabCount = tabbedPane.getTabCount();
            logger.info("getOpenedResourceTabs: Found {} tabs, searching for pattern '{}'", tabCount, filenamePattern);
            
            for (int i = 0; i < tabCount; i++) {
                String tabTitle = tabbedPane.getTitleAt(i);
                logger.debug("  Tab {}: '{}'", i, tabTitle);
                
                // More flexible matching: check for "strings" in title for strings.xml
                boolean matches = false;
                if (filenamePattern.equals("strings.xml")) {
                    matches = tabTitle != null && (tabTitle.contains("strings.xml") || 
                              tabTitle.toLowerCase().startsWith("strings"));
                } else {
                    matches = tabTitle != null && tabTitle.contains(filenamePattern);
                }
                
                if (matches) {
                    logger.info("  Tab {} matches! Title: '{}'", i, tabTitle);
                    Component component = tabbedPane.getComponentAt(i);
                    String content = extractTextFromComponent(component);
                    if (content != null && !content.isEmpty()) {
                        logger.info("  Extracted {} characters from tab '{}'", content.length(), tabTitle);
                        Map<String, String> entry = new HashMap<>();
                        entry.put("name", tabTitle);
                        entry.put("content", content);
                        results.add(entry);
                    } else {
                        logger.warn("  Tab '{}' matched but content is empty/null", tabTitle);
                    }
                }
            }
            
            logger.info("getOpenedResourceTabs: Returning {} results", results.size());
        } catch (Exception e) {
            logger.warn("Error reading tabs: " + e.getMessage(), e);
        }
        
        return results;
    }
    
    /**
     * Recursively find JTextArea in component and extract text.
     */
    private String extractTextFromComponent(Component component) {
        if (component instanceof JTextArea) {
            return ((JTextArea) component).getText();
        }
        if (component instanceof Container) {
            for (Component child : ((Container) component).getComponents()) {
                String text = extractTextFromComponent(child);
                if (text != null && !text.isEmpty()) {
                    return text;
                }
            }
        }
        return null;
    }
    
    /**
     * Load a specific resource file content using Swing EDT thread.
     * 
     * JADX GUI uses EDT for all UI operations including resource loading.
     * By running loadContent in EDT, we match JADX's internal threading model.
     * 
     * @param targetFileName Name of the file to load (e.g. "res/values/strings.xml" or "AndroidManifest.xml")
     * @return Map with loaded content, or error information
     */
    private Map<String, Object> loadResourceViaEDT(String targetFileName) {
        Map<String, Object> result = new HashMap<>();
        result.put("requested_file", targetFileName);
        
        final java.util.concurrent.atomic.AtomicReference<String> contentRef = 
            new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<Exception> errorRef = 
            new java.util.concurrent.atomic.AtomicReference<>();
        
        try {
            SwingUtilities.invokeAndWait(() -> {
                try {
                    List<ResourceFile> resourceFiles = decompiler.getResources();
                    for (ResourceFile resFile : resourceFiles) {
                        if (resFile == null || resFile.getDeobfName() == null) continue;
                        
                        // Check for standalone resource files
                        if (resFile.getDeobfName().equals(targetFileName)) {
                            contentRef.set(resFile.loadContent().getText().getCodeStr());
                            break;
                        }
                        
                        // Check inside resources.arsc
                        if ("resources.arsc".equals(resFile.getDeobfName())) {
                            ResContainer container = resFile.loadContent();
                            if (container != null) {
                                String foundContent = findResourceRecursively(container, targetFileName);
                                if (foundContent != null) {
                                    contentRef.set(foundContent);
                                    break;
                                }
                            }
                        }
                    }
                } catch (Exception e) {
                    errorRef.set(e);
                }
            });
            
            if (errorRef.get() != null) {
                result.put("status", "error");
                result.put("error", "EDT loading failed: " + errorRef.get().getMessage());
            } else if (contentRef.get() != null) {
                result.put("status", "success");
                result.put("source", "edt_loading");
                result.put("content", contentRef.get());
            } else {
                result.put("status", "not_found");
            }
            
        } catch (java.lang.reflect.InvocationTargetException e) {
            result.put("status", "error");
            result.put("error", "EDT invocation failed: " + e.getCause().getMessage());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            result.put("status", "error");
            result.put("error", "EDT loading interrupted");
        }
        
        return result;
    }

    /**
     * Recursively search for a resource file in a ResContainer tree.
     */
    private String findResourceRecursively(ResContainer container, String targetFileName) {
        if (container == null) return null;

        // Check if current container matches the target file name
        String containerName = container.getName();
        String containerFileName = container.getFileName();
        
        if (targetFileName.equals(containerFileName) || targetFileName.equals(containerName)) {
             return container.getText().getCodeStr();
        }
        
        // Also check if targetFileName contains the container name (for partial matches)
        if (targetFileName.contains("strings.xml") && containerFileName != null && containerFileName.contains(targetFileName)) {
             return container.getText().getCodeStr();
        }

        // Check sub-files
        for (ResContainer sub : container.getSubFiles()) {
            // Check direct match or recursive search
            String result = findResourceRecursively(sub, targetFileName);
            if (result != null) return result;
        }
        return null;
    }
    
    /**
     * Helper class to hold string file reference without loading content.
     */
    private static class StringFileRef {
        final String fileName;
        final Object source; // Can be ResContainer or ResourceFile
        
        StringFileRef(String fileName, Object source) {
            this.fileName = fileName;
            this.source = source;
        }
    }
    
    /**
     * Load content from a string file reference.
     */
    private String loadStringFileContent(StringFileRef ref) throws Exception {
        if (ref.source instanceof ResContainer) {
            ResContainer container = (ResContainer) ref.source;
            return container.getText().getCodeStr();
        } else if (ref.source instanceof ResourceFile) {
            ResourceFile resFile = (ResourceFile) ref.source;
            return resFile.loadContent().getText().getCodeStr();
        }
        throw new IllegalArgumentException("Unknown source type: " + ref.source.getClass());
    }

    /**
     * @return void
     * @param Context
     * 
     * Handle the /get-resource-file MCP tool call with timeout protection.
     * Uses ExecutorService + Future.get(timeout) for controlled execution.
     */
    public void handleGetResourceFile(Context ctx) {
        String fileName = ctx.queryParam("file_name");
        if (fileName == null || fileName.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required 'file_name' parameter.", logger);
            return;
        }

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

        try {
            // 1. Try reading from GUI tabs first (instant, non-blocking)
            List<Map<String, String>> openedFiles = getOpenedResourceTabs(fileName);
            if (!openedFiles.isEmpty()) {
                String content = openedFiles.get(0).get("content");
                
                // Use SmartChunker for large resource files
                Map<String, Object> chunkedResult = com.zin.jadxaimcp.utils.SmartChunker.chunkResponse(
                    content, chunk, "content");
                
                Map<String, Object> result = new HashMap<>();
                result.put("type", "resource/text");
                result.put("status", "success");
                result.put("source", "gui_tabs");
                result.put("file_name", openedFiles.get(0).get("name"));
                
                // Merge chunking info
                result.putAll(chunkedResult);
                
                ctx.json(result);
                return;
            }

            // 2. Fallback to EDT-based loading
            logger.info("Resource file '{}' not in tabs. Falling back to EDT-based loading...", fileName);
            Map<String, Object> edtResult = loadResourceViaEDT(fileName);
            
            if ("success".equals(edtResult.get("status"))) {
                String content = (String) edtResult.get("content");
                
                // Use SmartChunker for large resource files
                Map<String, Object> chunkedResult = com.zin.jadxaimcp.utils.SmartChunker.chunkResponse(
                    content, chunk, "content");
                
                Map<String, Object> result = new HashMap<>();
                result.put("type", "resource/text");
                result.put("status", "success");
                result.put("source", "edt_loading");
                result.put("file_name", fileName);
                
                // Merge chunking info
                result.putAll(chunkedResult);
                
                ctx.json(result);
                return;
            }

            // 3. Fallback to Error/Not Found
            Map<String, Object> result = new HashMap<>();
            result.put("type", "resource/text");
            result.put("status", edtResult.get("status"));
            result.put("error", edtResult.getOrDefault("error", "Resource not found: " + fileName));
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Error in handleGetResourceFile: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @return void
     * @param Context
     * 
     * This method handle the /list-all-resource-file-names mcp tool call.
     * 
     * For each resource file, 
     *  1. if the resource file if compiled resource archive "resources.arsc"
     *      a. Use cached subfiles from ResourceCacheManager if available.
     *      b. Fall back to loading if cache not ready.
     *  2. If standalone file, directly get its name.
     *  3. If none found, return error.
     *  4. Return the list of resource file names with pagination support.
     */
    public void handleListAllResourceFilesNames(Context ctx) {
        try {
            List<String> resourceFileNames = new ArrayList<>();
            
            // Check if unified cache is available
            ResourceCacheManager.CacheStatus status = ResourceCacheManager.getStatus();
            
            if (status == ResourceCacheManager.CacheStatus.READY) {
                // Use cached subfile names
                resourceFileNames.addAll(ResourceCacheManager.getSubFileNames());
            } else if (status == ResourceCacheManager.CacheStatus.LOADING) {
                // Return 202 if still loading
                Map<String, Object> result = new HashMap<>();
                result.put("type", "application-resources");
                result.put("status", "loading");
                result.put("message", "Resource cache is loading, please retry in 10 seconds");
                result.put("retry_after", 10);
                ctx.status(202).json(result);
                return;
            } else if (status == ResourceCacheManager.CacheStatus.NOT_INITIALIZED) {
                // Trigger cache loading
                boolean started = ResourceCacheManager.initCache(decompiler);
                Map<String, Object> result = new HashMap<>();
                result.put("type", "application-resources");
                result.put("status", started ? "loading_started" : "loading");
                result.put("message", "Resource cache loading started, please retry in 30 seconds");
                result.put("retry_after", 30);
                ctx.status(202).json(result);
                return;
            }
            // On ERROR status, we still try to get standalone files
            
            // Also add standalone resource files (not in resources.arsc)
            List<ResourceFile> resourceFiles = decompiler.getResources();
            if (resourceFiles != null) {
                for (ResourceFile resFile : resourceFiles) {
                    if (resFile != null && resFile.getDeobfName() != null) {
                        String name = resFile.getDeobfName();
                        // Skip resources.arsc as subfiles are already in cache
                        if (!"resources.arsc".equals(name) && !resourceFileNames.contains(name)) {
                            resourceFileNames.add(name);
                        }
                    }
                }
            }

            if (resourceFileNames.isEmpty()) {
                String errorMsg = status == ResourceCacheManager.CacheStatus.ERROR 
                    ? "Cache error: " + ResourceCacheManager.getErrorMessage()
                    : "No resources found.";
                JadxAIMCPPluginError.handleError(ctx, 404, errorMsg, logger);
                return;
            }

            Map<String, Object> result = paginationUtils.handlePagination(
                ctx,
                resourceFileNames,
                "application-resources",
                "files",
                item -> item);
            
            // Add cache status info
            result.put("cached", status == ResourceCacheManager.CacheStatus.READY);

            ctx.json(result);
        } catch (PaginationException e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error while generating pagination result for handleListAllResourceFilesNames(): " + e.getMessage(), e, logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error while retrieving list of resource files names: " + e.getMessage(), e, logger);
        }
    }

    // Helper methods

    /**
     * @param
     * @return ResourceFile
     * 
     * This helper method is used to get the android manifest file using jadx's AndroidManifestParser class.
     */
    private ResourceFile getManifestFile() {
        return AndroidManifestParser.getAndroidManifest(decompiler.getResources());
    }
    
    /**
     * Handle the /jar-manifest MCP tool call.
     * 
     * Reads META-INF/MANIFEST.MF from JAR files and returns structured information.
     * Only available for JAR files.
     * 
     * Response format:
     * {
     *   "main_class": "com.example.App",
     *   "implementation_title": "my-app",
     *   "implementation_version": "1.0.0",
     *   "class_path": "lib/dep.jar",
     *   "spring_boot_classes": "BOOT-INF/classes/",
     *   "all_attributes": {...}
     * }
     */
    public void handleJarManifest(Context ctx) {
        try {
            // Check file type - only available for JAR files
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType =
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(decompiler);

            if (fileType.getPrimaryType() != com.zin.jadxaimcp.utils.FileTypeDetector.FileType.JAR) {
                // Not a JAR file - return NOT_APPLICABLE with APK alternative
                Map<String, Object> response = new HashMap<>();
                response.put("status", "NOT_APPLICABLE");
                response.put("reason", "JAR Manifest is only available for JAR files. This is a " +
                    fileType.getPrimaryType().getName().toUpperCase() + " file.");
                response.put("file_type", fileType.getPrimaryType().getName());
                response.put("alternatives", List.of(
                    Map.of("tool", "apk_get_manifest", "description", "Get AndroidManifest.xml for APK/AAR files")
                ));
                ctx.json(response);
                return;
            }

            // Get the loaded JAR file
            java.io.File jarFile = getLoadedFile();
            if (jarFile == null || !jarFile.exists()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "No JAR file loaded.", logger);
                return;
            }
            
            // Read MANIFEST.MF
            Map<String, Object> result = new HashMap<>();
            result.put("type", "jar-manifest");
            result.put("file_name", jarFile.getName());
            
            try (java.util.jar.JarFile jar = new java.util.jar.JarFile(jarFile)) {
                java.util.jar.Manifest manifest = jar.getManifest();
                
                if (manifest == null) {
                    result.put("status", "not_found");
                    result.put("message", "JAR file does not contain META-INF/MANIFEST.MF");
                    ctx.json(result);
                    return;
                }
                
                java.util.jar.Attributes mainAttrs = manifest.getMainAttributes();
                result.put("status", "success");
                
                // Extract commonly used attributes
                addIfPresent(result, "main_class", mainAttrs.getValue("Main-Class"));
                addIfPresent(result, "implementation_title", mainAttrs.getValue("Implementation-Title"));
                addIfPresent(result, "implementation_version", mainAttrs.getValue("Implementation-Version"));
                addIfPresent(result, "implementation_vendor", mainAttrs.getValue("Implementation-Vendor"));
                addIfPresent(result, "specification_title", mainAttrs.getValue("Specification-Title"));
                addIfPresent(result, "specification_version", mainAttrs.getValue("Specification-Version"));
                addIfPresent(result, "class_path", mainAttrs.getValue("Class-Path"));
                addIfPresent(result, "created_by", mainAttrs.getValue("Created-By"));
                addIfPresent(result, "built_by", mainAttrs.getValue("Built-By"));
                addIfPresent(result, "build_jdk", mainAttrs.getValue("Build-Jdk"));
                addIfPresent(result, "bundle_name", mainAttrs.getValue("Bundle-Name"));
                addIfPresent(result, "bundle_symbolic_name", mainAttrs.getValue("Bundle-SymbolicName"));
                addIfPresent(result, "bundle_version", mainAttrs.getValue("Bundle-Version"));
                
                // Spring Boot specific
                addIfPresent(result, "spring_boot_version", mainAttrs.getValue("Spring-Boot-Version"));
                addIfPresent(result, "spring_boot_classes", mainAttrs.getValue("Spring-Boot-Classes"));
                addIfPresent(result, "spring_boot_lib", mainAttrs.getValue("Spring-Boot-Lib"));
                addIfPresent(result, "start_class", mainAttrs.getValue("Start-Class"));
                
                // All attributes as map
                Map<String, String> allAttributes = new HashMap<>();
                for (Object key : mainAttrs.keySet()) {
                    String keyStr = key.toString();
                    String value = mainAttrs.getValue(keyStr);
                    if (value != null) {
                        allAttributes.put(keyStr, value);
                    }
                }
                result.put("all_attributes", allAttributes);
                result.put("attribute_count", allAttributes.size());
                
                // Check for named sections (per-entry attributes)
                Map<String, java.util.jar.Attributes> entries = manifest.getEntries();
                if (!entries.isEmpty()) {
                    Map<String, Map<String, String>> sections = new HashMap<>();
                    for (Map.Entry<String, java.util.jar.Attributes> entry : entries.entrySet()) {
                        Map<String, String> sectionAttrs = new HashMap<>();
                        for (Object key : entry.getValue().keySet()) {
                            sectionAttrs.put(key.toString(), entry.getValue().getValue(key.toString()));
                        }
                        sections.put(entry.getKey(), sectionAttrs);
                    }
                    result.put("named_sections", sections);
                    result.put("section_count", sections.size());
                }
            }
            
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Error reading JAR manifest: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Helper to add attribute to result map if value is not null.
     */
    private void addIfPresent(Map<String, Object> result, String key, String value) {
        if (value != null && !value.isEmpty()) {
            result.put(key, value);
        }
    }
    
    /**
     * Get the loaded file from JADX decompiler.
     */
    private java.io.File getLoadedFile() {
        try {
            java.util.List<java.io.File> inputFiles = decompiler.getArgs().getInputFiles();
            if (inputFiles != null && !inputFiles.isEmpty()) {
                return inputFiles.get(0);
            }
        } catch (Exception e) {
            logger.debug("Failed to get loaded file: " + e.getMessage());
        }
        return null;
    }
    
    /**
     * Handle the /jar-services MCP tool call.
     * 
     * Reads META-INF/services/* from JAR files to discover SPI service providers.
     * This is useful for understanding plugin architectures, JDBC drivers, logging frameworks, etc.
     * 
     * Response format:
     * {
     *   "services": [
     *     {"interface": "java.sql.Driver", "implementations": ["com.mysql.cj.jdbc.Driver"]},
     *     {"interface": "org.slf4j.spi.SLF4JServiceProvider", "implementations": ["ch.qos.logback..."]}
     *   ],
     *   "total_services": 2
     * }
     */
    public void handleJarServices(Context ctx) {
        try {
            // Check file type - only available for JAR files
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType =
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(decompiler);

            if (fileType.getPrimaryType() != com.zin.jadxaimcp.utils.FileTypeDetector.FileType.JAR) {
                // Not a JAR file - return NOT_APPLICABLE
                Map<String, Object> response = new HashMap<>();
                response.put("status", "NOT_APPLICABLE");
                response.put("reason", "JAR Services (SPI) is only available for JAR files. This is a " +
                    fileType.getPrimaryType().getName().toUpperCase() + " file.");
                response.put("file_type", fileType.getPrimaryType().getName());
                response.put("alternatives", List.of(
                    Map.of("tool", "search_classes_by_keyword", "description", "Search for interface implementations")
                ));
                ctx.json(response);
                return;
            }

            // Get the loaded JAR file
            java.io.File jarFile = getLoadedFile();
            if (jarFile == null || !jarFile.exists()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "No JAR file loaded.", logger);
                return;
            }
            
            // Read META-INF/services
            Map<String, Object> result = new HashMap<>();
            result.put("type", "jar-services");
            result.put("file_name", jarFile.getName());
            
            List<Map<String, Object>> services = new ArrayList<>();
            
            try (java.util.jar.JarFile jar = new java.util.jar.JarFile(jarFile)) {
                java.util.Enumeration<java.util.jar.JarEntry> entries = jar.entries();
                
                while (entries.hasMoreElements()) {
                    java.util.jar.JarEntry entry = entries.nextElement();
                    String name = entry.getName();
                    
                    // Look for META-INF/services/* files
                    if (name.startsWith("META-INF/services/") && !entry.isDirectory()) {
                        String interfaceName = name.substring("META-INF/services/".length());
                        
                        // Skip nested directories
                        if (interfaceName.contains("/")) continue;
                        
                        // Read implementations
                        List<String> implementations = new ArrayList<>();
                        try (InputStream is = jar.getInputStream(entry);
                             java.io.BufferedReader reader = new java.io.BufferedReader(
                                 new java.io.InputStreamReader(is, StandardCharsets.UTF_8))) {
                            String line;
                            while ((line = reader.readLine()) != null) {
                                line = line.trim();
                                // Skip comments and empty lines
                                if (!line.isEmpty() && !line.startsWith("#")) {
                                    // Remove inline comments
                                    int commentIdx = line.indexOf('#');
                                    if (commentIdx > 0) {
                                        line = line.substring(0, commentIdx).trim();
                                    }
                                    if (!line.isEmpty()) {
                                        implementations.add(line);
                                    }
                                }
                            }
                        }
                        
                        if (!implementations.isEmpty()) {
                            Map<String, Object> service = new HashMap<>();
                            service.put("interface", interfaceName);
                            service.put("implementations", implementations);
                            service.put("count", implementations.size());
                            services.add(service);
                        }
                    }
                }
            }
            
            result.put("status", "success");
            result.put("services", services);
            result.put("total_services", services.size());
            
            if (services.isEmpty()) {
                result.put("note", "No META-INF/services found. This JAR may not use Java SPI.");
            }
            
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Error reading JAR services: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Handle the /config-strings MCP tool call.
     * 
     * Unified configuration strings API that works for both APK and JAR files:
     * - APK/AAR: Returns strings.xml content (via existing get_strings logic)
     * - JAR: Searches for .properties files and returns their contents
     * 
     * Parameters:
     * - mode: "summary" (default) | "search" | "get"
     * - query: Search keyword for mode=search
     * - key: Property key for mode=get
     * - file: Specific properties file (for JAR), default searches all
     */
    public void handleConfigStrings(Context ctx) {
        try {
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType =
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(decompiler);

            String mode = ctx.queryParam("mode");
            if (mode == null) mode = "summary";

            Map<String, Object> result = new HashMap<>();
            result.put("type", "config-strings");

            if (fileType.hasAndroidFeatures()) {
                // APK/AAR: Delegate to existing strings handler logic
                result.put("source_type", "android_strings");
                result.put("source_file", "res/values/strings.xml");
                result.put("note", "For full functionality, use get_strings tool with mode parameter");

                // Quick summary of strings availability
                try {
                    ResourceFile stringsFile = findStringsXml();
                    if (stringsFile != null) {
                        result.put("available", true);
                        result.put("recommended_tool", "get_strings");
                    } else {
                        result.put("available", false);
                        result.put("error", "strings.xml not found");
                    }
                } catch (Exception e) {
                    result.put("available", false);
                    result.put("error", e.getMessage());
                }
            } else if (fileType.getPrimaryType() == com.zin.jadxaimcp.utils.FileTypeDetector.FileType.JAR) {
                // JAR: Search for .properties files
                result.put("source_type", "java_properties");
                
                java.util.List<java.io.File> cfgInputFiles = decompiler.getArgs().getInputFiles();
                java.nio.file.Path jarPath = (cfgInputFiles == null || cfgInputFiles.isEmpty()) ? null
                    : cfgInputFiles.get(0).toPath();
                if (jarPath == null) {
                    ctx.status(404).json(Map.of("error", "No JAR file loaded"));
                    return;
                }
                
                String query = ctx.queryParam("query");
                String key = ctx.queryParam("key");
                String targetFile = ctx.queryParam("file");
                
                List<Map<String, Object>> propertiesFiles = new ArrayList<>();
                
                try (java.util.jar.JarFile jar = new java.util.jar.JarFile(jarPath.toFile())) {
                    java.util.Enumeration<java.util.jar.JarEntry> entries = jar.entries();
                    
                    while (entries.hasMoreElements()) {
                        java.util.jar.JarEntry entry = entries.nextElement();
                        String name = entry.getName();
                        
                        // Look for .properties files
                        if (name.endsWith(".properties") && !entry.isDirectory()) {
                            // Filter by target file if specified
                            if (targetFile != null && !name.contains(targetFile)) {
                                continue;
                            }
                            
                            Map<String, Object> propFile = new HashMap<>();
                            propFile.put("file", name);
                            
                            // Read properties
                            java.util.Properties props = new java.util.Properties();
                            try (InputStream is = jar.getInputStream(entry)) {
                                props.load(is);
                            }
                            
                            propFile.put("key_count", props.size());
                            
                            if ("summary".equals(mode)) {
                                // Just file info and sample keys
                                List<String> sampleKeys = new ArrayList<>();
                                int count = 0;
                                for (String k : props.stringPropertyNames()) {
                                    if (count++ >= 5) break;
                                    sampleKeys.add(k);
                                }
                                propFile.put("sample_keys", sampleKeys);
                            } else if ("search".equals(mode) && query != null) {
                                // Search for matching keys/values
                                Map<String, String> matches = new HashMap<>();
                                for (String k : props.stringPropertyNames()) {
                                    String v = props.getProperty(k);
                                    if (k.toLowerCase().contains(query.toLowerCase()) ||
                                        (v != null && v.toLowerCase().contains(query.toLowerCase()))) {
                                        matches.put(k, v);
                                    }
                                }
                                propFile.put("matches", matches);
                                propFile.put("match_count", matches.size());
                            } else if ("get".equals(mode) && key != null) {
                                // Get specific key
                                String value = props.getProperty(key);
                                if (value != null) {
                                    propFile.put("key", key);
                                    propFile.put("value", value);
                                }
                            } else {
                                // Default: all properties
                                Map<String, String> allProps = new HashMap<>();
                                for (String k : props.stringPropertyNames()) {
                                    allProps.put(k, props.getProperty(k));
                                }
                                propFile.put("properties", allProps);
                            }
                            
                            propertiesFiles.add(propFile);
                            
                            // Limit files in summary mode
                            if ("summary".equals(mode) && propertiesFiles.size() >= 10) {
                                break;
                            }
                        }
                    }
                }
                
                result.put("files", propertiesFiles);
                result.put("total_files", propertiesFiles.size());
                
                if (propertiesFiles.isEmpty()) {
                    result.put("note", "No .properties files found in JAR");
                }
            } else {
                result.put("source_type", "unknown");
                result.put("error", "Config strings not available for this file type");
            }
            
            result.put("status", "success");
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Error reading config strings: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Find strings.xml in resources.
     */
    private ResourceFile findStringsXml() {
        List<ResourceFile> resources = decompiler.getResources();
        if (resources == null) return null;

        for (ResourceFile res : resources) {
            if (res.getOriginalName() != null &&
                res.getOriginalName().contains("strings.xml")) {
                return res;
            }
        }
        return null;
    }
    
    /**
     * Handle the /jar-dependencies MCP tool call.
     * 
     * Analyzes JAR dependencies from multiple sources:
     * 1. META-INF/maven/.../pom.properties - Maven coordinates
     * 2. META-INF/maven/.../pom.xml - Full dependency tree
     * 3. MANIFEST.MF - Class-Path entries
     * 4. Nested JARs in BOOT-INF/lib/ (Spring Boot)
     * 
     * Only available for JAR files.
     */
    public void handleJarDependencies(Context ctx) {
        try {
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType =
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(decompiler);

            if (fileType.getPrimaryType() != com.zin.jadxaimcp.utils.FileTypeDetector.FileType.JAR) {
                List<com.zin.jadxaimcp.utils.NotApplicableResponse.Alternative> alts = new ArrayList<>();
                alts.add(new com.zin.jadxaimcp.utils.NotApplicableResponse.Alternative(
                    "get_file_info", "Get file type and available features"));
                com.zin.jadxaimcp.utils.NotApplicableResponse.send(
                    ctx, "Dependency analysis is only for JAR files. This is a " +
                    fileType.getPrimaryType().getName().toUpperCase() + " file.",
                    fileType.getPrimaryType().getName(), alts);
                return;
            }

            java.util.List<java.io.File> depInputFiles = decompiler.getArgs().getInputFiles();
            java.nio.file.Path jarPath = (depInputFiles == null || depInputFiles.isEmpty()) ? null
                : depInputFiles.get(0).toPath();
            if (jarPath == null) {
                ctx.status(404).json(Map.of("error", "No JAR file loaded"));
                return;
            }
            
            Map<String, Object> result = new HashMap<>();
            result.put("type", "jar-dependencies");
            result.put("file_name", jarPath.getFileName().toString());
            
            List<Map<String, Object>> dependencies = new ArrayList<>();
            String groupId = null;
            String artifactId = null;
            String version = null;
            
            try (java.util.jar.JarFile jar = new java.util.jar.JarFile(jarPath.toFile())) {
                java.util.Enumeration<java.util.jar.JarEntry> entries = jar.entries();
                
                // Track nested JARs (Spring Boot BOOT-INF/lib/)
                List<String> nestedJars = new ArrayList<>();
                
                while (entries.hasMoreElements()) {
                    java.util.jar.JarEntry entry = entries.nextElement();
                    String name = entry.getName();
                    
                    // 1. Parse pom.properties for Maven coordinates
                    if (name.endsWith("pom.properties") && name.startsWith("META-INF/maven/")) {
                        try (InputStream is = jar.getInputStream(entry)) {
                            java.util.Properties props = new java.util.Properties();
                            props.load(is);
                            groupId = props.getProperty("groupId");
                            artifactId = props.getProperty("artifactId");
                            version = props.getProperty("version");
                        }
                    }
                    
                    // 2. Count nested JARs in BOOT-INF/lib/
                    if (name.startsWith("BOOT-INF/lib/") && name.endsWith(".jar")) {
                        String jarName = name.substring("BOOT-INF/lib/".length());
                        nestedJars.add(jarName);
                        
                        // Parse dependency info from jar name (e.g., spring-core-6.1.0.jar)
                        Map<String, Object> dep = parseDependencyFromJarName(jarName);
                        if (dep != null) {
                            dep.put("source", "BOOT-INF/lib");
                            dependencies.add(dep);
                        }
                    }
                }
                
                // 3. Check MANIFEST.MF for Class-Path
                java.util.jar.Manifest manifest = jar.getManifest();
                if (manifest != null) {
                    String classPath = manifest.getMainAttributes().getValue("Class-Path");
                    if (classPath != null && !classPath.isEmpty()) {
                        String[] paths = classPath.split("\\s+");
                        for (String path : paths) {
                            if (path.endsWith(".jar")) {
                                Map<String, Object> dep = parseDependencyFromJarName(path);
                                if (dep != null) {
                                    dep.put("source", "MANIFEST Class-Path");
                                    dependencies.add(dep);
                                }
                            }
                        }
                    }
                }
                
                result.put("nested_jars_count", nestedJars.size());
            }
            
            // Set main artifact info
            if (groupId != null) result.put("group_id", groupId);
            if (artifactId != null) result.put("artifact_id", artifactId);
            if (version != null) result.put("version", version);
            
            result.put("dependencies", dependencies);
            result.put("total_dependencies", dependencies.size());
            result.put("status", "success");
            
            if (dependencies.isEmpty()) {
                result.put("note", "No embedded dependencies found. Check external build files (pom.xml, build.gradle).");
            }
            
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Error analyzing JAR dependencies: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Parse dependency info from JAR filename.
     * E.g., "spring-core-6.1.0.jar" -> {name: "spring-core", version: "6.1.0"}
     */
    private Map<String, Object> parseDependencyFromJarName(String jarName) {
        if (jarName == null || !jarName.endsWith(".jar")) return null;
        
        // Remove .jar suffix
        String name = jarName.substring(0, jarName.length() - 4);
        
        // Try to extract version (last segment after -)
        int lastDash = name.lastIndexOf('-');
        if (lastDash > 0) {
            String possibleVersion = name.substring(lastDash + 1);
            // Check if it looks like a version (starts with digit)
            if (!possibleVersion.isEmpty() && Character.isDigit(possibleVersion.charAt(0))) {
                Map<String, Object> dep = new HashMap<>();
                dep.put("name", name.substring(0, lastDash));
                dep.put("version", possibleVersion);
                return dep;
            }
        }
        
        // No version detected
        Map<String, Object> dep = new HashMap<>();
        dep.put("name", name);
        return dep;
    }
}
