package com.zin.jadxaimcp.server;

import io.javalin.Javalin;
import jadx.gui.ui.MainWindow;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.zin.jadxaimcp.JadxAIMCP;
import com.zin.jadxaimcp.utils.JadxAIMCPBanner;
import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.server.routes.*; // MCP tool call's request handlers

public class PluginServer {
    private static final Logger logger = LoggerFactory.getLogger(PluginServer.class);
    private final MainWindow mainWindow;
    private final int port;
    private final String bindAddress;
    private Javalin app;
    private final PaginationUtils paginationUtils;
    private final AuthConfig authConfig;
    private JadxAIMCP plugin;
    private volatile boolean isRunning = false;

    /**
     * @param mainWindows - The main Jadx window context
     * @param port        - The port to listen on
     */
    public PluginServer(MainWindow mainWindow, int port) {
        this(mainWindow, port, "127.0.0.1");
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
            this.authConfig = new AuthConfig(plugin.getEnvAuthToken(), plugin.getEnvAuthEnabled());
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
            // Configure and start Javalin
            app = Javalin.create(config -> {
                config.showJavalinBanner = false;
                config.jetty.defaultHost = bindAddress;
            }).start(port);

            // Add authentication middleware (runs before all routes)
            app.before(ctx -> {
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
                            "<html><b>⚠️ Security Warning</b><br><br>" +
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

        } catch (Exception e) {
            logger.error("JADX-AI-MCP Plugin Error: Could not start HTTP Server. Exception: " + e.getMessage(), e);
            isRunning = false;
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
        if (app != null) {
            try {
                app.stop();
                logger.info("JADX-AI-MCP Plugin: HTTP Server Stopped");
            } catch (Exception e) {
                logger.error("JADX-AI-MCP Plugin Error: Error during shutdown: " + e.getMessage(), e);
            } finally {
                app = null;
                isRunning = false;
            }
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
     *    - Methods: /method-by-name, /search-method
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
        ClassRoutes classRoutes = new ClassRoutes(mainWindow, paginationUtils);
        MethodRoutes methodRoutes = new MethodRoutes(mainWindow, paginationUtils);
        ResourceRoutes resourceRoutes = new ResourceRoutes(mainWindow);
        RefactoringRoutes refactoringRoutes = new RefactoringRoutes(mainWindow);
        DebugRoutes debugRoutes = new DebugRoutes(mainWindow);
        XrefsRoutes xrefsRoutes = new XrefsRoutes(mainWindow);

        // --- General & Health ---
        app.get("/health", generalRoutes::handleHealth);

        // --- APK Info (for multi-instance management) ---
        if (plugin != null) {
            ApkInfoRoutes apkInfoRoutes = new ApkInfoRoutes(mainWindow, plugin);
            app.get("/apk-info", apkInfoRoutes::handleApkInfo);
        }

        // --- Class & Code Navigation ---
        app.get("/current-class", classRoutes::handleCurrentClass);
        app.get("/all-classes", classRoutes::handleAllClasses);
        app.get("/selected-text", classRoutes::handleSelectedText);
        app.get("/class-source", classRoutes::handleClassSource);
        app.get("/batch-class-source", classRoutes::handleBatchClassSource);
        app.get("/smali-of-class", classRoutes::handleSmaliOfClass);
        app.get("/methods-of-class", classRoutes::handleMethodsOfClass);
        app.get("/fields-of-class", classRoutes::handleFieldsOfClass);
        app.get("/main-application-classes-code", classRoutes::handleMainApplicationClassesCode);
        app.get("/main-application-classes-names", classRoutes::handleMainApplicationClassesNames);
        app.get("/main-activity", classRoutes::handleMainActivity);
        app.get("/search-classes-by-keyword", classRoutes::handleSearchClassesByKeyword);
        app.get("/class-info", classRoutes::handleClassInfo);


        // --- Methods ---
        app.get("/method-by-name", methodRoutes::handleMethodByName);
        app.get("/batch-method-by-name", methodRoutes::handleBatchMethodByName);
        app.get("/search-method", methodRoutes::handleSearchMethod);
        app.get("/method-signature", methodRoutes::handleMethodSignature);
        
        // --- Xrefs ---
        app.get("/xrefs-to-class", xrefsRoutes::handleXrefsToClass);
        app.get("/xrefs-to-method", xrefsRoutes::handleXrefsToMethod);
        app.get("/xrefs-to-field", xrefsRoutes::handleXrefsToField);

        // --- Resources & Manifest ---
        app.get("/manifest", resourceRoutes::handleManifest);
        app.get("/strings", resourceRoutes::handleStrings);
        app.get("/list-all-resource-files-names", resourceRoutes::handleListAllResourceFilesNames);
        app.get("/get-resource-file", resourceRoutes::handleGetResourceFile);

        // --- Renaming ---
        app.get("/rename-class", refactoringRoutes::handleRenameClass);
        app.get("/rename-method", refactoringRoutes::handleRenameMethod);
        app.get("/rename-field", refactoringRoutes::handleRenameField);
        app.get("/rename-package", refactoringRoutes::handleRenamePackage);

        // --- Debugging ---
        app.get("/debug/stack-frames", debugRoutes::handleGetStackFrames);
        app.get("/debug/variables", debugRoutes::handleGetVariables);
        app.get("/debug/threads", debugRoutes::handleGetThreads);        
    }

}