package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

import com.zin.jadxaimcp.server.PluginServer;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;

public class GeneralRoutes {
    private static final Logger logger = LoggerFactory.getLogger(GeneralRoutes.class);
    private final PluginServer server;

    public GeneralRoutes(PluginServer server) {
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
            result.put("memory", memory);

            ctx.json(result);
            logger.debug("JADX AI MCP Plugin: Health check - memory {}MB/{}MB ({}%)", usedMb, maxMb, memPercent);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Internal Error while trying to handle health ping request: " + e.getMessage(), e, logger);
        }
    }

}
