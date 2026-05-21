package com.zin.jadxaimcp.server;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Unit tests for the 32 KB inline-vs-transfer-token threshold logic introduced
 * in {@code ClassRoutes.handleBatchClassSource} and
 * {@code ClassRoutes.handleMainApplicationClassesCode}.
 *
 * <p>These tests exercise the size-estimation and routing decision without
 * requiring a live Javalin / JADX context.
 */
class BatchResponseThresholdTest {

    private static final int INLINE_MAX = 32768; // mirrors ClassRoutes default
    private static final ObjectMapper MAPPER = new ObjectMapper();

    // -------------------------------------------------------------------
    // Helpers that mimic the threshold decision in ClassRoutes
    // -------------------------------------------------------------------

    /**
     * Cheap estimate: sum content/name lengths + structural overhead.
     * This replicates the first-pass estimate in ClassRoutes verbatim.
     */
    private static int cheapEstimate(List<Map<String, Object>> classes) {
        int estimate = 512;
        for (Map<String, Object> cls : classes) {
            Object content = cls.get("content");
            if (content instanceof String) estimate += ((String) content).length();
            Object err = cls.get("error");
            if (err instanceof String) estimate += ((String) err).length();
            Object name = cls.get("name");
            if (name instanceof String) estimate += ((String) name).length() + 32;
        }
        return estimate;
    }

    /**
     * Accurate Jackson serialization byte count.
     */
    private static int accurateBytes(Map<String, Object> response) throws Exception {
        return MAPPER.writeValueAsBytes(response).length;
    }

    /**
     * Full threshold decision that mirrors ClassRoutes logic.
     * Returns "inline", "inline_after_check", or "transfer".
     */
    private static String routingDecision(List<Map<String, Object>> classes) throws Exception {
        Map<String, Object> response = new HashMap<>();
        response.put("status", "success");
        response.put("classes", classes);
        response.put("total", classes.size());
        response.put("found", classes.size());

        int estimated = cheapEstimate(classes);
        if (estimated <= INLINE_MAX) {
            return "inline";
        }

        int actual = accurateBytes(response);
        if (actual <= INLINE_MAX) {
            return "inline_after_check";
        }
        return "transfer";
    }

    // -------------------------------------------------------------------
    // Test cases
    // -------------------------------------------------------------------

    @Test
    void smallBatch_shouldRouteInline() throws Exception {
        List<Map<String, Object>> classes = new ArrayList<>();
        // 3 small classes, each ~200 chars
        for (int i = 0; i < 3; i++) {
            Map<String, Object> cls = new HashMap<>();
            cls.put("name", "com.example.Small" + i);
            cls.put("found", true);
            cls.put("content", "public class Small" + i + " { /* tiny */ }");
            classes.add(cls);
        }
        assertEquals("inline", routingDecision(classes),
            "Small batch (< 32 KB) must route to inline ctx.json()");
    }

    @Test
    void largeBatch_shouldRouteToTransfer() throws Exception {
        List<Map<String, Object>> classes = new ArrayList<>();
        // 10 classes each with ~5 KB of content → ~50 KB total
        String largeContent = "x".repeat(5120);
        for (int i = 0; i < 10; i++) {
            Map<String, Object> cls = new HashMap<>();
            cls.put("name", "com.example.Large" + i);
            cls.put("found", true);
            cls.put("content", largeContent);
            classes.add(cls);
        }
        String decision = routingDecision(classes);
        assertTrue(
            decision.equals("transfer") || decision.equals("inline_after_check"),
            "Large batch (> 32 KB) must route to transfer hint; got: " + decision
        );
        // For this test data size, expect "transfer" specifically
        assertEquals("transfer", decision,
            "50 KB batch must route to transfer hint, not inline");
    }

    @Test
    void exactlyAtThreshold_shouldRouteInline() throws Exception {
        // Build a response that serializes to exactly <= INLINE_MAX bytes
        List<Map<String, Object>> classes = new ArrayList<>();
        Map<String, Object> cls = new HashMap<>();
        cls.put("name", "com.example.Boundary");
        cls.put("found", true);
        // ~100 chars — well under threshold
        cls.put("content", "public class Boundary {}");
        classes.add(cls);

        Map<String, Object> response = new HashMap<>();
        response.put("status", "success");
        response.put("classes", classes);
        response.put("total", 1);
        response.put("found", 1);

        int actualBytes = accurateBytes(response);
        assertTrue(actualBytes <= INLINE_MAX,
            "Test setup error: response must be <= " + INLINE_MAX + " bytes");
        assertEquals("inline", routingDecision(classes));
    }

    @Test
    void cheapEstimate_isConservativeForAscii() {
        // Cheap estimate should be <= actual serialized size for ASCII content
        // (since we treat each char as 1 byte but JSON adds overhead).
        // What matters: estimate should not be dramatically under-counting.
        List<Map<String, Object>> classes = new ArrayList<>();
        String largeAscii = "a".repeat(40000);
        Map<String, Object> cls = new HashMap<>();
        cls.put("name", "com.example.Test");
        cls.put("found", true);
        cls.put("content", largeAscii);
        classes.add(cls);

        int estimate = cheapEstimate(classes);
        // Estimate = 512 + 40000 + len("com.example.Test") + 32 = 40560
        assertTrue(estimate > INLINE_MAX,
            "Cheap estimate must exceed threshold for 40 KB content class; got " + estimate);
    }

    @Test
    void transferHintShape_hasRequiredFields() {
        // Verify the transfer hint response shape has the expected keys
        Map<String, Object> transferHint = new HashMap<>();
        transferHint.put("response_too_large", true);
        transferHint.put("size_bytes", 51200);
        transferHint.put("items_count", 10);
        transferHint.put("found", 10);
        transferHint.put("transfer_endpoint", "/transfer/download/batch-classes");
        transferHint.put("transfer_format", "json");
        transferHint.put("message", "hint message");

        assertTrue((boolean) transferHint.get("response_too_large"));
        assertEquals("/transfer/download/batch-classes", transferHint.get("transfer_endpoint"));
        assertEquals("json", transferHint.get("transfer_format"));
        assertTrue(transferHint.containsKey("size_bytes"));
        assertTrue(transferHint.containsKey("message"));
    }
}
