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
import java.util.ArrayList;
import java.util.Collections;
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
    /** Secondary index keyed by getRawName() so alias-miss lookups avoid a linear scan. */
    private static final AtomicReference<Map<String, JavaClass>> rawNameCache = new AtomicReference<>();

    /**
     * Name indices built at cache-load time for O(1) exact-match lookup.
     * Each map key is lowercase; value is an immutable snapshot list of matching classes.
     * <ul>
     *   <li>classNameIndex  — keyed by the simple (last-segment) class name</li>
     *   <li>methodNameIndex — keyed by declared method short name; buckets = classes that have
     *       at least one method with that name</li>
     *   <li>fieldNameIndex  — same shape, for field names</li>
     * </ul>
     */
    private static final AtomicReference<Map<String, List<JavaClass>>> classNameIndex = new AtomicReference<>();
    private static final AtomicReference<Map<String, List<JavaClass>>> methodNameIndex = new AtomicReference<>();
    private static final AtomicReference<Map<String, List<JavaClass>>> fieldNameIndex = new AtomicReference<>();

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
                    Map<String, JavaClass> rawTemp = new HashMap<>();
                    // Name-index builder maps: key=lowercase name, value=mutable list (frozen after loop)
                    Map<String, List<JavaClass>> clsNameIdx = new HashMap<>();
                    Map<String, List<JavaClass>> mthNameIdx = new HashMap<>();
                    Map<String, List<JavaClass>> fldNameIdx = new HashMap<>();

                    for (JavaClass cls : allClasses) {
                        if (isLoadStale(generation)) {
                            logger.info("[JAI] Discarding stale class cache load for generation {}", generation);
                            return;
                        }
                        temp.put(cls.getFullName(), cls);
                        // Populate secondary raw-name index. In the rare case of a collision
                        // (two classes share the same rawName), keep the alphabetically first
                        // full-name entry so behaviour is deterministic, and log a warning once.
                        String rawName = JadxApiAdapter.getClassRawName(cls);
                        if (rawName != null && !rawName.isEmpty()) {
                            JavaClass existing = rawTemp.get(rawName);
                            if (existing == null) {
                                rawTemp.put(rawName, cls);
                            } else if (cls.getFullName().compareTo(existing.getFullName()) < 0) {
                                logger.warn("[JAI] Raw-name collision for '{}': keeping '{}', ignoring '{}'",
                                        rawName, cls.getFullName(), existing.getFullName());
                                rawTemp.put(rawName, cls);
                            } else {
                                logger.warn("[JAI] Raw-name collision for '{}': keeping '{}', ignoring '{}'",
                                        rawName, existing.getFullName(), cls.getFullName());
                            }
                        }

                        // --- Build name indices ---
                        // 1. Simple class name (last segment after '.', lowercased)
                        String simpleName = cls.getName();
                        if (simpleName != null && !simpleName.isEmpty()) {
                            clsNameIdx.computeIfAbsent(simpleName.toLowerCase(), k -> new ArrayList<>()).add(cls);
                        }
                        // 2. Method name index: each declared method short name → classes declaring it
                        for (JadxApiAdapter.MethodInfoSnapshot m : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                            String mName = m.getName();
                            if (mName != null && !mName.isEmpty()) {
                                mthNameIdx.computeIfAbsent(mName.toLowerCase(), k -> new ArrayList<>()).add(cls);
                            }
                            // Also index by alias name when it differs
                            String mAlias = m.getAliasName();
                            if (mAlias != null && !mAlias.isEmpty() && !mAlias.equals(mName)) {
                                mthNameIdx.computeIfAbsent(mAlias.toLowerCase(), k -> new ArrayList<>()).add(cls);
                            }
                        }
                        // 3. Field name index
                        for (JadxApiAdapter.FieldInfoSnapshot f : JadxApiAdapter.getDeclaredFieldInfos(cls)) {
                            String fName = f.getName();
                            if (fName != null && !fName.isEmpty()) {
                                fldNameIdx.computeIfAbsent(fName.toLowerCase(), k -> new ArrayList<>()).add(cls);
                            }
                            String fAlias = f.getAliasName();
                            if (fAlias != null && !fAlias.isEmpty() && !fAlias.equals(fName)) {
                                fldNameIdx.computeIfAbsent(fAlias.toLowerCase(), k -> new ArrayList<>()).add(cls);
                            }
                        }
                    }

                    if (isLoadStale(generation)) {
                        logger.info("[JAI] Discarding stale class cache result for generation {}", generation);
                        return;
                    }

                    // Freeze list values so callers cannot mutate index buckets
                    for (Map.Entry<String, List<JavaClass>> e : clsNameIdx.entrySet()) {
                        e.setValue(Collections.unmodifiableList(e.getValue()));
                    }
                    for (Map.Entry<String, List<JavaClass>> e : mthNameIdx.entrySet()) {
                        e.setValue(Collections.unmodifiableList(e.getValue()));
                    }
                    for (Map.Entry<String, List<JavaClass>> e : fldNameIdx.entrySet()) {
                        e.setValue(Collections.unmodifiableList(e.getValue()));
                    }

                    classCache.set(temp);
                    rawNameCache.set(rawTemp);
                    classNameIndex.set(clsNameIdx);
                    methodNameIndex.set(mthNameIdx);
                    fieldNameIndex.set(fldNameIdx);
                    completionTime.set(System.currentTimeMillis());
                    currentPhase.set("READY");

                    long duration = (completionTime.get() - startTime.get()) / 1000;
                    logger.info("[JAI] Class cache loaded: {} classes, {} simple-name buckets, "
                            + "{} method-name buckets, {} field-name buckets in {}s",
                            temp.size(), clsNameIdx.size(), mthNameIdx.size(), fldNameIdx.size(), duration);
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
     * Resolve a class by either its current alias (full) name or its raw/original name.
     *
     * <p>Lookup order:
     * <ol>
     *   <li>Primary map keyed by {@link JavaClass#getFullName()} — O(1) hash lookup.</li>
     *   <li>Secondary map keyed by {@link JavaClass#getRawName()} — O(1) hash lookup.</li>
     * </ol>
     * The former linear-scan fallback has been removed; if neither map produces a hit the
     * class is genuinely not indexed and {@code null} is returned.
     * </p>
     */
    public static JavaClass findClass(Map<String, JavaClass> classMap, String className) {
        if (classMap == null || className == null || className.isEmpty()) {
            return null;
        }

        // 1. Primary: full-name / alias lookup
        JavaClass directMatch = classMap.get(className);
        if (directMatch != null) {
            return directMatch;
        }

        // 2. Secondary: raw-name lookup (avoids O(N) linear scan)
        Map<String, JavaClass> rawMap = rawNameCache.get();
        if (rawMap != null) {
            JavaClass rawMatch = rawMap.get(className);
            if (rawMatch != null) {
                return rawMatch;
            }
        }

        return null;
    }

    public static boolean containsClass(Map<String, JavaClass> classMap, String className) {
        return findClass(classMap, className) != null;
    }

    /**
     * Exact-match lookup against the pre-built name indices.
     *
     * <p>Returns the (possibly empty) bucket for the given lowercased term from the
     * requested index. Callers must NOT mutate the returned list.</p>
     *
     * @param kind one of {@code "class"}, {@code "method"}, or {@code "field"}
     * @param term the search term (will be lowercased internally)
     * @return matching class list, or {@code null} if the index is not yet available
     */
    public static List<JavaClass> findByExactName(String kind, String term) {
        if (term == null || term.isEmpty()) {
            return Collections.emptyList();
        }
        String lower = term.toLowerCase();
        switch (kind) {
            case "class": {
                Map<String, List<JavaClass>> idx = classNameIndex.get();
                if (idx == null) return null;
                List<JavaClass> bucket = idx.get(lower);
                return bucket != null ? bucket : Collections.emptyList();
            }
            case "method": {
                Map<String, List<JavaClass>> idx = methodNameIndex.get();
                if (idx == null) return null;
                List<JavaClass> bucket = idx.get(lower);
                return bucket != null ? bucket : Collections.emptyList();
            }
            case "field": {
                Map<String, List<JavaClass>> idx = fieldNameIndex.get();
                if (idx == null) return null;
                List<JavaClass> bucket = idx.get(lower);
                return bucket != null ? bucket : Collections.emptyList();
            }
            default:
                return Collections.emptyList();
        }
    }

    /**
     * Re-index a single class after a rename event.
     *
     * <p>Removes the class from all name-index buckets it currently occupies, then
     * re-adds it under its current (post-rename) names. This is cheaper than
     * rebuilding the full index and keeps equality lookups accurate immediately
     * after a rename.</p>
     *
     * <p>If the indices have not been built yet (cache still loading) this is a no-op —
     * the correct data will appear when the initial build completes.</p>
     */
    public static void reindex(JavaClass cls) {
        if (cls == null) {
            return;
        }
        // Invalidate the content index: after a rename the decompiled source changes,
        // so remove the stale trigram entries; they will be rebuilt on next code access.
        CodeContentIndex.invalidate(cls);

        Map<String, List<JavaClass>> clsIdx = classNameIndex.get();
        Map<String, List<JavaClass>> mthIdx = methodNameIndex.get();
        Map<String, List<JavaClass>> fldIdx = fieldNameIndex.get();
        if (clsIdx == null || mthIdx == null || fldIdx == null) {
            return; // Index not built yet; initial build will include current names
        }

        // Remove cls from every bucket that contains it
        removeFromIndex(clsIdx, cls);
        removeFromIndex(mthIdx, cls);
        removeFromIndex(fldIdx, cls);

        // Re-add under current names (post-rename)
        String simpleName = cls.getName();
        if (simpleName != null && !simpleName.isEmpty()) {
            addToIndex(clsIdx, simpleName.toLowerCase(), cls);
        }
        for (JadxApiAdapter.MethodInfoSnapshot m : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
            String mName = m.getName();
            if (mName != null && !mName.isEmpty()) {
                addToIndex(mthIdx, mName.toLowerCase(), cls);
            }
            String mAlias = m.getAliasName();
            if (mAlias != null && !mAlias.isEmpty() && !mAlias.equals(mName)) {
                addToIndex(mthIdx, mAlias.toLowerCase(), cls);
            }
        }
        for (JadxApiAdapter.FieldInfoSnapshot f : JadxApiAdapter.getDeclaredFieldInfos(cls)) {
            String fName = f.getName();
            if (fName != null && !fName.isEmpty()) {
                addToIndex(fldIdx, fName.toLowerCase(), cls);
            }
            String fAlias = f.getAliasName();
            if (fAlias != null && !fAlias.isEmpty() && !fAlias.equals(fName)) {
                addToIndex(fldIdx, fAlias.toLowerCase(), cls);
            }
        }
    }

    /** Removes {@code cls} from all bucket lists in {@code index}. */
    private static void removeFromIndex(Map<String, List<JavaClass>> index, JavaClass cls) {
        for (Map.Entry<String, List<JavaClass>> entry : index.entrySet()) {
            List<JavaClass> bucket = entry.getValue();
            if (bucket instanceof java.util.ArrayList) {
                bucket.remove(cls);
            } else {
                // Bucket was frozen as unmodifiableList — replace with mutable copy minus cls
                boolean present = false;
                for (JavaClass c : bucket) {
                    if (c == cls) {
                        present = true;
                        break;
                    }
                }
                if (present) {
                    List<JavaClass> mutable = new ArrayList<>(bucket);
                    mutable.remove(cls);
                    entry.setValue(Collections.unmodifiableList(mutable));
                }
            }
        }
    }

    /** Adds {@code cls} to the bucket for {@code key} in {@code index}, creating if absent. */
    private static void addToIndex(Map<String, List<JavaClass>> index, String key, JavaClass cls) {
        List<JavaClass> existing = index.get(key);
        if (existing == null) {
            List<JavaClass> newBucket = new ArrayList<>();
            newBucket.add(cls);
            index.put(key, Collections.unmodifiableList(newBucket));
        } else if (existing instanceof java.util.ArrayList) {
            if (!existing.contains(cls)) {
                existing.add(cls);
            }
        } else {
            // Unmodifiable — replace with mutable copy + cls
            if (!existing.contains(cls)) {
                List<JavaClass> mutable = new ArrayList<>(existing);
                mutable.add(cls);
                index.put(key, Collections.unmodifiableList(mutable));
            }
        }
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
     * Retrieve the decompiled code for a {@link JavaClass} — triggering decompilation if needed —
     * and opportunistically populate the {@link CodeContentIndex} with the result.
     *
     * <p>This is the preferred hook point for content searches: callers pass the
     * {@link JavaClass} directly so the index can store the class reference without
     * an extra name-to-class resolution step.</p>
     *
     * @param cls the class whose code to retrieve
     * @return decompiled source (lowercased), or {@code null} if decompilation failed
     */
    public static String getCodeAndIndex(JavaClass cls) {
        if (cls == null) {
            return null;
        }
        registerUpstreamCodeCache(cls);
        try {
            String code = cls.getCode();
            if (code == null || code.isEmpty()) {
                return null;
            }
            String lower = code.toLowerCase();
            CodeContentIndex.index(cls, lower);
            return lower;
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * Retrieve the already-decompiled code string for a class from JADX's upstream
     * {@code ICodeCache} WITHOUT triggering a fresh decompile.
     *
     * <p>Returns {@code null} if the class has not been decompiled yet (cache miss).
     * This is safe to call from multiple threads concurrently — it only reads the
     * JADX code cache, no {@link JadxSearchLock} required.</p>
     *
     * @param cls the class whose cached code to retrieve
     * @return raw decompiled source string, or {@code null} if not cached
     */
    @SuppressWarnings("JadxInternalApiUsage")
    public static String getCachedCodeDirect(JavaClass cls) {
        if (cls == null) {
            return null;
        }
        try {
            ICodeInfo info = cls.getClassNode().getCodeFromCache();
            return info != null ? info.getCodeStr() : null;
        } catch (Exception e) {
            return null;
        }
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
     * Also removes the class from the trigram content index so stale code is not
     * returned by code-search queries; the index entry is rebuilt on next decompile.
     */
    public static void invalidateCode(String className) {
        removeCachedCodeFromJadx(className);
        JavaClass cls = resolveIndexedClass(className);
        if (cls != null) {
            CodeContentIndex.invalidate(cls);
        }
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
     * Return name-index size statistics for the /index-stats endpoint.
     *
     * <p>Returns a map with:
     * <ul>
     *   <li>{@code class_name_buckets}  — distinct simple-class-name entries</li>
     *   <li>{@code method_name_buckets} — distinct method-name entries</li>
     *   <li>{@code field_name_buckets}  — distinct field-name entries</li>
     *   <li>{@code raw_name_map_size}   — size of the secondary raw-name lookup map</li>
     *   <li>{@code index_ready}         — true when all three indices are non-null</li>
     * </ul>
     * </p>
     */
    public static Map<String, Object> getNameIndexStats() {
        Map<String, Object> stats = new HashMap<>();
        Map<String, List<JavaClass>> clsIdx = classNameIndex.get();
        Map<String, List<JavaClass>> mthIdx = methodNameIndex.get();
        Map<String, List<JavaClass>> fldIdx = fieldNameIndex.get();
        Map<String, JavaClass> rawMap = rawNameCache.get();

        stats.put("class_name_buckets", clsIdx != null ? clsIdx.size() : 0);
        stats.put("method_name_buckets", mthIdx != null ? mthIdx.size() : 0);
        stats.put("field_name_buckets", fldIdx != null ? fldIdx.size() : 0);
        stats.put("raw_name_map_size", rawMap != null ? rawMap.size() : 0);
        stats.put("index_ready", clsIdx != null && mthIdx != null && fldIdx != null);
        return stats;
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
     * Clear only the class-index (className -&gt; JavaClass mapping).
     * Does NOT evict the upstream JADX code cache.  Use this for lightweight
     * invalidation such as rename events where only one or a few classes changed.
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

            clearCacheState("manual clear (index only)", false);
            return true;
        }
    }

    /**
     * Full eviction: clears the class index AND the upstream JADX code cache.
     * Use only when the entire project changes (e.g., load_file replacing the APK).
     * Returns true if cache was cleared, false if debounced.
     */
    public static boolean clearCacheIncludingDecompiled() {
        long now = System.currentTimeMillis();
        long lastClear = lastClearTime.get();

        if (now - lastClear < CLEAR_DEBOUNCE_MS && !hasActiveCacheState()) {
            long remainingSecs = (CLEAR_DEBOUNCE_MS - (now - lastClear)) / 1000;
            logger.info("[JAI] Full cache clear debounced (cooldown: {}s remaining)", remainingSecs);
            return false;
        }

        synchronized (clearLock) {
            lastClear = lastClearTime.get();
            if (now - lastClear < CLEAR_DEBOUNCE_MS && !hasActiveCacheState()) {
                return false;
            }

            clearCacheState("full clear including decompiled", true);
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
                clearCacheState("project owner changed", true);
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

    /**
     * Core cache-state reset.
     *
     * @param reason            human-readable description for logs
     * @param evictCodeCache    when true, also evict the upstream JADX code cache;
     *                          set to false for lightweight index-only invalidation
     */
    private static void clearCacheState(String reason, boolean evictCodeCache) {
        lastClearTime.set(System.currentTimeMillis());
        if (evictCodeCache) {
            clearCodeCache();
            CodeContentIndex.clear();
        }
        long generation = generationToken.incrementAndGet();
        CompletableFuture<Void> future = initFuture.getAndSet(null);
        if (future != null) {
            future.cancel(true);
        }
        classCache.set(null);
        rawNameCache.set(null);
        classNameIndex.set(null);
        methodNameIndex.set(null);
        fieldNameIndex.set(null);
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
