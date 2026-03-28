package com.zin.jadxaimcp.utils;

import jadx.api.ICodeCache;
import jadx.api.ICodeInfo;
import jadx.api.JavaClass;
import jadx.api.impl.DelegateCodeCache;
import jadx.gui.JadxWrapper;
import jadx.gui.cache.code.FixedCodeCache;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Manages the plugin-owned class index cache.
 *
 * <p>Decompiled source itself is owned by JADX's upstream {@link ICodeCache}. We keep a
 * className -> JavaClass index because JADX doesn't expose an equivalent lookup table, but we do
 * not maintain a second plugin-side source LRU.</p>
 */
public class ClassCacheManager {
    private static final Logger logger = LoggerFactory.getLogger(ClassCacheManager.class);
    
    private static final AtomicReference<Map<String, JavaClass>> classCache = new AtomicReference<>();
    private static final AtomicBoolean isInitialized = new AtomicBoolean(false);
    private static final AtomicReference<CompletableFuture<Void>> initFuture = new AtomicReference<>();
    private static final AtomicLong generationToken = new AtomicLong(0);
    private static final AtomicReference<String> cacheOwnerKey = new AtomicReference<>("");
    private static final AtomicReference<ICodeCache> upstreamCodeCacheRef = new AtomicReference<>();
    
    // Health monitoring
    private static final AtomicLong startTime = new AtomicLong(0);
    private static final AtomicLong completionTime = new AtomicLong(0);
    private static final AtomicReference<String> currentPhase = new AtomicReference<>("NOT_INITIALIZED");
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
        if (wrapper == null) {
            logger.warn("[JAI] Cannot initialize class cache: wrapper is null");
            return;
        }
        rotateCacheOwnerIfNeeded(wrapper);
        long generation = generationToken.get();
        if (isInitialized.compareAndSet(false, true)) {
            startTime.set(System.currentTimeMillis());
            currentPhase.set("LOADING");
            
            CompletableFuture<Void> future = CompletableFuture.runAsync(() -> {
                try {
                    logger.info("[JAI] Loading class cache...");
                    List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();
                    registerUpstreamCodeCache(allClasses);
                    
                    Map<String, JavaClass> temp = new HashMap<>();
                    for (JavaClass cls : allClasses) {
                        if (isLoadStale(generation)) {
                            logger.info("[JAI] Discarding stale class cache load for generation {}", generation);
                            return;
                        }
                        temp.put(cls.getFullName(), cls);
                    }

                    if (isLoadStale(generation)) {
                        logger.info("[JAI] Discarding stale class cache result for generation {}", generation);
                        return;
                    }
                    
                    classCache.set(temp);
                    completionTime.set(System.currentTimeMillis());
                    currentPhase.set("READY");
                    
                    long duration = (completionTime.get() - startTime.get()) / 1000;
                    logger.info("[JAI] Class cache loaded: {} classes in {}s", temp.size(), duration);
                } catch (Exception e) {
                    if (isLoadStale(generation)) {
                        logger.info("[JAI] Ignoring stale class cache failure for generation {}", generation);
                        return;
                    }
                    currentPhase.set("ERROR");
                    logger.error("[JAI] Failed to load class cache", e);
                    throw new RuntimeException("Class cache initialization failed", e);
                }
            });
            
            initFuture.set(future);
            if (isLoadStale(generation)) {
                future.cancel(true);
                initFuture.compareAndSet(future, null);
            }
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
            cache = classCache.get();
            if (cache != null) {
                return cache;
            }
            throw new IllegalStateException("Cache initialization was cancelled or invalidated.");
        }
        
        throw new IllegalStateException("Cache not initialized. Call initCache() first.");
    }

    /**
     * Resolve a class by either its current alias name or its raw/original name.
     */
    public static JavaClass findClass(Map<String, JavaClass> classMap, String className) {
        if (classMap == null || className == null || className.isEmpty()) {
            return null;
        }

        JavaClass directMatch = classMap.get(className);
        if (directMatch != null) {
            return directMatch;
        }

        for (JavaClass cls : classMap.values()) {
            if (JadxApiAdapter.matchesClassName(cls, className)) {
                return cls;
            }
        }
        return null;
    }

    public static boolean containsClass(Map<String, JavaClass> classMap, String className) {
        return findClass(classMap, className) != null;
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
     * Compatibility facade over JADX upstream {@link ICodeCache}.
     *
     * <p>{@link JavaClass#getCode()} already reads and writes the upstream code cache, so this
     * method only consults that cache instead of maintaining a second plugin-owned source map.</p>
     */
    public static String getCachedCode(String className) {
        String code = getCachedCodeFromJadx(className);
        if (code != null) {
            codeCacheHits.incrementAndGet();
            return code;
        }
        codeCacheMisses.incrementAndGet();
        return null;
    }

    /**
     * Compatibility no-op.
     *
     * <p>Once {@link JavaClass#getCode()} returns, JADX has already stored the full
     * {@code ICodeInfo} in the upstream cache. Re-adding only a raw string here would duplicate
     * storage and drop metadata.</p>
     */
    public static void putCachedCode(String className, String code) {
        // Intentionally empty: upstream ICodeCache is populated by JavaClass.getCode().
    }

    /**
     * Invalidate cached upstream code for a single class (for example after rename).
     */
    public static void invalidateCode(String className) {
        removeCachedCodeFromJadx(className);
    }

    /**
     * Clear cached upstream code for the currently indexed project.
     */
    public static void clearCodeCache() {
        Map<String, JavaClass> cache = classCache.get();
        if (cache == null || cache.isEmpty()) {
            logger.info("[JAI] Skipped upstream code cache clear: class index not available");
            return;
        }

        int removed = 0;
        Set<String> rawNames = new HashSet<>();
        for (JavaClass cls : cache.values()) {
            if (cls == null) {
                continue;
            }
            String rawName = JadxApiAdapter.getClassRawName(cls);
            if (rawName != null && !rawName.isEmpty() && rawNames.add(rawName)) {
                ICodeCache codeCache = resolveMutableCodeCache(cls);
                if (codeCache != null) {
                    codeCache.remove(rawName);
                    removed++;
                }
            }
        }
        logger.info("[JAI] Cleared {} upstream code cache entries", removed);
    }

    /**
     * Report stats for the plugin's compatibility facade over upstream code caching.
     */
    public static Map<String, Object> getCodeCacheStats() {
        Map<String, Object> stats = new HashMap<>();
        Map<String, JavaClass> cache = classCache.get();
        stats.put("delegates_to_jadx_icodecache", true);
        stats.put("plugin_source_lru_enabled", false);
        stats.put("class_index_size", cache != null ? cache.size() : 0);
        stats.put("code_cache_size", -1);
        stats.put("code_cache_max", -1);
        stats.put("code_cache_hits", codeCacheHits.get());
        stats.put("code_cache_misses", codeCacheMisses.get());
        return stats;
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

        // Debounce only redundant clear requests that would not invalidate any live state.
        if (now - lastClear < CLEAR_DEBOUNCE_MS && !hasActiveCacheState()) {
            long remainingSecs = (CLEAR_DEBOUNCE_MS - (now - lastClear)) / 1000;
            logger.info("[JAI] Cache clear debounced (cooldown: {}s remaining)", remainingSecs);
            return false;
        }

        synchronized (clearLock) {
            lastClear = lastClearTime.get();
            if (now - lastClear < CLEAR_DEBOUNCE_MS && !hasActiveCacheState()) {
                return false;
            }

            clearCacheState("manual clear", true);
            return true;
        }
    }

    private static boolean isLoadStale(long generation) {
        return Thread.currentThread().isInterrupted() || generationToken.get() != generation;
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

    private static boolean hasActiveCacheState() {
        return classCache.get() != null
            || initFuture.get() != null
            || isInitialized.get()
            || !"NOT_INITIALIZED".equals(currentPhase.get())
            || !cacheOwnerKey.get().isEmpty();
    }

    private static void rotateCacheOwnerIfNeeded(JadxWrapper wrapper) {
        String ownerKey = buildCacheOwnerKey(wrapper);
        String previousOwner = cacheOwnerKey.get();
        if (!previousOwner.isEmpty() && !previousOwner.equals(ownerKey)) {
            synchronized (clearLock) {
                if (!previousOwner.equals(cacheOwnerKey.get())) {
                    cacheOwnerKey.set(ownerKey);
                    return;
                }
                clearCacheState("project owner changed", false);
                cacheOwnerKey.set(ownerKey);
            }
            logger.info("[JAI] Class index cache invalidated due to project switch");
            return;
        }
        cacheOwnerKey.set(ownerKey);
    }

    private static String buildCacheOwnerKey(JadxWrapper wrapper) {
        StringBuilder ownerKey = new StringBuilder();
        ownerKey.append("wrapper@").append(System.identityHashCode(wrapper));
        try {
            Object project = wrapper.getProject();
            ownerKey.append("|project@").append(project != null ? System.identityHashCode(project) : 0);
            List<Path> filePaths = project != null ? wrapper.getProject().getFilePaths() : null;
            if (filePaths == null || filePaths.isEmpty()) {
                ownerKey.append("|no-input");
            } else {
                for (Path path : filePaths) {
                    ownerKey.append('|').append(path.toAbsolutePath());
                    try {
                        ownerKey.append(':').append(Files.size(path));
                        ownerKey.append(':').append(Files.getLastModifiedTime(path).toMillis());
                    } catch (Exception ignored) {
                        ownerKey.append(":na:na");
                    }
                }
            }
        } catch (Exception e) {
            ownerKey.append("|unknown-project");
        }
        return ownerKey.toString();
    }

    private static void clearCacheState(String reason, boolean updateCooldown) {
        if (updateCooldown) {
            lastClearTime.set(System.currentTimeMillis());
        }
        clearCodeCache();
        long generation = generationToken.incrementAndGet();
        CompletableFuture<Void> future = initFuture.getAndSet(null);
        if (future != null) {
            future.cancel(true);
        }
        classCache.set(null);
        upstreamCodeCacheRef.set(null);
        cacheOwnerKey.set("");
        isInitialized.set(false);
        startTime.set(0);
        completionTime.set(0);
        currentPhase.set("NOT_INITIALIZED");
        logger.info("[JAI] Class cache cleared (generation {}, reason: {})", generation, reason);
    }

    @SuppressWarnings("JadxInternalApiUsage")
    private static String getCachedCodeFromJadx(String className) {
        JavaClass cls = resolveIndexedClass(className);
        if (cls != null) {
            registerUpstreamCodeCache(cls);
            ICodeInfo codeInfo = cls.getClassNode().getCodeFromCache();
            return codeInfo != null ? codeInfo.getCodeStr() : null;
        }
        ICodeCache codeCache = upstreamCodeCacheRef.get();
        if (codeCache == null || className == null || className.isEmpty()) {
            return null;
        }
        return codeCache.getCode(className);
    }

    private static void removeCachedCodeFromJadx(String className) {
        JavaClass cls = resolveIndexedClass(className);
        if (cls != null) {
            ICodeCache codeCache = resolveMutableCodeCache(cls);
            if (codeCache != null) {
                String rawName = JadxApiAdapter.getClassRawName(cls);
                if (rawName != null && !rawName.isEmpty()) {
                    codeCache.remove(rawName);
                }
                String aliasName = JadxApiAdapter.getClassAliasName(cls);
                if (aliasName != null && !aliasName.isEmpty()) {
                    codeCache.remove(aliasName);
                }
            }
            return;
        }
        ICodeCache codeCache = unwrapFixedCodeCache(upstreamCodeCacheRef.get());
        if (codeCache != null && className != null && !className.isEmpty()) {
            codeCache.remove(className);
        }
    }

    private static JavaClass resolveIndexedClass(String className) {
        Map<String, JavaClass> cache = classCache.get();
        return cache != null ? findClass(cache, className) : null;
    }

    private static void registerUpstreamCodeCache(List<JavaClass> allClasses) {
        if (allClasses == null || allClasses.isEmpty()) {
            return;
        }
        registerUpstreamCodeCache(allClasses.get(0));
    }

    @SuppressWarnings("JadxInternalApiUsage")
    private static void registerUpstreamCodeCache(JavaClass cls) {
        if (cls == null) {
            return;
        }
        ICodeCache codeCache = cls.getClassNode().root().getCodeCache();
        if (codeCache != null) {
            upstreamCodeCacheRef.set(codeCache);
        }
    }

    private static ICodeCache resolveMutableCodeCache(JavaClass cls) {
        registerUpstreamCodeCache(cls);
        return unwrapFixedCodeCache(upstreamCodeCacheRef.get());
    }

    private static ICodeCache unwrapFixedCodeCache(ICodeCache codeCache) {
        if (!(codeCache instanceof FixedCodeCache)) {
            return codeCache;
        }
        try {
            Field backCacheField = DelegateCodeCache.class.getDeclaredField("backCache");
            backCacheField.setAccessible(true);
            Object backCache = backCacheField.get(codeCache);
            if (backCache instanceof ICodeCache) {
                return (ICodeCache) backCache;
            }
        } catch (ReflectiveOperationException e) {
            logger.debug("[JAI] Failed to unwrap FixedCodeCache for invalidation: {}", e.getMessage());
        }
        return codeCache;
    }
}
