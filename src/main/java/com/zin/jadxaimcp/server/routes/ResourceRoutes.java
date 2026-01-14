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
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

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

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.ResourceCacheManager;

public class ResourceRoutes {
    private static final Logger logger = LoggerFactory.getLogger(ResourceRoutes.class);
    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;

    public ResourceRoutes(MainWindow mainWindow) {
        this.mainWindow = mainWindow;
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
     */
    public void handleManifest(Context ctx) {
        try {
            ResourceFile manifest = getManifestFile();
            if (manifest == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "AndroidManifest.xml not found.", logger);
                return;
            }
            ResContainer container = manifest.loadContent();
            String content = container.getText().getCodeStr();
            ctx.json(Map.of("name", manifest.getOriginalName(), "type", "manifest/xml", "content", content));
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error occurred while trying to fetch the AndroidManifest.xml file: " + e.getMessage(), e, logger);
        }
    }

    /**
     * Handle the /strings MCP tool call using unified ResourceCacheManager.
     * 
     * Performance optimization for large APKs:
     * 1. First request triggers background loading via ResourceCacheManager
     * 2. Subsequent requests use shared cache for instant response
     */
    public void handleStrings(Context ctx) {
        try {
            ResourceCacheManager.CacheStatus status = ResourceCacheManager.getStatus();
            
            switch (status) {
                case READY:
                    serveStringsFromUnifiedCache(ctx);
                    return;
                    
                case LOADING:
                    Map<String, Object> loading = new HashMap<>();
                    loading.put("type", "resource/strings-xml");
                    loading.put("status", "loading");
                    loading.put("message", "Resource data is being loaded in background, please retry in 10 seconds");
                    loading.put("retry_after", 10);
                    ctx.status(202).json(loading);
                    return;
                    
                case ERROR:
                    Map<String, Object> error = new HashMap<>();
                    error.put("type", "resource/strings-xml");
                    error.put("error", ResourceCacheManager.getErrorMessage());
                    error.put("suggestion", "Use get_resource_file with specific path like 'res/values/strings.xml'");
                    ctx.status(500).json(error);
                    return;
                    
                case NOT_INITIALIZED:
                    // Trigger background loading
                    boolean started = ResourceCacheManager.initCache(mainWindow.getWrapper());
                    Map<String, Object> result = new HashMap<>();
                    result.put("type", "resource/strings-xml");
                    if (started) {
                        result.put("status", "loading_started");
                        result.put("message", "Background loading started, please retry in 30 seconds");
                        result.put("retry_after", 30);
                    } else {
                        result.put("status", "loading");
                        result.put("message", "Loading already in progress, please retry in 10 seconds");
                        result.put("retry_after", 10);
                    }
                    ctx.status(202).json(result);
                    return;
                    
                default:
                    JadxAIMCPPluginError.handleError(ctx, 500, "Unknown cache status", logger);
            }
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, 
                "Internal error occurred while trying to handle the /strings: " + e.getMessage(), e, logger);
        }
    }
    
    /**
     * Serve strings.xml files from unified cache with pagination.
     */
    private void serveStringsFromUnifiedCache(Context ctx) {
        // Get pre-computed strings.xml files from unified cache (O(1))
        List<ResContainer> stringsFiles = ResourceCacheManager.getStringsFiles();
        
        if (stringsFiles.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 404, "No strings.xml resource found in cache.", logger);
            return;
        }
        
        // Parse pagination params
        int offset = paginationUtils.getIntParam(ctx, "offset", 0);
        int limit = paginationUtils.getIntParam(ctx, "limit", 0);
        if (limit == 0) {
            limit = paginationUtils.getIntParam(ctx, "count", paginationUtils.DEFAULT_PAGE_SIZE);
        }
        
        int totalFiles = stringsFiles.size();
        int startIdx = Math.max(0, Math.min(offset, totalFiles));
        int endIdx = Math.min(startIdx + (limit == 0 ? totalFiles : limit), totalFiles);
        
        // Load content only for items in range
        List<Map<String, String>> paginatedEntries = new ArrayList<>();
        for (int i = startIdx; i < endIdx; i++) {
            ResContainer file = stringsFiles.get(i);
            String fileName = file.getFileName();
            if (fileName == null) fileName = "unknown";
            
            try {
                String content = ResourceCacheManager.getContent(file);
                if (content != null) {
                    paginatedEntries.add(Map.of(
                        "file", fileName,
                        "content", content
                    ));
                } else {
                    paginatedEntries.add(Map.of(
                        "file", fileName,
                        "error", "Content unavailable"
                    ));
                }
            } catch (Exception e) {
                paginatedEntries.add(Map.of(
                    "file", fileName,
                    "error", "Failed to load: " + e.getMessage()
                ));
            }
        }
        
        // Build pagination response
        Map<String, Object> result = new HashMap<>();
        result.put("type", "resource/strings-xml");
        result.put("strings", paginatedEntries);
        result.put("cached", true);
        
        Map<String, Object> pagination = new HashMap<>();
        pagination.put("total", totalFiles);
        pagination.put("offset", startIdx);
        pagination.put("limit", endIdx - startIdx);
        pagination.put("count", paginatedEntries.size());
        pagination.put("has_more", endIdx < totalFiles);
        if (endIdx < totalFiles) {
            pagination.put("next_offset", endIdx);
        }
        if (startIdx > 0) {
            int prevLimit = limit > 0 ? limit : paginationUtils.DEFAULT_PAGE_SIZE;
            pagination.put("prev_offset", Math.max(0, startIdx - prevLimit));
        }
        result.put("pagination", pagination);
        
        ctx.json(result);
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
     * This method handle the /get-resource-file mcp tool call.
     * 
     * First it validates the http request for 'file_name' parameter.
     * Then for each ResourceFile 
     *  1. if this ResourceFile's is equal to the requested file
     *      a. return this file
     *  2. If this ResourceFile is compiled resource archive
     *      a. Use cached subfiles from ResourceCacheManager if available
     *  3. Break once any matching file is found
     * If none found then handle it else return the requested file.
     */
    public void handleGetResourceFile(Context ctx) {
        String fileName = ctx.queryParam("file_name");
        if (fileName == null || fileName.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required 'file_name' parameter.", logger);
            return;
        }

        try {
            Map<String, String> resFileContent = new HashMap<>();
            
            // First try to find in cached subfiles (from resources.arsc)
            if (ResourceCacheManager.isReady()) {
                ResContainer cached = ResourceCacheManager.findSubFile(fileName);
                if (cached != null) {
                    String content = ResourceCacheManager.getContent(cached);
                    if (content != null) {
                        resFileContent.put("file_name", cached.getFileName());
                        resFileContent.put("content", content);
                    }
                }
            }
            
            // If not found in cache, try standalone resource files
            if (resFileContent.isEmpty()) {
                List<ResourceFile> resourceFiles = mainWindow.getWrapper().getResources();
                for (ResourceFile resFile : resourceFiles) {
                    if (resFile == null || resFile.getDeobfName() == null) continue;
                    
                    if (resFile.getDeobfName().equals(fileName)) {
                        // Direct match - load content
                        resFileContent.put("file_name", resFile.getDeobfName());
                        resFileContent.put("content", resFile.loadContent().getText().getCodeStr());
                        break;
                    }
                }
            }
            
            // If still not found and cache not ready, suggest retry
            if (resFileContent.isEmpty() && 
                ResourceCacheManager.getStatus() == ResourceCacheManager.CacheStatus.LOADING) {
                Map<String, Object> result = new HashMap<>();
                result.put("type", "resource/text");
                result.put("status", "loading");
                result.put("message", "Resource cache is loading, please retry in 10 seconds");
                result.put("retry_after", 10);
                ctx.status(202).json(result);
                return;
            }

            if (resFileContent.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "No resource file found: " + fileName, logger);
                return;
            }
            ctx.json(Map.of("type", "resource/text", "file", resFileContent, "cached", ResourceCacheManager.isReady()));
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal Error occurred while trying to handle the handleGetResourceFile(): " + e.getMessage(), e, logger);
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
                boolean started = ResourceCacheManager.initCache(mainWindow.getWrapper());
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
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper != null) {
                List<ResourceFile> resourceFiles = wrapper.getResources();
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
        return AndroidManifestParser.getAndroidManifest(mainWindow.getWrapper().getResources());
    }
}
