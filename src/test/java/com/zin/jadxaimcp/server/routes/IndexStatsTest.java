package com.zin.jadxaimcp.server.routes;

import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.CodeContentIndex;
import com.zin.jadxaimcp.utils.JadxApiAdapter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for the /index-stats endpoint logic.
 *
 * <p>Verifies that each helper method called by {@link GeneralRoutes#handleIndexStats}
 * returns a map with the expected keys and value types in both the empty (not-yet-warmed)
 * state and after manual state injection via reflection.</p>
 *
 * <p>These tests do NOT spin up a Javalin server — they test the data-layer methods
 * ({@link ClassCacheManager#getNameIndexStats()}, {@link CodeContentIndex#getStats()},
 * {@link JadxApiAdapter#getSnapshotCacheStats()}) directly.</p>
 */
class IndexStatsTest {

    // -------------------------------------------------------------------------
    // Reset state before each test
    // -------------------------------------------------------------------------

    @BeforeEach
    void resetCodeContentIndex() {
        // Use the public clear() API to get a fresh empty state
        CodeContentIndex.clear();
    }

    @BeforeEach
    void resetClassCacheManager() throws Exception {
        // Clear the three name-index AtomicReferences so we get null (not-ready) state
        for (String name : new String[]{"classNameIndex", "methodNameIndex", "fieldNameIndex",
                "rawNameCache", "classCache"}) {
            Field f = ClassCacheManager.class.getDeclaredField(name);
            f.setAccessible(true);
            @SuppressWarnings("unchecked")
            java.util.concurrent.atomic.AtomicReference<Object> ref =
                    (java.util.concurrent.atomic.AtomicReference<Object>) f.get(null);
            ref.set(null);
        }
    }

    // =========================================================================
    // ClassCacheManager.getNameIndexStats()
    // =========================================================================

    @Test
    void nameIndexStats_keysPresent_whenNotInitialised() {
        Map<String, Object> stats = ClassCacheManager.getNameIndexStats();

        assertNotNull(stats, "getNameIndexStats() must never return null");
        assertTrue(stats.containsKey("class_name_buckets"), "missing class_name_buckets");
        assertTrue(stats.containsKey("method_name_buckets"), "missing method_name_buckets");
        assertTrue(stats.containsKey("field_name_buckets"), "missing field_name_buckets");
        assertTrue(stats.containsKey("raw_name_map_size"), "missing raw_name_map_size");
        assertTrue(stats.containsKey("index_ready"), "missing index_ready");
    }

    @Test
    void nameIndexStats_zeros_whenNotInitialised() {
        Map<String, Object> stats = ClassCacheManager.getNameIndexStats();

        assertEquals(0, stats.get("class_name_buckets"), "should be 0 when index is null");
        assertEquals(0, stats.get("method_name_buckets"), "should be 0 when index is null");
        assertEquals(0, stats.get("field_name_buckets"), "should be 0 when index is null");
        assertEquals(0, stats.get("raw_name_map_size"), "should be 0 when raw map is null");
        assertEquals(false, stats.get("index_ready"), "index_ready must be false when indices are null");
    }

    @Test
    void nameIndexStats_indexReady_whenAllIndicesPopulated() throws Exception {
        java.util.Map<String, java.util.List<jadx.api.JavaClass>> emptyMap = new java.util.HashMap<>();

        for (String fieldName : new String[]{"classNameIndex", "methodNameIndex", "fieldNameIndex"}) {
            Field f = ClassCacheManager.class.getDeclaredField(fieldName);
            f.setAccessible(true);
            @SuppressWarnings("unchecked")
            java.util.concurrent.atomic.AtomicReference<java.util.Map<String, java.util.List<jadx.api.JavaClass>>> ref =
                    (java.util.concurrent.atomic.AtomicReference<java.util.Map<String, java.util.List<jadx.api.JavaClass>>>) f.get(null);
            ref.set(emptyMap);
        }

        Map<String, Object> stats = ClassCacheManager.getNameIndexStats();
        assertEquals(true, stats.get("index_ready"),
                "index_ready must be true when all three indices are non-null");
    }

    // =========================================================================
    // CodeContentIndex.getStats()
    // =========================================================================

    @Test
    void codeIndexStats_keysPresent_emptyState() {
        Map<String, Object> stats = CodeContentIndex.getStats();

        assertNotNull(stats);
        assertTrue(stats.containsKey("enabled"), "missing enabled");
        assertTrue(stats.containsKey("indexed_classes"), "missing indexed_classes");
        assertTrue(stats.containsKey("trigram_count"), "missing trigram_count");
        assertTrue(stats.containsKey("max_trigrams"), "missing max_trigrams");
        assertTrue(stats.containsKey("max_class_size_bytes"), "missing max_class_size_bytes");
        assertTrue(stats.containsKey("estimated_memory_mb"), "missing estimated_memory_mb");
        assertTrue(stats.containsKey("saturation_percent"), "missing saturation_percent");
    }

    @Test
    void codeIndexStats_zerosAndEnabled_emptyState() {
        Map<String, Object> stats = CodeContentIndex.getStats();

        assertEquals(0, stats.get("indexed_classes"), "no classes indexed yet");
        assertEquals(0, stats.get("trigram_count"), "no trigrams yet");
        assertEquals(0, stats.get("estimated_memory_mb"), "no memory used yet");
        assertEquals(0.0, (double) stats.get("saturation_percent"), 0.001, "saturation must be 0.0");
        // enabled value should be Boolean
        assertInstanceOf(Boolean.class, stats.get("enabled"));
        // max values should be positive
        assertTrue((int) stats.get("max_trigrams") > 0, "max_trigrams must be > 0");
        assertTrue((int) stats.get("max_class_size_bytes") > 0, "max_class_size_bytes must be > 0");
    }

    // =========================================================================
    // JadxApiAdapter.getSnapshotCacheStats()
    // =========================================================================

    @Test
    void snapshotCacheStats_keysPresent() {
        Map<String, Object> stats = JadxApiAdapter.getSnapshotCacheStats();

        assertNotNull(stats);
        assertTrue(stats.containsKey("method_snapshot_classes"), "missing method_snapshot_classes");
        assertTrue(stats.containsKey("field_snapshot_classes"), "missing field_snapshot_classes");
    }

    @Test
    void snapshotCacheStats_zeros_afterClear() {
        JadxApiAdapter.clearAllSnapshotCaches();
        Map<String, Object> stats = JadxApiAdapter.getSnapshotCacheStats();

        assertEquals(0, stats.get("method_snapshot_classes"),
                "method snapshot cache should be empty after clear");
        assertEquals(0, stats.get("field_snapshot_classes"),
                "field snapshot cache should be empty after clear");
    }

    // =========================================================================
    // ClassCacheManager.getCodeCacheStats() — mirrored in code_cache section
    // =========================================================================

    @Test
    void codeCacheStats_delegatesFlag_isTrue() {
        Map<String, Object> stats = ClassCacheManager.getCodeCacheStats();
        assertTrue(stats.containsKey("delegates_to_jadx_icodecache"),
                "missing delegates_to_jadx_icodecache");
        assertEquals(true, stats.get("delegates_to_jadx_icodecache"),
                "plugin always delegates to JADX ICodeCache");
    }
}
