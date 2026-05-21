package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

import com.zin.jadxaimcp.server.PluginServer;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.CodeContentIndex;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.JadxApiAdapter;

public class GeneralRoutes {
    private static final Logger logger = LoggerFactory.getLogger(GeneralRoutes.class);
    private final MainWindow mainWindow;
    private final PluginServer server;

    public GeneralRoutes(MainWindow mainWindow, int port, PluginServer server) {
        this.mainWindow = mainWindow;
        this.server = server;
    }

    /**
     * @name handleHealth
     * @param ctx - The jadx plugin server context
     * @return void
     * 
     * This method handles health-check requests.
     * Enhanced to include JVM memory stats and class loading info.
     */
    public void handleHealth(Context ctx) {
        try {
            boolean isRunning = server.isRunning();
            boolean oomDetected = PluginServer.isOomDetected();
            // "degraded" when OOM has been detected; monitoring must keep polling on 200.
            String status = oomDetected ? "degraded" : (isRunning ? "Running" : "Stopped");
            String url = isRunning ? "http://127.0.0.1:" + server.getPort() + "/" : "N/A";

            Map<String, Object> result = new HashMap<>();
            result.put("status", status);
            result.put("oom_detected", oomDetected);
            result.put("url", url);
            result.put("timestamp", java.time.Instant.now().toString());
            
            // JVM Memory stats
            Runtime runtime = Runtime.getRuntime();
            long usedMb = (runtime.totalMemory() - runtime.freeMemory()) / (1024 * 1024);
            long maxMb = runtime.maxMemory() / (1024 * 1024);
            int memPercent = (int) ((usedMb * 100) / maxMb);
            
            Map<String, Object> memory = new HashMap<>();
            memory.put("used_mb", usedMb);
            memory.put("max_mb", maxMb);
            memory.put("percent", memPercent);
            memory.put("oom_detected", PluginServer.isOomDetected());
            result.put("memory", memory);
            
            // JADX class loading stats (lightweight - just counts, no decompilation triggered)
            try {
                int totalClasses = mainWindow.getWrapper().getIncludedClassesWithInners().size();
                Map<String, Object> jadx = new HashMap<>();
                jadx.put("classes_total", totalClasses);
                result.put("jadx", jadx);
            } catch (Exception e) {
                // If JADX not fully loaded, skip
                result.put("jadx", Map.of("status", "loading"));
            }
            
            ctx.json(result);
            logger.debug("JADX AI MCP Plugin: Health check - memory {}MB/{}MB ({}%)", usedMb, maxMb, memPercent);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal Error while trying to handle health ping request: " + e.getMessage(), e, logger);
        }
    }

    /**
     * @name handleIndexStats
     * @param ctx - The jadx plugin server context
     * @return void
     *
     * Returns a unified health snapshot of all internal plugin indices:
     * name indices (class/method/field), trigram content index, snapshot cache,
     * and a summary of the upstream code cache delegation.
     *
     * Useful for AI clients to decide whether trigram-based code search is warm
     * enough to use efficiently, or whether to fall back to metadata searches.
     */
    public void handleIndexStats(Context ctx) {
        try {
            Map<String, Object> response = new HashMap<>();

            // --- Name indices (ClassCacheManager) ---
            response.put("name_indices", ClassCacheManager.getNameIndexStats());

            // --- Trigram content index (CodeContentIndex) ---
            response.put("trigram_index", CodeContentIndex.getStats());

            // --- Snapshot cache (JadxApiAdapter) ---
            response.put("snapshot_cache", JadxApiAdapter.getSnapshotCacheStats());

            // --- Code cache (ClassCacheManager facade over JADX ICodeCache) ---
            Map<String, Object> codeCacheRaw = ClassCacheManager.getCodeCacheStats();
            Map<String, Object> codeCache = new HashMap<>();
            codeCache.put("class_index_size", codeCacheRaw.getOrDefault("class_index_size", 0));
            codeCache.put("delegates_to_jadx_icodecache",
                    codeCacheRaw.getOrDefault("delegates_to_jadx_icodecache", true));
            response.put("code_cache", codeCache);

            ctx.json(response);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal Error while handling index-stats request: " + e.getMessage(), e, logger);
        }
    }

}
