package com.zin.jadxaimcp.server;

import java.nio.channels.ServerSocketChannel;
import java.util.function.Consumer;

import io.javalin.Javalin;
import jadx.api.plugins.events.JadxEvents;
import jadx.gui.ui.MainWindow;
import jadx.api.plugins.events.types.NodeRenamedByUser;
import org.eclipse.jetty.server.ServerConnector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.zin.jadxaimcp.JadxAIMCP;
import com.zin.jadxaimcp.utils.JadxAIMCPBanner;
import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.CodeSearchCoordinator;
import com.zin.jadxaimcp.utils.FilePathSandbox;
import com.zin.jadxaimcp.server.routes.*; // MCP tool call's request handlers

public class PluginServer {
    private static final Logger logger = LoggerFactory.getLogger(PluginServer.class);
    private static final String JVM_SERVER_KEY = "jadx-ai-mcp-server-channel";
    private static final String JVM_OOM_KEY = "jadx-ai-mcp-oom-detected";
    private final MainWindow mainWindow;
    private final int port;
    private final String bindAddress;
    private Javalin app;
    private final PaginationUtils paginationUtils;
    private final AuthConfig authConfig;
    private JadxAIMCP plugin;
    private ClassRoutes classRoutes;
    private Consumer<NodeRenamedByUser> renameListener;
    private Thread.UncaughtExceptionHandler previousUncaughtExceptionHandler;
    private Thread.UncaughtExceptionHandler oomExceptionHandler;
    private volatile boolean isRunning = false;

    /**
     * @param mainWindows - The main Jadx window context
     * @param port        - The port to listen on
     */
    public PluginServer(MainWindow mainWindow, int port) {
        this(mainWindow, port, "0.0.0.0");
    }

    /**
     * @param mainWindow  - The main Jadx window context
     * @param port        - The port to listen on
     * @param bindAddress - The address to bind to (e.g., "127.0.0.1" or "0.0.0.0")
     */
    public PluginServer(MainWindow mainWindow, int port, String bindAddress) {
        this(mainWindow, port, bindAddress, null);
    }

    /**
     * @param mainWindow  - The main Jadx window context
     * @param port        - The port to listen on
     * @param bindAddress - The address to bind to
     * @param plugin      - The plugin instance for APK info access and environment config
     */
    public PluginServer(MainWindow mainWindow, int port, String bindAddress, JadxAIMCP plugin) {
        this.mainWindow = mainWindow;
        this.port = port;
        this.bindAddress = bindAddress;
        this.paginationUtils = new PaginationUtils();
        this.plugin = plugin;
        
        // Initialize AuthConfig with environment overrides if plugin is available
        if (plugin != null) {
            this.authConfig = new AuthConfig(plugin.getEnvAuthToken(), plugin.getEnvAuthEnabled(), plugin.getEnvAuthTokenFile());
        } else {
            this.authConfig = new AuthConfig();
        }
    }

    /**
     * Sets the plugin reference (for lazy initialization).
     */
    public void setPlugin(JadxAIMCP plugin) {
        this.plugin = plugin;
    }

    /**
     * @return void
     * 
     * This method starts the Javalin HTTP server for the MCP plugin.
     * 1. It creates a Javalin instance with custom configuration:
     *    - Disables the default Javalin banner
     * 2. It starts the server on the configured port
     * 3. It registers all API route handlers via registerRoutes()
     * 4. It sets the running flag to true
     * 5. It logs the startup success message with custom banner and server URL
     * 6. If startup fails, it:
     *    - Logs the error with exception details
     *    - Sets running flag to false
     *    - Re-throws a RuntimeException to notify the plugin
     * 
     * This method is called by the plugin initialization mechanism after
     * JADX has fully loaded the APK content.
     */
    public void start() {
        try {
            // Close orphaned server socket from previous classloader (e.g., after "Reset Code Cache")
            closePreviousServerSocket();

            // Register global OOM detection handler
            installOomHandler();

            // Configure and start Javalin with a bounded Jetty QueuedThreadPool.
            // Hard cap prevents unbounded thread creation under load; the bounded queue
            // causes the server to reject with a visible 503 rather than silently queuing
            // requests until OOM.  Both limits are tunable via env vars.
            int maxThreads = parseEnvInt("JADX_MCP_MAX_THREADS", 64);
            int queueCapacity = parseEnvInt("JADX_MCP_QUEUE_SIZE", 64);
            org.eclipse.jetty.util.thread.QueuedThreadPool threadPool =
                    new org.eclipse.jetty.util.thread.QueuedThreadPool(
                            maxThreads, /* maxThreads */
                            8,          /* minThreads */
                            60_000,     /* idleTimeout ms */
                            new java.util.concurrent.LinkedBlockingQueue<>(queueCapacity));
            threadPool.setName("jadx-ai-mcp-qtp");
            logger.info("[JAI] Jetty QTP: maxThreads={}, queueCapacity={}", maxThreads, queueCapacity);

            app = Javalin.create(config -> {
                config.showJavalinBanner = false;
                config.jetty.threadPool = threadPool;
                config.jetty.defaultHost = bindAddress;
            }).start(port);

            // Add authentication middleware (runs before all routes)
            app.before(ctx -> {
                // OOM circuit-breaker: refuse all non-health requests when heap is exhausted.
                // /health is kept alive so monitoring continues to poll.
                if (isOomDetected() && !ctx.path().equals("/health")) {
                    ctx.status(503).json(java.util.Map.of(
                        "error", "oom_detected",
                        "message", "JVM heap exhaustion detected; container restart required",
                        "restart_required", true
                    ));
                    return;
                }

                // Skip auth for health check endpoint
                if (ctx.path().equals("/health")) {
                    return;
                }

                // Validate authentication token
                if (authConfig.isAuthEnabled()) {
                    String authHeader = ctx.header("Authorization");
                    String token = null;

                    // Extract token from Authorization header (Bearer token format)
                    if (authHeader != null && authHeader.startsWith("Bearer ")) {
                        token = authHeader.substring(7);
                    }

                    // Validate token
                    if (!authConfig.validateToken(token)) {
                        logger.warn("Unauthorized request from " + ctx.ip() + " to " + ctx.path());
                        ctx.status(401).json(java.util.Map.of(
                            "error", "Unauthorized",
                            "message", "Invalid or missing authentication token"
                        ));
                        ctx.result();
                        return;
                    }
                }
            });

            // Register all route handlers
            registerRoutes();

            // Store the underlying ServerSocketChannel in JVM-global properties
            // so the next classloader can close it before rebinding
            storeServerSocketChannel();

            // Register event listener for cache invalidation
            setupCacheInvalidation();

            isRunning = true;

            // Log startup success and banner
            logger.info(JadxAIMCPBanner.banner);
            logger.info("// -------------------- JADX AI MCP PLUGIN -------------------- //");
            logger.info("JADX AI MCP Plugin HTTP Server Started at http://" + bindAddress + ":" + port + "/");

            if (authConfig.isAuthEnabled()) {
                logger.info("Authentication: ENABLED");
                logger.info("Auth Token: " + maskToken(authConfig.getAuthToken()));
                logger.info("Config File: " + authConfig.getConfigFilePath());
            } else {
                logger.info("Authentication: DISABLED (for security, enable in settings)");
                logger.info("Auth Token (masked): " + maskToken(authConfig.getAuthToken()));
                logger.info("Config File: " + authConfig.getConfigFilePath());
                
                // Security warning when binding to all interfaces without auth
                if ("0.0.0.0".equals(bindAddress)) {
                    logger.warn("SECURITY WARNING: Server is bound to 0.0.0.0 without authentication!");
                    // Show GUI warning dialog on EDT
                    javax.swing.SwingUtilities.invokeLater(() -> {
                        javax.swing.JOptionPane.showMessageDialog(
                            mainWindow,
                            "<html><b>[!] Security Warning</b><br><br>" +
                            "Server is bound to <b>0.0.0.0</b> (all network interfaces),<br>" +
                            "but <font color='red'>authentication is disabled</font>!<br><br>" +
                            "This exposes your decompiled code to anyone on the network.<br><br>" +
                            "Please enable authentication immediately:<br>" +
                            "<i>Plugins → JADX AI MCP Server → Settings → Enable Auth</i></html>",
                            "JADX AI MCP Security Warning",
                            javax.swing.JOptionPane.WARNING_MESSAGE
                        );
                    });
                }
            }

            // Asynchronous cache warmup for class cache
            Thread cacheWarmupThread = new Thread(() -> {
                try {
                    Thread.sleep(2000); // Wait 2s for server to fully stabilize
                    logger.info("[JAI] Starting background cache warmup...");

                    // Warmup class cache (name indices are built inside initCache)
                    try {
                        ClassCacheManager.initCache(mainWindow.getWrapper());
                        logger.info("[JAI] Class cache warmup initiated");
                    } catch (Exception e) {
                        logger.warn("[JAI] Failed to warmup class cache: " + e.getMessage());
                    }

                    // Predecompile top-K most-referenced classes
                    runPredecompileWarmup();

                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "JAI-CacheWarmup");
            cacheWarmupThread.setDaemon(true);
            cacheWarmupThread.start();

        } catch (Exception e) {
            logger.error("JADX-AI-MCP Plugin Error: Could not start HTTP Server. Exception: " + e.getMessage(), e);
            stop();
            // Re-throw to let the main plugin know startup failed
            throw new RuntimeException("Failed to start Javalin Server", e);
        }
    }

    /**
     * @return void
     * 
     * This method performs graceful shutdown of the Javalin server.
     * 1. It checks if the server instance exists
     * 2. It calls Javalin's stop() method to close all connections
     * 3. It logs the successful shutdown
     * 4. If shutdown fails, it logs the error
     * 5. In the finally block, it:
     *    - Nullifies the server instance
     *    - Sets running flag to false
     * 
     * This method is called during plugin restart or JADX shutdown.
     */
    public void stop() {
        try {
            if (app != null) {
                app.stop();
                logger.info("JADX-AI-MCP Plugin: HTTP Server Stopped");
            }
        } catch (Exception e) {
            logger.error("JADX-AI-MCP Plugin Error: Error during shutdown: " + e.getMessage(), e);
        } finally {
            teardownCacheInvalidation();
            restoreOomHandler();
            if (classRoutes != null) {
                classRoutes.shutdownSearchExecutor();
                classRoutes = null;
            }
            app = null;
            isRunning = false;
            System.getProperties().remove(JVM_SERVER_KEY);
        }
    }

    /**
     * @return boolean True if server is running, false otherwise
     * 
     * This method returns the volatile running flag indicating server status.
     * The flag is thread-safe and reflects the actual server state.
     */
    public boolean isRunning() {
        return isRunning;
    }

    /**
     * @return int The port number the server is configured to listen on
     *
     * This method returns the port number used by the server.
     * The port is set during construction and remains constant for the server's lifetime.
     */
    public int getPort() {
        return port;
    }

    /**
     * @return AuthConfig The authentication configuration object
     *
     * This method returns the authentication configuration for managing tokens and auth settings.
     */
    public AuthConfig getAuthConfig() {
        return authConfig;
    }

    /**
     * @return String The bind address the server is listening on
     */
    public String getBindAddress() {
        return bindAddress;
    }

    /**
     * Closes any orphaned ServerSocketChannel left by a previous classloader.
     * When JADX performs "Reset Code Cache", it creates a new classloader and
     * the old static fields are lost—but the OS-level socket remains open.
     * We use JVM-global System.getProperties() to pass the channel reference
     * across classloader boundaries.
     */
    private void closePreviousServerSocket() {
        try {
            Object prev = System.getProperties().get(JVM_SERVER_KEY);
            if (prev instanceof ServerSocketChannel) {
                ServerSocketChannel oldChannel = (ServerSocketChannel) prev;
                if (oldChannel.isOpen()) {
                    logger.info("Closing orphaned ServerSocketChannel from previous classloader");
                    oldChannel.close();
                    // Brief wait for OS to release the port
                    Thread.sleep(500);
                }
            }
        } catch (Exception e) {
            logger.warn("Failed to close previous server socket: " + e.getMessage(), e);
        } finally {
            System.getProperties().remove(JVM_SERVER_KEY);
        }
    }

    /**
     * Stores the underlying ServerSocketChannel in JVM-global properties so
     * the next classloader instance can close it before rebinding.
     */
    private void storeServerSocketChannel() {
        try {
            org.eclipse.jetty.server.Server jettyServer = app.jettyServer().server();
            org.eclipse.jetty.server.Connector[] connectors = jettyServer.getConnectors();
            if (connectors.length > 0 && connectors[0] instanceof ServerConnector) {
                ServerConnector connector = (ServerConnector) connectors[0];
                Object transport = connector.getTransport();
                if (transport instanceof ServerSocketChannel) {
                    System.getProperties().put(JVM_SERVER_KEY, transport);
                    logger.debug("Stored ServerSocketChannel in JVM-global properties for cross-classloader cleanup");
                }
            }
        } catch (Exception e) {
            logger.warn("Could not store ServerSocketChannel (non-fatal): " + e.getMessage());
        }
    }

    /**
     * Masks a token for safe logging, showing only first 8 characters.
     *
     * @param token The full token
     * @return Masked token string (e.g., "abcd1234********")
     */
    private String maskToken(String token) {
        if (token == null || token.length() <= 8) {
            return "********";
        }
        return token.substring(0, 8) + "********";
    }

    /**
     * @return void
     * 
     * This method registers all HTTP API endpoints with their route handlers.
     * 1. It instantiates route handler classes, passing required dependencies:
     *    - GeneralRoutes: Health checks and general endpoints
     *    - ClassRoutes: Class navigation and analysis
     *    - MethodRoutes: Method search and retrieval
     *    - ResourceRoutes: Manifest and resource file access
     *    - RefactoringRoutes: Code renaming operations
     *    - DebugRoutes: Debugging information
     *    - XrefsRoutes: Cross-reference analysis
     * 2. It maps HTTP GET endpoints to handler methods organized by category:
     *    - General: /health
     *    - Classes: /current-class, /all-classes, /class-source, etc.
     *    - Methods: /method-by-name
     *    - Xrefs: /xrefs-to-class, /xrefs-to-method, /xrefs-to-field
     *    - Resources: /manifest, /strings, /list-all-resource-files-names
     *    - Refactoring: /rename-class, /rename-method, /rename-field, /rename-package
     *    - Debugging: /debug/stack-frames, /debug/variables, /debug/threads
     * 
     * All route handlers receive mainWindow and paginationUtils for accessing
     * JADX API and providing consistent pagination across endpoints.
     */
    private void registerRoutes() {
        // Instantiate Route Controllers
        // Passing 'mainWindow' and 'paginationUtils' to them so they can do their work
        GeneralRoutes generalRoutes = new GeneralRoutes(mainWindow, port, this);
        classRoutes = new ClassRoutes(mainWindow, paginationUtils);
        SearchRoutes searchRoutes = classRoutes.getSearchRoutes();
        BatchRoutes batchRoutes = new BatchRoutes(mainWindow, paginationUtils, searchRoutes);
        DecompileRoutes decompileRoutes = new DecompileRoutes(mainWindow, searchRoutes);
        MethodRoutes methodRoutes = new MethodRoutes(mainWindow, paginationUtils);
        ResourceRoutes resourceRoutes = new ResourceRoutes(mainWindow);
        RefactoringRoutes refactoringRoutes = new RefactoringRoutes(mainWindow);
        XrefsRoutes xrefsRoutes = new XrefsRoutes(mainWindow);

        // --- General & Health ---
        app.get("/health", generalRoutes::handleHealth);
        app.get("/index-stats", generalRoutes::handleIndexStats);

        // --- APK Info (for multi-instance management) ---
        if (plugin != null) {
            ApkInfoRoutes apkInfoRoutes = new ApkInfoRoutes(mainWindow, plugin);
            app.get("/apk-info", apkInfoRoutes::handleApkInfo);
            app.get("/file-info", apkInfoRoutes::handleFileInfo);
        }

        // --- File Management (sandboxed list + dynamic load) ---
        FilePathSandbox sandbox = FilePathSandbox.fromEnvironment();
        FileManagementRoutes fileManagementRoutes = new FileManagementRoutes(mainWindow, sandbox);
        app.get("/list-available-files", fileManagementRoutes::handleListAvailableFiles);
        app.post("/load-file", fileManagementRoutes::handleLoadFile);

        // --- Class & Code Navigation ---
        app.get("/current-class", classRoutes::handleCurrentClass);
        app.get("/all-classes", classRoutes::handleAllClasses);
        app.get("/selected-text", classRoutes::handleSelectedText);
        app.get("/class-source", decompileRoutes::handleClassSource);
        app.get("/batch-class-source", batchRoutes::handleBatchClassSource);
        app.get("/smali-of-class", decompileRoutes::handleSmaliOfClass);
        app.get("/methods-of-class", classRoutes::handleMethodsOfClass);
        app.get("/fields-of-class", classRoutes::handleFieldsOfClass);
        app.get("/main-application-classes-code", batchRoutes::handleMainApplicationClassesCode);
        app.get("/main-application-classes-names", batchRoutes::handleMainApplicationClassesNames);
        app.get("/main-activity", batchRoutes::handleMainActivity);
        app.get("/search-classes-by-keyword", searchRoutes::handleSearchClassesByKeyword);
        app.get("/class-info", classRoutes::handleClassInfo);


        // --- Methods ---
        app.get("/method-by-name", methodRoutes::handleMethodByName);
        app.get("/batch-method-by-name", methodRoutes::handleBatchMethodByName);
        app.get("/method-signature", methodRoutes::handleMethodSignature);
        app.get("/method-callees", methodRoutes::handleMethodCallees);
        app.get("/search-native-methods", methodRoutes::handleSearchNativeMethods);

        
        // --- Xrefs ---
        app.get("/xrefs-to-class", xrefsRoutes::handleXrefsToClass);
        app.get("/xrefs-to-method", xrefsRoutes::handleXrefsToMethod);
        app.get("/xrefs-to-field", xrefsRoutes::handleXrefsToField);
        app.get("/batch-xrefs", xrefsRoutes::handleBatchXrefs);

        // --- Resources & Manifest ---
        app.get("/manifest", resourceRoutes::handleManifest);
        app.get("/strings", resourceRoutes::handleStrings);
        app.get("/list-all-resource-files-names", resourceRoutes::handleListAllResourceFilesNames);
        app.get("/get-resource-file", resourceRoutes::handleGetResourceFile);
        
        // --- JAR-specific Resources ---
        app.get("/jar-manifest", resourceRoutes::handleJarManifest);
        app.get("/jar-services", resourceRoutes::handleJarServices);
        app.get("/jar-entry-points", classRoutes::handleJarEntryPoints);
        app.get("/jar-dependencies", resourceRoutes::handleJarDependencies);
        app.get("/jar-bytecode", classRoutes::handleJarBytecode);
        
        // --- Unified Interface (APK + JAR) ---
        app.get("/config-strings", resourceRoutes::handleConfigStrings);
        app.get("/package-classes", classRoutes::handlePackageClasses);
        app.get("/package-tree", classRoutes::handleGetPackageTree);

        // --- Frida Hook Generation ---
        FridaRoutes fridaRoutes = new FridaRoutes(mainWindow);
        app.get("/generate-frida-hook", fridaRoutes::handleGenerateFridaHook);
        app.get("/generate-frida-trace", fridaRoutes::handleGenerateFridaTrace);
        app.get("/generate-frida-enum", fridaRoutes::handleGenerateFridaEnum);

        // --- Renaming ---
        app.post("/rename-class", refactoringRoutes::handleRenameClass);
        app.post("/rename-method", refactoringRoutes::handleRenameMethod);
        app.post("/rename-field", refactoringRoutes::handleRenameField);
        app.post("/rename-package", refactoringRoutes::handleRenamePackage);
        app.post("/rename-variable", refactoringRoutes::handleRenameVariable);

        // --- Rename Mappings Import/Export ---
        app.get("/export-rename-mappings", refactoringRoutes::handleExportRenameMappings);
        app.post("/import-rename-mappings", refactoringRoutes::handleImportRenameMappings);

        // --- Collaborative Workspace: Annotations / Bookmarks / Tags ---
        AnnotationRoutes annotationRoutes = new AnnotationRoutes(mainWindow);
        app.post("/annotations", annotationRoutes::handleAddAnnotation);
        app.get("/annotations", annotationRoutes::handleGetAnnotations);
        app.delete("/annotations/{id}", annotationRoutes::handleDeleteAnnotation);
        app.post("/bookmarks", annotationRoutes::handleAddBookmark);
        app.get("/bookmarks", annotationRoutes::handleGetBookmarks);
        app.delete("/bookmarks/{id}", annotationRoutes::handleDeleteBookmark);
        app.post("/tags", annotationRoutes::handleAddTag);
        app.get("/tags", annotationRoutes::handleGetTags);
        app.delete("/tags/{id}", annotationRoutes::handleDeleteTag);
        app.get("/analysis-notes", annotationRoutes::handleGetAnalysisNotes);

        // --- Decompilation Status ---
        app.get("/decompile-status", ctx -> {
            try {
                jadx.gui.JadxWrapper wrapper = mainWindow.getWrapper();
                if (wrapper == null) {
                    ctx.status(503).json(java.util.Map.of(
                        "error", "JADX wrapper not initialized"
                    ));
                    return;
                }
                
                java.util.List<jadx.api.JavaClass> classes = wrapper.getIncludedClassesWithInners();
                int total = classes.size();
                int processed = 0;
                
                // Count classes that have completed processing (cached)
                for (jadx.api.JavaClass cls : classes) {
                    if (cls.getClassNode() != null && 
                        cls.getClassNode().getState().isProcessComplete()) {
                        processed++;
                    }
                }
                
                int cachedPercentage = total > 0 ? (processed * 100 / total) : 0;
                
                java.util.Map<String, Object> response = new java.util.HashMap<>();
                
                // === Class Cache Statistics (from JADX ProcessState) ===
                response.put("total_classes", total);
                response.put("cached_classes", processed);
                response.put("cached_percentage", cachedPercentage);
                
                // === JVM Memory Statistics (real data from Runtime) ===
                Runtime runtime = Runtime.getRuntime();
                long maxMemory = runtime.maxMemory();
                long totalMemory = runtime.totalMemory();
                long freeMemory = runtime.freeMemory();
                long usedMemory = totalMemory - freeMemory;
                
                java.util.Map<String, Object> memoryInfo = new java.util.LinkedHashMap<>();
                memoryInfo.put("max_mb", maxMemory / (1024 * 1024));
                memoryInfo.put("total_mb", totalMemory / (1024 * 1024));
                memoryInfo.put("used_mb", usedMemory / (1024 * 1024));
                memoryInfo.put("free_mb", freeMemory / (1024 * 1024));
                memoryInfo.put("usage_percentage", totalMemory > 0 ? (int)(usedMemory * 100 / totalMemory) : 0);
                response.put("memory", memoryInfo);
                
                // === Thread Statistics (real data from ThreadMXBean) ===
                java.lang.management.ThreadMXBean threadMXBean = java.lang.management.ManagementFactory.getThreadMXBean();
                java.util.Map<String, Object> threadInfo = new java.util.LinkedHashMap<>();
                threadInfo.put("active_count", threadMXBean.getThreadCount());
                threadInfo.put("peak_count", threadMXBean.getPeakThreadCount());
                threadInfo.put("daemon_count", threadMXBean.getDaemonThreadCount());
                response.put("threads", threadInfo);
                
                // === JADX Settings (real config from settings) ===
                try {
                    jadx.gui.settings.JadxSettings settings = mainWindow.getSettings();
                    if (settings != null) {
                        java.util.Map<String, Object> jadxConfig = new java.util.LinkedHashMap<>();
                        jadxConfig.put("threads_count", settings.getThreadsCount());
                        jadxConfig.put("code_cache_mode", settings.getCodeCacheMode().name());
                        response.put("jadx_config", jadxConfig);
                    }
                } catch (Exception e) {
                    // Settings access may fail, ignore
                }
                
                // === Decompiled Code Cache Statistics ===
                response.put("code_cache", ClassCacheManager.getCodeCacheStats());

                // === Search Lock Status (from JadxSearchLock) ===
                response.put("search_lock", com.zin.jadxaimcp.utils.JadxSearchLock.getStatus());
                response.put("search_coordinator", CodeSearchCoordinator.getStatus());
                
                ctx.json(response);
            } catch (Exception e) {
                logger.error("Error getting decompile status", e);
                ctx.status(500).json(java.util.Map.of(
                    "error", "Failed to get decompile status: " + e.getMessage()
                ));
            }
        });
        
        // --- Cache Management ---
        app.post("/cache/clear", ctx -> {
            try {
                CodeSearchCoordinator.clearCache();
                boolean cleared = ClassCacheManager.clearCacheIncludingDecompiled();
                if (cleared) {
                    logger.info("[JAI] Class cache and code search cache cleared manually via API");
                    ctx.json(java.util.Map.of(
                        "success", true,
                        "message", "Class cache cleared successfully",
                        "cooldown_seconds", ClassCacheManager.getCooldownDuration()
                    ));
                } else {
                    long remaining = ClassCacheManager.getRemainingCooldown();
                    logger.info("[JAI] Cache clear debounced, {}s remaining", remaining);
                    ctx.json(java.util.Map.of(
                        "success", false,
                        "message", "Cache clear debounced (30s global cooldown)",
                        "cooldown_remaining_seconds", remaining
                    ));
                }
            } catch (Exception e) {
                logger.error("[JAI] Failed to clear cache", e);
                ctx.status(500).json(java.util.Map.of(
                    "success", false,
                    "error", "Failed to clear cache: " + e.getMessage()
                ));
            }
        });
    }
    
    /**
     * Setup cache invalidation listener for rename operations.
     *
     * <p>On each {@link NodeRenamedByUser} event we perform a <em>scalpel</em> invalidation:
     * only the upstream decompiled code for the affected class is evicted, not the entire
     * code cache.  The class-index ({@link ClassCacheManager}) is also invalidated so a
     * fresh lookup will occur on the next request.</p>
     *
     * <p>We intentionally do <strong>not</strong> call
     * {@code CodeSearchCoordinator.clearCache()} here: cancelling in-flight search
     * futures every time a user or AI renames a node causes a request-cancellation storm
     * (503 cascade).  Search results that pre-date the rename will be slightly stale at
     * worst; callers can always re-search if needed.</p>
     *
     * <p>Manual repro for the old storm: open a large APK, trigger a code search that
     * takes &gt;2 s, then rename any class via the GUI — the search future was cancelled,
     * producing an immediate 503 for the in-flight MCP request.</p>
     */
    private void setupCacheInvalidation() {
        if (renameListener != null) {
            return;
        }
        renameListener = event -> {
            // Extract the affected class name from the renamed node.
            // ICodeNodeRef does not expose a class-name accessor directly; we derive it
            // from the node's string representation (toString includes the class context)
            // or fall back to a full class-index invalidation if the node type is opaque.
            String affectedClass = extractClassNameFromRenameEvent(event);
            if (affectedClass != null) {
                logger.info("[JAI] Rename detected for class '{}', invalidating code cache entry", affectedClass);
                ClassCacheManager.invalidateCode(affectedClass);
                // Also invalidate the per-class method/field snapshot caches so that
                // subsequent getDeclaredMethodInfos / getDeclaredFieldInfos calls see
                // the updated alias names.
                try {
                    java.util.Map<String, jadx.api.JavaClass> cache = ClassCacheManager.getCache();
                    jadx.api.JavaClass cls = ClassCacheManager.findClass(cache, affectedClass);
                    if (cls != null) {
                        com.zin.jadxaimcp.utils.JadxApiAdapter.invalidateSnapshots(cls);
                        // Rebuild name-index buckets for this class so subsequent
                        // exact-match searches reflect the new alias.
                        ClassCacheManager.reindex(cls);
                    }
                } catch (Exception ignored) {
                    // getCache() may throw if still initializing; snapshot staleness is
                    // acceptable in that case — they'll be rebuilt on next access.
                }
            } else {
                // Unknown node type (e.g. variable/package rename) — invalidate index only,
                // which is cheap and avoids dumping the entire decompiled code cache.
                logger.info("[JAI] Rename detected (unknown node type), clearing class index");
                ClassCacheManager.clearCache();
                com.zin.jadxaimcp.utils.JadxApiAdapter.clearAllSnapshotCaches();
            }
            // NOTE: CodeSearchCoordinator.clearCache() is deliberately NOT called here.
            // See Javadoc above for the rationale.
        };
        mainWindow.events().addListener(JadxEvents.NODE_RENAMED_BY_USER, renameListener);
        logger.info("[JAI] Cache invalidation listener registered");
    }

    /**
     * Attempts to extract the affected class full name from a rename event.
     *
     * <p>The event's {@code node} is an internal JADX {@code ICodeNodeRef} (e.g.
     * {@code ClassNode}, {@code MethodNode}, {@code FieldNode}, or {@code PackageNode}).
     * We cannot safely {@code instanceof}-check these internal types, so we rely on their
     * {@code toString()} representation, which for class/method/field nodes typically has
     * the form {@code "ClassName"} or {@code "ClassName.memberName"}.</p>
     *
     * <p>If the {@code JRenameNode} attachment is present (set by {@code RenameDialog}),
     * we prefer extracting the class name from it via its {@link jadx.api.JavaNode} wrapper,
     * which gives us the declaring-class's full name without depending on internal types.</p>
     *
     * @return the affected class full name, or null if not determinable
     */
    private static String extractClassNameFromRenameEvent(NodeRenamedByUser event) {
        if (event == null) {
            return null;
        }
        // Try via the JRenameNode attachment first (most reliable path).
        // RenameDialog sets this via event.setRenameNode(node); cast via reflection
        // to avoid a compile-time dependency on jadx.gui.treemodel.JRenameNode.
        Object renameNodeObj = event.getRenameNode();
        if (renameNodeObj != null) {
            try {
                // JRenameNode.getJavaNode() returns jadx.api.JavaNode
                java.lang.reflect.Method getJavaNode = renameNodeObj.getClass().getMethod("getJavaNode");
                Object javaNode = getJavaNode.invoke(renameNodeObj);
                if (javaNode instanceof jadx.api.JavaClass) {
                    return ((jadx.api.JavaClass) javaNode).getFullName();
                }
                if (javaNode instanceof jadx.api.JavaMethod) {
                    jadx.api.JavaClass declaring = ((jadx.api.JavaMethod) javaNode).getDeclaringClass();
                    if (declaring != null) {
                        return declaring.getFullName();
                    }
                }
                if (javaNode instanceof jadx.api.JavaField) {
                    jadx.api.JavaClass declaring = ((jadx.api.JavaField) javaNode).getDeclaringClass();
                    if (declaring != null) {
                        return declaring.getFullName();
                    }
                }
            } catch (Exception ignored) {
                // Reflection failed (API changed or security manager); fall through to toString path
            }
        }
        // Fallback: parse the node's toString().
        // ClassNode.toString() → "ClassName", MethodNode.toString() → "ClassName.methodName(…)"
        jadx.api.metadata.ICodeNodeRef node = event.getNode();
        if (node == null) {
            return null;
        }
        String nodeStr = node.toString();
        if (nodeStr == null || nodeStr.isEmpty()) {
            return null;
        }
        // Strip method/field suffix after the first '(' or last '.' that looks like a member
        int parenIdx = nodeStr.indexOf('(');
        String stripped = parenIdx >= 0 ? nodeStr.substring(0, parenIdx) : nodeStr;
        if (stripped.contains(".")) {
            return stripped.substring(0, stripped.lastIndexOf('.'));
        }
        // Node toString IS the class name (e.g. bare ClassNode)
        return stripped.isEmpty() ? null : stripped;
    }

    private void teardownCacheInvalidation() {
        if (renameListener == null) {
            return;
        }
        mainWindow.events().removeListener(JadxEvents.NODE_RENAMED_BY_USER, renameListener);
        renameListener = null;
        logger.info("[JAI] Cache invalidation listener unregistered");
    }

    /**
     * Android entry-point superclass names used to identify high-priority classes
     * that the AI always probes first.
     */
    private static final java.util.Set<String> ANDROID_ENTRY_POINT_SUPERS = java.util.Set.of(
        "android.app.Activity",
        "android.app.Service",
        "android.app.Application",
        "android.content.BroadcastReceiver",
        "android.content.ContentProvider"
    );

    /**
     * Two-phase warmup that runs after the name-index is built.
     *
     * <h3>Phase 1 — Serial decompile under write-lock</h3>
     * <p>JADX's {@code getCode()} is NOT thread-safe for concurrent callers; the write-lock
     * comment in {@link com.zin.jadxaimcp.utils.JadxSearchLock} is definitive.  We therefore
     * decompile top-K candidates serially: acquire write-lock, call {@code getCode()}, release.
     * This serialises cleanly with concurrent API requests that also contend for the lock,
     * giving those requests a fair shot at the lock between warmup classes.</p>
     *
     * <p>Reads {@code JADX_MCP_WARMUP_TOP_K} (default 100); set to 0 to disable entirely.
     * Also includes Android entry-point classes ({@code Activity}, {@code Service}, etc.).</p>
     *
     * <h3>Phase 2 — Parallel trigram index fill</h3>
     * <p>After all decompiles finish, N worker threads iterate the candidate list and call
     * {@link com.zin.jadxaimcp.utils.CodeContentIndex#tryIndexFromCache} for each class
     * that has cached code but isn't yet in the trigram index.
     * {@code CodeContentIndex} is fully thread-safe (ConcurrentHashMap + per-BitSet
     * synchronisation), so this phase is truly parallel — no JADX lock needed.</p>
     *
     * <p>Reads {@code JADX_MCP_WARMUP_INDEX_WORKERS} (default 4) to tune parallelism.</p>
     *
     * <p>Emits a final summary log:
     * "Warmup complete: %d classes decompiled, %d indexed, trigram coverage %.1f%%".</p>
     */
    private void runPredecompileWarmup() {
        try {
            int topK = parseEnvIntAllowZero("JADX_MCP_WARMUP_TOP_K", 100);
            if (topK == 0) {
                logger.info("[JAI] Predecompile warmup disabled (JADX_MCP_WARMUP_TOP_K=0)");
                return;
            }

            // Wait for the class cache to be ready (it was just initiated, may still be loading)
            java.util.Map<String, jadx.api.JavaClass> cacheMap;
            try {
                cacheMap = ClassCacheManager.getCache();
            } catch (Exception e) {
                logger.warn("[JAI] Predecompile warmup skipped: cache not ready — {}", e.getMessage());
                return;
            }

            java.util.List<jadx.api.JavaClass> allClasses = new java.util.ArrayList<>(cacheMap.values());
            if (allClasses.isEmpty()) {
                logger.info("[JAI] Predecompile warmup skipped: no classes in cache");
                return;
            }

            // Score each class by the number of methods that reference it (useInMth)
            allClasses.sort((a, b) -> {
                int aScore = com.zin.jadxaimcp.utils.JadxApiAdapter.getClassUseInMethods(a).size();
                int bScore = com.zin.jadxaimcp.utils.JadxApiAdapter.getClassUseInMethods(b).size();
                return Integer.compare(bScore, aScore); // descending
            });

            // Build candidate set: top-K by score + Android entry points
            java.util.LinkedHashSet<jadx.api.JavaClass> candidates = new java.util.LinkedHashSet<>();
            int added = 0;
            for (jadx.api.JavaClass cls : allClasses) {
                if (added >= topK) break;
                candidates.add(cls);
                added++;
            }
            for (jadx.api.JavaClass cls : allClasses) {
                if (candidates.contains(cls)) continue;
                String superClass = com.zin.jadxaimcp.utils.JadxApiAdapter.getSuperClass(cls);
                if (superClass != null && ANDROID_ENTRY_POINT_SUPERS.contains(superClass)) {
                    candidates.add(cls);
                }
            }

            java.util.List<jadx.api.JavaClass> candidateList = new java.util.ArrayList<>(candidates);
            logger.info("[JAI] Warmup phase-1 start: {} candidates (topK={} + entry-points)",
                candidateList.size(), topK);

            // ----------------------------------------------------------------
            // Phase 1: Serial decompile under write-lock.
            // JADX getCode() is NOT thread-safe; all callers must serialise via
            // JadxSearchLock.  We acquire per-class with a 30s timeout so
            // concurrent API requests can interleave between warmup steps.
            // ----------------------------------------------------------------
            // Per-class timeout: each class decompile runs in a dedicated daemon thread that
            // owns the write lock. The warmup supervisor waits at most perClassTimeoutSec
            // seconds per class. On timeout the daemon thread is interrupted and the
            // executor is restarted so subsequent classes get a fresh thread.
            // This prevents a single stuck class from holding the write lock indefinitely.
            final int perClassTimeoutSec = parseEnvInt("JADX_MCP_WARMUP_PER_CLASS_TIMEOUT", 30);
            long phase1Start = System.currentTimeMillis();
            int decompiled = 0;
            int lockSkipped = 0;

            java.util.concurrent.ExecutorService decompileExecutor =
                java.util.concurrent.Executors.newSingleThreadExecutor(r -> {
                    Thread t = new Thread(r, "jadx-warmup-decompile");
                    t.setDaemon(true);
                    return t;
                });

            for (jadx.api.JavaClass cls : candidateList) {
                if (Thread.currentThread().isInterrupted()) {
                    Thread.interrupted();
                    break;
                }
                final String clsName = cls.getFullName();
                java.util.concurrent.Future<Boolean> task = decompileExecutor.submit(() -> {
                    if (!com.zin.jadxaimcp.utils.JadxSearchLock.tryAcquire(perClassTimeoutSec)) {
                        return Boolean.FALSE;
                    }
                    try {
                        cls.getCode();
                        return Boolean.TRUE;
                    } catch (Exception ignored) {
                        return Boolean.FALSE;
                    } finally {
                        com.zin.jadxaimcp.utils.JadxSearchLock.release();
                    }
                });

                try {
                    if (Boolean.TRUE.equals(
                            task.get(perClassTimeoutSec, java.util.concurrent.TimeUnit.SECONDS))) {
                        decompiled++;
                    } else {
                        lockSkipped++;
                    }
                } catch (java.util.concurrent.TimeoutException te) {
                    task.cancel(true);
                    lockSkipped++;
                    logger.warn("[JAI] Warmup: class {} exceeded {}s timeout, skipping. Recycling decompile thread.",
                        clsName, perClassTimeoutSec);
                    // Restart so the next class gets a clean thread.
                    // The interrupted daemon eventually releases the lock in its finally block.
                    decompileExecutor.shutdownNow();
                    decompileExecutor = java.util.concurrent.Executors.newSingleThreadExecutor(r -> {
                        Thread t = new Thread(r, "jadx-warmup-decompile");
                        t.setDaemon(true);
                        return t;
                    });
                } catch (java.util.concurrent.ExecutionException ee) {
                    lockSkipped++;
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }

                if (decompiled % 10 == 0 && decompiled > 0) {
                    logger.info("[JAI] Warmup phase-1: {}/{} decompiled", decompiled, candidateList.size());
                }
            }

            decompileExecutor.shutdownNow();
            long phase1Ms = System.currentTimeMillis() - phase1Start;
            logger.info("[JAI] Warmup phase-1 done: {} decompiled, {} lock-skipped in {}ms",
                decompiled, lockSkipped, phase1Ms);

            // ----------------------------------------------------------------
            // Phase 2: Parallel trigram index fill.
            // Reads already-cached code only (no JADX lock needed).
            // CodeContentIndex is thread-safe — this phase is truly parallel.
            // ----------------------------------------------------------------
            int indexWorkers = parseEnvInt("JADX_MCP_WARMUP_INDEX_WORKERS", 4);
            int effectiveWorkers = Math.min(indexWorkers, Math.max(1, candidateList.size()));
            java.util.concurrent.atomic.AtomicInteger indexed = new java.util.concurrent.atomic.AtomicInteger(0);
            java.util.concurrent.atomic.AtomicInteger indexPos = new java.util.concurrent.atomic.AtomicInteger(0);
            long phase2Start = System.currentTimeMillis();

            java.util.concurrent.ExecutorService indexPool =
                java.util.concurrent.Executors.newFixedThreadPool(effectiveWorkers);
            java.util.concurrent.CountDownLatch latch =
                new java.util.concurrent.CountDownLatch(effectiveWorkers);

            for (int w = 0; w < effectiveWorkers; w++) {
                indexPool.submit(() -> {
                    try {
                        int pos;
                        while ((pos = indexPos.getAndIncrement()) < candidateList.size()) {
                            jadx.api.JavaClass cls = candidateList.get(pos);
                            // getCachedCodeDirect reads from ICodeCache without acquiring
                            // JadxSearchLock — safe because phase-1 has already populated it.
                            String code = ClassCacheManager.getCachedCodeDirect(cls);
                            if (com.zin.jadxaimcp.utils.CodeContentIndex.tryIndexFromCache(cls, code)) {
                                indexed.incrementAndGet();
                            }
                        }
                    } finally {
                        latch.countDown();
                    }
                });
            }

            try {
                latch.await(120, java.util.concurrent.TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                indexPool.shutdownNow();
            }

            long phase2Ms = System.currentTimeMillis() - phase2Start;
            int totalIndexed = com.zin.jadxaimcp.utils.CodeContentIndex.indexedClassCount();
            int totalClasses = allClasses.size();
            double coverage = totalClasses > 0 ? (100.0 * totalIndexed / totalClasses) : 0.0;

            logger.info(String.format(
                "[JAI] Warmup complete: %d classes decompiled, %d indexed, "
                + "trigram coverage %.1f%% (%d/%d). Phase1=%dms phase2=%dms",
                decompiled, indexed.get(), coverage, totalIndexed, totalClasses,
                phase1Ms, phase2Ms));

        } catch (Exception e) {
            logger.warn("[JAI] Predecompile warmup failed (non-fatal): {}", e.getMessage());
        }
    }

    /**
     * Installs a global UncaughtExceptionHandler that detects OutOfMemoryError.
     * Sets a JVM-global sticky flag so the /health endpoint can report it,
     * even across classloader reloads.
     */
    private void installOomHandler() {
        if (oomExceptionHandler != null) {
            return;
        }
        previousUncaughtExceptionHandler = Thread.getDefaultUncaughtExceptionHandler();
        oomExceptionHandler = (thread, throwable) -> {
            if (isOomRelated(throwable)) {
                // Write flag first — this must succeed even if heap is exhausted
                System.getProperties().put(JVM_OOM_KEY, System.currentTimeMillis());
                // Best-effort logging; may fail if heap is fully exhausted
                try {
                    logger.error("[JAI] OutOfMemoryError detected on thread '{}'. "
                            + "Instance marked as degraded. Restart JADX to recover.", thread.getName());
                } catch (OutOfMemoryError ignored) {
                    // Flag already set above, logging is non-critical
                }
            }
            // Delegate to previous handler if any
            if (previousUncaughtExceptionHandler != null) {
                previousUncaughtExceptionHandler.uncaughtException(thread, throwable);
            }
        };
        Thread.setDefaultUncaughtExceptionHandler(oomExceptionHandler);
        logger.debug("[JAI] Global OOM detection handler installed");
    }

    private void restoreOomHandler() {
        if (oomExceptionHandler == null) {
            return;
        }
        if (Thread.getDefaultUncaughtExceptionHandler() == oomExceptionHandler) {
            Thread.setDefaultUncaughtExceptionHandler(previousUncaughtExceptionHandler);
        }
        oomExceptionHandler = null;
        previousUncaughtExceptionHandler = null;
        logger.debug("[JAI] Global OOM detection handler restored");
    }

    /**
     * Checks if a throwable or any of its causes is an OutOfMemoryError.
     * Uses a depth limit to guard against circular cause chains.
     */
    private static boolean isOomRelated(Throwable t) {
        int depth = 0;
        while (t != null && depth < 50) {
            if (t instanceof OutOfMemoryError) {
                return true;
            }
            t = t.getCause();
            depth++;
        }
        return false;
    }

    /**
     * Reads an integer from an environment variable.
     * Falls back to {@code defaultValue} if the variable is unset or unparseable.
     */
    private static int parseEnvInt(String envVar, int defaultValue) {
        String raw = System.getenv(envVar);
        if (raw != null && !raw.isEmpty()) {
            try {
                int val = Integer.parseInt(raw.trim());
                if (val > 0) {
                    return val;
                }
                logger.warn("[JAI] Env var {} must be > 0 (got {}), using default {}", envVar, raw, defaultValue);
            } catch (NumberFormatException e) {
                logger.warn("[JAI] Env var {} is not a valid integer (got '{}'), using default {}", envVar, raw, defaultValue);
            }
        }
        return defaultValue;
    }

    /**
     * Like {@link #parseEnvInt} but accepts 0 as a valid value (used for "disabled" flags).
     * Falls back to {@code defaultValue} only if the variable is unset, empty, or non-numeric.
     */
    private static int parseEnvIntAllowZero(String envVar, int defaultValue) {
        String raw = System.getenv(envVar);
        if (raw != null && !raw.isEmpty()) {
            try {
                int val = Integer.parseInt(raw.trim());
                if (val >= 0) {
                    return val;
                }
                logger.warn("[JAI] Env var {} must be >= 0 (got {}), using default {}", envVar, raw, defaultValue);
            } catch (NumberFormatException e) {
                logger.warn("[JAI] Env var {} is not a valid integer (got '{}'), using default {}", envVar, raw, defaultValue);
            }
        }
        return defaultValue;
    }

    /**
     * Returns true if an OutOfMemoryError has been detected since last JVM start.
     * Uses JVM-global storage so it survives classloader reloads.
     */
    public static boolean isOomDetected() {
        return System.getProperties().containsKey(JVM_OOM_KEY);
    }

    /**
     * Returns the timestamp (epoch millis) when OOM was detected, or 0 if none.
     */
    public static long getOomTimestamp() {
        Object val = System.getProperties().get(JVM_OOM_KEY);
        if (val instanceof Long) {
            return (Long) val;
        }
        return 0;
    }

}
