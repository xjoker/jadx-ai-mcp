package com.zin.jadxaimcp.utils;

import java.util.Map;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for SmartChunker functionality.
 */
class SmartChunkerTest {

    @Test
    void smallContentShouldNotBeChunked() {
        String smallContent = "Small content that fits in one chunk";
        Map<String, Object> result = SmartChunker.chunkResponse(smallContent, 0, "content");

        assertFalse(result.containsKey("_chunking"));
        assertEquals(smallContent, result.get("content"));
    }

    @Test
    void largeContentShouldBeChunked() {
        String content = buildLargeContent();
        Map<String, Object> result = SmartChunker.chunkResponse(content, 0, "content");

        assertTrue(result.containsKey("_chunking"), "Large content should trigger chunking");
        @SuppressWarnings("unchecked")
        Map<String, Object> chunking = (Map<String, Object>) result.get("_chunking");
        assertNotNull(chunking.get("total_chunks"));
        assertEquals(1, chunking.get("current_chunk")); // SmartChunker uses 1-based chunk numbers
        assertTrue((boolean) chunking.get("has_more"));
        assertTrue(((String) result.get("content")).length() < content.length());
    }

    @Test
    void secondChunkShouldBeRetrievable() {
        String content = buildLargeContent();
        Map<String, Object> result = SmartChunker.chunkResponse(content, 2, "content");

        assertTrue(result.containsKey("_chunking"));
        @SuppressWarnings("unchecked")
        Map<String, Object> chunking = (Map<String, Object>) result.get("_chunking");
        assertEquals(2, chunking.get("current_chunk"));
    }

    @Test
    void invalidChunkNumberShouldReturnError() {
        String content = buildLargeContent();
        Map<String, Object> result = SmartChunker.chunkResponse(content, 999, "content");

        assertTrue(result.containsKey("error"), "Invalid chunk number should return error");
    }

    @Test
    void nullContentShouldBeHandled() {
        Map<String, Object> result = SmartChunker.chunkResponse(null, 0, "content");

        assertNotNull(result);
        // Should not throw
    }

    private static String buildLargeContent() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 1000; i++) {
            sb.append("This is line ").append(i).append(" of test content.\n");
        }
        return sb.toString();
    }
}
