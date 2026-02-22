/* 
 * Copyright (c) 2025 Jadx AI MCP developer(s) (https://github.com/zinja-coder/jadx-ai-mcp)
 * See the file 'LICENSE' for copying permission
*/

package com.zin.jadxaimcp;

import jadx.api.plugins.JadxPlugin;
import jadx.api.plugins.JadxPluginContext;
import jadx.api.plugins.JadxPluginInfo;
import jadx.api.plugins.JadxPluginInfoBuilder;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.swing.*;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.prefs.Preferences;

// Importing custom banner string
import com.zin.jadxaimcp.utils.JadxAIMCPBanner;
import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.ui.PluginMenu;
import com.zin.jadxaimcp.server.PluginServer;

public class JadxAIMCP implements JadxPlugin {
    public static final String PLUGIN_ID = "jadx-ai-mcp";
    private static final Logger logger = LoggerFactory.getLogger(JadxAIMCP.class);
    private static final String PREF_KEY_PORT = "jadx_ai_mcp_port";
    private static final String PREF_KEY_BIND_ADDRESS = "jadx_ai_mcp_bind_address";
    private static final String PREF_KEY_INSTANCE_NAME = "jadx_ai_mcp_instance_name";
    private static final int DEFAULT_PORT = 8650;
    private static final String DEFAULT_BIND_ADDRESS = "0.0.0.0";
    
    // Environment variable names for Docker/container configuration
    private static final String ENV_BIND_ADDRESS = "JADX_MCP_BIND_ADDRESS";
    private static final String ENV_PORT = "JADX_MCP_PORT";
    private static final String ENV_AUTH_TOKEN = "JADX_MCP_AUTH_TOKEN";
    private static final String ENV_AUTH_ENABLED = "JADX_MCP_AUTH_ENABLED";

    // Config & State
    private int currentPort = DEFAULT_PORT;
    private String currentBindAddress = DEFAULT_BIND_ADDRESS;
    private String instanceName = null;
    private Preferences prefs;
    private ScheduledExecutorService scheduler;

    // Components
    private MainWindow mainWindow;
    private PluginServer pluginServer;
    private PluginMenu pluginMenu;
    
    // Static singleton protection to prevent multiple server instances
    private static volatile PluginServer sharedServer = null;
    private static final Object SERVER_LOCK = new Object();
    private static volatile boolean initialized = false;

    public JadxAIMCP() {}

    @Override
    public JadxPluginInfo getPluginInfo() {
        return JadxPluginInfoBuilder.pluginId(PLUGIN_ID)
                .name("JADX-AI-MCP Plugin")
                .description("Integrates MCP Server support for JADX")
                .homepage("https://github.com/xjoker/jadx-ai-mcp")
                .requiredJadxVersion("1.5.1, r2333")
                .build();
    }

    @Override
    public void init(JadxPluginContext context) {
        if (context.getGuiContext() == null) {
            logger.info("JADX-AI-MCP Plugin: Running in non-GUI mode, plugin features disabled.");
            return;
        }

        try {
            this.mainWindow = (MainWindow) context.getGuiContext().getMainFrame();
            if (this.mainWindow == null) {
                logger.error("JADX-AI-MCP Plugin: Main Window is null.");
                return;
            }

            // 1. Initialize Config from Preferences
            prefs = Preferences.userNodeForPackage(JadxAIMCP.class);
            currentPort = prefs.getInt(PREF_KEY_PORT, DEFAULT_PORT);
            currentBindAddress = prefs.get(PREF_KEY_BIND_ADDRESS, DEFAULT_BIND_ADDRESS);
            instanceName = prefs.get(PREF_KEY_INSTANCE_NAME, null);
            
            // 1.1 Override from environment variables (for Docker deployment)
            applyEnvironmentOverrides();

            // 2. Initialize UI
            this.pluginMenu = new PluginMenu(mainWindow, this);
            this.pluginMenu.addMenuItems();

            // 3. Start Server Lifecycle
            logger.info("JADX-AI-MCP Plugin: Initializing...");
            startDelayedInitialization();
        } catch (Exception e) {
            logger.error("JADX-AI-MCP Plugin: Initialization error: " + e.getMessage(), e);
        }
    }
    
    /**
     * Applies configuration overrides from environment variables.
     * Environment variables take precedence over Preferences for Docker/container deployments.
     */
    private void applyEnvironmentOverrides() {
        // Override bind address
        String envBindAddress = System.getenv(ENV_BIND_ADDRESS);
        if (envBindAddress != null && !envBindAddress.isEmpty()) {
            currentBindAddress = envBindAddress;
            logger.info("JADX-AI-MCP Plugin: Using bind address from environment: " + envBindAddress);
        }
        
        // Override port
        String envPort = System.getenv(ENV_PORT);
        if (envPort != null && !envPort.isEmpty()) {
            try {
                currentPort = Integer.parseInt(envPort);
                logger.info("JADX-AI-MCP Plugin: Using port from environment: " + currentPort);
            } catch (NumberFormatException e) {
                logger.warn("JADX-AI-MCP Plugin: Invalid port in environment variable: " + envPort);
            }
        }
    }
    
    /**
     * Gets authentication token from environment variable if set.
     * @return The auth token from environment, or null if not set
     */
    public String getEnvAuthToken() {
        return System.getenv(ENV_AUTH_TOKEN);
    }
    
    /**
     * Gets authentication enabled flag from environment variable if set.
     * @return Boolean.TRUE if enabled, Boolean.FALSE if disabled, null if not set
     */
    public Boolean getEnvAuthEnabled() {
        String envAuthEnabled = System.getenv(ENV_AUTH_ENABLED);
        if (envAuthEnabled != null && !envAuthEnabled.isEmpty()) {
            return Boolean.parseBoolean(envAuthEnabled);
        }
        return null;
    }

    // ---- Server lifecycle management ---

    /**
     * @return void
     * 
     * This method initializes the delayed server startup mechanism using a scheduled executor.
     * 
     * 1. It creates a daemon thread executor for background initialization tasks
     * 2. It schedules a periodic check (every 1 second after 2 second initial delay) to verify:
     *  - Whether the server is already running (exits if true)
     *  - Whether JADX has fully loaded its content (starts server if true)
     * 3. It implements a fallback timeout of 30 seconds that forces server start if JADX hasn't
     * loaded by then to prevent indefinite waiting
     * 4. Once the server starts successfully, the scheduler shuts down
     * 
     * This delayed initialization is necessary because the plugin may load before Jadx completes
     * loading the APK content, and the server requires access to decompled classes.
     */
    private void startDelayedInitialization() {
        scheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "JADX-AI-MCP-Startup");
            t.setDaemon(true);
            return t;
        });

        // Wait for JADX to load content before starting server
        scheduler.scheduleAtFixedRate(() -> {
            try {
                if (isServerRunning()) {
                    scheduler.shutdown();
                    return;
                }
                if (isJadxFullyLoaded()) {
                    logger.info("JADX-AI-MCP Plugin: JADX ready, starting server...");
                    startServer();
                    scheduler.shutdown();
                }
            } catch (Exception e) {
                logger.error("JADX-AI-MCP Plugin: Init error: " + e.getMessage());
            }
        }, 2, 1, TimeUnit.SECONDS);

        // Fallback timeout (30s)
        scheduler.schedule(() -> {
            if (!isServerRunning()) {
                logger.warn("JADX-AI-MCP Plugin: Timeout waiting for JADX. Forcing start...");
                startServer();
            }
        }, 30, TimeUnit.SECONDS);
    }

    /**
     * @return void
     * 
     * This method starts the plugin's HTTP server on the configured port.
     * 
     * 1. It stops any existing server instance to prevent port conflicts
     * 2. It creates a new PluginServer instnace with the current MainWindow reference
     * and port
     * 3. It starts the server to begin listening for MCP client connnections.
     * 4. If any error occurs during startup, it logs the error message.
     * 
     * This method is called by the delayed initialization mechanism after JADX is ready.
     * Uses static singleton protection to prevent multiple server instances.
     */
    private void startServer() {
        synchronized (SERVER_LOCK) {
            try {
                // Check if a shared server is already running
                if (sharedServer != null && sharedServer.isRunning()) {
                    logger.info("JADX-AI-MCP Plugin: Server already running on port " + sharedServer.getPort() + ", reusing existing instance.");
                    this.pluginServer = sharedServer;
                    return;
                }
                
                // Stop any existing local server
                if (pluginServer != null) {
                    pluginServer.stop();
                }
                
                // === Disable JADX auto-rename — REQUIRED for accurate Frida/Xposed hook development ===
                //
                // WHY this is necessary:
                //   JADX's auto-rename rewrites obfuscated names (e.g. "a()", "b", class "C") into
                //   human-readable names like "getUserData()", "mContext", class "MainActivity2".
                //   These renamed names exist ONLY inside JADX's display — they do NOT exist in
                //   the actual APK bytecode at runtime.
                //
                //   Frida hooks, Xposed modules, and any runtime instrumentation MUST reference
                //   the original bytecode names. Using JADX-renamed names in a hook script will
                //   cause the hook to silently fail at runtime because the method/field cannot be found.
                //
                // EFFECT:
                //   After the server starts, JADX will show the original obfuscated names.
                //   If you already have the APK loaded, reload it (File > Reload) for the change
                //   to take effect in the UI.
                //
                // This behavior is intentional and cannot be disabled via settings.
                try {
                    jadx.gui.JadxWrapper wrapper = mainWindow.getWrapper();
                    if (wrapper != null && wrapper.getDecompiler() != null) {
                        jadx.api.JadxArgs args = wrapper.getDecompiler().getArgs();
                        if (args != null && args.getRenameFlags() != null) {
                            args.getRenameFlags().clear();
                            logger.info("JADX-AI-MCP Plugin: Auto-rename disabled — names now match actual APK bytecode for Frida/Xposed hook accuracy");
                        }
                    }
                } catch (Exception e) {
                    logger.warn("JADX-AI-MCP Plugin: Could not disable auto-rename: " + e.getMessage());
                }
                
                // Create and start new server
                pluginServer = new PluginServer(mainWindow, currentPort, currentBindAddress, this);
                pluginServer.start();
                
                // Store as shared server
                sharedServer = pluginServer;
                initialized = true;
                
            } catch (Exception e) {
                logger.error("JADX-AI-MCP Plugin: Failed to start server: " + e.getMessage());
            }
        }
    }

    /**
     * @return void
     * 
     * This method performs a graceful restart of the plugin server.
     * 
     * 1. It spawns a new daemon thread to handle the restart asynchronously
     * 2. it stops the current server instance if one is running
     * 3. It waits 1 second to ensure the port is fully released by the OS
     * 4. It starts a new server instance on the configured port
     * 5. It displays a success dialog to inform the user of the restart
     * 6. If restart fails, it logs the error
     * 
     * This methods is typically called from the plugin menu UI when users need to restart the server after configuration changes or connection issues.
     */
    public void restartServer() {
        new Thread(() -> {
            logger.info("JADX-AI-MCP Plugin: Restarting server on port " + currentPort);
            if (pluginServer != null) pluginServer.stop();
            try {
                Thread.sleep(1000); // Wait for port release
                startServer();
                SwingUtilities.invokeLater(() ->
                    JOptionPane.showMessageDialog(mainWindow,
                        "Server restarted on port " + currentPort,
                        "Server restarted.", JOptionPane.INFORMATION_MESSAGE));
            } catch (Exception e) {
                logger.error("Failed to restart server", e);
            }
        }, "JADX-AI-MCP-Restart").start();
    }

    // --- Configuration Methods (Used by UI) ---
    
    /**
     * @param newPort The new port number to configure for the server
     * @return void
     * 
     * This method updates the server port configuration and persists it.
     * 1. It updates the currentPort instance variable with the new port value
     * 2. It saves the new port to Java Preferences API for persistence across sessions
     * 
     * This method does not restart the server automatically. Call restartServer()
     * after updating the port to apply the changes.
     */
    public void updatePort(int newPort) {
        this.currentPort = newPort;
        prefs.putInt(PREF_KEY_PORT, newPort);
    }


    /**
     * @return void
     * 
     * This method resets the server port configuration to the default value (8650).
     * It delegates to updatePort() to handle the actual update and persistence.
     * 
     * The server must be restarted for the default port to take effect.
     */
    public void resetToDefaultPort() {
        updatePort(DEFAULT_PORT);
    }

    /**
     * @return int The currently configured port number
     * 
     * This method returns the port number on which the server is configured to run.
     * The value is loaded from Java Preferences on plugin initialization and can be
     * modified via updatePort() or resetToDefaultPort().
     */
    public int getCurrentPort() {
        return currentPort;
    }

    /**
     * @param newBindAddress The new bind address to configure for the server
     * @return void
     * 
     * This method updates the server bind address configuration and persists it.
     * 1. It updates the currentBindAddress instance variable with the new value
     * 2. It saves the new bind address to Java Preferences API for persistence
     * 
     * Common values: "127.0.0.1" (localhost only), "0.0.0.0" (all interfaces)
     * This method does not restart the server automatically. Call restartServer()
     * after updating the bind address to apply the changes.
     */
    public void updateBindAddress(String newBindAddress) {
        this.currentBindAddress = newBindAddress;
        prefs.put(PREF_KEY_BIND_ADDRESS, newBindAddress);
    }

    /**
     * @return void
     * 
     * This method resets the server bind address to the default value (127.0.0.1).
     * It delegates to updateBindAddress() to handle the actual update and persistence.
     * 
     * The server must be restarted for the default bind address to take effect.
     */
    public void resetToDefaultBindAddress() {
        updateBindAddress(DEFAULT_BIND_ADDRESS);
    }

    /**
     * @return String The currently configured bind address
     * 
     * This method returns the bind address on which the server is configured to listen.
     * The value is loaded from Java Preferences on plugin initialization.
     */
    public String getCurrentBindAddress() {
        return currentBindAddress;
    }

    /**
     * @return boolean True if the server is running, false otherwise
     *
     * This method checks the runtime status of the plugin server.
     * It verifies that:
     * 1. The pluginServer instance is not null
     * 2. The server's internal running state is true
     *
     * This check is used by the delayed initialization mechanism and UI status displays.
     */
    public boolean isServerRunning() {
        return pluginServer != null && pluginServer.isRunning();
    }

    /**
     * @return AuthConfig The authentication configuration object, or null if server not initialized
     *
     * This method provides access to the authentication configuration for the plugin UI.
     * It allows the menu system to display and manage authentication settings.
     */
    public com.zin.jadxaimcp.server.AuthConfig getAuthConfig() {
        return pluginServer != null ? pluginServer.getAuthConfig() : null;
    }

    // --- Helpers ---

    /**
     * @return boolean True if JADX has completed loading APK content, false otherwise
     * 
     * This method determines whether JADX has finished loading and decompiling the APK.
     * It checks for:
     * 1. MainWindow instance availability
     * 2. JadxWrapper instance availability
     * 3. Presence of decompiled classes or an initialized decompiler instance
     * 
     * This is used by startDelayedInitialization() to determine when it's safe
     * to start the MCP server, ensuring the server has access to decompiled content.
     */
    private boolean isJadxFullyLoaded() {
        try {
            if (mainWindow == null) return false;
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) return false;
            // Check if we have classes or at least a decompiler instance
            List<?> classes = wrapper.getIncludedClassesWithInners();
            return (classes != null && !classes.isEmpty()) || wrapper.getDecompiler() != null;
        } catch (Exception e) {
            return false;
        }
    }

    // --- Instance Management ---

    /**
     * @return String The configured instance name, or null if not set
     *
     * This method returns the user-defined instance name for multi-instance management.
     * When null, the MCP server will use APK name + versionCode as the identifier.
     */
    public String getInstanceName() {
        return instanceName;
    }

    /**
     * @param name The instance name to set, or null to use automatic naming
     *
     * This method updates the instance name configuration and persists it.
     */
    public void setInstanceName(String name) {
        this.instanceName = name;
        if (name != null && !name.isEmpty()) {
            prefs.put(PREF_KEY_INSTANCE_NAME, name);
        } else {
            prefs.remove(PREF_KEY_INSTANCE_NAME);
        }
    }

    /**
     * Stops the plugin server.
     */
    public void stopServer() {
        if (pluginServer != null) {
            pluginServer.stop();
            logger.info("JADX-AI-MCP Plugin: Server stopped by user");
        }
    }

    /**
     * @return String Human-readable APK information, or null if no APK loaded
     *
     * This method retrieves basic APK information from JADX for display in the UI.
     * Parses the AndroidManifest.xml to extract package and version info.
     */
    public String getApkInfo() {
        try {
            if (mainWindow == null) return null;
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) return null;
            
            java.util.List<jadx.api.ResourceFile> resources = wrapper.getResources();
            if (resources == null || resources.isEmpty()) return null;
            
            jadx.api.ResourceFile manifestFile = jadx.core.utils.android.AndroidManifestParser.getAndroidManifest(resources);
            if (manifestFile == null) return null;
            
            jadx.core.xmlgen.ResContainer container = manifestFile.loadContent();
            String manifestXml = container.getText().getCodeStr();
            
            String pkgName = extractManifestAttribute(manifestXml, "package");
            if (pkgName != null) {
                StringBuilder sb = new StringBuilder(pkgName);
                String versionName = extractManifestAttribute(manifestXml, "android:versionName");
                String versionCodeStr = extractManifestAttribute(manifestXml, "android:versionCode");
                if (versionName != null || versionCodeStr != null) {
                    sb.append(" (");
                    if (versionName != null) {
                        sb.append("v").append(versionName);
                    }
                    if (versionCodeStr != null) {
                        if (versionName != null) sb.append(", ");
                        sb.append("code: ").append(versionCodeStr);
                    }
                    sb.append(")");
                }
                return sb.toString();
            }
        } catch (Exception e) {
            logger.debug("Failed to get APK info: " + e.getMessage());
        }
        return null;
    }

    /**
     * @return String The automatically generated instance name based on file info
     *
     * This method generates a default instance name.
     * For APK: Uses package name + version code (e.g., "xhs-v12345")
     * For JAR: Uses priority order:
     *   1. MANIFEST.MF Implementation-Title + Implementation-Version
     *   2. MANIFEST.MF Main-Class (last segment)
     *   3. JAR file name (without .jar extension)
     *   4. Fallback: jadx-port
     */
    public String getAutoInstanceName() {
        try {
            if (mainWindow == null) return "jadx-" + currentPort;
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) return "jadx-" + currentPort;
            
            // Detect file type using FileTypeDetector
            java.io.File loadedFile = getLoadedFile();
            if (loadedFile != null) {
                com.zin.jadxaimcp.utils.FileTypeDetector.FileType fileType = 
                    com.zin.jadxaimcp.utils.FileTypeDetector.detectFileType(loadedFile);
                
                // For JAR files, use JAR-specific naming
                if (fileType == com.zin.jadxaimcp.utils.FileTypeDetector.FileType.JAR) {
                    return getJarInstanceName(loadedFile);
                }
            }
            
            // For APK/AAR/DEX: Use Android manifest-based naming
            java.util.List<jadx.api.ResourceFile> resources = wrapper.getResources();
            if (resources != null && !resources.isEmpty()) {
                jadx.api.ResourceFile manifestFile = jadx.core.utils.android.AndroidManifestParser.getAndroidManifest(resources);
                if (manifestFile != null) {
                    jadx.core.xmlgen.ResContainer container = manifestFile.loadContent();
                    String manifestXml = container.getText().getCodeStr();
                    
                    String pkgName = extractManifestAttribute(manifestXml, "package");
                    if (pkgName != null) {
                        // Use last part of package name + version code
                        String[] parts = pkgName.split("\\.");
                        String shortName = parts[parts.length - 1];
                        String versionCodeStr = extractManifestAttribute(manifestXml, "android:versionCode");
                        if (versionCodeStr != null) {
                            return shortName + "-v" + versionCodeStr;
                        }
                        return shortName;
                    }
                }
            }
        } catch (Exception e) {
            logger.debug("Failed to generate auto instance name: " + e.getMessage());
        }
        return "jadx-" + currentPort;
    }
    
    /**
     * Gets the currently loaded file from JADX wrapper.
     */
    private java.io.File getLoadedFile() {
        try {
            if (mainWindow == null) return null;
            JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) return null;
            
            java.util.List<java.nio.file.Path> inputFiles = wrapper.getProject().getFilePaths();
            if (inputFiles != null && !inputFiles.isEmpty()) {
                return inputFiles.get(0).toFile();
            }
        } catch (Exception e) {
            logger.debug("Failed to get loaded file: " + e.getMessage());
        }
        return null;
    }
    
    /**
     * Generates instance name for JAR files using MANIFEST.MF or file name.
     * Priority:
     *   1. Implementation-Title + Implementation-Version
     *   2. Main-Class (last segment)
     *   3. File name (without .jar extension)
     */
    private String getJarInstanceName(java.io.File jarFile) {
        try (java.util.jar.JarFile jar = new java.util.jar.JarFile(jarFile)) {
            java.util.jar.Manifest manifest = jar.getManifest();
            if (manifest != null) {
                java.util.jar.Attributes attrs = manifest.getMainAttributes();
                
                // Priority 1: Implementation-Title + Implementation-Version
                String implTitle = attrs.getValue("Implementation-Title");
                String implVersion = attrs.getValue("Implementation-Version");
                if (implTitle != null && !implTitle.isEmpty()) {
                    if (implVersion != null && !implVersion.isEmpty()) {
                        return sanitizeInstanceName(implTitle) + "-v" + sanitizeInstanceName(implVersion);
                    }
                    return sanitizeInstanceName(implTitle);
                }
                
                // Priority 2: Main-Class (use last segment)
                String mainClass = attrs.getValue("Main-Class");
                if (mainClass != null && !mainClass.isEmpty()) {
                    String[] parts = mainClass.split("\\.");
                    return sanitizeInstanceName(parts[parts.length - 1]);
                }
            }
        } catch (Exception e) {
            logger.debug("Failed to read JAR manifest: " + e.getMessage());
        }
        
        // Priority 3: File name without extension
        String fileName = jarFile.getName();
        if (fileName.toLowerCase().endsWith(".jar")) {
            fileName = fileName.substring(0, fileName.length() - 4);
        }
        return sanitizeInstanceName(fileName);
    }
    
    /**
     * Sanitizes instance name by removing/replacing problematic characters.
     */
    private String sanitizeInstanceName(String name) {
        if (name == null) return "unknown";
        // Replace spaces and special chars with hyphens, keep alphanumeric and hyphens
        return name.replaceAll("[^a-zA-Z0-9._-]", "-")
                   .replaceAll("-+", "-")  // Collapse multiple hyphens
                   .replaceAll("^-|-$", ""); // Remove leading/trailing hyphens
    }
    
    /**
     * Helper method to extract attribute from manifest XML
     */
    private String extractManifestAttribute(String manifestXml, String attrName) {
        try {
            int start = manifestXml.indexOf(attrName + "=\"");
            if (start == -1) {
                start = manifestXml.indexOf(attrName + "='");
            }
            if (start != -1) {
                start += attrName.length() + 2;
                char quote = manifestXml.charAt(start - 1);
                int end = manifestXml.indexOf(quote, start);
                if (end != -1) {
                    return manifestXml.substring(start, end);
                }
            }
        } catch (Exception e) {
            logger.debug("Failed to extract attribute " + attrName);
        }
        return null;
    }
}