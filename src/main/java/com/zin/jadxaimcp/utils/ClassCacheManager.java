package com.zin.jadxaimcp.utils;

import jadx.api.JavaClass;
import jadx.gui.JadxWrapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Manages global cache of all Java classes to avoid repeated expensive iterations.
 * Similar design to ResourceCacheManager.
 */
public class ClassCacheManager {
    private static final Logger logger = LoggerFactory.getLogger(ClassCacheManager.class);
    
    private static final AtomicReference<Map<String, JavaClass>> classCache = new AtomicReference<>();
    private static final AtomicBoolean isInitialized = new AtomicBoolean(false);
    private static final AtomicReference<CompletableFuture<Void>> initFuture = new AtomicReference<>();
    
    // Health monitoring
    private static final AtomicLong startTime = new AtomicLong(0);
    private static final AtomicLong completionTime = new AtomicLong(0);
    private static final AtomicReference<String> currentPhase = new AtomicReference<>("NOT_INITIALIZED");

    // Decompiled source code LRU cache: className -> decompiled Java source
    private static final int MAX_CODE_CACHE_SIZE = 200;
    private static final Object codeCacheLock = new Object();
    private static final LinkedHashMap<String, String> codeCache = new LinkedHashMap<>(
            MAX_CODE_CACHE_SIZE, 0.75f, true) {
        @Override
        protected boolean removeEldestEntry(Map.Entry<String, String> eldest) {
            return size() > MAX_CODE_CACHE_SIZE;
        }
    };
    private static final AtomicLong codeCacheHits = new AtomicLong(0);
    private static final AtomicLong codeCacheMisses = new AtomicLong(0);
    
    public enum CacheStatus {
        NOT_INITIALIZED,
        LOADING,
        READY,
        ERROR
    }
    
    /**
     * Initialize the cache asynchronously
     */
    public static void initCache(JadxWrapper wrapper) {
        if (isInitialized.compareAndSet(false, true)) {
            startTime.set(System.currentTimeMillis());
            currentPhase.set("LOADING");
            
            CompletableFuture<Void> future = CompletableFuture.runAsync(() -> {
                try {
                    logger.info("[JAI] Loading class cache...");
                    List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();
                    
                    Map<String, JavaClass> temp = new HashMap<>();
                    for (JavaClass cls : allClasses) {
                        temp.put(cls.getFullName(), cls);
                    }
                    
                    classCache.set(temp);
                    completionTime.set(System.currentTimeMillis());
                    currentPhase.set("READY");
                    
                    long duration = (completionTime.get() - startTime.get()) / 1000;
                    logger.info("[JAI] Class cache loaded: {} classes in {}s", temp.size(), duration);
                } catch (Exception e) {
                    currentPhase.set("ERROR");
                    logger.error("[JAI] Failed to load class cache", e);
                    throw new RuntimeException("Class cache initialization failed", e);
                }
            });
            
            initFuture.set(future);
        }
    }
    
    /**
     * Get the class cache, waiting if necessary
     */
    public static Map<String, JavaClass> getCache() throws Exception {
        Map<String, JavaClass> cache = classCache.get();
        if (cache != null) {
            return cache;
        }
        
        // Wait for initialization
        CompletableFuture<Void> future = initFuture.get();
        if (future != null) {
            future.get(); // Wait for completion
            return classCache.get();
        }
        
        throw new IllegalStateException("Cache not initialized. Call initCache() first.");
    }
    
    /**
     * Get cache status
     */
    public static CacheStatus getStatus() {
        String phase = currentPhase.get();
        return CacheStatus.valueOf(phase);
    }
    
    /**
     * Get health information
     */
    public static Map<String, Object> getHealthInfo() {
        Map<String, Object> health = new HashMap<>();
        
        String phase = currentPhase.get();
        health.put("status", phase);
        
        if ("LOADING".equals(phase)) {
            long elapsed = (System.currentTimeMillis() - startTime.get()) / 1000;
            health.put("elapsed_seconds", elapsed);
            health.put("message", "Loading all classes into cache...");
        } else if ("READY".equals(phase)) {
            Map<String, JavaClass> cache = classCache.get();
            health.put("total_classes", cache != null ? cache.size() : 0);
            
            long duration = (completionTime.get() - startTime.get()) / 1000;
            health.put("load_duration_seconds", duration);
        } else if ("ERROR".equals(phase)) {
            health.put("error", "Cache initialization failed");
        }
        
        return health;
    }
    
    /**
     * Get cached decompiled source code for a class.
     * @return cached source code, or null if not cached
     */
    public static String getCachedCode(String className) {
        synchronized (codeCacheLock) {
            String code = codeCache.get(className);
            if (code != null) {
                codeCacheHits.incrementAndGet();
                return code;
            }
            codeCacheMisses.incrementAndGet();
            return null;
        }
    }

    /**
     * Store decompiled source code in the cache.
     * Null or empty code is not cached.
     */
    public static void putCachedCode(String className, String code) {
        if (className == null || code == null || code.isEmpty()) {
            return;
        }
        synchronized (codeCacheLock) {
            codeCache.put(className, code);
        }
    }

    /**
     * Invalidate cached code for a single class (e.g., after rename).
     */
    public static void invalidateCode(String className) {
        synchronized (codeCacheLock) {
            codeCache.remove(className);
        }
    }

    /**
     * Clear all cached decompiled source code.
     */
    public static void clearCodeCache() {
        synchronized (codeCacheLock) {
            codeCache.clear();
        }
        logger.info("[JAI] Decompiled code cache cleared");
    }

    /**
     * Get code cache statistics for monitoring.
     */
    public static Map<String, Object> getCodeCacheStats() {
        synchronized (codeCacheLock) {
            Map<String, Object> stats = new HashMap<>();
            stats.put("code_cache_size", codeCache.size());
            stats.put("code_cache_max", MAX_CODE_CACHE_SIZE);
            stats.put("code_cache_hits", codeCacheHits.get());
            stats.put("code_cache_misses", codeCacheMisses.get());
            return stats;
        }
    }

    // Debounce for cache clearing (prevent rapid successive clears)
    // All cache clear operations share this global 30-second cooldown
    private static final long CLEAR_DEBOUNCE_MS = 30000; // 30 seconds cooldown
    private static final AtomicLong lastClearTime = new AtomicLong(0);
    private static final Object clearLock = new Object();

    /**
     * Clear the cache with global 30-second cooldown (shared across all cache clear triggers).
     * Returns true if cache was cleared, false if debounced.
     */
    public static boolean clearCache() {
        long now = System.currentTimeMillis();
        long lastClear = lastClearTime.get();

        // Debounce: skip if cleared within cooldown period
        if (now - lastClear < CLEAR_DEBOUNCE_MS) {
            long remainingSecs = (CLEAR_DEBOUNCE_MS - (now - lastClear)) / 1000;
            logger.info("[JAI] Cache clear debounced (cooldown: {}s remaining)", remainingSecs);
            return false;
        }

        // Use synchronized block to ensure atomic update of all cache state
        synchronized (clearLock) {
            // Double-check after acquiring lock
            lastClear = lastClearTime.get();
            if (now - lastClear < CLEAR_DEBOUNCE_MS) {
                return false;
            }

            lastClearTime.set(now);
            classCache.set(null);
            isInitialized.set(false);
            initFuture.set(null);
            currentPhase.set("NOT_INITIALIZED");
            clearCodeCache();
            logger.info("[JAI] Class cache cleared");
            return true;
        }
    }
    
    /**
     * Get remaining cooldown time in seconds.
     */
    public static long getRemainingCooldown() {
        long now = System.currentTimeMillis();
        long lastClear = lastClearTime.get();
        long remaining = CLEAR_DEBOUNCE_MS - (now - lastClear);
        return remaining > 0 ? remaining / 1000 : 0;
    }
    
    /**
     * Get the cooldown duration in seconds.
     */
    public static long getCooldownDuration() {
        return CLEAR_DEBOUNCE_MS / 1000;
    }
}
