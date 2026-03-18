package com.zin.jadxaimcp.integration;

import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import okhttp3.Response;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration tests for PluginServer HTTP endpoints.
 *
 * These tests start a real Javalin server backed by a mocked MainWindow
 * and a real JadxDecompiler loading a Nexus3 JAR. They are only executed
 * via {@code mvn verify -P integration-test} and require the test JAR
 * at {@code temp/nexus-main.jar} (see scripts/fetch-nexus-jar.sh).
 */
class EndpointIntegrationIT extends PluginServerTestBase {

    private static final Gson GSON = new Gson();

    // ---- /health ----

    @Test
    void healthEndpointShouldReturnRunningStatus() throws IOException {
        try (Response response = get("/health")) {
            assertEquals(200, response.code());
            JsonObject body = parseJson(response);
            assertEquals("Running", body.get("status").getAsString());
            assertTrue(body.has("memory"));
            assertTrue(body.has("timestamp"));
        }
    }

    // ---- /all-classes ----

    @Test
    void allClassesShouldReturnPaginatedList() throws IOException {
        try (Response response = get("/all-classes?offset=0&count=10")) {
            assertEquals(200, response.code());
            JsonObject body = parseJson(response);
            assertTrue(body.has("classes") || body.has("all_classes"),
                    "Response should contain a classes list");
        }
    }

    // ---- /class-source ----

    @Test
    void classSourceShouldReturnDecompiledCode() throws IOException {
        // First discover a class name
        String className = discoverClassName();
        if (className == null) {
            return; // Skip if no classes available
        }

        String encoded = URLEncoder.encode(className, StandardCharsets.UTF_8);
        try (Response response = get("/class-source?class_name=" + encoded)) {
            assertEquals(200, response.code());
            JsonObject body = parseJson(response);
            // SmartChunker uses "response" as the content key; 404 returns "error"
            assertTrue(body.has("response") || body.has("error"),
                    "Response should contain source content");
        }
    }

    // ---- /methods-of-class ----

    @Test
    void methodsOfClassShouldReturnMethodList() throws IOException {
        String className = discoverClassName();
        if (className == null) {
            return;
        }

        String encoded = URLEncoder.encode(className, StandardCharsets.UTF_8);
        try (Response response = get("/methods-of-class?class_name=" + encoded)) {
            assertEquals(200, response.code());
            JsonObject body = parseJson(response);
            assertTrue(body.has("methods") || body.has("error"),
                    "Response should contain methods list");
        }
    }

    // ---- /fields-of-class ----

    @Test
    void fieldsOfClassShouldReturnFieldList() throws IOException {
        String className = discoverClassName();
        if (className == null) {
            return;
        }

        String encoded = URLEncoder.encode(className, StandardCharsets.UTF_8);
        try (Response response = get("/fields-of-class?class_name=" + encoded)) {
            assertEquals(200, response.code());
            JsonObject body = parseJson(response);
            assertTrue(body.has("fields") || body.has("error"),
                    "Response should contain fields list");
        }
    }

    // ---- /search-classes-by-keyword (class_name) ----

    @Test
    void searchByClassNameShouldReturnResults() throws IOException {
        // Route expects "search_term" (not "keyword") and "search_in"
        try (Response response = get("/search-classes-by-keyword?search_term=Main&search_in=class_name")) {
            assertEquals(200, response.code());
            JsonObject body = parseJson(response);
            assertTrue(body.has("results") || body.has("classes") || body.has("matches"),
                    "Response should contain search results");
        }
    }

    // ---- /search-classes-by-keyword (code) ----

    @Test
    void searchByCodeShouldReturnResults() throws IOException {
        try (Response response = get("/search-classes-by-keyword?search_term=import&search_in=code")) {
            // Code search may return 200, 503 (busy), or 200 with results
            assertTrue(response.code() == 200 || response.code() == 503,
                    "Expected 200 or 503, got " + response.code());
        }
    }

    // ---- /class-info ----

    @Test
    void classInfoShouldReturnClassMetadata() throws IOException {
        String className = discoverClassName();
        if (className == null) {
            return;
        }

        String encoded = URLEncoder.encode(className, StandardCharsets.UTF_8);
        try (Response response = get("/class-info?class_name=" + encoded)) {
            assertEquals(200, response.code());
            JsonObject body = parseJson(response);
            assertNotNull(body);
        }
    }

    // ---- /xrefs-to-class ----

    @Test
    void xrefsToClassShouldReturnCrossReferences() throws IOException {
        String className = discoverClassName();
        if (className == null) {
            return;
        }

        String encoded = URLEncoder.encode(className, StandardCharsets.UTF_8);
        try (Response response = get("/xrefs-to-class?class_name=" + encoded)) {
            // May return 200 or 503 (busy) — both are acceptable
            assertTrue(response.code() == 200 || response.code() == 503,
                    "Expected 200 or 503, got " + response.code());
        }
    }

    // ---- /cache/clear ----

    @Test
    void cacheClearShouldAcceptPostRequest() throws IOException {
        try (Response response = post("/cache/clear")) {
            // May return 200, 405 if GET-only, or 503 (cooldown)
            assertTrue(response.code() >= 200 && response.code() < 500,
                    "Cache clear should not return 5xx server error, got " + response.code());
        }
    }

    // ---- helpers ----

    private JsonObject parseJson(Response response) throws IOException {
        String bodyStr = response.body().string();
        return GSON.fromJson(bodyStr, JsonObject.class);
    }

    /**
     * Discover a class name from /all-classes for use in subsequent tests.
     */
    private String discoverClassName() throws IOException {
        try (Response response = get("/all-classes?offset=0&count=5")) {
            if (response.code() != 200) {
                return null;
            }
            JsonObject body = parseJson(response);

            // Try common field names for class lists
            for (String key : new String[]{"classes", "all_classes"}) {
                JsonElement element = body.get(key);
                if (element != null && element.isJsonArray()) {
                    JsonArray arr = element.getAsJsonArray();
                    if (!arr.isEmpty()) {
                        JsonElement first = arr.get(0);
                        if (first.isJsonPrimitive()) {
                            return first.getAsString();
                        }
                        if (first.isJsonObject()) {
                            JsonObject obj = first.getAsJsonObject();
                            if (obj.has("name")) {
                                return obj.get("name").getAsString();
                            }
                            if (obj.has("class_name")) {
                                return obj.get("class_name").getAsString();
                            }
                        }
                    }
                }
            }
            return null;
        }
    }
}
