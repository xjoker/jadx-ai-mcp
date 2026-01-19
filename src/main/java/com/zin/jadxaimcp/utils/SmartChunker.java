package com.zin.jadxaimcp.utils;

import java.util.HashMap;
import java.util.Map;

/**
 * Smart content chunker for large responses.
 * 
 * Automatically chunks large responses (>8KB) to prevent truncation by MCP clients.
 * Small responses are returned as-is for backward compatibility.
 * 
 * Usage:
 * - First call: Returns first chunk + metadata indicating more chunks available
 * - Subsequent calls with chunk=N: Returns the Nth chunk
 * 
 * @author JADX AI MCP Team
 */
public class SmartChunker {
    
    /**
     * Default chunk size in bytes.
     * 8KB is chosen as a safe threshold based on:
     * - Claude Code: ~700 char display limit
     * - Antigravity: 16KB hard limit
     * - Codex CLI: 10KB default limit
     */
    public static final int DEFAULT_CHUNK_SIZE = 8000;
    
    /**
     * Minimum size to trigger chunking.
     * Content smaller than this is returned as-is.
     */
    public static final int MIN_CHUNK_THRESHOLD = DEFAULT_CHUNK_SIZE;
    
    /**
     * Process content and return chunked response if needed.
     * 
     * @param content The full content to potentially chunk
     * @param requestedChunk Chunk number: 0=first chunk with metadata, 1-N=specific chunk
     * @param responseKey The key name for the response content (e.g., "response", "content")
     * @return Map containing response and optional _chunking metadata
     */
    public static Map<String, Object> chunkResponse(String content, int requestedChunk, String responseKey) {
        return chunkResponse(content, requestedChunk, responseKey, DEFAULT_CHUNK_SIZE);
    }
    
    /**
     * Process content and return chunked response with custom chunk size.
     * 
     * @param content The full content to potentially chunk
     * @param requestedChunk Chunk number: 0=first chunk with metadata, 1-N=specific chunk
     * @param responseKey The key name for the response content
     * @param chunkSize Custom chunk size in bytes
     * @return Map containing response and optional _chunking metadata
     */
    public static Map<String, Object> chunkResponse(String content, int requestedChunk, String responseKey, int chunkSize) {
        Map<String, Object> result = new HashMap<>();
        
        // Handle null or empty content
        if (content == null || content.isEmpty()) {
            result.put(responseKey, content != null ? content : "");
            return result;
        }
        
        int contentLength = content.length();
        
        // Small content: return as-is (no chunking)
        if (contentLength <= chunkSize) {
            result.put(responseKey, content);
            return result;
        }
        
        // Large content: apply chunking
        int totalChunks = (int) Math.ceil((double) contentLength / chunkSize);
        int chunk = requestedChunk <= 0 ? 1 : requestedChunk;
        
        // Validate chunk number
        if (chunk > totalChunks) {
            result.put("error", "Invalid chunk number. Requested: " + chunk + ", Total: " + totalChunks);
            return result;
        }
        
        // Calculate chunk boundaries
        int start = (chunk - 1) * chunkSize;
        int end = Math.min(start + chunkSize, contentLength);
        
        // Extract chunk content
        result.put(responseKey, content.substring(start, end));
        
        // Add chunking metadata
        Map<String, Object> chunking = new HashMap<>();
        chunking.put("enabled", true);
        chunking.put("total_size", contentLength);
        chunking.put("total_chunks", totalChunks);
        chunking.put("current_chunk", chunk);
        chunking.put("chunk_size", chunkSize);
        chunking.put("has_more", chunk < totalChunks);
        
        if (chunk < totalChunks) {
            chunking.put("next_chunk", chunk + 1);
        }
        
        chunking.put("warning", 
            "Response chunked due to size (" + contentLength + " bytes). " +
            "Use chunk=" + (chunk + 1) + " parameter to get next chunk. " +
            "Total chunks: " + totalChunks);
        
        result.put("_chunking", chunking);
        
        return result;
    }
    
    /**
     * Check if content would be chunked.
     * 
     * @param content The content to check
     * @return true if content exceeds chunk threshold
     */
    public static boolean wouldChunk(String content) {
        return content != null && content.length() > MIN_CHUNK_THRESHOLD;
    }
    
    /**
     * Get the number of chunks for given content.
     * 
     * @param content The content to check
     * @return Number of chunks (1 if no chunking needed)
     */
    public static int getChunkCount(String content) {
        if (content == null || content.length() <= DEFAULT_CHUNK_SIZE) {
            return 1;
        }
        return (int) Math.ceil((double) content.length() / DEFAULT_CHUNK_SIZE);
    }
}
