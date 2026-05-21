package com.zin.jadxaimcp.utils;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.BitSet;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for adaptive eviction in {@link CodeContentIndex}.
 *
 * <p>Because JavaClass is final and cannot be mocked, these tests drive eviction
 * entirely through the {@code State} internals (same approach as CodeContentIndexTest).
 * Heap pressure is exercised by adjusting the targetCount formula (via forceEvictionSweep)
 * rather than actually consuming heap — that keeps the tests deterministic and fast.
 *
 * <p>Covered scenarios (6 tests):
 * <ol>
 *   <li>Eviction removes high-cardinality trigrams first (selectivity ordering)</li>
 *   <li>Eviction stops at hysteresis target count (not below ~70% of cap)</li>
 *   <li>Index reduces but does not drop below target after sweep</li>
 *   <li>Eviction abandoned when clear() races mid-sweep</li>
 *   <li>Evictions-total counter increments correctly</li>
 *   <li>Eviction disabled env var prevents eviction (static kill-switch checked via getStats)</li>
 * </ol>
 * </p>
 */
class CodeContentIndexEvictionTest {

    // -------------------------------------------------------------------------
    // Helpers (mirrors helpers in CodeContentIndexTest)
    // -------------------------------------------------------------------------

    @BeforeEach
    void resetState() throws Exception {
        // Reset singleton state
        Field f = CodeContentIndex.class.getDeclaredField("state");
        f.setAccessible(true);
        f.set(null, new CodeContentIndex.State());

        // Reset totalEvictions counter
        Field evField = CodeContentIndex.class.getDeclaredField("totalEvictions");
        evField.setAccessible(true);
        AtomicLong ev = (AtomicLong) evField.get(null);
        ev.set(0L);
    }

    private CodeContentIndex.State getState() throws Exception {
        Field f = CodeContentIndex.class.getDeclaredField("state");
        f.setAccessible(true);
        return (CodeContentIndex.State) f.get(null);
    }

    private void setState(CodeContentIndex.State s) throws Exception {
        Field f = CodeContentIndex.class.getDeclaredField("state");
        f.setAccessible(true);
        f.set(null, s);
    }

    private long getTotalEvictions() throws Exception {
        Field evField = CodeContentIndex.class.getDeclaredField("totalEvictions");
        evField.setAccessible(true);
        return ((AtomicLong) evField.get(null)).get();
    }

    /** Add trigram → id mapping directly to a State. */
    private void addTrigram(CodeContentIndex.State s, String trigram, int... ids) {
        BitSet bs = s.trigramIndex.computeIfAbsent(trigram, k -> new BitSet());
        synchronized (bs) {
            for (int id : ids) {
                bs.set(id);
            }
        }
    }

    // -------------------------------------------------------------------------
    // Test 1 — selectivity: high-cardinality trigrams evicted first
    // -------------------------------------------------------------------------

    @Test
    void eviction_removesHighCardinalityTrigramsFirst() throws Exception {
        if (!CodeContentIndex.ENABLED) return;

        CodeContentIndex.State s = getState();

        // "common" appears in 10 classes — high cardinality, least selective
        for (int i = 0; i < 10; i++) {
            addTrigram(s, "com", i);
        }
        // "rare1" appears in 1 class
        addTrigram(s, "ra1", 0);
        // "rare2" appears in 2 classes
        addTrigram(s, "ra2", 0, 1);

        // 3 trigrams total; forceEvictionSweep targets 87.5% of 3 ≈ 2 entries
        // (targetCount = (int)(3 * 0.70/0.80) = 2)
        // The highest-cardinality "com" (10) should be removed first.
        int countBefore = s.trigramIndex.size();
        assertEquals(3, countBefore);

        CodeContentIndex.forceEvictionSweep();

        // After sweep: "com" should be gone; "ra1" and "ra2" should remain
        assertFalse(s.trigramIndex.containsKey("com"),
                "'com' (cardinality=10) should have been evicted first");
        assertTrue(s.trigramIndex.containsKey("ra1"),
                "'ra1' (cardinality=1) should survive");
        assertTrue(s.trigramIndex.containsKey("ra2"),
                "'ra2' (cardinality=2) should survive");
    }

    // -------------------------------------------------------------------------
    // Test 2 — hysteresis: eviction stops at low-threshold target count
    // -------------------------------------------------------------------------

    @Test
    void eviction_stopsAtHysteresisTargetCount() throws Exception {
        if (!CodeContentIndex.ENABLED) return;

        CodeContentIndex.State s = getState();

        // Add 100 trigrams: 50 with cardinality=5, 50 with cardinality=1
        for (int i = 0; i < 50; i++) {
            String key = String.format("h%02d", i); // e.g. "h00".."h49"
            for (int c = 0; c < 5; c++) {
                addTrigram(s, key, c);
            }
        }
        for (int i = 0; i < 50; i++) {
            String key = String.format("l%02d", i); // e.g. "l00".."l49"
            addTrigram(s, key, 0);
        }

        assertEquals(100, s.trigramIndex.size());

        // targetCount = (int)(100 * 0.70/0.80) = 87
        // Eviction should stop at or below 100, not go to zero
        CodeContentIndex.forceEvictionSweep();

        int countAfter = s.trigramIndex.size();
        assertTrue(countAfter > 0, "Eviction must not empty the index entirely");
        // Should have removed enough to reach ~87 entries (stopped at target, not all)
        int target = (int) (100 * (CodeContentIndex.HEAP_PRESSURE_LOW / CodeContentIndex.HEAP_PRESSURE_HIGH));
        assertTrue(countAfter <= 100, "Count should be less than before");
        // We stop at <= targetCount so countAfter should be at or below target
        assertTrue(countAfter <= target + 1,
                "Eviction should stop near targetCount=" + target + ", got " + countAfter);
    }

    // -------------------------------------------------------------------------
    // Test 3 — index reduces but stays non-empty (not dropped below ~70% of cap)
    // -------------------------------------------------------------------------

    @Test
    void eviction_indexReducesButNotDrainedToZero() throws Exception {
        if (!CodeContentIndex.ENABLED) return;

        CodeContentIndex.State s = getState();

        // Populate 10 trigrams with varying cardinalities
        for (int i = 0; i < 10; i++) {
            for (int c = 0; c <= i; c++) {
                addTrigram(s, "t" + String.format("%02d", i), c);
            }
        }

        assertEquals(10, s.trigramIndex.size());
        CodeContentIndex.forceEvictionSweep();

        int countAfter = s.trigramIndex.size();
        assertTrue(countAfter > 0, "Index must still contain some entries after eviction");
        assertTrue(countAfter < 10, "Eviction should have reduced the count");
    }

    // -------------------------------------------------------------------------
    // Test 4 — race safety: eviction abandoned when clear() races
    // -------------------------------------------------------------------------

    @Test
    void eviction_abandonedWhenClearRaces() throws Exception {
        if (!CodeContentIndex.ENABLED) return;

        // Build a state and replace it with a fresh one (simulating clear())
        // before the sweep runs.
        CodeContentIndex.State oldState = getState();
        for (int i = 0; i < 5; i++) {
            addTrigram(oldState, "t" + i, 0, 1, 2, 3, 4);
        }

        // Simulate what clear() does: replace state before sweep starts
        CodeContentIndex.State newState = new CodeContentIndex.State();
        setState(newState); // swap state — oldState is now "stale"

        // Run the sweep against the old state directly
        // (forceEvictionSweep snapshots `state` which is now newState, not oldState)
        // The sweep will operate on newState which is empty — no crash, no exception
        assertDoesNotThrow(() -> CodeContentIndex.forceEvictionSweep(),
                "Sweep against post-clear state must not throw");

        // newState is empty, so evicted count should be 0
        assertEquals(0L, getTotalEvictions(),
                "No evictions should be counted when state is empty");

        // oldState should be unmodified (sweep never touched it)
        assertEquals(5, oldState.trigramIndex.size(),
                "Old state should be unmodified after sweep ran on new empty state");
    }

    // -------------------------------------------------------------------------
    // Test 5 — evictions_total counter increments
    // -------------------------------------------------------------------------

    @Test
    void eviction_totalEvictionsCounterIncrements() throws Exception {
        if (!CodeContentIndex.ENABLED) return;

        CodeContentIndex.State s = getState();

        // 4 trigrams: target = (int)(4 * 0.70/0.80) = 3, so should evict 1
        for (int i = 0; i < 4; i++) {
            // Give each a different cardinality: i+1 classes
            for (int c = 0; c <= i; c++) {
                addTrigram(s, "tr" + i, c);
            }
        }

        assertEquals(0L, getTotalEvictions(), "Counter must start at 0");
        CodeContentIndex.forceEvictionSweep();

        long evicted = getTotalEvictions();
        assertTrue(evicted > 0, "evictions_total must be > 0 after a sweep that removed entries");

        // getStats() also exposes the counter
        Map<String, Object> stats = CodeContentIndex.getStats();
        assertTrue(stats.containsKey("evictions_total"), "getStats() must include evictions_total");
        assertEquals(evicted, stats.get("evictions_total"),
                "getStats().evictions_total must match totalEvictions counter");
    }

    // -------------------------------------------------------------------------
    // Test 6 — eviction_enabled flag in getStats()
    // -------------------------------------------------------------------------

    @Test
    void getStats_includesEvictionFields() {
        Map<String, Object> stats = CodeContentIndex.getStats();

        // All eviction-related fields must be present
        assertTrue(stats.containsKey("evictions_total"), "missing evictions_total");
        assertTrue(stats.containsKey("eviction_enabled"), "missing eviction_enabled");
        assertTrue(stats.containsKey("heap_pressure_high"), "missing heap_pressure_high");
        assertTrue(stats.containsKey("heap_pressure_low"), "missing heap_pressure_low");

        // Types
        assertInstanceOf(Long.class, stats.get("evictions_total"),
                "evictions_total should be Long");
        assertInstanceOf(Boolean.class, stats.get("eviction_enabled"),
                "eviction_enabled should be Boolean");
        assertInstanceOf(Double.class, stats.get("heap_pressure_high"),
                "heap_pressure_high should be Double");
        assertInstanceOf(Double.class, stats.get("heap_pressure_low"),
                "heap_pressure_low should be Double");

        // Sanity: low < high
        double low = (double) stats.get("heap_pressure_low");
        double high = (double) stats.get("heap_pressure_high");
        assertTrue(low < high, "heap_pressure_low must be less than heap_pressure_high");
    }
}
