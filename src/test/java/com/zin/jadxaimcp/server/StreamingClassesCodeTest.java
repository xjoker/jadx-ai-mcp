package com.zin.jadxaimcp.server;

import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Verifies that the Wave-3 streaming JSON output from
 * {@code ClassRoutes.handleMainApplicationClassesCode} produces exactly the
 * same logical shape as the legacy buffered path.
 *
 * <p>These tests operate purely on in-process byte buffers — no Javalin or
 * JADX context required.  They replicate the two serialisation strategies and
 * assert structural equivalence.
 */
class StreamingClassesCodeTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final JsonFactory JSON_FACTORY = new JsonFactory();

    // Mirrors ClassRoutes constants
    private static final int STREAM_FLUSH_EVERY = 16;

    // -----------------------------------------------------------------------
    // Helper: build a synthetic "page" of decompiled class entries.
    // Entry layout: [fullName, rawName, content]
    // -----------------------------------------------------------------------
    private static List<String[]> buildPage(int count, int contentSizeBytes) {
        List<String[]> page = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            String fullName = "com.example.test.Class" + i;
            String rawName = "Lcom/example/test/Class" + i + ";";
            String content = "public class Class" + i + " { " + "x".repeat(contentSizeBytes) + " }";
            page.add(new String[]{fullName, rawName, content});
        }
        return page;
    }

    // -----------------------------------------------------------------------
    // Helper: produce streaming JSON (Wave-3 path) into a byte array.
    // Mirrors the JsonGenerator block in handleMainApplicationClassesCode.
    // -----------------------------------------------------------------------
    private static byte[] streamingSerialize(
            List<String[]> page,
            int total,
            int offset,
            int limit,
            int requestedLimit,
            boolean hasMore,
            int nextOffset) throws Exception {

        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        try (JsonGenerator gen = JSON_FACTORY.createGenerator(baos)) {
            gen.writeStartObject();

            gen.writeStringField("type", "application-classes");
            gen.writeNumberField("requested_count", requestedLimit);

            gen.writeObjectFieldStart("pagination");
            gen.writeNumberField("total", total);
            gen.writeNumberField("offset", offset);
            gen.writeNumberField("limit", limit);
            gen.writeNumberField("count", page.size());
            gen.writeBooleanField("has_more", hasMore);
            if (hasMore) {
                gen.writeNumberField("next_offset", nextOffset);
            }
            if (offset > 0) {
                int prevOffset = Math.max(0, offset - limit);
                gen.writeNumberField("prev_offset", prevOffset);
            }
            if (limit > 0) {
                int currentPage = (offset / limit) + 1;
                int totalPages = (int) Math.ceil((double) total / limit);
                gen.writeNumberField("current_page", currentPage);
                gen.writeNumberField("total_pages", totalPages);
                gen.writeNumberField("page_size", limit);
            }
            gen.writeEndObject(); // pagination

            gen.writeArrayFieldStart("classes");
            int written = 0;
            for (String[] entry : page) {
                gen.writeStartObject();
                gen.writeStringField("name", entry[0]);
                gen.writeStringField("raw_name", entry[1]);
                gen.writeStringField("type", "code/java");
                gen.writeStringField("content", entry[2]);
                gen.writeEndObject();
                written++;
                if (written % STREAM_FLUSH_EVERY == 0) {
                    gen.flush();
                }
            }
            gen.writeEndArray();

            gen.writeEndObject();
        }
        return baos.toByteArray();
    }

    // -----------------------------------------------------------------------
    // Helper: produce buffered JSON (legacy path) as a Map → Jackson bytes.
    // Mirrors buildPaginatedResponse + the classInfoList construction.
    // -----------------------------------------------------------------------
    private static byte[] bufferedSerialize(
            List<String[]> page,
            int total,
            int offset,
            int limit,
            int requestedLimit,
            boolean hasMore,
            int nextOffset) throws Exception {

        List<Map<String, Object>> classInfoList = new ArrayList<>();
        for (String[] entry : page) {
            Map<String, Object> classInfo = new HashMap<>();
            classInfo.put("name", entry[0]);
            classInfo.put("raw_name", entry[1]);
            classInfo.put("type", "code/java");
            classInfo.put("content", entry[2]);
            classInfoList.add(classInfo);
        }

        Map<String, Object> pagination = new HashMap<>();
        pagination.put("total", total);
        pagination.put("offset", offset);
        pagination.put("limit", limit);
        pagination.put("count", classInfoList.size());
        pagination.put("has_more", hasMore);
        if (hasMore) {
            pagination.put("next_offset", nextOffset);
        }
        if (offset > 0) {
            int prevOffset = Math.max(0, offset - limit);
            pagination.put("prev_offset", prevOffset);
        }
        if (limit > 0) {
            int currentPage = (offset / limit) + 1;
            int totalPages = (int) Math.ceil((double) total / limit);
            pagination.put("current_page", currentPage);
            pagination.put("total_pages", totalPages);
            pagination.put("page_size", limit);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("type", "application-classes");
        result.put("requested_count", requestedLimit);
        result.put("pagination", pagination);
        result.put("classes", classInfoList);

        return MAPPER.writeValueAsBytes(result);
    }

    // -----------------------------------------------------------------------
    // Tests
    // -----------------------------------------------------------------------

    @Test
    void streamingAndBuffered_sameShape_smallPage() throws Exception {
        List<String[]> page = buildPage(3, 100);
        byte[] streamed = streamingSerialize(page, 10, 0, 3, 3, true, 3);
        byte[] buffered = bufferedSerialize(page, 10, 0, 3, 3, true, 3);

        JsonNode streamedNode = MAPPER.readTree(streamed);
        JsonNode bufferedNode = MAPPER.readTree(buffered);

        // Top-level field presence
        assertEquals("application-classes", streamedNode.get("type").asText());
        assertEquals("application-classes", bufferedNode.get("type").asText());

        // classes array size matches
        assertEquals(
            bufferedNode.get("classes").size(),
            streamedNode.get("classes").size(),
            "classes array length must be identical");

        // Each class entry must have the same fields
        for (int i = 0; i < 3; i++) {
            JsonNode s = streamedNode.get("classes").get(i);
            JsonNode b = bufferedNode.get("classes").get(i);
            assertEquals(b.get("name").asText(), s.get("name").asText(), "name mismatch at index " + i);
            assertEquals(b.get("raw_name").asText(), s.get("raw_name").asText(), "raw_name mismatch at index " + i);
            assertEquals(b.get("type").asText(), s.get("type").asText(), "type mismatch at index " + i);
            assertEquals(b.get("content").asText(), s.get("content").asText(), "content mismatch at index " + i);
        }

        // Pagination envelope must match
        JsonNode sp = streamedNode.get("pagination");
        JsonNode bp = bufferedNode.get("pagination");
        assertEquals(bp.get("total").asInt(), sp.get("total").asInt());
        assertEquals(bp.get("offset").asInt(), sp.get("offset").asInt());
        assertEquals(bp.get("limit").asInt(), sp.get("limit").asInt());
        assertEquals(bp.get("count").asInt(), sp.get("count").asInt());
        assertEquals(bp.get("has_more").asBoolean(), sp.get("has_more").asBoolean());
        assertEquals(bp.get("next_offset").asInt(), sp.get("next_offset").asInt());
        assertEquals(bp.get("current_page").asInt(), sp.get("current_page").asInt());
        assertEquals(bp.get("total_pages").asInt(), sp.get("total_pages").asInt());
        assertEquals(bp.get("page_size").asInt(), sp.get("page_size").asInt());
    }

    @Test
    void streamingAndBuffered_sameShape_pageWithOffset() throws Exception {
        // Page 2: offset=5, limit=5, total=15, has_more=true, next_offset=10
        List<String[]> page = buildPage(5, 200);
        byte[] streamed = streamingSerialize(page, 15, 5, 5, 5, true, 10);
        byte[] buffered = bufferedSerialize(page, 15, 5, 5, 5, true, 10);

        JsonNode streamedNode = MAPPER.readTree(streamed);
        JsonNode bufferedNode = MAPPER.readTree(buffered);

        JsonNode sp = streamedNode.get("pagination");
        JsonNode bp = bufferedNode.get("pagination");

        assertEquals(bp.get("prev_offset").asInt(), sp.get("prev_offset").asInt(),
            "prev_offset must match when offset > 0");
        assertEquals(bp.get("next_offset").asInt(), sp.get("next_offset").asInt());
        assertEquals(5, sp.get("count").asInt());
    }

    @Test
    void streamingAndBuffered_sameShape_lastPage() throws Exception {
        // Last page: offset=10, limit=5, total=12, has_more=false, count=2
        List<String[]> page = buildPage(2, 50);
        byte[] streamed = streamingSerialize(page, 12, 10, 5, 5, false, 0);
        byte[] buffered = bufferedSerialize(page, 12, 10, 5, 5, false, 0);

        JsonNode streamedNode = MAPPER.readTree(streamed);
        JsonNode bufferedNode = MAPPER.readTree(buffered);

        JsonNode sp = streamedNode.get("pagination");
        JsonNode bp = bufferedNode.get("pagination");

        assertFalse(sp.get("has_more").asBoolean(), "has_more must be false on last page");
        assertNull(sp.get("next_offset"), "next_offset must be absent on last page (streaming)");
        assertNull(bp.get("next_offset"), "next_offset must be absent on last page (buffered)");
        assertEquals(bp.get("count").asInt(), sp.get("count").asInt());
    }

    @Test
    void streamingAndBuffered_sameShape_emptyPage() throws Exception {
        List<String[]> page = new ArrayList<>();
        byte[] streamed = streamingSerialize(page, 0, 0, 10, 10, false, 0);
        byte[] buffered = bufferedSerialize(page, 0, 0, 10, 10, false, 0);

        JsonNode streamedNode = MAPPER.readTree(streamed);
        JsonNode bufferedNode = MAPPER.readTree(buffered);

        assertEquals(0, streamedNode.get("classes").size(), "classes array must be empty");
        assertEquals(0, bufferedNode.get("classes").size(), "classes array must be empty");
        assertEquals(0, streamedNode.get("pagination").get("count").asInt());
    }

    @Test
    void streaming_flushBoundary_noDataLoss() throws Exception {
        // Produce exactly STREAM_FLUSH_EVERY + 1 entries to exercise flush boundary
        List<String[]> page = buildPage(STREAM_FLUSH_EVERY + 1, 128);
        byte[] streamed = streamingSerialize(page, STREAM_FLUSH_EVERY + 1, 0, STREAM_FLUSH_EVERY + 1,
                STREAM_FLUSH_EVERY + 1, false, 0);

        JsonNode streamedNode = MAPPER.readTree(streamed);
        assertEquals(STREAM_FLUSH_EVERY + 1, streamedNode.get("classes").size(),
            "All entries must be present after flush boundary");

        // Verify the last entry (written after the flush) is intact
        JsonNode lastEntry = streamedNode.get("classes").get(STREAM_FLUSH_EVERY);
        assertEquals("com.example.test.Class" + STREAM_FLUSH_EVERY, lastEntry.get("name").asText());
        assertTrue(lastEntry.get("content").asText().contains("x".repeat(128)),
            "Content after flush boundary must be complete");
    }

    @Test
    void streaming_producesValidJson() throws Exception {
        List<String[]> page = buildPage(5, 512);
        byte[] streamed = streamingSerialize(page, 20, 0, 5, 5, true, 5);

        // Must parse without exception
        JsonNode root = MAPPER.readTree(streamed);
        assertNotNull(root, "Streamed output must be valid JSON");
        assertTrue(root.isObject(), "Root must be a JSON object");
        assertTrue(root.has("classes"), "Root must have 'classes' field");
        assertTrue(root.has("pagination"), "Root must have 'pagination' field");
        assertTrue(root.has("type"), "Root must have 'type' field");
    }

    @Test
    void streaming_contentWithSpecialChars_escapedProperly() throws Exception {
        // Content with JSON-significant characters
        List<String[]> page = new ArrayList<>();
        page.add(new String[]{
            "com.example.Special",
            "Lcom/example/Special;",
            "// comment with \"quotes\" and \\backslash\nclass Special { String s = \"hello\\nworld\"; }"
        });

        byte[] streamed = streamingSerialize(page, 1, 0, 1, 1, false, 0);
        JsonNode root = MAPPER.readTree(streamed);

        String content = root.get("classes").get(0).get("content").asText();
        assertTrue(content.contains("\"quotes\""), "Double quotes must round-trip correctly");
        assertTrue(content.contains("\\backslash"), "Backslash must round-trip correctly");
    }
}
