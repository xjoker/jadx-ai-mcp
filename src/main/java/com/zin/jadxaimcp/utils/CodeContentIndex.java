package com.zin.jadxaimcp.utils;

import jadx.api.JavaClass;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.BitSet;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.StampedLock;

/**
 * Trigram bitmap inverted index for code-content search.
 *
 * <p>Maintains a {@code ConcurrentHashMap<String, BitSet>} mapping each lowercased
 * 3-gram → BitSet of class IDs that contain it.  A stable ID is assigned to each
 * {@link JavaClass} on first index insertion; the mapping is kept in a parallel
 * {@code JavaClass[] idToClass} array (sized lazily, doubled on overflow).</p>
 *
 * <h2>Memory budget</h2>
 * <ul>
 *   <li>Each 3-gram entry: ~40B key object + ~N/8 bytes for a N-class BitSet.</li>
 *   <li>For 10 000 classes × ~1 800 unique trigrams per class ≈ 18M trigram
 *       occurrences; with heavy de-duplication the map stays well under 100 MB in
 *       practice.  The {@code JADX_MCP_CODE_INDEX_MAX_TRIGRAMS} cap (default 500 000)
 *       prevents unbounded growth on very large APKs.</li>
 * </ul>
 *
 * <h2>Adaptive eviction</h2>
 * <p>A background heap-watcher thread periodically checks JVM heap pressure.
 * When used/max ratio exceeds {@code HEAP_PRESSURE_HIGH} (default 0.80), a
 * selectivity-based eviction sweep removes trigrams with the highest BitSet
 * cardinality first — those trigrams appear in many classes and provide the
 * least filtering benefit.  Eviction stops when the ratio drops below
 * {@code HEAP_PRESSURE_LOW} (default 0.70), providing hysteresis.</p>
 *
 * <h2>Thread safety</h2>
 * <ul>
 *   <li>Class-ID assignment uses a {@link StampedLock} upgrading write-lock.</li>
 *   <li>BitSet mutation is guarded by per-entry {@code synchronized(bitSet)} blocks
 *       (BitSet is not thread-safe natively).</li>
 *   <li>{@link #clear()} atomically replaces the internal state so in-flight
 *       readers see either the old or new view, never a torn intermediate.</li>
 *   <li>Eviction sweeps snapshot the {@code state} reference once; if {@link #clear()}
 *       races and replaces the state mid-sweep, the sweep detects the mismatch and
 *       abandons safely.</li>
 * </ul>
 */
public final class CodeContentIndex {

    private static final Logger logger = LoggerFactory.getLogger(CodeContentIndex.class);

    // -------------------------------------------------------------------------
    // Environment-variable configuration
    // -------------------------------------------------------------------------

    /** Set to {@code "false"} to disable the index entirely. Default: {@code true}. */
    static final boolean ENABLED;

    /** Maximum number of distinct trigrams stored before further classes are skipped. Default: 500 000. */
    static final int MAX_TRIGRAMS;

    /**
     * Maximum size in bytes of a single class's decompiled source that will be indexed.
     * Classes larger than this limit are skipped (they would dominate every trigram bucket
     * and provide little selective benefit).  Default: 1 048 576 (1 MB).
     */
    static final int MAX_CLASS_SIZE_BYTES;

    /** Set to {@code "false"} to disable adaptive eviction. Default: {@code true}. */
    static final boolean EVICTION_ENABLED;

    /** Heap pressure ratio above which eviction sweeps begin. Default: 0.80. */
    static final double HEAP_PRESSURE_HIGH;

    /** Heap pressure ratio below which eviction sweeps stop (hysteresis). Default: 0.70. */
    static final double HEAP_PRESSURE_LOW;

    /** Interval in seconds between heap-watcher ticks. Default: 10. */
    static final int HEAP_WATCHER_INTERVAL_SECONDS;

    static {
        String enabledEnv = System.getenv("JADX_MCP_CODE_INDEX_ENABLED");
        ENABLED = enabledEnv == null || !enabledEnv.equalsIgnoreCase("false");

        String maxTrigramsEnv = System.getenv("JADX_MCP_CODE_INDEX_MAX_TRIGRAMS");
        int maxTrigrams = 500_000;
        if (maxTrigramsEnv != null) {
            try {
                maxTrigrams = Integer.parseInt(maxTrigramsEnv.trim());
            } catch (NumberFormatException ignored) {
                logger.warn("[JAI] Invalid JADX_MCP_CODE_INDEX_MAX_TRIGRAMS='{}'; using default {}",
                        maxTrigramsEnv, maxTrigrams);
            }
        }
        MAX_TRIGRAMS = maxTrigrams;

        String maxSizeEnv = System.getenv("JADX_MCP_CODE_INDEX_MAX_CLASS_SIZE_BYTES");
        int maxSize = 1_048_576;
        if (maxSizeEnv != null) {
            try {
                maxSize = Integer.parseInt(maxSizeEnv.trim());
            } catch (NumberFormatException ignored) {
                logger.warn("[JAI] Invalid JADX_MCP_CODE_INDEX_MAX_CLASS_SIZE_BYTES='{}'; using default {}",
                        maxSizeEnv, maxSize);
            }
        }
        MAX_CLASS_SIZE_BYTES = maxSize;

        String evictionEnabledEnv = System.getenv("JADX_MCP_CODE_INDEX_EVICTION_ENABLED");
        EVICTION_ENABLED = evictionEnabledEnv == null || !evictionEnabledEnv.equalsIgnoreCase("false");

        String pressureHighEnv = System.getenv("JADX_MCP_CODE_INDEX_HEAP_PRESSURE_HIGH");
        double pressureHigh = 0.80;
        if (pressureHighEnv != null) {
            try {
                pressureHigh = Double.parseDouble(pressureHighEnv.trim());
            } catch (NumberFormatException ignored) {
                logger.warn("[JAI] Invalid JADX_MCP_CODE_INDEX_HEAP_PRESSURE_HIGH='{}'; using default {}",
                        pressureHighEnv, pressureHigh);
            }
        }
        HEAP_PRESSURE_HIGH = pressureHigh;

        String pressureLowEnv = System.getenv("JADX_MCP_CODE_INDEX_HEAP_PRESSURE_LOW");
        double pressureLow = 0.70;
        if (pressureLowEnv != null) {
            try {
                pressureLow = Double.parseDouble(pressureLowEnv.trim());
            } catch (NumberFormatException ignored) {
                logger.warn("[JAI] Invalid JADX_MCP_CODE_INDEX_HEAP_PRESSURE_LOW='{}'; using default {}",
                        pressureLowEnv, pressureLow);
            }
        }
        HEAP_PRESSURE_LOW = pressureLow;

        String intervalEnv = System.getenv("JADX_MCP_HEAP_WATCHER_INTERVAL_SECONDS");
        int interval = 10;
        if (intervalEnv != null) {
            try {
                interval = Integer.parseInt(intervalEnv.trim());
            } catch (NumberFormatException ignored) {
                logger.warn("[JAI] Invalid JADX_MCP_HEAP_WATCHER_INTERVAL_SECONDS='{}'; using default {}",
                        intervalEnv, interval);
            }
        }
        HEAP_WATCHER_INTERVAL_SECONDS = interval;
    }

    // -------------------------------------------------------------------------
    // Singleton state — replaced atomically on clear()
    // -------------------------------------------------------------------------

    /** Volatile reference to the active state; replace entirely on clear(). */
    private static volatile State state = new State();

    // -------------------------------------------------------------------------
    // Eviction statistics
    // -------------------------------------------------------------------------

    /** Cumulative total of trigrams removed by eviction sweeps across all state generations. */
    private static final AtomicLong totalEvictions = new AtomicLong(0);

    // -------------------------------------------------------------------------
    // Background heap-watcher
    // -------------------------------------------------------------------------

    private static final ScheduledExecutorService heapWatcher;

    static {
        if (ENABLED && EVICTION_ENABLED) {
            ScheduledExecutorService svc = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "jadx-heap-watcher");
                t.setDaemon(true);
                return t;
            });
            svc.scheduleAtFixedRate(
                    CodeContentIndex::heapWatcherTick,
                    HEAP_WATCHER_INTERVAL_SECONDS,
                    HEAP_WATCHER_INTERVAL_SECONDS,
                    TimeUnit.SECONDS);
            heapWatcher = svc;
        } else {
            heapWatcher = null;
        }
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /**
     * Index a class's decompiled source if the index is enabled and within budget.
     *
     * <p>If the same class has been indexed before (identity check via {@code ==}),
     * this is a no-op — the code content has not changed.  If the class was
     * previously indexed and then {@link #invalidate(JavaClass)} was called, its
     * bit is cleared from all existing trigram sets; calling {@code index()} again
     * re-adds it under a new (or re-used) ID.</p>
     *
     * @param cls  the class whose code to index (must not be null)
     * @param code the lowercased decompiled source (caller should pass {@code cls.getCode().toLowerCase()})
     */
    public static void index(JavaClass cls, String code) {
        if (!ENABLED || cls == null || code == null) {
            return;
        }
        State s = state;
        if (s.capReached.get()) {
            return; // Already at trigram cap — skip silently
        }
        int len = code.length();
        if (len < 3) {
            return; // Nothing to index
        }
        if (len > MAX_CLASS_SIZE_BYTES) {
            logger.debug("[JAI] CodeContentIndex: skipping class {} — source size {}B > limit {}B",
                    cls.getFullName(), len, MAX_CLASS_SIZE_BYTES);
            return;
        }

        int id = s.assignId(cls);
        if (id == State.ALREADY_INDEXED) {
            return;
        }

        // Enumerate distinct trigrams and insert into the map
        int newTrigramCount = 0;
        for (int i = 0; i <= len - 3; i++) {
            char c0 = code.charAt(i);
            char c1 = code.charAt(i + 1);
            char c2 = code.charAt(i + 2);
            // Skip trigrams with whitespace-only chars to reduce noise
            if (c0 <= ' ' && c1 <= ' ' && c2 <= ' ') {
                continue;
            }
            String trigram = new String(new char[]{c0, c1, c2});
            BitSet existing = s.trigramIndex.get(trigram);
            if (existing == null) {
                // Check cap before creating a new entry
                if (s.trigramIndex.size() >= MAX_TRIGRAMS) {
                    if (s.capReached.compareAndSet(false, true)) {
                        logger.warn("[JAI] CodeContentIndex: trigram cap ({}) reached; "
                                + "further classes will not be indexed.", MAX_TRIGRAMS);
                    }
                    return;
                }
                BitSet newBs = new BitSet();
                BitSet race = s.trigramIndex.putIfAbsent(trigram, newBs);
                existing = (race != null) ? race : newBs;
                if (race == null) {
                    newTrigramCount++;
                }
            }
            synchronized (existing) {
                existing.set(id);
            }
        }
        if (logger.isTraceEnabled() && newTrigramCount > 0) {
            logger.trace("[JAI] CodeContentIndex: indexed class {} (id={}, new trigrams={})",
                    cls.getFullName(), id, newTrigramCount);
        }
    }

    /**
     * Look up candidate class IDs for a given search term.
     *
     * <p>Returns a {@link BitSet} whose set bits are class IDs that contain
     * <em>all</em> trigrams of the search term (AND-intersection).  A {@code null}
     * return value means the index cannot narrow the candidate set — the caller
     * should fall back to an O(N) scan.</p>
     *
     * <p>Callers receive a <em>copy</em> of the intersection result; they may
     * iterate it safely without synchronisation.</p>
     *
     * @param term the <strong>lowercased</strong> search term
     * @return intersection BitSet, or {@code null} if the index is disabled / not
     *         applicable (term too short, or any trigram has no entries)
     */
    public static BitSet candidatesForTerm(String term) {
        if (!ENABLED || term == null || term.length() < 3) {
            return null;
        }
        State s = state;
        if (s.trigramIndex.isEmpty()) {
            return null;
        }

        BitSet result = null;
        int len = term.length();
        for (int i = 0; i <= len - 3; i++) {
            String trigram = term.substring(i, i + 3);
            BitSet bs = s.trigramIndex.get(trigram);
            if (bs == null) {
                // No class contains this trigram → intersection is empty
                return null;
            }
            BitSet copy;
            synchronized (bs) {
                copy = (BitSet) bs.clone();
            }
            if (result == null) {
                result = copy;
            } else {
                result.and(copy);
                if (result.isEmpty()) {
                    return null; // Intersection already empty — short-circuit
                }
            }
        }
        return result; // null only if len < 3, already guarded above
    }

    /**
     * Resolve a class ID (from a {@link #candidatesForTerm(String)} BitSet) back
     * to its {@link JavaClass}.
     *
     * @param id class ID obtained from a candidate BitSet
     * @return the corresponding {@link JavaClass}, or {@code null} if the ID is out of range
     */
    public static JavaClass resolveClass(int id) {
        State s = state;
        JavaClass[] arr = s.idToClass;
        if (id < 0 || id >= arr.length) {
            return null;
        }
        return arr[id];
    }

    /**
     * Remove a class from the index (e.g., after a rename or code invalidation).
     *
     * <p>Clears the class's bit from every trigram BitSet.  The class ID slot is
     * freed so it can be reused.  A subsequent call to {@link #index(JavaClass, String)}
     * with the same class object will re-assign an ID and re-index it.</p>
     */
    public static void invalidate(JavaClass cls) {
        if (!ENABLED || cls == null) {
            return;
        }
        State s = state;
        int id = s.removeId(cls);
        if (id < 0) {
            return; // Was not indexed
        }
        // Clear bit from all trigram sets
        for (BitSet bs : s.trigramIndex.values()) {
            synchronized (bs) {
                bs.clear(id);
            }
        }
        logger.debug("[JAI] CodeContentIndex: invalidated class {} (id={})", cls.getFullName(), id);
    }

    /**
     * Atomically replace the entire index with a fresh empty state.
     * Called when the upstream code cache is cleared (project reload).
     */
    public static void clear() {
        if (!ENABLED) {
            return;
        }
        state = new State();
        logger.info("[JAI] CodeContentIndex: cleared");
    }

    /**
     * Index a class using its already-decompiled code from JADX's upstream cache,
     * without triggering a fresh decompile.
     *
     * <p>This is the preferred entry-point for the parallel trigram-fill phase:
     * the code is already in JADX's {@code ICodeCache} (no JADX lock needed), and
     * {@link CodeContentIndex} is fully thread-safe, so multiple workers can call
     * this concurrently.</p>
     *
     * @param cls      the class to index (must not be null)
     * @param codeStr  the decompiled source as returned by {@code getCodeFromCache()};
     *                 pass {@code null} to skip silently (class not yet decompiled)
     * @return {@code true} if the class was newly indexed, {@code false} if it was
     *         already present or skipped (null/empty code, cap reached, disabled)
     */
    public static boolean tryIndexFromCache(JavaClass cls, String codeStr) {
        if (!ENABLED || cls == null || codeStr == null || codeStr.isEmpty()) {
            return false;
        }
        State s = state;
        // Fast-path: already indexed (no work to do)
        if (s.classToId.containsKey(cls)) {
            return false;
        }
        // Delegate to the normal index path using pre-lowercased code
        int beforeCount = s.classCount.get();
        index(cls, codeStr.toLowerCase());
        return state.classCount.get() > beforeCount;
    }

    /**
     * Return the number of distinct trigrams currently stored in the index.
     * Useful for health/stats endpoints.
     */
    public static int trigramCount() {
        return state.trigramIndex.size();
    }

    /**
     * Return the number of classes currently indexed.
     */
    public static int indexedClassCount() {
        return state.classCount.get();
    }

    /**
     * Return the cumulative number of trigrams evicted by adaptive eviction sweeps.
     */
    public static long evictionsTotal() {
        return totalEvictions.get();
    }

    /**
     * Return a stats snapshot suitable for the /index-stats endpoint.
     *
     * @return map with keys: enabled, indexed_classes, trigram_count, max_trigrams,
     *         max_class_size_bytes, estimated_memory_mb, saturation_percent,
     *         evictions_total, eviction_enabled, heap_pressure_high, heap_pressure_low
     */
    public static java.util.Map<String, Object> getStats() {
        java.util.Map<String, Object> stats = new java.util.LinkedHashMap<>();
        stats.put("enabled", ENABLED);
        int indexedClasses = indexedClassCount();
        int trigramCnt = trigramCount();
        stats.put("indexed_classes", indexedClasses);
        stats.put("trigram_count", trigramCnt);
        stats.put("max_trigrams", MAX_TRIGRAMS);
        stats.put("max_class_size_bytes", MAX_CLASS_SIZE_BYTES);
        // Rough memory estimate: each trigram entry ≈ 40B key + ceiling(indexedClasses/8) bytes for BitSet
        long bitsetBytesPerEntry = (long) Math.ceil((double) Math.max(indexedClasses, 1) / 8.0);
        long estimatedBytes = (long) trigramCnt * (40 + bitsetBytesPerEntry);
        stats.put("estimated_memory_mb", (int) (estimatedBytes / (1024 * 1024)));
        double saturation = MAX_TRIGRAMS > 0 ? (double) trigramCnt / MAX_TRIGRAMS : 0.0;
        stats.put("saturation_percent", Math.round(saturation * 10000.0) / 100.0);
        // Eviction stats
        stats.put("evictions_total", totalEvictions.get());
        stats.put("eviction_enabled", EVICTION_ENABLED);
        stats.put("heap_pressure_high", HEAP_PRESSURE_HIGH);
        stats.put("heap_pressure_low", HEAP_PRESSURE_LOW);
        return stats;
    }

    // -------------------------------------------------------------------------
    // Adaptive eviction — heap watcher and sweep
    // -------------------------------------------------------------------------

    /**
     * Called on each heap-watcher tick. Checks heap pressure and triggers an
     * eviction sweep if the HIGH threshold is exceeded.
     */
    static void heapWatcherTick() {
        try {
            Runtime rt = Runtime.getRuntime();
            double pressure = heapPressure(rt);
            if (pressure > HEAP_PRESSURE_HIGH) {
                logger.info("[JAI] CodeContentIndex: heap pressure {}% exceeds threshold {}% — starting eviction sweep",
                        String.format("%.1f", pressure * 100), String.format("%.0f", HEAP_PRESSURE_HIGH * 100));
                runEvictionSweep(pressure);
            }
        } catch (Exception e) {
            logger.warn("[JAI] CodeContentIndex: heap-watcher tick failed: {}", e.getMessage());
        }
    }

    /**
     * Compute current JVM heap pressure as used/max ratio.
     * Package-private so tests can call it.
     */
    static double heapPressure(Runtime rt) {
        long used = rt.totalMemory() - rt.freeMemory();
        long max = rt.maxMemory();
        if (max <= 0) return 0.0;
        return (double) used / max;
    }

    /**
     * Run one eviction sweep against the current state.
     *
     * <p>Strategy: sort trigram entries by BitSet cardinality descending (high cardinality
     * = present in many classes = least selective) and remove the top entries until either
     * the trigram count drops to {@code targetCount} or the heap pressure falls below
     * {@link #HEAP_PRESSURE_LOW}.</p>
     *
     * <p>Race safety: snapshot {@code state} at entry; abandon if {@code clear()} replaces
     * it during the sweep.</p>
     *
     * @param initialPressure heap pressure that triggered this sweep (for logging)
     */
    static void runEvictionSweep(double initialPressure) {
        State currentState = state; // snapshot — must stay stable throughout sweep
        ConcurrentHashMap<String, BitSet> index = currentState.trigramIndex;

        int countBefore = index.size();
        if (countBefore == 0) {
            return;
        }

        // Target: drop to 87.5% of current count (= 0.70 / 0.80 hysteresis ratio)
        // so that after eviction heap pressure should be roughly below HEAP_PRESSURE_LOW.
        int targetCount = (int) (countBefore * (HEAP_PRESSURE_LOW / HEAP_PRESSURE_HIGH));

        // Phase 1: collect all (trigram, cardinality) pairs — O(N) scan
        List<Map.Entry<String, Integer>> candidates = new ArrayList<>(countBefore);
        for (Map.Entry<String, BitSet> entry : index.entrySet()) {
            if (state != currentState) {
                logger.debug("[JAI] CodeContentIndex: eviction sweep abandoned — clear() raced");
                return;
            }
            int cardinality;
            synchronized (entry.getValue()) {
                cardinality = entry.getValue().cardinality();
            }
            candidates.add(new java.util.AbstractMap.SimpleEntry<>(entry.getKey(), cardinality));
        }

        // Phase 2: sort descending by cardinality (highest = least selective = evict first)
        candidates.sort((a, b) -> Integer.compare(b.getValue(), a.getValue()));

        // Phase 3: remove until we hit targetCount or state is replaced
        int evicted = 0;
        for (Map.Entry<String, Integer> candidate : candidates) {
            if (state != currentState) {
                logger.debug("[JAI] CodeContentIndex: eviction sweep abandoned mid-pass — clear() raced");
                break;
            }
            if (index.size() <= targetCount) {
                break;
            }
            index.remove(candidate.getKey());
            evicted++;
        }

        int countAfter = index.size();
        if (evicted > 0) {
            totalEvictions.addAndGet(evicted);
            // Reset capReached so new classes can be indexed again
            currentState.capReached.set(false);
            logger.info("[JAI] CodeContentIndex: eviction sweep complete — pressure={}%, evicted={}, count {}->{}",
                    String.format("%.1f", initialPressure * 100), evicted, countBefore, countAfter);
        }
    }

    /**
     * Trigger an eviction sweep directly, bypassing the heap-pressure check.
     * Package-private; used by tests.
     */
    static void forceEvictionSweep() {
        runEvictionSweep(HEAP_PRESSURE_HIGH + 0.01);
    }

    // -------------------------------------------------------------------------
    // Internal state container (replaced atomically on clear)
    // -------------------------------------------------------------------------

    static final class State {
        static final int ALREADY_INDEXED = -1;

        /** trigram → BitSet of class IDs. */
        final ConcurrentHashMap<String, BitSet> trigramIndex = new ConcurrentHashMap<>();

        /** JavaClass → assigned integer ID. */
        final ConcurrentHashMap<JavaClass, Integer> classToId = new ConcurrentHashMap<>();

        /** Reverse mapping: class ID → JavaClass.  Guarded by idLock for resize. */
        volatile JavaClass[] idToClass = new JavaClass[256];

        /** Next available ID counter. */
        final AtomicInteger nextId = new AtomicInteger(0);

        /** Number of live classes in the index (not counting invalidated slots). */
        final AtomicInteger classCount = new AtomicInteger(0);

        /** Set to true once the trigram cap is reached. */
        final AtomicBoolean capReached = new AtomicBoolean(false);

        /** Guards ID-to-class array resize and class registration. */
        final StampedLock idLock = new StampedLock();

        /**
         * Assign a new ID to {@code cls} if it has not been indexed yet.
         *
         * @return the assigned ID, or {@link #ALREADY_INDEXED} if already in the index
         */
        int assignId(JavaClass cls) {
            // Fast-path: already indexed
            if (classToId.containsKey(cls)) {
                return ALREADY_INDEXED;
            }

            int id = nextId.getAndIncrement();

            // Store cls → id
            Integer prev = classToId.putIfAbsent(cls, id);
            if (prev != null) {
                // Another thread raced us; return the winner's ID so we fall into ALREADY_INDEXED
                // semantics — the racing thread will handle indexing.
                nextId.decrementAndGet(); // reclaim the ID we grabbed (best effort)
                return ALREADY_INDEXED;
            }

            // Ensure idToClass is large enough, then store id → cls
            long stamp = idLock.writeLock();
            try {
                if (id >= idToClass.length) {
                    int newLen = Math.max(idToClass.length * 2, id + 1);
                    JavaClass[] newArr = new JavaClass[newLen];
                    System.arraycopy(idToClass, 0, newArr, 0, idToClass.length);
                    idToClass = newArr;
                }
                idToClass[id] = cls;
            } finally {
                idLock.unlockWrite(stamp);
            }

            classCount.incrementAndGet();
            return id;
        }

        /**
         * Remove {@code cls} from the ID registry and return its former ID.
         *
         * @return the former ID, or -1 if the class was not registered
         */
        int removeId(JavaClass cls) {
            Integer id = classToId.remove(cls);
            if (id == null) {
                return -1;
            }
            long stamp = idLock.writeLock();
            try {
                if (id < idToClass.length) {
                    idToClass[id] = null;
                }
            } finally {
                idLock.unlockWrite(stamp);
            }
            classCount.decrementAndGet();
            return id;
        }
    }
}
