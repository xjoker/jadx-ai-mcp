package com.zin.jadxaimcp.utils;

import io.javalin.http.Context;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Utility class for generating NOT_APPLICABLE responses.
 * 
 * Used when a tool is called on an unsupported file type (e.g., get_smali on JAR).
 * Provides helpful alternative suggestions for AI guidance.
 * 
 * @author JADX AI MCP Team
 */
public class NotApplicableResponse {

    /**
     * Alternative tool suggestion
     */
    public static class Alternative {
        private final String tool;
        private final String description;

        public Alternative(String tool, String description) {
            this.tool = tool;
            this.description = description;
        }

        public Map<String, String> toMap() {
            Map<String, String> map = new HashMap<>();
            map.put("tool", tool);
            map.put("description", description);
            return map;
        }
    }

    /**
     * Sends a NOT_APPLICABLE response to the client.
     * 
     * @param ctx The Javalin context
     * @param reason Human-readable explanation of why this feature is not available
     * @param fileType The current file type (e.g., "jar", "dex")
     * @param alternatives List of alternative tools to suggest
     */
    public static void send(Context ctx, String reason, String fileType, List<Alternative> alternatives) {
        Map<String, Object> response = new HashMap<>();
        response.put("status", "NOT_APPLICABLE");
        response.put("reason", reason);
        response.put("file_type", fileType);

        if (alternatives != null && !alternatives.isEmpty()) {
            List<Map<String, String>> altList = new ArrayList<>();
            for (Alternative alt : alternatives) {
                altList.add(alt.toMap());
            }
            response.put("alternatives", altList);
        }

        ctx.status(200); // Use 200 instead of error codes for AI-friendly response
        ctx.json(response);
    }

    /**
     * Sends a NOT_APPLICABLE response for Smali-related tools.
     */
    public static void sendSmaliNotAvailable(Context ctx, String fileType) {
        List<Alternative> alts = new ArrayList<>();
        alts.add(new Alternative("get_class_source", "Get decompiled Java source code"));
        send(ctx, 
            "Smali generation is only available for APK/DEX files. JAR files use JVM bytecode, not Dalvik bytecode.",
            fileType, 
            alts);
    }

    /**
     * Sends a NOT_APPLICABLE response for Android Manifest tools.
     */
    public static void sendManifestNotAvailable(Context ctx, String fileType) {
        List<Alternative> alts = new ArrayList<>();
        alts.add(new Alternative("get_all_classes", "Browse all classes in the package"));
        alts.add(new Alternative("search_classes_by_keyword", "Search for specific classes"));
        send(ctx,
            "AndroidManifest.xml is only available in APK/AAR files. This is a " + fileType.toUpperCase() + " file.",
            fileType,
            alts);
    }

    /**
     * Sends a NOT_APPLICABLE response for Android strings tools.
     */
    public static void sendStringsNotAvailable(Context ctx, String fileType) {
        List<Alternative> alts = new ArrayList<>();
        alts.add(new Alternative("search_classes_by_keyword", "Search for strings in code"));
        alts.add(new Alternative("get_class_source", "View class source for hardcoded strings"));
        send(ctx,
            "Android string resources (res/values/strings.xml) are only available in APK/AAR files.",
            fileType,
            alts);
    }

    /**
     * Sends a NOT_APPLICABLE response for Main Activity tools.
     */
    public static void sendMainActivityNotAvailable(Context ctx, String fileType) {
        List<Alternative> alts = new ArrayList<>();
        alts.add(new Alternative("search_classes_by_keyword", "Search for 'Main' or 'Application' classes"));
        alts.add(new Alternative("get_all_classes", "Browse package structure to find entry points"));
        send(ctx,
            "Main Activity detection requires AndroidManifest.xml, which is not available in " + fileType.toUpperCase() + " files.",
            fileType,
            alts);
    }
}
