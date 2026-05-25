package com.zin.jadxaimcp.server.routes;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import io.javalin.http.Context;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * AnnotationRoutes - Collaborative Workspace Phase 1
 *
 * Provides SQLite-backed persistence endpoints for annotations, bookmarks, and tags.
 * Database location: ~/.jadx-ai-mcp/annotations.db
 *
 * Endpoints:
 *   POST   /annotations          - Add an annotation
 *   GET    /annotations          - Query annotations
 *   DELETE /annotations/{id}     - Delete an annotation
 *   POST   /bookmarks            - Add a bookmark
 *   GET    /bookmarks            - Query bookmarks
 *   DELETE /bookmarks/{id}       - Delete a bookmark
 *   POST   /tags                 - Add a tag
 *   GET    /tags                 - Query tags
 *   DELETE /tags/{id}            - Delete a tag
 *   GET    /analysis-notes       - Summarize all notes for the current APK
 */
public class AnnotationRoutes {
    private static final Logger logger = LoggerFactory.getLogger(AnnotationRoutes.class);
    private static final Gson GSON = new Gson();

    private final MainWindow mainWindow;
    private final String dbPath;

    public AnnotationRoutes(MainWindow mainWindow) {
        this.mainWindow = mainWindow;
        this.dbPath = System.getProperty("user.home") + "/.jadx-ai-mcp/annotations.db";
        initDatabase();
    }

    // ==================== Database initialization ====================

    private void initDatabase() {
        File dbFile = new File(dbPath);
        File dbDir = dbFile.getParentFile();
        if (!dbDir.exists()) {
            boolean created = dbDir.mkdirs();
            if (created) {
                logger.info("[JAI] Created annotations DB directory: {}", dbDir.getAbsolutePath());
            }
        }

        try (Connection conn = getConnection();
             Statement stmt = conn.createStatement()) {

            // Enable WAL mode on first open so it persists in the DB file.
            // busy_timeout=5000 is also set per-connection in getConnection().
            stmt.execute("PRAGMA journal_mode=WAL");

            stmt.executeUpdate(
                "CREATE TABLE IF NOT EXISTS annotations (" +
                "  id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "  apk_hash TEXT," +
                "  target_type TEXT," +
                "  target_name TEXT," +
                "  content TEXT," +
                "  author TEXT DEFAULT 'anonymous'," +
                "  created_at TEXT DEFAULT (datetime('now'))," +
                "  updated_at TEXT DEFAULT (datetime('now'))" +
                ")"
            );

            stmt.executeUpdate(
                "CREATE TABLE IF NOT EXISTS bookmarks (" +
                "  id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "  apk_hash TEXT," +
                "  target_type TEXT," +
                "  target_name TEXT," +
                "  label TEXT," +
                "  note TEXT," +
                "  author TEXT DEFAULT 'anonymous'," +
                "  created_at TEXT DEFAULT (datetime('now'))" +
                ")"
            );

            stmt.executeUpdate(
                "CREATE TABLE IF NOT EXISTS tags (" +
                "  id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "  apk_hash TEXT," +
                "  target_type TEXT," +
                "  target_name TEXT," +
                "  tag TEXT," +
                "  author TEXT DEFAULT 'anonymous'," +
                "  created_at TEXT DEFAULT (datetime('now'))" +
                ")"
            );

            logger.info("[JAI] Annotations database initialized at {}", dbPath);
        } catch (SQLException e) {
            logger.error("[JAI] Failed to initialize annotations database: {}", e.getMessage(), e);
        }
    }

    /**
     * Opens a new SQLite connection with WAL journal mode and a 5-second busy
     * timeout.  WAL mode is set as a persistent DB property on first open (via
     * {@link #initDatabase()}), so subsequent connections inherit it; the
     * PRAGMA here is a belt-and-suspenders guard for freshly opened connections.
     * The 5-second busy_timeout lets writers queue briefly instead of immediately
     * returning SQLITE_BUSY, eliminating concurrent-write errors under normal load.
     */
    private Connection getConnection() throws SQLException {
        Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath);
        try (Statement pragma = conn.createStatement()) {
            pragma.execute("PRAGMA journal_mode=WAL");
            pragma.execute("PRAGMA busy_timeout=5000");
        }
        return conn;
    }

    // ==================== APK hash retrieval ====================

    /**
     * Derives apk_hash from the currently opened file (package name + version, or hashCode of the file path).
     * Uses a simple string hash to avoid extra dependencies while still providing per-APK isolation.
     */
    private String getCurrentApkHash() {
        try {
            jadx.gui.JadxWrapper wrapper = mainWindow.getWrapper();
            if (wrapper == null) return "unknown";

            // Prefer the opened file's path as the hash source
            java.util.List<jadx.api.ResourceFile> resources = wrapper.getResources();
            if (!resources.isEmpty()) {
                String path = resources.get(0).getOriginalName();
                if (path != null && !path.isEmpty()) {
                    return Integer.toHexString(path.hashCode());
                }
            }
        } catch (Exception e) {
            logger.debug("[JAI] Could not get APK hash: {}", e.getMessage());
        }
        return "unknown";
    }

    // ==================== JSON parsing utilities ====================

    private JsonObject parseJsonBody(Context ctx) {
        try {
            String body = ctx.body();
            if (body == null || body.isBlank()) {
                ctx.status(400).json(Map.of("error", "Request body is empty"));
                return null;
            }
            return GSON.fromJson(body, JsonObject.class);
        } catch (JsonParseException e) {
            ctx.status(400).json(Map.of("error", "Invalid JSON: " + e.getMessage()));
            return null;
        }
    }

    private String getBodyString(JsonObject body, String key) {
        if (body.has(key) && !body.get(key).isJsonNull()) {
            return body.get(key).getAsString();
        }
        return null;
    }

    private String getBodyStringOrDefault(JsonObject body, String key, String defaultValue) {
        String value = getBodyString(body, key);
        return (value != null && !value.isBlank()) ? value : defaultValue;
    }

    // ==================== Annotation endpoints ====================

    /**
     * POST /annotations
     * Body: { target_type, target_name, content, author?, apk_hash? }
     */
    public void handleAddAnnotation(Context ctx) {
        JsonObject body = parseJsonBody(ctx);
        if (body == null) return;

        String targetType = getBodyString(body, "target_type");
        String targetName = getBodyString(body, "target_name");
        String content = getBodyString(body, "content");

        if (targetType == null || targetType.isBlank()) {
            ctx.status(400).json(Map.of("error", "target_type is required"));
            return;
        }
        if (targetName == null || targetName.isBlank()) {
            ctx.status(400).json(Map.of("error", "target_name is required"));
            return;
        }
        if (content == null || content.isBlank()) {
            ctx.status(400).json(Map.of("error", "content is required"));
            return;
        }

        String author = getBodyStringOrDefault(body, "author", "anonymous");
        String apkHash = getBodyStringOrDefault(body, "apk_hash", getCurrentApkHash());

        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement(
                 "INSERT INTO annotations (apk_hash, target_type, target_name, content, author) VALUES (?,?,?,?,?)",
                 Statement.RETURN_GENERATED_KEYS)) {

            ps.setString(1, apkHash);
            ps.setString(2, targetType);
            ps.setString(3, targetName);
            ps.setString(4, content);
            ps.setString(5, author);
            ps.executeUpdate();

            long id = -1;
            try (ResultSet keys = ps.getGeneratedKeys()) {
                if (keys.next()) id = keys.getLong(1);
            }

            logger.info("[JAI] Added annotation id={} for {}/{}", id, targetType, targetName);
            ctx.status(201).json(Map.of(
                "success", true,
                "id", id,
                "target_type", targetType,
                "target_name", targetName,
                "apk_hash", apkHash
            ));
        } catch (SQLException e) {
            logger.error("[JAI] Failed to add annotation: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }

    /**
     * GET /annotations
     * Query params: target_type?, target_name?, apk_hash?
     */
    public void handleGetAnnotations(Context ctx) {
        String targetType = ctx.queryParam("target_type");
        String targetName = ctx.queryParam("target_name");
        String apkHash = ctx.queryParam("apk_hash");

        // Fall back to the currently opened APK if apk_hash is not specified
        if (apkHash == null || apkHash.isBlank()) {
            apkHash = getCurrentApkHash();
        }

        StringBuilder sql = new StringBuilder(
            "SELECT id, apk_hash, target_type, target_name, content, author, created_at, updated_at FROM annotations WHERE 1=1"
        );
        List<String> params = new ArrayList<>();

        sql.append(" AND apk_hash = ?");
        params.add(apkHash);

        if (targetType != null && !targetType.isBlank()) {
            sql.append(" AND target_type = ?");
            params.add(targetType);
        }
        if (targetName != null && !targetName.isBlank()) {
            sql.append(" AND target_name = ?");
            params.add(targetName);
        }
        sql.append(" ORDER BY created_at DESC");

        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement(sql.toString())) {

            for (int i = 0; i < params.size(); i++) {
                ps.setString(i + 1, params.get(i));
            }

            List<Map<String, Object>> results = new ArrayList<>();
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    Map<String, Object> row = new HashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("apk_hash", rs.getString("apk_hash"));
                    row.put("target_type", rs.getString("target_type"));
                    row.put("target_name", rs.getString("target_name"));
                    row.put("content", rs.getString("content"));
                    row.put("author", rs.getString("author"));
                    row.put("created_at", rs.getString("created_at"));
                    row.put("updated_at", rs.getString("updated_at"));
                    results.add(row);
                }
            }

            ctx.json(Map.of("annotations", results, "count", results.size()));
        } catch (SQLException e) {
            logger.error("[JAI] Failed to get annotations: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }

    /**
     * DELETE /annotations/{id}
     */
    public void handleDeleteAnnotation(Context ctx) {
        String idStr = ctx.pathParam("id");
        long id;
        try {
            id = Long.parseLong(idStr);
        } catch (NumberFormatException e) {
            ctx.status(400).json(Map.of("error", "Invalid id: " + idStr));
            return;
        }

        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement("DELETE FROM annotations WHERE id = ?")) {

            ps.setLong(1, id);
            int affected = ps.executeUpdate();

            if (affected == 0) {
                ctx.status(404).json(Map.of("error", "Annotation not found: " + id));
            } else {
                logger.info("[JAI] Deleted annotation id={}", id);
                ctx.json(Map.of("success", true, "deleted_id", id));
            }
        } catch (SQLException e) {
            logger.error("[JAI] Failed to delete annotation: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }

    // ==================== Bookmark endpoints ====================

    /**
     * POST /bookmarks
     * Body: { target_type, target_name, label, note?, author?, apk_hash? }
     */
    public void handleAddBookmark(Context ctx) {
        JsonObject body = parseJsonBody(ctx);
        if (body == null) return;

        String targetType = getBodyString(body, "target_type");
        String targetName = getBodyString(body, "target_name");
        String label = getBodyString(body, "label");

        if (targetType == null || targetType.isBlank()) {
            ctx.status(400).json(Map.of("error", "target_type is required"));
            return;
        }
        if (targetName == null || targetName.isBlank()) {
            ctx.status(400).json(Map.of("error", "target_name is required"));
            return;
        }
        if (label == null || label.isBlank()) {
            ctx.status(400).json(Map.of("error", "label is required"));
            return;
        }

        String note = getBodyStringOrDefault(body, "note", "");
        String author = getBodyStringOrDefault(body, "author", "anonymous");
        String apkHash = getBodyStringOrDefault(body, "apk_hash", getCurrentApkHash());

        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement(
                 "INSERT INTO bookmarks (apk_hash, target_type, target_name, label, note, author) VALUES (?,?,?,?,?,?)",
                 Statement.RETURN_GENERATED_KEYS)) {

            ps.setString(1, apkHash);
            ps.setString(2, targetType);
            ps.setString(3, targetName);
            ps.setString(4, label);
            ps.setString(5, note);
            ps.setString(6, author);
            ps.executeUpdate();

            long id = -1;
            try (ResultSet keys = ps.getGeneratedKeys()) {
                if (keys.next()) id = keys.getLong(1);
            }

            logger.info("[JAI] Added bookmark id={} label='{}' for {}/{}", id, label, targetType, targetName);
            ctx.status(201).json(Map.of(
                "success", true,
                "id", id,
                "label", label,
                "target_type", targetType,
                "target_name", targetName,
                "apk_hash", apkHash
            ));
        } catch (SQLException e) {
            logger.error("[JAI] Failed to add bookmark: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }

    /**
     * GET /bookmarks
     * Query params: target_type?, target_name?, apk_hash?
     */
    public void handleGetBookmarks(Context ctx) {
        String targetType = ctx.queryParam("target_type");
        String targetName = ctx.queryParam("target_name");
        String apkHash = ctx.queryParam("apk_hash");

        if (apkHash == null || apkHash.isBlank()) {
            apkHash = getCurrentApkHash();
        }

        StringBuilder sql = new StringBuilder(
            "SELECT id, apk_hash, target_type, target_name, label, note, author, created_at FROM bookmarks WHERE 1=1"
        );
        List<String> params = new ArrayList<>();

        sql.append(" AND apk_hash = ?");
        params.add(apkHash);

        if (targetType != null && !targetType.isBlank()) {
            sql.append(" AND target_type = ?");
            params.add(targetType);
        }
        if (targetName != null && !targetName.isBlank()) {
            sql.append(" AND target_name = ?");
            params.add(targetName);
        }
        sql.append(" ORDER BY created_at DESC");

        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement(sql.toString())) {

            for (int i = 0; i < params.size(); i++) {
                ps.setString(i + 1, params.get(i));
            }

            List<Map<String, Object>> results = new ArrayList<>();
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    Map<String, Object> row = new HashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("apk_hash", rs.getString("apk_hash"));
                    row.put("target_type", rs.getString("target_type"));
                    row.put("target_name", rs.getString("target_name"));
                    row.put("label", rs.getString("label"));
                    row.put("note", rs.getString("note"));
                    row.put("author", rs.getString("author"));
                    row.put("created_at", rs.getString("created_at"));
                    results.add(row);
                }
            }

            ctx.json(Map.of("bookmarks", results, "count", results.size()));
        } catch (SQLException e) {
            logger.error("[JAI] Failed to get bookmarks: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }

    /**
     * DELETE /bookmarks/{id}
     */
    public void handleDeleteBookmark(Context ctx) {
        String idStr = ctx.pathParam("id");
        long id;
        try {
            id = Long.parseLong(idStr);
        } catch (NumberFormatException e) {
            ctx.status(400).json(Map.of("error", "Invalid id: " + idStr));
            return;
        }

        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement("DELETE FROM bookmarks WHERE id = ?")) {

            ps.setLong(1, id);
            int affected = ps.executeUpdate();

            if (affected == 0) {
                ctx.status(404).json(Map.of("error", "Bookmark not found: " + id));
            } else {
                logger.info("[JAI] Deleted bookmark id={}", id);
                ctx.json(Map.of("success", true, "deleted_id", id));
            }
        } catch (SQLException e) {
            logger.error("[JAI] Failed to delete bookmark: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }

    // ==================== Tag endpoints ====================

    /**
     * POST /tags
     * Body: { target_type, target_name, tag, author?, apk_hash? }
     */
    public void handleAddTag(Context ctx) {
        JsonObject body = parseJsonBody(ctx);
        if (body == null) return;

        String targetType = getBodyString(body, "target_type");
        String targetName = getBodyString(body, "target_name");
        String tag = getBodyString(body, "tag");

        if (targetType == null || targetType.isBlank()) {
            ctx.status(400).json(Map.of("error", "target_type is required"));
            return;
        }
        if (targetName == null || targetName.isBlank()) {
            ctx.status(400).json(Map.of("error", "target_name is required"));
            return;
        }
        if (tag == null || tag.isBlank()) {
            ctx.status(400).json(Map.of("error", "tag is required"));
            return;
        }

        String author = getBodyStringOrDefault(body, "author", "anonymous");
        String apkHash = getBodyStringOrDefault(body, "apk_hash", getCurrentApkHash());

        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement(
                 "INSERT INTO tags (apk_hash, target_type, target_name, tag, author) VALUES (?,?,?,?,?)",
                 Statement.RETURN_GENERATED_KEYS)) {

            ps.setString(1, apkHash);
            ps.setString(2, targetType);
            ps.setString(3, targetName);
            ps.setString(4, tag);
            ps.setString(5, author);
            ps.executeUpdate();

            long id = -1;
            try (ResultSet keys = ps.getGeneratedKeys()) {
                if (keys.next()) id = keys.getLong(1);
            }

            logger.info("[JAI] Added tag id={} tag='{}' for {}/{}", id, tag, targetType, targetName);
            ctx.status(201).json(Map.of(
                "success", true,
                "id", id,
                "tag", tag,
                "target_type", targetType,
                "target_name", targetName,
                "apk_hash", apkHash
            ));
        } catch (SQLException e) {
            logger.error("[JAI] Failed to add tag: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }

    /**
     * GET /tags
     * Query params: target_type?, target_name?, apk_hash?
     */
    public void handleGetTags(Context ctx) {
        String targetType = ctx.queryParam("target_type");
        String targetName = ctx.queryParam("target_name");
        String apkHash = ctx.queryParam("apk_hash");

        if (apkHash == null || apkHash.isBlank()) {
            apkHash = getCurrentApkHash();
        }

        StringBuilder sql = new StringBuilder(
            "SELECT id, apk_hash, target_type, target_name, tag, author, created_at FROM tags WHERE 1=1"
        );
        List<String> params = new ArrayList<>();

        sql.append(" AND apk_hash = ?");
        params.add(apkHash);

        if (targetType != null && !targetType.isBlank()) {
            sql.append(" AND target_type = ?");
            params.add(targetType);
        }
        if (targetName != null && !targetName.isBlank()) {
            sql.append(" AND target_name = ?");
            params.add(targetName);
        }
        sql.append(" ORDER BY created_at DESC");

        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement(sql.toString())) {

            for (int i = 0; i < params.size(); i++) {
                ps.setString(i + 1, params.get(i));
            }

            List<Map<String, Object>> results = new ArrayList<>();
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    Map<String, Object> row = new HashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("apk_hash", rs.getString("apk_hash"));
                    row.put("target_type", rs.getString("target_type"));
                    row.put("target_name", rs.getString("target_name"));
                    row.put("tag", rs.getString("tag"));
                    row.put("author", rs.getString("author"));
                    row.put("created_at", rs.getString("created_at"));
                    results.add(row);
                }
            }

            ctx.json(Map.of("tags", results, "count", results.size()));
        } catch (SQLException e) {
            logger.error("[JAI] Failed to get tags: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }

    /**
     * DELETE /tags/{id}
     */
    public void handleDeleteTag(Context ctx) {
        String idStr = ctx.pathParam("id");
        long id;
        try {
            id = Long.parseLong(idStr);
        } catch (NumberFormatException e) {
            ctx.status(400).json(Map.of("error", "Invalid id: " + idStr));
            return;
        }

        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement("DELETE FROM tags WHERE id = ?")) {

            ps.setLong(1, id);
            int affected = ps.executeUpdate();

            if (affected == 0) {
                ctx.status(404).json(Map.of("error", "Tag not found: " + id));
            } else {
                logger.info("[JAI] Deleted tag id={}", id);
                ctx.json(Map.of("success", true, "deleted_id", id));
            }
        } catch (SQLException e) {
            logger.error("[JAI] Failed to delete tag: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }

    // ==================== Summary endpoint ====================

    /**
     * GET /analysis-notes
     * Query params: apk_hash?
     * Returns a summary of all annotations, bookmarks, and tags for the current APK.
     */
    public void handleGetAnalysisNotes(Context ctx) {
        String apkHash = ctx.queryParam("apk_hash");
        if (apkHash == null || apkHash.isBlank()) {
            apkHash = getCurrentApkHash();
        }

        Map<String, Object> response = new HashMap<>();
        response.put("apk_hash", apkHash);

        try (Connection conn = getConnection()) {

            // Annotations
            try (PreparedStatement ps = conn.prepareStatement(
                    "SELECT id, target_type, target_name, content, author, created_at, updated_at " +
                    "FROM annotations WHERE apk_hash = ? ORDER BY created_at DESC")) {
                ps.setString(1, apkHash);
                List<Map<String, Object>> annotations = new ArrayList<>();
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        Map<String, Object> row = new HashMap<>();
                        row.put("id", rs.getLong("id"));
                        row.put("target_type", rs.getString("target_type"));
                        row.put("target_name", rs.getString("target_name"));
                        row.put("content", rs.getString("content"));
                        row.put("author", rs.getString("author"));
                        row.put("created_at", rs.getString("created_at"));
                        row.put("updated_at", rs.getString("updated_at"));
                        annotations.add(row);
                    }
                }
                response.put("annotations", annotations);
                response.put("annotations_count", annotations.size());
            }

            // Bookmarks
            try (PreparedStatement ps = conn.prepareStatement(
                    "SELECT id, target_type, target_name, label, note, author, created_at " +
                    "FROM bookmarks WHERE apk_hash = ? ORDER BY created_at DESC")) {
                ps.setString(1, apkHash);
                List<Map<String, Object>> bookmarks = new ArrayList<>();
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        Map<String, Object> row = new HashMap<>();
                        row.put("id", rs.getLong("id"));
                        row.put("target_type", rs.getString("target_type"));
                        row.put("target_name", rs.getString("target_name"));
                        row.put("label", rs.getString("label"));
                        row.put("note", rs.getString("note"));
                        row.put("author", rs.getString("author"));
                        row.put("created_at", rs.getString("created_at"));
                        bookmarks.add(row);
                    }
                }
                response.put("bookmarks", bookmarks);
                response.put("bookmarks_count", bookmarks.size());
            }

            // Tags
            try (PreparedStatement ps = conn.prepareStatement(
                    "SELECT id, target_type, target_name, tag, author, created_at " +
                    "FROM tags WHERE apk_hash = ? ORDER BY created_at DESC")) {
                ps.setString(1, apkHash);
                List<Map<String, Object>> tags = new ArrayList<>();
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        Map<String, Object> row = new HashMap<>();
                        row.put("id", rs.getLong("id"));
                        row.put("target_type", rs.getString("target_type"));
                        row.put("target_name", rs.getString("target_name"));
                        row.put("tag", rs.getString("tag"));
                        row.put("author", rs.getString("author"));
                        row.put("created_at", rs.getString("created_at"));
                        tags.add(row);
                    }
                }
                response.put("tags", tags);
                response.put("tags_count", tags.size());
            }

            ctx.json(response);
        } catch (SQLException e) {
            logger.error("[JAI] Failed to get analysis notes: {}", e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Database error: " + e.getMessage()));
        }
    }
}
