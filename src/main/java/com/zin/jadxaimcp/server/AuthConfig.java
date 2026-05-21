package com.zin.jadxaimcp.server;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Properties;

/**
 * Authentication Configuration Manager
 *
 * Handles generation, storage, and validation of API authentication tokens.
 * Tokens are stored in a secure properties file and validated on each request.
 *
 * Supports file-mount mode via JADX_MCP_AUTH_TOKEN_FILE environment variable,
 * which is the recommended pattern for Docker secrets and container deployments.
 *
 * @author JADX AI MCP Team
 */
public class AuthConfig {
    private static final Logger logger = LoggerFactory.getLogger(AuthConfig.class);

    private static final String CONFIG_DIR = System.getProperty("user.home") + File.separator + ".jadx-ai-mcp";
    private static final String AUTH_CONFIG_FILE = CONFIG_DIR + File.separator + "auth.properties";
    private static final String TOKEN_KEY = "auth.token";
    private static final String ENABLED_KEY = "auth.enabled";
    private static final int TOKEN_LENGTH = 32; // 32 bytes = 256 bits

    private String authToken;
    private boolean authEnabled;

    // Environment variable overrides (used in Docker deployments)
    private String envAuthToken = null;
    private Boolean envAuthEnabled = null;

    // File-mount mode: token sourced from an external secret file
    private boolean externallyManaged = false;
    private String tokenFilePath = null;

    /**
     * Initializes authentication configuration.
     * Loads existing token or generates a new one if not present.
     */
    public AuthConfig() {
        this(null, null, null);
    }

    /**
     * Initializes authentication configuration with optional environment overrides.
     *
     * @param envToken Authentication token from environment variable, or null
     * @param envEnabled Authentication enabled flag from environment, or null
     */
    public AuthConfig(String envToken, Boolean envEnabled) {
        this(envToken, envEnabled, null);
    }

    /**
     * Initializes authentication configuration with optional environment overrides
     * and optional file-mount path.
     *
     * Priority (highest to lowest):
     *   1. JADX_MCP_AUTH_TOKEN_FILE (file-mount / Docker secrets)
     *   2. JADX_MCP_AUTH_TOKEN (env var)
     *   3. Persisted ~/.jadx-ai-mcp/auth.properties
     *   4. Generated random token
     *
     * When sourced from a file, token persistence and rotation are disabled.
     *
     * @param envToken     Authentication token from JADX_MCP_AUTH_TOKEN, or null
     * @param envEnabled   Authentication enabled flag from JADX_MCP_AUTH_ENABLED, or null
     * @param tokenFilePath Path from JADX_MCP_AUTH_TOKEN_FILE, or null
     */
    public AuthConfig(String envToken, Boolean envEnabled, String tokenFilePath) {
        this.envAuthToken = envToken;
        this.envAuthEnabled = envEnabled;
        this.tokenFilePath = tokenFilePath;
        ensureConfigDirectory();
        loadOrGenerateToken();

        // Apply environment overrides after loading (file-mount wins over env var)
        applyEnvironmentOverrides();
    }

    /**
     * Applies environment variable overrides.
     * File-mount token takes highest priority; plain env token is fallback.
     */
    private void applyEnvironmentOverrides() {
        // Priority 1: file-mount token (Docker secrets pattern)
        if (tokenFilePath != null && !tokenFilePath.isEmpty()) {
            String fileToken = loadTokenFromFile(tokenFilePath);
            // loadTokenFromFile throws/exits on error, so if we get here it's valid
            authToken = fileToken;
            externallyManaged = true;
            logger.info("Using authentication token from file: " + tokenFilePath);
            if (envAuthEnabled != null) {
                authEnabled = envAuthEnabled;
            }
            return;
        }
        // Priority 2: env var token
        if (envAuthToken != null && !envAuthToken.isEmpty()) {
            authToken = envAuthToken;
            logger.info("Using authentication token from environment variable");
        }
        if (envAuthEnabled != null) {
            authEnabled = envAuthEnabled;
            logger.info("Authentication " + (authEnabled ? "enabled" : "disabled") + " via environment variable");
        }
    }

    /**
     * Reads and trims the token from the specified file.
     * Fails fast (throws RuntimeException) if the file cannot be read,
     * to prevent silent fallback to a weaker token source.
     *
     * @param filePath Path to the secret file
     * @return Trimmed token string
     */
    private String loadTokenFromFile(String filePath) {
        try {
            byte[] bytes = Files.readAllBytes(Paths.get(filePath));
            String token = new String(bytes, StandardCharsets.UTF_8).trim();
            if (token.isEmpty()) {
                String msg = "JADX_MCP_AUTH_TOKEN_FILE points to an empty file: " + filePath;
                logger.error(msg);
                throw new RuntimeException(msg);
            }
            return token;
        } catch (IOException e) {
            String msg = "JADX_MCP_AUTH_TOKEN_FILE is set but file cannot be read: " + filePath
                       + " — " + e.getMessage();
            logger.error(msg);
            throw new RuntimeException(msg, e);
        }
    }

    /**
     * Returns true when the token was loaded from an external file
     * (JADX_MCP_AUTH_TOKEN_FILE). In this mode, token rotation via the UI
     * or API is disabled; edit the secret file externally to change the token.
     *
     * @return true if token is externally managed via file-mount
     */
    public boolean isExternallyManaged() {
        return externallyManaged;
    }

    /**
     * Ensures the configuration directory exists.
     */
    private void ensureConfigDirectory() {
        File configDir = new File(CONFIG_DIR);
        if (!configDir.exists()) {
            if (configDir.mkdirs()) {
                logger.info("Created JADX AI MCP config directory: " + CONFIG_DIR);
            } else {
                logger.warn("Failed to create config directory: " + CONFIG_DIR);
            }
        }
    }

    /**
     * Loads existing authentication token or generates a new one.
     */
    private void loadOrGenerateToken() {
        File configFile = new File(AUTH_CONFIG_FILE);

        if (configFile.exists()) {
            loadToken();
        } else {
            generateAndSaveToken();
        }
    }

    /**
     * Loads authentication token from properties file.
     */
    private void loadToken() {
        Properties props = new Properties();
        try (FileInputStream fis = new FileInputStream(AUTH_CONFIG_FILE)) {
            props.load(fis);
            authToken = props.getProperty(TOKEN_KEY);
            authEnabled = Boolean.parseBoolean(props.getProperty(ENABLED_KEY, "false"));

            if (authToken == null || authToken.isEmpty()) {
                logger.warn("Invalid token in config file, regenerating...");
                generateAndSaveToken();
            } else {
                logger.info("Loaded authentication token from config");
            }
        } catch (IOException e) {
            logger.error("Failed to load auth config: " + e.getMessage(), e);
            generateAndSaveToken();
        }
    }

    /**
     * Generates a new secure random token and saves it to file.
     */
    private void generateAndSaveToken() {
        authToken = generateSecureToken();
        authEnabled = false; // Disabled by default for backward compatibility
        saveToken();
    }

    /**
     * Generates a cryptographically secure random token.
     *
     * @return Base64-encoded random token string
     */
    private String generateSecureToken() {
        SecureRandom random = new SecureRandom();
        byte[] tokenBytes = new byte[TOKEN_LENGTH];
        random.nextBytes(tokenBytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(tokenBytes);
    }

    /**
     * Saves the authentication token to properties file.
     * Skipped when token is sourced from an external file to avoid writing secrets to disk.
     */
    private void saveToken() {
        if (externallyManaged) {
            // Never persist externally-managed tokens back to disk
            return;
        }
        Properties props = new Properties();
        props.setProperty(TOKEN_KEY, authToken);
        props.setProperty(ENABLED_KEY, String.valueOf(authEnabled));

        try (FileOutputStream fos = new FileOutputStream(AUTH_CONFIG_FILE)) {
            props.store(fos, "JADX AI MCP Authentication Configuration");
            logger.info("Authentication token saved to: " + AUTH_CONFIG_FILE);
        } catch (IOException e) {
            logger.error("Failed to save auth config: " + e.getMessage(), e);
        }
    }

    /**
     * Validates an incoming request token against the stored token.
     *
     * @param requestToken The token from the HTTP request
     * @return true if authentication is disabled or token matches, false otherwise
     */
    public boolean validateToken(String requestToken) {
        // If auth is disabled, allow all requests
        if (!authEnabled) {
            return true;
        }

        // If auth is enabled, validate token
        if (requestToken == null || requestToken.isEmpty()) {
            logger.warn("Request missing authentication token");
            return false;
        }

        // Use constant-time comparison to prevent timing attacks
        return constantTimeEquals(authToken, requestToken);
    }

    /**
     * Performs constant-time string comparison to prevent timing attacks.
     *
     * @param a First string
     * @param b Second string
     * @return true if strings are equal
     */
    private boolean constantTimeEquals(String a, String b) {
        if (a == null || b == null) {
            return false;
        }

        byte[] aBytes = a.getBytes(StandardCharsets.UTF_8);
        byte[] bBytes = b.getBytes(StandardCharsets.UTF_8);

        // Prevent timing attack: always compare using the longer length
        // XOR length difference into result to ensure different lengths fail
        int result = aBytes.length ^ bBytes.length;

        // Compare up to the length of the shorter array
        int minLen = Math.min(aBytes.length, bBytes.length);
        for (int i = 0; i < minLen; i++) {
            result |= aBytes[i] ^ bBytes[i];
        }

        return result == 0;
    }

    /**
     * Gets the current authentication token.
     *
     * @return The authentication token
     */
    public String getAuthToken() {
        return authToken;
    }

    /**
     * Checks if authentication is enabled.
     *
     * @return true if authentication is enabled
     */
    public boolean isAuthEnabled() {
        return authEnabled;
    }

    /**
     * Enables or disables authentication.
     *
     * @param enabled true to enable authentication
     */
    public void setAuthEnabled(boolean enabled) {
        this.authEnabled = enabled;
        saveToken();
        logger.info("Authentication " + (enabled ? "enabled" : "disabled"));
    }

    /**
     * Regenerates the authentication token.
     * Rejected when token is sourced from JADX_MCP_AUTH_TOKEN_FILE.
     *
     * @return true if token was regenerated, false if rejected (externally managed)
     */
    public boolean regenerateToken() {
        if (externallyManaged) {
            logger.warn("token sourced from JADX_MCP_AUTH_TOKEN_FILE; rotation disabled, edit the secret externally");
            return false;
        }
        authToken = generateSecureToken();
        saveToken();
        logger.info("Authentication token regenerated");
        return true;
    }

    /**
     * Sets a custom authentication token.
     * Rejected when token is sourced from JADX_MCP_AUTH_TOKEN_FILE.
     *
     * @param token The new authentication token
     * @return true if token was set, false if rejected (externally managed or blank)
     */
    public boolean setAuthToken(String token) {
        if (externallyManaged) {
            logger.warn("token sourced from JADX_MCP_AUTH_TOKEN_FILE; rotation disabled, edit the secret externally");
            return false;
        }
        if (token != null && !token.isEmpty()) {
            this.authToken = token;
            saveToken();
            logger.info("Authentication token updated manually");
            return true;
        }
        return false;
    }

    /**
     * Gets the configuration file path.
     *
     * @return Path to the auth config file
     */
    public String getConfigFilePath() {
        return AUTH_CONFIG_FILE;
    }
}
