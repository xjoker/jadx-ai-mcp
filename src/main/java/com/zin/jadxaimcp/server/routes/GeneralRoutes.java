package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

import com.zin.jadxaimcp.server.PluginServer;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;

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
            String status = isRunning ? "Running" : "Stopped";
            String url = isRunning ? "http://127.0.0.1:" + server.getPort() + "/" : "N/A";

            Map<String, Object> result = new HashMap<>();
            result.put("status", status);
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
    
}
