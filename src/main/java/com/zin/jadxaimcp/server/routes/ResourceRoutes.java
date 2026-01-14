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

public class ResourceRoutes {
    private static final Logger logger = LoggerFactory.getLogger(ResourceRoutes.class);
    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;

    public ResourceRoutes(MainWindow mainWindow) {
        this.mainWindow = mainWindow;
        this.paginationUtils = new PaginationUtils();
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
     * Handle the /strings MCP tool call with streaming pagination.
     * 
     * Performance optimization:
     * 1. First pass: Collect string file references WITHOUT loading content
     * 2. Second pass: Only load content for files within pagination range
     * 
     * This prevents timeout on large APKs with many string resources.
     */
    public void handleStrings(Context ctx) {
        try {
            // Phase 1: Collect string file references
            // Note: loadContent() for resources.arsc can be slow on large APKs
            List<StringFileRef> stringFileRefs = new ArrayList<>();
            List<ResourceFile> resourceFiles = mainWindow.getWrapper().getResources();
            boolean resourcesTimedOut = false;
            
            for (ResourceFile resFile : resourceFiles) {
                try {
                    if ("resources.arsc".equals(resFile.getDeobfName())) {
                        // Use timeout protection for large resources.arsc loading
                        try {
                            java.util.concurrent.CompletableFuture<ResContainer> future = 
                                java.util.concurrent.CompletableFuture.supplyAsync(() -> {
                                    try {
                                        return resFile.loadContent();
                                    } catch (Exception e) {
                                        return null;
                                    }
                                });
                            
                            // 30 second timeout for resources.arsc parsing
                            ResContainer content = future.get(30, java.util.concurrent.TimeUnit.SECONDS);
                            
                            if (content != null) {
                                for (ResContainer subFile : content.getSubFiles()) {
                                    String fileName = subFile.getFileName();
                                    if (fileName != null && fileName.contains("strings.xml")) {
                                        stringFileRefs.add(new StringFileRef(fileName, subFile));
                                    }
                                }
                            }
                        } catch (java.util.concurrent.TimeoutException e) {
                            logger.warn("Timeout loading resources.arsc - APK may be too large");
                            resourcesTimedOut = true;
                        } catch (Exception e) {
                            logger.warn("Error loading resources.arsc: " + e.getMessage());
                        }
                    } else if (resFile.getDeobfName() != null && 
                               resFile.getDeobfName().contains("strings.xml")) {
                        stringFileRefs.add(new StringFileRef(resFile.getDeobfName(), resFile));
                    }
                } catch (Exception e) {
                    logger.warn("Error scanning resource file: " + e.getMessage());
                }
            }
            
            // Handle timeout case
            if (stringFileRefs.isEmpty() && resourcesTimedOut) {
                Map<String, Object> result = new HashMap<>();
                result.put("type", "resource/strings-xml");
                result.put("error", "resources.arsc parsing timed out - APK is too large");
                result.put("suggestion", "Use get_resource_file with specific path like 'res/values/strings.xml'");
                ctx.status(504).json(result);
                return;
            }
            
            if (stringFileRefs.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "No strings.xml resource found.", logger);
                return;
            }
            
            // Phase 2: Parse pagination params and load only needed content
            int offset = paginationUtils.getIntParam(ctx, "offset", 0);
            int limit = paginationUtils.getIntParam(ctx, "limit", 0);
            if (limit == 0) {
                limit = paginationUtils.getIntParam(ctx, "count", paginationUtils.DEFAULT_PAGE_SIZE);
            }
            
            int totalFiles = stringFileRefs.size();
            int startIdx = Math.min(offset, totalFiles);
            int endIdx = Math.min(startIdx + (limit == 0 ? totalFiles : limit), totalFiles);
            
            // Load content only for items in range
            List<Map<String, String>> paginatedEntries = new ArrayList<>();
            for (int i = startIdx; i < endIdx; i++) {
                StringFileRef ref = stringFileRefs.get(i);
                try {
                    String content = loadStringFileContent(ref);
                    paginatedEntries.add(Map.of(
                        "file", ref.fileName,
                        "content", content
                    ));
                } catch (Exception e) {
                    paginatedEntries.add(Map.of(
                        "file", ref.fileName,
                        "error", "Failed to load: " + e.getMessage()
                    ));
                }
            }
            
            // Build pagination response
            Map<String, Object> result = new HashMap<>();
            result.put("type", "resource/strings-xml");
            result.put("strings", paginatedEntries);
            
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
                pagination.put("prev_offset", Math.max(0, startIdx - limit));
            }
            result.put("pagination", pagination);
            
            ctx.json(result);
            
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error occurred while trying to handle the /strings: " + e.getMessage(), e, logger);
        }
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
     *      a. Then for each subfile in this compiled resource archive
     *          - Check if the subfile is the one requested - if yes then return it
     *  3. Break once any mathcing file is found
     * If none found then handle it else return the requested file.
     */
    public void handleGetResourceFile(Context ctx) {
        String fileName = ctx.queryParam("file_name");
        if (fileName == null || fileName.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing required 'file_name' parameter.", logger);
            return;
        }

        try {
            List<ResourceFile> resourceFiles = mainWindow.getWrapper().getResources();
            Map<String, String> resFileContent = new HashMap<>();

            for (ResourceFile resFile : resourceFiles) {
                if (resFile.getDeobfName().equals(fileName)) {
                    resFileContent.put("file_name", resFile.getDeobfName());
                    resFileContent.put("content", resFile.loadContent().getText().getCodeStr());
                    break;
                } else if ("resources.arsc".equals(resFile.getDeobfName())) {
                    for (ResContainer file : resFile.loadContent().getSubFiles()) {
                        resFileContent.put("file_name", file.getFileName());
                        resFileContent.put("content", file.getText().getCodeStr());
                        break;
                    }
                }
                if (!resFileContent.isEmpty()) break;
            }

            if (resFileContent.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "No resource file found", logger);
                return;
            }
            ctx.json(Map.of("type", "resource/text", "file", resFileContent));
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal Error occured while trying to handle the handleGetResourceFile(): " + e.getMessage(), e, logger);
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
     *      a. load the content of complied resource archive.
     *      b. get all the sub files.
     *      c. get the names of or sub files' names.
     *  2. if it is standalone file, then directly get it's name.
     *  3. If none file is found, return error
     *  4. else return the list of resoure files names with pagination support.
     */
    public void handleListAllResourceFilesNames(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<ResourceFile> resourceFiles = wrapper.getResources();
            List<String> resourceFileNames = new ArrayList<>();

            for (ResourceFile resFile : resourceFiles) {
                try {
                    if (resFile.getDeobfName().equals("resources.arsc")) {
                        ResContainer container = resFile.loadContent();
                        List<ResContainer> subFiles = container.getSubFiles();
                        for (ResContainer file : subFiles) {
                            resourceFileNames.add(file.getFileName());
                        }
                    }
                    resourceFileNames.add(resFile.getDeobfName());
                } catch (Exception e) {
                    logger.error("JADX AI MCP Error: Internal error occurred while trying to read the resourcefile in handleListAllResourceFilesNames" + e.getMessage(), e);
                }
            }

            if (resourceFileNames.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "No resources found.", logger);
                return;
            }

            Map<String, Object> result = paginationUtils.handlePagination(
                ctx,
                resourceFileNames,
                "application-resources",
                "files",
                item -> item);

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
