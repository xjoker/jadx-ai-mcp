package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.JadxSearchLock;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.SmartChunker;

/**
 * Handles single-class decompilation and Smali inspection MCP endpoints.
 *
 * <p>Covers: {@code /class-source} (decompiled Java source) and
 * {@code /smali-of-class} (Dalvik bytecode for APK/DEX files).</p>
 *
 * <p>Both endpoints use {@link JadxSearchLock} for serialised access to the
 * JADX decompiler and {@link ClassCacheManager} for cache-first retrieval.</p>
 */
public class DecompileRoutes {
    private static final Logger logger = LoggerFactory.getLogger(DecompileRoutes.class);

    private final MainWindow mainWindow;
    private final SearchRoutes searchRoutes;

    public DecompileRoutes(MainWindow mainWindow, SearchRoutes searchRoutes) {
        this.mainWindow = mainWindow;
        this.searchRoutes = searchRoutes;
    }

    // ------------------------------- Request Handlers --------------------------

    /**
     * Handles {@code /class-source}.
     *
     * <p>Returns the decompiled Java source of a single class. Supports chunking for
     * large responses ({@code ?chunk=N}).</p>
     */
    public void handleClassSource(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

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
            JadxWrapper wrapper = mainWindow.getWrapper();
            JavaClass targetClass = findClassByName(wrapper, className);
            String cacheKey = targetClass != null ? targetClass.getFullName() : className;

            // Check decompiled code cache first (no lock needed for cache read)
            String code = ClassCacheManager.getCachedCode(cacheKey);
            if (code != null) {
                Map<String, Object> result = SmartChunker.chunkResponse(code, chunk, "response");
                if (result.containsKey("error")) {
                    JadxAIMCPPluginError.handleError(ctx, 400, (String) result.get("error"), logger);
                    return;
                }
                ctx.json(result);
                return;
            }

            // Decompilation requires write lock (JADX internal state is not thread-safe)
            if (!JadxSearchLock.tryAcquire()) {
                ctx.status(503).json(Map.of(
                    "error", "Decompilation operation in progress",
                    "retry_after", JadxSearchLock.RETRY_AFTER_SECONDS
                ));
                return;
            }
            try {
                // Re-check cache after acquiring lock (another thread may have decompiled it)
                code = ClassCacheManager.getCachedCode(cacheKey);
                if (code == null) {
                    if (targetClass == null) {
                        targetClass = findClassByName(wrapper, className);
                    }
                    if (targetClass != null) {
                        code = targetClass.getCode();
                        ClassCacheManager.putCachedCode(targetClass.getFullName(), code);
                    }
                }
            } finally {
                JadxSearchLock.release();
            }

            if (code == null) {
                ctx.status(404).json(Map.of("error", "Class " + className + " not found"));
                return;
            }

            Map<String, Object> result = SmartChunker.chunkResponse(code, chunk, "response");
            if (result.containsKey("error")) {
                JadxAIMCPPluginError.handleError(ctx, 400, (String) result.get("error"), logger);
                return;
            }
            ctx.json(result);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving class source: " + e.getMessage(), e,
                    logger);
        }
    }

    /**
     * Handles {@code /smali-of-class}.
     *
     * <p>Returns the Dalvik bytecode (Smali) for a class. Only available for APK/DEX
     * files. Supports chunking for large responses ({@code ?chunk=N}).</p>
     */
    public void handleSmaliOfClass(Context ctx) {
        String className = checkClassParam(ctx);
        if (className == null)
            return;

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

        boolean lockAcquired = false;
        try {
            JadxWrapper wrapper = mainWindow.getWrapper();

            // Check file type - Smali only available for DEX-based files
            com.zin.jadxaimcp.utils.FileTypeDetector.DetectionResult fileType =
                com.zin.jadxaimcp.utils.FileTypeDetector.detect(wrapper);
            if (!fileType.isSmaliAvailable()) {
                com.zin.jadxaimcp.utils.NotApplicableResponse.sendSmaliNotAvailable(
                    ctx, fileType.getPrimaryType().getName());
                return;
            }

            if (!JadxSearchLock.tryAcquire()) {
                searchRoutes.sendSearchDecompilationBusyResponse(ctx);
                return;
            }
            lockAcquired = true;

            JavaClass cls = findClassByName(wrapper, className);
            if (cls != null) {
                String smali = cls.getSmali();
                if (smali == null || smali.isEmpty()) {
                    JadxAIMCPPluginError.handleError(ctx, 404,
                        "Smali generation returned empty for class " + className +
                        ". This may indicate the class was loaded from a non-DEX source.", logger);
                    return;
                }

                Map<String, Object> result = SmartChunker.chunkResponse(smali, chunk, "response");

                if (result.containsKey("error")) {
                    JadxAIMCPPluginError.handleError(ctx, 400, (String) result.get("error"), logger);
                    return;
                }

                ctx.json(result);
                return;
            }
            JadxAIMCPPluginError.handleError(ctx, 404, "Class " + className + " not found.", logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal error retrieving smali: " + e.getMessage(), e, logger);
        } finally {
            if (lockAcquired) {
                JadxSearchLock.release();
            }
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
            if (com.zin.jadxaimcp.utils.JadxApiAdapter.matchesClassName(cls, className)) {
                return cls;
            }
        }
        return null;
    }
}
