package com.zin.jadxaimcp.utils;

import jadx.api.JavaClass;
import jadx.gui.JadxWrapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Background full-cache warmup manager.
 *
 * <p>Two-phase warmup:
 * <ol>
 *   <li>Phase 1 — parallel decompile using up to {@code JADX_MCP_WARMUP_DECOMPILE_WORKERS}
 *       threads (default 8). No {@link JadxSearchLock} held: JADX handles its own
 *       per-class concurrency internally, so searches can run freely during warmup.</li>
 *   <li>Phase 2 — parallel trigram index fill from the already-populated JADX code cache
 *       (no lock needed; {@link CodeContentIndex} is thread-safe).</li>
 * </ol>
 *
 * <p>Only one warmup may run at a time. Starting while one is in progress returns
 * the current status without restarting.</p>
 */
public class WarmupManager {
    private static final Logger logger = LoggerFactory.getLogger(WarmupManager.class);

    private static final String[] LIBRARY_PREFIXES = {
        "android.", "androidx.", "com.google.", "kotlin.", "kotlinx.",
        "okhttp3.", "okio.", "retrofit2.", "com.squareup.", "io.reactivex.",
        "dagger.", "javax.", "com.facebook.", "com.amazonaws.", "org.apache.",
        "org.json.", "com.fasterxml.", "io.netty.", "com.bumptech.glide.",
        "org.greenrobot.", "com.airbnb.", "com.unity3d.", "io.flutter.",
        "com.tencent.", "com.alibaba.", "com.umeng.", "com.adjust."
    };

    // Phase-1 parallel decompile worker count — configurable via JADX_MCP_WARMUP_DECOMPILE_WORKERS
    private static final int DECOMPILE_WORKERS;
    // Phase-2 index worker count — configurable via JADX_MCP_WARMUP_INDEX_WORKERS
    private static final int INDEX_WORKERS;

    static {
        int decompileWorkers = 8;
        String raw = System.getenv("JADX_MCP_WARMUP_DECOMPILE_WORKERS");
        if (raw != null && !raw.isEmpty()) {
            try { decompileWorkers = Math.max(1, Integer.parseInt(raw.trim())); } catch (NumberFormatException ignored) {}
        }
        DECOMPILE_WORKERS = decompileWorkers;

        int workers = 4;
        raw = System.getenv("JADX_MCP_WARMUP_INDEX_WORKERS");
        if (raw != null && !raw.isEmpty()) {
            try { workers = Math.max(1, Integer.parseInt(raw.trim())); } catch (NumberFormatException ignored) {}
        }
        INDEX_WORKERS = workers;
    }

    // -------------------------------------------------------------------------
    // Warmup state — readable via getStatus() at any time
    // -------------------------------------------------------------------------

    private static final AtomicBoolean running = new AtomicBoolean(false);
    private static final AtomicBoolean cancelRequested = new AtomicBoolean(false);
    private static final AtomicInteger total = new AtomicInteger(0);
    private static final AtomicInteger processed = new AtomicInteger(0);
    private static final AtomicInteger failed = new AtomicInteger(0);
    private static final AtomicInteger skipped = new AtomicInteger(0);
    private static final AtomicLong startTime = new AtomicLong(0);
    private static final AtomicLong endTime = new AtomicLong(0);
    private static final AtomicReference<String> phase = new AtomicReference<>("IDLE");
    private static final Object startLock = new Object();

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /**
     * Start a full-cache warmup in the background.
     *
     * <p>Returns immediately.  If a warmup is already running, returns the current
     * status without starting a new one.</p>
     *
     * @param wrapper       JADX wrapper for the loaded file
     * @param skipLibraries when true, well-known third-party SDK packages are skipped
     * @return result map — keys: started (boolean), message, total_classes, skipped_libraries
     */
    public static Map<String, Object> start(JadxWrapper wrapper, boolean skipLibraries) {
        synchronized (startLock) {
            if (running.get()) {
                return Map.of(
                    "started", false,
                    "message", "Warmup already in progress",
                    "status", getStatus()
                );
            }

            List<JavaClass> allClasses;
            try {
                allClasses = wrapper.getIncludedClassesWithInners();
            } catch (Exception e) {
                return Map.of(
                    "started", false,
                    "error", "Failed to get class list: " + e.getMessage()
                );
            }

            List<JavaClass> targets = new ArrayList<>();
            int skippedCount = 0;
            for (JavaClass cls : allClasses) {
                if (skipLibraries && isLibraryClass(cls.getFullName())) {
                    skippedCount++;
                } else {
                    targets.add(cls);
                }
            }

            // Reset counters
            total.set(targets.size());
            processed.set(0);
            failed.set(0);
            skipped.set(skippedCount);
            startTime.set(System.currentTimeMillis());
            endTime.set(0);
            cancelRequested.set(false);
            running.set(true);
            phase.set("PHASE1_DECOMPILE");

            logger.info("[JAI] Full warmup started: {} targets, {} library classes skipped",
                targets.size(), skippedCount);

            Thread warmupThread = new Thread(() -> runWarmup(targets), "jadx-full-warmup");
            warmupThread.setDaemon(true);
            warmupThread.start();

            return Map.of(
                "started", true,
                "total_classes", targets.size(),
                "skipped_libraries", skippedCount,
                "message", "Full cache warmup started in background. "
                    + "Poll get_decompile_status or /cache/warmup-status for progress."
            );
        }
    }

    /** Signal the running warmup to stop at the next class boundary. */
    public static void cancel() {
        cancelRequested.set(true);
        logger.info("[JAI] Full warmup cancel requested");
    }

    /**
     * Return a progress snapshot suitable for a JSON API response.
     *
     * <p>Fields: phase, running, total, processed, failed, skipped_libraries,
     * percentage, elapsed_seconds.</p>
     */
    public static Map<String, Object> getStatus() {
        int tot = total.get();
        int proc = processed.get();
        int fail = failed.get();
        int skip = skipped.get();
        String ph = phase.get();
        boolean isRunning = running.get();
        long start = startTime.get();
        long end = endTime.get();

        long elapsedSec = isRunning
            ? (start > 0 ? (System.currentTimeMillis() - start) / 1000 : 0)
            : (start > 0 && end > 0 ? (end - start) / 1000 : 0);

        int percentage = tot > 0 ? (proc * 100 / tot) : 0;

        Map<String, Object> status = new java.util.LinkedHashMap<>();
        status.put("phase", ph);
        status.put("running", isRunning);
        status.put("total", tot);
        status.put("processed", proc);
        status.put("failed", fail);
        status.put("skipped_libraries", skip);
        status.put("percentage", percentage);
        status.put("elapsed_seconds", elapsedSec);
        return status;
    }

    // -------------------------------------------------------------------------
    // Internal — two-phase warmup loop
    // -------------------------------------------------------------------------

    private static void runWarmup(List<JavaClass> targets) {
        try {
            runPhase1(targets);

            if (!cancelRequested.get()) {
                phase.set("PHASE2_INDEX");
                runPhase2(targets);
            }

            phase.set(cancelRequested.get() ? "CANCELLED" : "DONE");
        } catch (Exception e) {
            phase.set("ERROR");
            logger.warn("[JAI] Full warmup failed: {}", e.getMessage());
        } finally {
            endTime.set(System.currentTimeMillis());
            running.set(false);
            logger.info("[JAI] Full warmup finished — processed={}, failed={}, phase={}",
                processed.get(), failed.get(), phase.get());
        }
    }

    /**
     * Phase 1: parallel decompile without JadxSearchLock.
     *
     * JADX handles per-class concurrency internally (each ClassNode has its own lock),
     * so calling cls.getCode() from multiple threads is safe. Removing the global
     * write lock allows searches to run freely while warmup is in progress.
     */
    private static void runPhase1(List<JavaClass> targets) {
        long phaseStart = System.currentTimeMillis();
        int workers = Math.min(DECOMPILE_WORKERS, Math.max(1, targets.size()));
        java.util.concurrent.atomic.AtomicInteger indexPos = new java.util.concurrent.atomic.AtomicInteger(0);
        java.util.concurrent.atomic.AtomicInteger decompiled = new java.util.concurrent.atomic.AtomicInteger(0);

        ExecutorService pool = Executors.newFixedThreadPool(workers, r -> {
            Thread t = new Thread(r, "jadx-warmup-decompile");
            t.setDaemon(true);
            return t;
        });
        CountDownLatch latch = new CountDownLatch(workers);

        for (int w = 0; w < workers; w++) {
            pool.submit(() -> {
                try {
                    int pos;
                    while ((pos = indexPos.getAndIncrement()) < targets.size()) {
                        if (cancelRequested.get() || Thread.currentThread().isInterrupted()) break;

                        if (isHighMemoryPressure()) {
                            logger.debug("[JAI] Warmup: high memory pressure — pausing 2s");
                            try { Thread.sleep(2000); } catch (InterruptedException ie) { break; }
                            System.gc();
                        }

                        JavaClass cls = targets.get(pos);
                        try {
                            cls.getCode();
                            processed.incrementAndGet();
                            decompiled.incrementAndGet();
                        } catch (Exception ignored) {
                            failed.incrementAndGet();
                        }

                        int proc = processed.get();
                        if (proc % 500 == 0 && proc > 0) {
                            logger.info("[JAI] Warmup phase-1: {}/{} decompiled", proc, total.get());
                        }
                    }
                } finally {
                    latch.countDown();
                }
            });
        }

        try {
            latch.await(Long.MAX_VALUE, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            pool.shutdownNow();
        }

        long phaseMs = System.currentTimeMillis() - phaseStart;
        logger.info("[JAI] Warmup phase-1 done: {} decompiled, {} failed, {} workers in {}ms",
            decompiled.get(), failed.get(), workers, phaseMs);
    }

    /** Phase 2: parallel trigram index fill from already-cached code (no lock needed). */
    private static void runPhase2(List<JavaClass> targets) {
        int workers = Math.min(INDEX_WORKERS, Math.max(1, targets.size()));
        java.util.concurrent.atomic.AtomicInteger indexPos = new java.util.concurrent.atomic.AtomicInteger(0);
        java.util.concurrent.atomic.AtomicInteger indexed = new java.util.concurrent.atomic.AtomicInteger(0);
        long phaseStart = System.currentTimeMillis();

        ExecutorService indexPool = Executors.newFixedThreadPool(workers);
        CountDownLatch latch = new CountDownLatch(workers);

        for (int w = 0; w < workers; w++) {
            indexPool.submit(() -> {
                try {
                    int pos;
                    while ((pos = indexPos.getAndIncrement()) < targets.size()) {
                        if (cancelRequested.get()) break;
                        JavaClass cls = targets.get(pos);
                        String code = ClassCacheManager.getCachedCodeDirect(cls);
                        if (CodeContentIndex.tryIndexFromCache(cls, code)) {
                            indexed.incrementAndGet();
                        }
                    }
                } finally {
                    latch.countDown();
                }
            });
        }

        try {
            latch.await(300, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            indexPool.shutdownNow();
        }

        long phaseMs = System.currentTimeMillis() - phaseStart;
        int totalIndexed = CodeContentIndex.indexedClassCount();
        int totalClasses = total.get() + skipped.get();
        double coverage = totalClasses > 0 ? 100.0 * totalIndexed / totalClasses : 0.0;
        logger.info("[JAI] Warmup phase-2 done: {} newly indexed, trigram coverage {}% in {}ms",
            indexed.get(), String.format("%.1f", coverage), phaseMs);
    }

    private static boolean isLibraryClass(String fullName) {
        for (String prefix : LIBRARY_PREFIXES) {
            if (fullName.startsWith(prefix)) return true;
        }
        return false;
    }

    private static boolean isHighMemoryPressure() {
        Runtime rt = Runtime.getRuntime();
        long used = rt.totalMemory() - rt.freeMemory();
        long max = rt.maxMemory();
        return max > 0 && (double) used / max > 0.88;
    }
}
