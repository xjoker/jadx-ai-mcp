package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import javax.swing.SwingUtilities;

import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.FilePathSandbox;
import com.zin.jadxaimcp.utils.FilePathSandbox.SandboxViolation;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;

/**
 * File-management routes: list the sandboxed file root and load an APK/JAR
 * into the running JADX instance without GUI interaction.
 *
 * Endpoints:
 *   GET  /list-available-files?subdir=&pattern=*.apk[&recursive=true]
 *   POST /load-file                              body: {path, mode}
 *
 * Both endpoints reject any request when the sandbox root is unavailable.
 * Path sandbox semantics are owned by {@link FilePathSandbox}.
 */
public class FileManagementRoutes {
    private static final Logger logger = LoggerFactory.getLogger(FileManagementRoutes.class);

    private static final List<String> ALLOWED_EXTENSIONS = List.of(
            ".apk", ".jar", ".dex", ".aar", ".class", ".zip");

    private final MainWindow mainWindow;
    private final FilePathSandbox sandbox;

    public FileManagementRoutes(MainWindow mainWindow, FilePathSandbox sandbox) {
        this.mainWindow = mainWindow;
        this.sandbox = sandbox;
    }

    public void handleListAvailableFiles(Context ctx) {
        if (!sandbox.isEnabled()) {
            JadxAIMCPPluginError.handleError(ctx, 503,
                    "Sandbox not configured. Set JADX_FILE_ROOT or mount a directory at /apks.", logger);
            return;
        }
        try {
            String subdir = ctx.queryParam("subdir");
            String pattern = ctx.queryParam("pattern");
            boolean recursive = Boolean.parseBoolean(ctx.queryParamAsClass("recursive", String.class)
                    .getOrDefault("false"));

            Path base = (subdir == null || subdir.isEmpty())
                    ? sandbox.getRoot()
                    : sandbox.resolveWithinRoot(subdir);
            if (!Files.isDirectory(base)) {
                JadxAIMCPPluginError.handleError(ctx, 400,
                        "subdir is not a directory: " + subdir, logger);
                return;
            }

            String glob = (pattern == null || pattern.isEmpty()) ? "*" : pattern;
            List<Map<String, Object>> files = new ArrayList<>();
            collect(base, glob, recursive, files);
            files.sort((a, b) -> ((String) a.get("path")).compareTo((String) b.get("path")));

            Map<String, Object> result = new HashMap<>();
            result.put("root", sandbox.getRoot().toString());
            result.put("base", base.toString());
            result.put("count", files.size());
            result.put("files", files);
            ctx.json(result);
        } catch (SandboxViolation e) {
            JadxAIMCPPluginError.handleError(ctx, 400, e.getMessage(), logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Failed to list files: " + e.getMessage(), e, logger);
        }
    }

    public void handleLoadFile(Context ctx) {
        if (!sandbox.isEnabled()) {
            JadxAIMCPPluginError.handleError(ctx, 503,
                    "Sandbox not configured. Set JADX_FILE_ROOT or mount a directory at /apks.", logger);
            return;
        }
        if (mainWindow == null) {
            JadxAIMCPPluginError.handleError(ctx, 503, "JADX main window not available", logger);
            return;
        }
        try {
            Map<String, Object> body = ctx.bodyAsClass(Map.class);
            String userPath = body == null ? null : (String) body.get("path");
            String mode = body == null ? "replace" : (String) body.getOrDefault("mode", "replace");
            if (userPath == null || userPath.isEmpty()) {
                JadxAIMCPPluginError.handleError(ctx, 400, "path is required", logger);
                return;
            }
            if (!"replace".equals(mode) && !"append".equals(mode)) {
                JadxAIMCPPluginError.handleError(ctx, 400,
                        "mode must be 'replace' or 'append', got: " + mode, logger);
                return;
            }

            Path canonical = sandbox.resolveWithinRoot(userPath);
            if (!Files.isRegularFile(canonical)) {
                JadxAIMCPPluginError.handleError(ctx, 400,
                        "path is not a regular file: " + canonical, logger);
                return;
            }
            String name = canonical.getFileName().toString().toLowerCase(Locale.ROOT);
            boolean extOk = ALLOWED_EXTENSIONS.stream().anyMatch(name::endsWith);
            if (!extOk) {
                JadxAIMCPPluginError.handleError(ctx, 400,
                        "extension not allowed (need one of " + ALLOWED_EXTENSIONS + "): " + name, logger);
                return;
            }

            // JADX GUI APIs must run on the EDT. Dispatch async and return immediately;
            // callers poll /decompile-status (or /apk-info) for readiness.
            final String finalMode = mode;
            SwingUtilities.invokeLater(() -> {
                try {
                    if ("append".equals(finalMode)) {
                        mainWindow.addFiles(Collections.singletonList(canonical));
                    } else {
                        mainWindow.open(canonical);
                    }
                    try {
                        // Full eviction: the entire project changed, so the upstream decompiled
                        // code cache must also be cleared, not just the class index.
                        ClassCacheManager.clearCacheIncludingDecompiled();
                    } catch (Throwable t) {
                        logger.warn("ClassCacheManager.clearCacheIncludingDecompiled failed: {}", t.getMessage());
                    }
                    logger.info("load_file: dispatched {} for {}", finalMode, canonical);
                } catch (Throwable t) {
                    logger.error("load_file: EDT task failed for {}: {}", canonical, t.getMessage(), t);
                }
            });

            Map<String, Object> result = new HashMap<>();
            result.put("dispatched", true);
            result.put("mode", mode);
            result.put("path", canonical.toString());
            result.put("ready", false);
            result.put("poll_with", "/decompile-status");
            result.put("note", "Decompilation continues asynchronously; poll /decompile-status for progress.");
            ctx.status(202).json(result);
        } catch (SandboxViolation e) {
            JadxAIMCPPluginError.handleError(ctx, 400, e.getMessage(), logger);
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "load_file failed: " + e.getMessage(), e, logger);
        }
    }

    private void collect(Path base, String glob, boolean recursive,
                         List<Map<String, Object>> out) throws IOException {
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(base, glob)) {
            for (Path entry : stream) {
                if (Files.isDirectory(entry)) {
                    if (recursive) collect(entry, glob, true, out);
                    continue;
                }
                Map<String, Object> item = new HashMap<>();
                Path rel = sandbox.getRoot().relativize(entry);
                item.put("path", rel.toString());
                item.put("absolute", entry.toString());
                try {
                    item.put("size_bytes", Files.size(entry));
                } catch (IOException ignored) {
                    item.put("size_bytes", -1);
                }
                String n = entry.getFileName().toString().toLowerCase(Locale.ROOT);
                String ext = n.contains(".") ? n.substring(n.lastIndexOf('.')) : "";
                item.put("extension", ext);
                item.put("loadable", ALLOWED_EXTENSIONS.contains(ext));
                out.add(item);
            }
        }

        if (recursive && glob.equals("*")) {
            // Built-in glob "*" matches directories too; recursive walk above already
            // descends into them, so nothing extra needed here.
            return;
        }
        if (recursive) {
            // For non-"*" glob we still need to descend into subdirs that did not
            // match the pattern themselves.
            try (DirectoryStream<Path> stream = Files.newDirectoryStream(base)) {
                for (Path entry : stream) {
                    if (Files.isDirectory(entry)) {
                        collect(entry, glob, true, out);
                    }
                }
            }
        }
    }
}
