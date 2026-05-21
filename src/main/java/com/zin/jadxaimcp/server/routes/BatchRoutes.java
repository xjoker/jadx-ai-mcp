package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.api.ResourceFile;
import jadx.api.security.IJadxSecurity;
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

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.ObjectMapper;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.PaginationUtils.PaginationException;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.JadxSearchLock;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.JadxApiAdapter;
import com.zin.jadxaimcp.utils.SmartChunker;

/**
 * Handles batch and multi-class decompilation MCP endpoints.
 *
 * <p>Covers: {@code /batch-class-source}, {@code /main-application-classes-code},
 * {@code /main-application-classes-names}, and {@code /main-activity}. Also owns the
 * streaming JSON path (Jackson {@link JsonGenerator} → response output stream) and the
 * buffered legacy fallback activated by {@code ?force_chunk=true}.</p>
 */
public class BatchRoutes {
    private static final Logger logger = LoggerFactory.getLogger(BatchRoutes.class);

    // Threshold for inline JSON response vs. transfer-token redirect.
    // Configurable via JADX_MCP_INLINE_RESPONSE_MAX_BYTES env var (default 32768).
    static final int INLINE_RESPONSE_MAX_BYTES;
    static {
        int threshold = 32768;
        String envVal = System.getenv("JADX_MCP_INLINE_RESPONSE_MAX_BYTES");
        if (envVal != null && !envVal.isEmpty()) {
            try {
                threshold = Integer.parseInt(envVal.trim());
            } catch (NumberFormatException ignored) {
                LoggerFactory.getLogger(BatchRoutes.class)
                    .warn("Invalid JADX_MCP_INLINE_RESPONSE_MAX_BYTES='{}', using default 32768", envVal);
            }
        }
        INLINE_RESPONSE_MAX_BYTES = threshold;
    }

    // Shared Jackson mapper for size-estimation serialization.
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    // JsonFactory for streaming JSON output in handleMainApplicationClassesCode.
    private static final JsonFactory JSON_FACTORY = new JsonFactory();

    // Flush the JsonGenerator every N classes during streaming to bound the write-buffer size.
    private static final int STREAM_FLUSH_EVERY = 16;

    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;
    private final SearchRoutes searchRoutes;

    public BatchRoutes(MainWindow mainWindow, PaginationUtils paginationUtils, SearchRoutes searchRoutes) {
        this.mainWindow = mainWindow;
        this.paginationUtils = paginationUtils;
        this.searchRoutes = searchRoutes;
    }

    // ------------------------------- Request Handlers --------------------------

    /**
     * Handles {@code /batch-class-source}.
     *
     * <p>Allows fetching multiple class sources in a single request to reduce
     * MCP interaction overhead. Max 20 classes per request.</p>
     */
    public void handleBatchClassSource(Context ctx) {
        String classNamesParam = ctx.queryParam("class_names");
        if (classNamesParam == null || classNamesParam.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing 'class_names' parameter. Provide comma-separated class names.", logger);
            return;
        }

        // Parse chunk parameter for large response handling
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
                Map<String, Object> health = ClassCacheManager.getHealthInfo();
                Map<String, Object> response = new HashMap<>();
                response.put("status", "loading");
                response.put("type", "batch-class-source");
                response.put("message", "Class cache is being loaded in background. First load takes ~30-60 seconds for large APKs.");
                response.put("retry_after", 10);
                response.put("health", health);

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

            // Collect classes that need decompilation (cache miss)
            List<String> needDecompile = new ArrayList<>();
            Map<String, String> cachedResults = new HashMap<>();
            Map<String, JavaClass> resolvedClasses = new HashMap<>();

            for (String className : classNames) {
                String trimmedName = className.trim();
                JavaClass resolvedClass = ClassCacheManager.findClass(classMap, trimmedName);
                if (resolvedClass != null) {
                    resolvedClasses.put(trimmedName, resolvedClass);
                }

                String cacheKey = resolvedClass != null ? resolvedClass.getFullName() : trimmedName;
                String cachedCode = ClassCacheManager.getCachedCode(cacheKey);
                if (cachedCode != null) {
                    cachedResults.put(trimmedName, cachedCode);
                } else if (resolvedClass != null) {
                    needDecompile.add(trimmedName);
                }
            }

            // Decompile cache-missed classes under write lock
            Map<String, String> decompiledResults = new HashMap<>();
            if (!needDecompile.isEmpty()) {
                if (!JadxSearchLock.tryAcquire()) {
                    ctx.status(503).json(Map.of(
                        "error", "Decompilation operation in progress",
                        "retry_after", JadxSearchLock.RETRY_AFTER_SECONDS
                    ));
                    return;
                }
                try {
                    for (String name : needDecompile) {
                        // Re-check cache (another thread may have decompiled it)
                        String code = ClassCacheManager.getCachedCode(name);
                        if (code != null) {
                            decompiledResults.put(name, code);
                            continue;
                        }
                        JavaClass cls = resolvedClasses.get(name);
                        if (cls != null) {
                            try {
                                code = cls.getCode();
                                ClassCacheManager.putCachedCode(cls.getFullName(), code);
                                decompiledResults.put(name, code);
                            } catch (Exception e) {
                                logger.error("Decompilation failed for {}: {}", name, e.getMessage());
                                decompiledResults.put(name, null); // mark as failed
                            }
                        }
                    }
                } finally {
                    JadxSearchLock.release();
                }
            }

            // Build response
            for (String className : classNames) {
                String trimmedName = className.trim();
                Map<String, Object> classResult = new HashMap<>();
                classResult.put("name", trimmedName);

                if (cachedResults.containsKey(trimmedName)) {
                    classResult.put("found", true);
                    classResult.put("content", cachedResults.get(trimmedName));
                    foundCount++;
                } else if (decompiledResults.containsKey(trimmedName)) {
                    String code = decompiledResults.get(trimmedName);
                    if (code != null) {
                        classResult.put("found", true);
                        classResult.put("content", code);
                        foundCount++;
                    } else {
                        classResult.put("found", true);
                        classResult.put("error", "Decompilation failed (see server log)");
                    }
                } else if (!resolvedClasses.containsKey(trimmedName)) {
                    classResult.put("found", false);
                    classResult.put("error", "Class not found");
                } else {
                    classResult.put("found", false);
                    classResult.put("error", "Decompilation not attempted");
                }
                results.add(classResult);
            }

            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("classes", results);
            response.put("total", classNames.length);
            response.put("found", foundCount);

            // --- Threshold routing ---
            boolean forceChunk = "true".equalsIgnoreCase(ctx.queryParam("force_chunk"));
            boolean forceRaw   = "true".equalsIgnoreCase(ctx.queryParam("force_raw"));

            if (forceChunk) {
                com.google.gson.Gson gson = new com.google.gson.Gson();
                String responseJson = gson.toJson(response);
                Map<String, Object> chunkedResponse = SmartChunker.chunkResponse(
                    responseJson, chunk, "batch_result");
                ctx.json(chunkedResponse);
                return;
            }

            if (forceRaw) {
                ctx.json(response);
                return;
            }

            // Estimate serialized size cheaply: sum all content string lengths
            int estimatedBytes = 512;
            for (Map<String, Object> cls : results) {
                Object content = cls.get("content");
                if (content instanceof String) {
                    estimatedBytes += ((String) content).length();
                }
                Object err = cls.get("error");
                if (err instanceof String) {
                    estimatedBytes += ((String) err).length();
                }
                Object name = cls.get("name");
                if (name instanceof String) {
                    estimatedBytes += ((String) name).length() + 32;
                }
            }

            if (estimatedBytes <= INLINE_RESPONSE_MAX_BYTES) {
                ctx.json(response);
            } else {
                int actualBytes;
                try {
                    actualBytes = OBJECT_MAPPER.writeValueAsBytes(response).length;
                } catch (Exception serEx) {
                    logger.warn("Size check serialization failed, falling back to inline: {}", serEx.getMessage());
                    ctx.json(response);
                    return;
                }

                if (actualBytes <= INLINE_RESPONSE_MAX_BYTES) {
                    ctx.json(response);
                } else {
                    Map<String, Object> transferHint = new HashMap<>();
                    transferHint.put("response_too_large", true);
                    transferHint.put("size_bytes", actualBytes);
                    transferHint.put("items_count", classNames.length);
                    transferHint.put("found", foundCount);
                    transferHint.put("transfer_endpoint", "/transfer/download/batch-classes");
                    transferHint.put("transfer_format", "json");
                    transferHint.put("message",
                        "Response exceeds inline threshold (" + INLINE_RESPONSE_MAX_BYTES + " bytes). "
                        + "Call create_transfer_token(resource_type='batch_classes') then GET "
                        + "/transfer/download/batch-classes?classes=<names>&token=<token>&force_raw=true");
                    ctx.json(transferHint);
                }
            }

        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving batch class sources: " + e.getMessage(), e, logger);
        }
    }

    /**
     * Handles {@code /main-application-classes-names}.
     *
     * <p>Parses the AndroidManifest.xml to extract the app package name, then returns
     * all class names (including inner classes) under that package.</p>
     */
    public void handleMainApplicationClassesNames(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<ResourceFile> resources = wrapper.getResources();

            ResourceFile manifestRes = AndroidManifestParser.getAndroidManifest(resources);
            if (manifestRes == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "AndroidManifest.xml not found.", logger);
                return;
            }

            String manifestXml = manifestRes.loadContent().getText().getCodeStr();
            Document manifestDoc = parseManifestXml(manifestXml, wrapper.getArgs().getSecurity());

            Element manifestElement = (Element) manifestDoc.getElementsByTagName("manifest").item(0);
            String packageName = manifestElement.getAttribute("package");

            if (packageName.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Package name not found in AndroidManifest.xml", logger);
                return;
            }

            List<JavaClass> matchedClasses = wrapper.getDecompiler()
                    .getClassesWithInners()
                    .stream()
                    .filter(cls -> cls.getFullName().startsWith(packageName))
                    .collect(Collectors.toList());

            List<Map<String, Object>> classesInfo = new ArrayList<>();
            for (JavaClass cls : matchedClasses) {
                Map<String, Object> classInfo = new HashMap<>();
                classInfo.put("name", cls.getFullName());
                classInfo.put("raw_name", JadxApiAdapter.getClassRawName(cls));
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
     * Handles {@code /main-activity}.
     *
     * <p>Only available for APK/AAR files with AndroidManifest.xml.</p>
     */
    public void handleMainActivity(Context ctx) {
        boolean lockAcquired = false;
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

            JadxWrapper wrapper = mainWindow.getWrapper();

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

            if (!JadxSearchLock.tryAcquire()) {
                searchRoutes.sendSearchDecompilationBusyResponse(ctx);
                return;
            }
            lockAcquired = true;

            String code = mainActivityClass.getCode();
            Map<String, Object> result = com.zin.jadxaimcp.utils.SmartChunker.chunkResponse(
                code, chunk, "content");
            result.put("name", mainActivityClass.getFullName());
            result.put("raw_name", JadxApiAdapter.getClassRawName(mainActivityClass));
            result.put("type", "code/java");

            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error occurred while trying to get the Main Activity class code: " + e.getMessage(), e,
                    logger);
        } finally {
            if (lockAcquired) {
                JadxSearchLock.release();
            }
        }
    }

    /**
     * Handles {@code /main-application-classes-code}.
     *
     * <p>Streaming path (default): Jackson JsonGenerator → ctx.outputStream().<br>
     * Buffered legacy path: activated by {@code ?force_chunk=true}.</p>
     */
    public void handleMainApplicationClassesCode(Context ctx) {
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<ResourceFile> resources = wrapper.getResources();

            ResourceFile manifestRes = AndroidManifestParser.getAndroidManifest(resources);
            if (manifestRes == null) {
                JadxAIMCPPluginError.handleError(ctx, 404, "AndroidManifest.xml not found.", logger);
                return;
            }

            String manifestXml = manifestRes.loadContent().getText().getCodeStr();
            Document manifestDoc = parseManifestXml(manifestXml, wrapper.getArgs().getSecurity());

            Element manifestElement = (Element) manifestDoc.getElementsByTagName("manifest").item(0);
            String packageName = manifestElement.getAttribute("package");

            if (packageName.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 404, "Package name not found in AndroidManifest.xml", logger);
                return;
            }

            logger.info("JADX AI MCP: Package name: " + packageName);
            List<JavaClass> matchedClasses = wrapper.getDecompiler()
                    .getClassesWithInners()
                    .stream()
                    .filter(cls -> cls.getFullName().startsWith(packageName))
                    .collect(Collectors.toList());

            logger.info("JADX AI MCP: Found " + matchedClasses.size() + " classes in package " + packageName);
            logger.info("JADX AI MCP: Request params - offset: " + ctx.queryParam("offset") +
                    ", limit: " + ctx.queryParam("limit") +
                    ", count: " + ctx.queryParam("count"));

            PaginationWindow paginationWindow = resolvePaginationWindow(ctx, matchedClasses.size());

            boolean forceChunk = "true".equalsIgnoreCase(ctx.queryParam("force_chunk"));
            if (forceChunk) {
                handleMainApplicationClassesCodeBuffered(ctx, matchedClasses, paginationWindow);
                return;
            }

            // --- Streaming path (Phase 1: decompile under lock, Phase 2: stream lock-free) ---
            List<String[]> decompiledPage = new ArrayList<>();
            if (paginationWindow.hasResults()) {
                if (!JadxSearchLock.tryAcquire()) {
                    searchRoutes.sendSearchDecompilationBusyResponse(ctx);
                    return;
                }
                try {
                    for (JavaClass cls : matchedClasses.subList(
                            paginationWindow.getStartIndex(),
                            paginationWindow.getEndIndex())) {
                        String fullName = cls.getFullName();
                        String rawName = JadxApiAdapter.getClassRawName(cls);
                        String content;
                        try {
                            content = cls.getCode();
                            logger.debug("JADX AI MCP: Decompiled {} ({} chars)", fullName, content.length());
                        } catch (Exception e) {
                            logger.warn("Failed to decompile class {}: {}", fullName, e.getMessage());
                            content = "// Error decompiling class: " + e.getMessage();
                        }
                        decompiledPage.add(new String[]{fullName, rawName, content});
                    }
                } finally {
                    JadxSearchLock.release();
                }
            }

            logger.info("JADX AI MCP: Streaming {} decompiled class entries", decompiledPage.size());

            ctx.contentType("application/json");
            OutputStream out = ctx.outputStream();
            try (JsonGenerator gen = JSON_FACTORY.createGenerator(out)) {
                gen.writeStartObject();

                gen.writeStringField("type", "application-classes");
                gen.writeNumberField("requested_count", paginationWindow.getRequestedLimit());

                gen.writeObjectFieldStart("pagination");
                gen.writeNumberField("total", matchedClasses.size());
                gen.writeNumberField("offset", paginationWindow.getOffset());
                gen.writeNumberField("limit", paginationWindow.getLimit());
                gen.writeNumberField("count", decompiledPage.size());
                gen.writeBooleanField("has_more", paginationWindow.hasMore());
                if (paginationWindow.hasMore()) {
                    gen.writeNumberField("next_offset", paginationWindow.getNextOffset());
                }
                if (paginationWindow.getOffset() > 0) {
                    int prevOffset = Math.max(0, paginationWindow.getOffset() - paginationWindow.getLimit());
                    gen.writeNumberField("prev_offset", prevOffset);
                }
                if (paginationWindow.getLimit() > 0) {
                    int currentPage = (paginationWindow.getOffset() / paginationWindow.getLimit()) + 1;
                    int totalPages = (int) Math.ceil((double) matchedClasses.size() / paginationWindow.getLimit());
                    gen.writeNumberField("current_page", currentPage);
                    gen.writeNumberField("total_pages", totalPages);
                    gen.writeNumberField("page_size", paginationWindow.getLimit());
                }
                gen.writeEndObject(); // pagination

                gen.writeArrayFieldStart("classes");
                int written = 0;
                for (String[] entry : decompiledPage) {
                    gen.writeStartObject();
                    gen.writeStringField("name", entry[0]);
                    gen.writeStringField("raw_name", entry[1]);
                    gen.writeStringField("type", "code/java");
                    gen.writeStringField("content", entry[2]);
                    gen.writeEndObject();
                    written++;
                    if (written % STREAM_FLUSH_EVERY == 0) {
                        gen.flush();
                    }
                }
                gen.writeEndArray(); // classes

                gen.writeEndObject(); // root
            }
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
     * Legacy full-buffer path for {@link #handleMainApplicationClassesCode}.
     * Activated by {@code ?force_chunk=true}.
     */
    private void handleMainApplicationClassesCodeBuffered(
            Context ctx,
            List<JavaClass> matchedClasses,
            PaginationWindow paginationWindow) {

        List<Map<String, Object>> classInfoList = new ArrayList<>();
        if (paginationWindow.hasResults()) {
            if (!JadxSearchLock.tryAcquire()) {
                searchRoutes.sendSearchDecompilationBusyResponse(ctx);
                return;
            }
            try {
                for (JavaClass cls : matchedClasses.subList(
                        paginationWindow.getStartIndex(),
                        paginationWindow.getEndIndex())) {
                    Map<String, Object> classInfo = new HashMap<>();
                    classInfo.put("name", cls.getFullName());
                    classInfo.put("raw_name", JadxApiAdapter.getClassRawName(cls));
                    classInfo.put("type", "code/java");
                    try {
                        String code = cls.getCode();
                        classInfo.put("content", code);
                        logger.debug("JADX AI MCP: Got code for {} (length: {})", cls.getFullName(), code.length());
                    } catch (Exception e) {
                        logger.warn("Failed to decompile class {}: {}", cls.getFullName(), e.getMessage());
                        classInfo.put("content", "// Error decompiling class: " + e.getMessage());
                    }
                    classInfoList.add(classInfo);
                }
            } finally {
                JadxSearchLock.release();
            }
        }

        logger.info("JADX AI MCP: Built {} class info objects (buffered path)", classInfoList.size());

        Map<String, Object> result = buildPaginatedResponse(
                classInfoList,
                matchedClasses.size(),
                paginationWindow,
                "application-classes",
                "classes");

        int estimatedBytes = 512;
        for (Map<String, Object> cls : classInfoList) {
            Object content = cls.get("content");
            if (content instanceof String) {
                estimatedBytes += ((String) content).length();
            }
            Object name = cls.get("name");
            if (name instanceof String) {
                estimatedBytes += ((String) name).length() + 32;
            }
        }

        if (estimatedBytes <= INLINE_RESPONSE_MAX_BYTES) {
            ctx.json(result);
        } else {
            int actualBytes;
            try {
                actualBytes = OBJECT_MAPPER.writeValueAsBytes(result).length;
            } catch (Exception serEx) {
                logger.warn("Size check serialization failed, falling back to inline: {}", serEx.getMessage());
                ctx.json(result);
                return;
            }

            if (actualBytes <= INLINE_RESPONSE_MAX_BYTES) {
                ctx.json(result);
            } else {
                Map<String, Object> transferHint = new HashMap<>();
                transferHint.put("response_too_large", true);
                transferHint.put("size_bytes", actualBytes);
                transferHint.put("items_count", classInfoList.size());
                transferHint.put("total_classes", matchedClasses.size());
                transferHint.put("transfer_endpoint", "/transfer/download/batch-classes");
                transferHint.put("transfer_format", "json");
                transferHint.put("message",
                    "Response exceeds inline threshold (" + INLINE_RESPONSE_MAX_BYTES + " bytes). "
                    + "Use pagination (smaller count) or call create_transfer_token(resource_type='batch_classes').");
                ctx.json(transferHint);
            }
        }
    }

    // ------------------------------- Pagination Helpers ------------------------

    PaginationWindow resolvePaginationWindow(Context ctx, int totalItems) throws PaginationException {
        String offsetParam = ctx.queryParam("offset");
        String limitParam = ctx.queryParam("limit");
        String countParam = ctx.queryParam("count");
        String pageSizeParam = limitParam != null ? limitParam : countParam;

        int offset = 0;
        int requestedLimit = 0;
        boolean hasCustomLimit = pageSizeParam != null && !pageSizeParam.isEmpty();

        if (offsetParam != null && !offsetParam.isEmpty()) {
            try {
                offset = Integer.parseInt(offsetParam.trim());
                if (offset < 0) {
                    throw paginationUtils.new PaginationException("Offset must be non-negative, got: " + offset);
                }
                if (offset > paginationUtils.MAX_OFFSET) {
                    throw paginationUtils.new PaginationException(
                        "Offset too large, maximum: " + paginationUtils.MAX_OFFSET);
                }
            } catch (NumberFormatException e) {
                throw paginationUtils.new PaginationException("Invalid offset format: '" + offsetParam + "'");
            }
        }

        if (hasCustomLimit) {
            try {
                requestedLimit = Integer.parseInt(pageSizeParam.trim());
                if (requestedLimit < 0) {
                    throw paginationUtils.new PaginationException(
                        "Limit must be non-negative, got: " + requestedLimit);
                }
                if (requestedLimit > paginationUtils.MAX_PAGE_SIZE) {
                    throw paginationUtils.new PaginationException(
                        "Limit too large, maximum: " + paginationUtils.MAX_PAGE_SIZE);
                }
            } catch (NumberFormatException e) {
                throw paginationUtils.new PaginationException("Invalid limit format: '" + pageSizeParam + "'");
            }
        }

        int effectiveLimit;
        if (hasCustomLimit) {
            effectiveLimit = requestedLimit == 0 ? Math.max(0, totalItems - offset) : requestedLimit;
        } else {
            effectiveLimit = Math.min(paginationUtils.DEFAULT_PAGE_SIZE, Math.max(0, totalItems - offset));
        }
        effectiveLimit = Math.max(0, Math.min(effectiveLimit, totalItems - offset));

        if (offset >= totalItems) {
            return new PaginationWindow(offset, effectiveLimit, requestedLimit, 0, 0, false, totalItems);
        }

        int startIndex = offset;
        int endIndex = Math.min(startIndex + effectiveLimit, totalItems);
        boolean hasMore = endIndex < totalItems;
        int nextOffset = hasMore ? endIndex : -1;

        return new PaginationWindow(offset, effectiveLimit, requestedLimit, startIndex, endIndex, hasMore, nextOffset);
    }

    private Map<String, Object> buildPaginatedResponse(
        List<?> data,
        int totalItems,
        PaginationWindow window,
        String dataType,
        String itemsKey
    ) {
        Map<String, Object> result = new HashMap<>();
        result.put("type", dataType);
        result.put(itemsKey, data);

        Map<String, Object> pagination = new HashMap<>();
        pagination.put("total", totalItems);
        pagination.put("offset", window.getOffset());
        pagination.put("limit", window.getLimit());
        pagination.put("count", data.size());
        pagination.put("has_more", window.hasMore());

        if (window.hasMore()) {
            pagination.put("next_offset", window.getNextOffset());
        }

        if (window.getOffset() > 0) {
            int prevOffset = Math.max(0, window.getOffset() - window.getLimit());
            pagination.put("prev_offset", prevOffset);
        }

        if (window.getLimit() > 0) {
            int currentPage = (window.getOffset() / window.getLimit()) + 1;
            int totalPages = (int) Math.ceil((double) totalItems / window.getLimit());
            pagination.put("current_page", currentPage);
            pagination.put("total_pages", totalPages);
            pagination.put("page_size", window.getLimit());
        }

        result.put("requested_count", window.getRequestedLimit());
        result.put("pagination", pagination);
        return result;
    }

    // ------------------------------- Inner class: PaginationWindow -------------

    static final class PaginationWindow {
        private final int offset;
        private final int limit;
        private final int requestedLimit;
        private final int startIndex;
        private final int endIndex;
        private final boolean hasMore;
        private final int nextOffset;

        PaginationWindow(
            int offset,
            int limit,
            int requestedLimit,
            int startIndex,
            int endIndex,
            boolean hasMore,
            int nextOffset
        ) {
            this.offset = offset;
            this.limit = limit;
            this.requestedLimit = requestedLimit;
            this.startIndex = startIndex;
            this.endIndex = endIndex;
            this.hasMore = hasMore;
            this.nextOffset = nextOffset;
        }

        public int getOffset() { return offset; }
        public int getLimit() { return limit; }
        public int getRequestedLimit() { return requestedLimit; }
        public int getStartIndex() { return startIndex; }
        public int getEndIndex() { return endIndex; }
        public boolean hasMore() { return hasMore; }
        public int getNextOffset() { return nextOffset; }
        public boolean hasResults() { return endIndex > startIndex; }
    }

    // ------------------------------- XML Helper --------------------------------

    /**
     * Reusing JADX's secure XML parsing logic for parsing manifest XML file.
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
}
