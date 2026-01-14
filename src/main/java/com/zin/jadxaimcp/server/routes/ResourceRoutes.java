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
import java.util.concurrent.CompletableFuture;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.ResourceCacheManager;


public class ResourceRoutes {
    private static final Logger logger = LoggerFactory.getLogger(ResourceRoutes.class);
    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;
    
    // Dedicated single-thread executor for resource loading
    // Daemon thread to not prevent JVM shutdown
    private static final java.util.concurrent.ExecutorService resourceExecutor = 
        java.util.concurrent.Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "ResourceLoader");
            t.setDaemon(true);
            return t;
        });

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
     * Handle the /strings MCP tool call with async loading.
     * 
     * Uses Javalin async HTTP to prevent blocking the server.
     * Resource loading runs in a separate thread with 60s timeout.
     */
    public void handleStrings(Context ctx) {
        // Parse variant param before async call
        String requestedVariant = ctx.queryParam("variant");
        
        // Use Javalin async with dedicated thread pool (not ForkJoinPool)
        ctx.future(() -> CompletableFuture.supplyAsync(() -> {
            try {
                List<ResourceFile> resourceFiles = mainWindow.getWrapper().getResources();
                List<String> availableVariants = new ArrayList<>();
                String defaultContent = null;
                String targetContent = null;
                String targetVariant = null;
                
                for (ResourceFile resFile : resourceFiles) {
                    try {
                        if ("resources.arsc".equals(resFile.getDeobfName())) {
                            ResContainer container = resFile.loadContent();
                            if (container != null) {
                                for (ResContainer file : container.getSubFiles()) {
                                    String fileName = file.getFileName();
                                    if (fileName != null && fileName.contains("strings.xml")) {
                                        availableVariants.add(fileName);
                                        
                                        // Load requested variant or default
                                        if (requestedVariant != null && requestedVariant.equals(fileName)) {
                                            targetContent = file.getText().getCodeStr();
                                            targetVariant = fileName;
                                        } else if ("res/values/strings.xml".equals(fileName) && requestedVariant == null) {
                                            defaultContent = file.getText().getCodeStr();
                                        }
                                    }
                                }
                            }
                            break;
                        }
                    } catch (Exception e) {
                        logger.warn("Error processing resource file: " + e.getMessage());
                    }
                }
                
                Map<String, Object> result = new HashMap<>();
                result.put("type", "resource/strings-xml");
                result.put("available_variants", availableVariants);
                result.put("total_variants", availableVariants.size());
                
                if (targetContent != null) {
                    result.put("loaded_variant", targetVariant);
                    result.put("content", targetContent);
                } else if (defaultContent != null) {
                    result.put("loaded_variant", "res/values/strings.xml");
                    result.put("content", defaultContent);
                } else if (requestedVariant != null) {
                    result.put("error", "Variant not found: " + requestedVariant);
                } else if (!availableVariants.isEmpty()) {
                    result.put("message", "No res/values/strings.xml found");
                    result.put("suggestion", "Use variant=" + availableVariants.get(0));
                } else {
                    result.put("error", "No strings.xml resources found");
                }
                
                return result;
                
            } catch (Exception e) {
                Map<String, Object> error = new HashMap<>();
                error.put("type", "resource/strings-xml");
                error.put("error", "Internal error: " + e.getMessage());
                return error;
            }
        }, resourceExecutor).orTimeout(60, java.util.concurrent.TimeUnit.SECONDS)
          .exceptionally(ex -> {
              Map<String, Object> timeout = new HashMap<>();
              timeout.put("type", "resource/strings-xml");
              if (ex.getCause() instanceof java.util.concurrent.TimeoutException) {
                  timeout.put("error", "Resource loading timed out after 60 seconds");
                  timeout.put("reason", "The APK's resources.arsc is too large to process");
                  timeout.put("workaround", "Navigate to Resources in JADX GUI, then use fetch_current_class");
              } else {
                  timeout.put("error", "Loading failed: " + ex.getMessage());
              }
              return timeout;
          }));
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
     * Handle the /get-resource-file MCP tool call with async loading.
     * Uses Javalin async to prevent blocking, with 60s timeout.
     */
    public void handleGetResourceFile(Context ctx) {
        String fileName = ctx.queryParam("file_name");
        if (fileName == null || fileName.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required 'file_name' parameter.", logger);
            return;
        }

        // Use Javalin async with CompletableFuture
        ctx.future(() -> CompletableFuture.supplyAsync(() -> {
            try {
                List<ResourceFile> resourceFiles = mainWindow.getWrapper().getResources();
                Map<String, String> resFileContent = new HashMap<>();
                
                for (ResourceFile resFile : resourceFiles) {
                    if (resFile == null || resFile.getDeobfName() == null) continue;
                    
                    if (resFile.getDeobfName().equals(fileName)) {
                        // Direct match - standalone resource file
                        resFileContent.put("file_name", resFile.getDeobfName());
                        resFileContent.put("content", resFile.loadContent().getText().getCodeStr());
                        break;
                    } else if ("resources.arsc".equals(resFile.getDeobfName())) {
                        // Search in resources.arsc subfiles
                        ResContainer container = resFile.loadContent();
                        if (container != null) {
                            for (ResContainer file : container.getSubFiles()) {
                                if (fileName.equals(file.getFileName())) {
                                    resFileContent.put("file_name", file.getFileName());
                                    resFileContent.put("content", file.getText().getCodeStr());
                                    break;
                                }
                            }
                        }
                        if (!resFileContent.isEmpty()) break;
                    }
                }
                
                if (!resFileContent.isEmpty()) {
                    return Map.of("type", "resource/text", "file", resFileContent);
                }
                
                Map<String, Object> notFound = new HashMap<>();
                notFound.put("type", "resource/text");
                notFound.put("error", "No resource file found: " + fileName);
                return notFound;
                
            } catch (Exception e) {
                Map<String, Object> error = new HashMap<>();
                error.put("type", "resource/text");
                error.put("error", "Internal error: " + e.getMessage());
                return error;
            }
        }, resourceExecutor).orTimeout(60, java.util.concurrent.TimeUnit.SECONDS)
          .exceptionally(ex -> {
              Map<String, Object> timeout = new HashMap<>();
              timeout.put("type", "resource/text");
              if (ex.getCause() instanceof java.util.concurrent.TimeoutException) {
                  timeout.put("error", "Resource loading timed out after 60 seconds");
                  timeout.put("reason", "The APK's resources.arsc is too large");
                  timeout.put("workaround", "Navigate to Resources > " + fileName + " in JADX GUI, then use fetch_current_class");
              } else {
                  timeout.put("error", "Loading failed: " + ex.getMessage());
              }
              return timeout;
          }));
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
