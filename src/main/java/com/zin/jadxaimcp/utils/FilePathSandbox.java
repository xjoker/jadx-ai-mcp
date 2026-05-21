package com.zin.jadxaimcp.utils;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * File-path sandbox for the load_file / list_available_files MCP tools.
 *
 * Inspired by ghidra-mcp SecurityConfig#resolveWithinFileRoot: every user-supplied
 * path is canonicalized and required to live under a configured root directory,
 * blocking traversal via ".." and symlink escapes.
 *
 * Root resolution order:
 *   1. env JADX_FILE_ROOT (explicit opt-in)
 *   2. /apks if it exists (Docker convention used by this project)
 *   3. null (sandbox disabled — handlers MUST reject any load_file call)
 */
public final class FilePathSandbox {

    private static final Logger logger = LoggerFactory.getLogger(FilePathSandbox.class);
    private static final String ENV_FILE_ROOT = "JADX_FILE_ROOT";
    private static final String DEFAULT_DOCKER_ROOT = "/apks";

    private final Path root;

    public FilePathSandbox(Path root) {
        this.root = root;
    }

    /**
     * Build the sandbox from environment, falling back to /apks in Docker.
     * Returns an instance with root=null if neither is available — callers
     * MUST check isEnabled() before resolving paths.
     */
    public static FilePathSandbox fromEnvironment() {
        String envRoot = System.getenv(ENV_FILE_ROOT);
        if (envRoot != null && !envRoot.isEmpty()) {
            try {
                Path canonical = Paths.get(envRoot).toRealPath();
                if (Files.isDirectory(canonical)) {
                    logger.info("FilePathSandbox: root from JADX_FILE_ROOT = {}", canonical);
                    return new FilePathSandbox(canonical);
                }
                logger.warn("JADX_FILE_ROOT={} exists but is not a directory; sandbox disabled.", envRoot);
            } catch (IOException e) {
                logger.warn("JADX_FILE_ROOT={} cannot be canonicalized ({}); sandbox disabled.",
                        envRoot, e.getMessage());
            }
            return new FilePathSandbox(null);
        }

        Path dockerDefault = Paths.get(DEFAULT_DOCKER_ROOT);
        if (Files.isDirectory(dockerDefault)) {
            try {
                Path canonical = dockerDefault.toRealPath();
                logger.info("FilePathSandbox: root defaulted to {} (Docker convention).", canonical);
                return new FilePathSandbox(canonical);
            } catch (IOException e) {
                logger.warn("Default root /apks not resolvable ({}); sandbox disabled.", e.getMessage());
            }
        }

        logger.info("FilePathSandbox: no root configured (set JADX_FILE_ROOT to enable load_file).");
        return new FilePathSandbox(null);
    }

    public boolean isEnabled() {
        return root != null;
    }

    public Path getRoot() {
        return root;
    }

    /**
     * Canonicalize the user-supplied path and verify it resolves inside the
     * sandbox root. Accepts both absolute paths and paths relative to root.
     *
     * @throws SandboxViolation when sandbox is disabled, path escapes root,
     *                          or file does not exist.
     */
    public Path resolveWithinRoot(String userPath) throws SandboxViolation {
        if (root == null) {
            throw new SandboxViolation(
                    "load_file disabled: JADX_FILE_ROOT not set and /apks not present");
        }
        if (userPath == null || userPath.isEmpty()) {
            throw new SandboxViolation("path is required");
        }

        Path requested = Paths.get(userPath);
        Path absolute = requested.isAbsolute() ? requested : root.resolve(requested);

        Path canonical;
        try {
            canonical = absolute.toRealPath();
        } catch (IOException e) {
            throw new SandboxViolation("file not found: " + userPath);
        }

        if (!canonical.startsWith(root)) {
            throw new SandboxViolation(
                    "path escapes sandbox root " + root + ": " + canonical);
        }
        return canonical;
    }

    /** Thrown when a path violates sandbox rules; HTTP layer maps to 400. */
    public static final class SandboxViolation extends Exception {
        public SandboxViolation(String message) {
            super(message);
        }
    }
}
