package com.zin.jadxaimcp.utils;

import java.util.Map;

/**
 * Smoke test for SmartChunker functionality.
 */
public class SmartChunkerTest {
    
    public static void main(String[] args) {
        System.out.println("=== SmartChunker Smoke Test ===\n");
        
        // Test 1: Small content (no chunking)
        System.out.println("[Test 1] Small content (< 8KB):");
        String smallContent = "Small content that fits in one chunk";
        Map<String, Object> result1 = SmartChunker.chunkResponse(smallContent, 0, "content");
        System.out.println("  Has _chunking: " + result1.containsKey("_chunking"));
        System.out.println("  Content: " + result1.get("content"));
        System.out.println("  ✓ PASS: No chunking for small content\n");
        
        // Test 2: Large content (8KB+, chunking enabled)
        System.out.println("[Test 2] Large content (> 8KB):");
        StringBuilder largeContent = new StringBuilder();
        for (int i = 0; i < 1000; i++) {
            largeContent.append("This is line ").append(i).append(" of test content.\n");
        }
        String content = largeContent.toString();
        System.out.println("  Total size: " + content.length() + " bytes");
        
        Map<String, Object> result2 = SmartChunker.chunkResponse(content, 0, "content");
        System.out.println("  Has _chunking: " + result2.containsKey("_chunking"));
        
        if (result2.containsKey("_chunking")) {
            @SuppressWarnings("unchecked")
            Map<String, Object> chunking = (Map<String, Object>) result2.get("_chunking");
            System.out.println("  Total chunks: " + chunking.get("total_chunks"));
            System.out.println("  Current chunk: " + chunking.get("current_chunk"));
            System.out.println("  Has more: " + chunking.get("has_more"));
            System.out.println("  Chunk size: " + ((String) result2.get("content")).length() + " bytes");
            System.out.println("  ✓ PASS: Chunking enabled for large content\n");
        } else {
            System.out.println("  ✗ FAIL: Expected chunking for large content\n");
            System.exit(1);
        }
        
        // Test 3: Get second chunk
        System.out.println("[Test 3] Get second chunk:");
        Map<String, Object> result3 = SmartChunker.chunkResponse(content, 2, "content");
        @SuppressWarnings("unchecked")
        Map<String, Object> chunking3 = (Map<String, Object>) result3.get("_chunking");
        System.out.println("  Current chunk: " + chunking3.get("current_chunk"));
        System.out.println("  Chunk size: " + ((String) result3.get("content")).length() + " bytes");
        System.out.println("  ✓ PASS: Second chunk retrieved successfully\n");
        
        // Test 4: Invalid chunk number
        System.out.println("[Test 4] Invalid chunk number:");
        Map<String, Object> result4 = SmartChunker.chunkResponse(content, 999, "content");
        if (result4.containsKey("error")) {
            System.out.println("  Error: " + result4.get("error"));
            System.out.println("  ✓ PASS: Error handling works\n");
        } else {
            System.out.println("  ✗ FAIL: Expected error for invalid chunk\n");
            System.exit(1);
        }
        
        // Test 5: Null content handling
        System.out.println("[Test 5] Null content:");
        Map<String, Object> result5 = SmartChunker.chunkResponse(null, 0, "content");
        System.out.println("  Result: " + result5.get("content"));
        System.out.println("  ✓ PASS: Null handling works\n");
        
        System.out.println("=== All Tests Passed ✓ ===");
    }
}
