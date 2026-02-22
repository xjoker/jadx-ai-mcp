package com.zin.jadxaimcp.utils;

import jadx.api.JadxDecompiler;
import jadx.api.ResourceFile;
import jadx.core.xmlgen.ResContainer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Unified cache manager for resources.arsc parsing results.
 * 
 * Solves the timeout problem on large APKs by:
 * 1. Background loading resources.arsc once
 * 2. Sharing the parsed result across multiple endpoints
 * 3. Thread-safe access with proper synchronization
 * 4. Health monitoring with progress and timing info
 * 
 * Usage:
 * - Call initCache(wrapper) to start background loading
 * - Use getSubFiles() to access cached subfiles
 * - Use getHealthInfo() to monitor loading progress
 * - Call clearCache() when APK changes
 */
public class ResourceCacheManager {
    
    private static final Logger logger = LoggerFactory.getLogger(ResourceCacheManager.class);
    
    // Cache state
    private static final AtomicReference<List<ResContainer>> cachedSubFiles = new AtomicReference<>(null);
    private static final AtomicReference<List<ResContainer>> cachedStringsFiles = new AtomicReference<>(null);
    private static final AtomicBoolean isLoading = new AtomicBoolean(false);
    private static final AtomicReference<String> loadError = new AtomicReference<>(null);
    private static final Object cacheLock = new Object();
    
    // Health monitoring
    private static final AtomicLong loadStartTime = new AtomicLong(0);
    private static final AtomicLong loadEndTime = new AtomicLong(0);
    private static final AtomicReference<String> currentPhase = new AtomicReference<>("idle");
    private static final AtomicInteger processedFiles = new AtomicInteger(0);
    private static final AtomicInteger totalFiles = new AtomicInteger(0);
    
    // Prevent instantiation
    private ResourceCacheManager() {}
    
    /**
     * Cache status enum for caller to determine action.
     */
    public enum CacheStatus {
        READY,          // Cache is available
        LOADING,        // Cache is being loaded
        ERROR,          // Loading failed
        NOT_INITIALIZED // Cache not started
    }
    
    /**
     * Get current cache status.
     * 
     * @return Current cache state
     */
    public static CacheStatus getStatus() {
        if (cachedSubFiles.get() != null) {
            return CacheStatus.READY;
        }
        if (loadError.get() != null) {
            return CacheStatus.ERROR;
        }
        if (isLoading.get()) {
            return CacheStatus.LOADING;
        }
        return CacheStatus.NOT_INITIALIZED;
    }
    
    /**
     * Get error message if cache loading failed.
     * 
     * @return Error message or null
     */
    public static String getErrorMessage() {
        return loadError.get();
    }
    
    /**
     * Initialize cache with background loading.
     * Safe to call multiple times - will only trigger loading once.
     * 
     * @param wrapper JADX wrapper to load resources from
     * @return true if loading was started, false if already cached/loading
     */
    public static boolean initCache(JadxDecompiler decompiler) {
        if (decompiler == null) {
            logger.warn("Cannot init cache: decompiler is null");
            return false;
        }

        // Fast path: already cached
        if (cachedSubFiles.get() != null) {
            return false;
        }

        // Check if already loading (atomic check-and-set)
        if (!isLoading.compareAndSet(false, true)) {
            return false; // Another thread is loading
        }

        // Start background loading
        try {
            final List<ResourceFile> resources = decompiler.getResources();
            if (resources == null || resources.isEmpty()) {
                isLoading.set(false);
                loadError.set("No resources found in APK");
                return false;
            }
            
            CompletableFuture.runAsync(() -> loadResourcesArsc(resources));
            return true;
            
        } catch (Exception e) {
            isLoading.set(false);
            loadError.set("Failed to start loading: " + e.getMessage());
            logger.error("Failed to init resource cache", e);
            return false;
        }
    }
    
    /**
     * Load resources.arsc in background thread with progress tracking.
     * 
     * @param resources List of resource files from JADX
     */
    private static void loadResourcesArsc(List<ResourceFile> resources) {
        loadStartTime.set(System.currentTimeMillis());
        currentPhase.set("finding_resources");
        processedFiles.set(0);
        totalFiles.set(resources.size());
        
        try {
            List<ResContainer> allSubFiles = new ArrayList<>();
            int fileIndex = 0;
            
            for (ResourceFile resFile : resources) {
                fileIndex++;
                processedFiles.set(fileIndex);
                
                if (resFile == null) continue;
                
                String name = resFile.getDeobfName();
                if (name == null) continue;
                
                try {
                    if ("resources.arsc".equals(name)) {
                        currentPhase.set("parsing_resources_arsc");
                        logger.info("Found resources.arsc, starting parse...");
                        
                        ResContainer content = resFile.loadContent();
                        
                        if (content != null) {
                            currentPhase.set("indexing_subfiles");
                            List<ResContainer> subFiles = content.getSubFiles();
                            
                            if (subFiles != null) {
                                totalFiles.set(subFiles.size());
                                int subIndex = 0;
                                
                                for (ResContainer sub : subFiles) {
                                    subIndex++;
                                    processedFiles.set(subIndex);
                                    
                                    if (sub != null && sub.getFileName() != null) {
                                        allSubFiles.add(sub);
                                    }
                                }
                            }
                        }
                        break;
                    }
                } catch (Exception e) {
                    logger.warn("Error loading resource file '{}': {}", name, e.getMessage());
                }
            }
            
            // Atomically update cache
            currentPhase.set("finalizing");
            synchronized (cacheLock) {
                if (allSubFiles.isEmpty()) {
                    loadError.set("resources.arsc contains no subfiles");
                    currentPhase.set("error");
                    logger.warn("resources.arsc parsed but contains no subfiles");
                } else {
                    cachedSubFiles.set(Collections.unmodifiableList(allSubFiles));
                    
                    // Pre-compute strings.xml cache
                    List<ResContainer> stringsFiles = new ArrayList<>();
                    for (ResContainer sub : allSubFiles) {
                        String fileName = sub.getFileName();
                        if (fileName != null && fileName.contains("strings.xml")) {
                            stringsFiles.add(sub);
                        }
                    }
                    cachedStringsFiles.set(Collections.unmodifiableList(stringsFiles));
                    
                    currentPhase.set("ready");
                    logger.info("Resource cache loaded: {} subfiles, {} strings.xml files", 
                        allSubFiles.size(), stringsFiles.size());
                }
                loadEndTime.set(System.currentTimeMillis());
                isLoading.set(false);
            }
            
        } catch (Exception e) {
            synchronized (cacheLock) {
                loadError.set("Failed to parse resources.arsc: " + e.getMessage());
                currentPhase.set("error");
                loadEndTime.set(System.currentTimeMillis());
                isLoading.set(false);
            }
            logger.error("Error loading resource cache", e);
        }
    }
    
    /**
     * Get health information for monitoring.
     * Only includes accurate, known information - no estimates.
     * 
     * @return Map with status, phase, timing, and stuck detection
     */
    public static Map<String, Object> getHealthInfo() {
        Map<String, Object> info = new HashMap<>();
        
        CacheStatus status = getStatus();
        info.put("status", status.name());
        info.put("phase", currentPhase.get());
        
        long startTime = loadStartTime.get();
        long endTime = loadEndTime.get();
        long now = System.currentTimeMillis();
        
        if (status == CacheStatus.LOADING && startTime > 0) {
            long elapsed = now - startTime;
            info.put("elapsed_seconds", elapsed / 1000);
            
            // Stuck detection: if parsing takes > 300 seconds, might be stuck
            if (elapsed > 300_000) {
                info.put("warning", "Loading is taking unusually long (>" + (elapsed / 1000) + "s). May be stuck.");
                info.put("possibly_stuck", true);
            } else {
                info.put("alive", true);
            }
        }
        
        if (status == CacheStatus.READY && endTime > 0 && startTime > 0) {
            info.put("duration_seconds", (endTime - startTime) / 1000);
            
            List<ResContainer> cached = cachedSubFiles.get();
            List<ResContainer> strings = cachedStringsFiles.get();
            info.put("cached_files", cached != null ? cached.size() : 0);
            info.put("strings_files", strings != null ? strings.size() : 0);
        }
        
        if (status == CacheStatus.ERROR) {
            info.put("error", loadError.get());
        }
        
        return info;
    }
    
    /**
     * Get cached subfiles list.
     * 
     * @return Immutable list of ResContainer, or null if not cached
     */
    public static List<ResContainer> getSubFiles() {
        return cachedSubFiles.get();
    }
    
    /**
     * Get pre-computed strings.xml files list (O(1) access).
     * 
     * @return Immutable list of strings.xml ResContainers, or empty list
     */
    public static List<ResContainer> getStringsFiles() {
        List<ResContainer> strings = cachedStringsFiles.get();
        return strings != null ? strings : Collections.emptyList();
    }
    
    /**
     * Get subfiles matching a filename pattern.
     * 
     * @param pattern Pattern to match (uses contains)
     * @return List of matching ResContainers, or empty list
     */
    public static List<ResContainer> getSubFilesMatching(String pattern) {
        List<ResContainer> cached = cachedSubFiles.get();
        if (cached == null || pattern == null) {
            return Collections.emptyList();
        }
        
        List<ResContainer> matches = new ArrayList<>();
        for (ResContainer sub : cached) {
            String fileName = sub.getFileName();
            if (fileName != null && fileName.contains(pattern)) {
                matches.add(sub);
            }
        }
        return matches;
    }
    
    /**
     * Get all subfile names (for listing endpoints).
     * 
     * @return List of file names, or empty list if not cached
     */
    public static List<String> getSubFileNames() {
        List<ResContainer> cached = cachedSubFiles.get();
        if (cached == null) {
            return Collections.emptyList();
        }
        
        List<String> names = new ArrayList<>(cached.size());
        for (ResContainer sub : cached) {
            String fileName = sub.getFileName();
            if (fileName != null) {
                names.add(fileName);
            }
        }
        return names;
    }
    
    /**
     * Find a specific subfile by exact name.
     * 
     * @param fileName Exact file name to find
     * @return ResContainer or null if not found
     */
    public static ResContainer findSubFile(String fileName) {
        if (fileName == null) return null;
        
        List<ResContainer> cached = cachedSubFiles.get();
        if (cached == null) return null;
        
        for (ResContainer sub : cached) {
            if (fileName.equals(sub.getFileName())) {
                return sub;
            }
        }
        return null;
    }
    
    /**
     * Get content of a subfile safely.
     * 
     * @param subFile ResContainer to get content from
     * @return Content string or null on error
     */
    public static String getContent(ResContainer subFile) {
        if (subFile == null) return null;
        
        try {
            var text = subFile.getText();
            if (text != null) {
                return text.getCodeStr();
            }
        } catch (Exception e) {
            logger.warn("Error getting content for '{}': {}", subFile.getFileName(), e.getMessage());
        }
        return null;
    }
    
    /**
     * Clear the cache (call when APK changes).
     */
    public static void clearCache() {
        synchronized (cacheLock) {
            cachedSubFiles.set(null);
            cachedStringsFiles.set(null);
            isLoading.set(false);
            loadError.set(null);
        }
        logger.info("Resource cache cleared");
    }
    
    /**
     * Check if cache is ready for use.
     * 
     * @return true if cache is loaded and available
     */
    public static boolean isReady() {
        return cachedSubFiles.get() != null;
    }
    
    /**
     * Check if cache is currently loading.
     * 
     * @return true if background loading is in progress
     */
    public static boolean isLoading() {
        return isLoading.get();
    }
    
    /**
     * Get cache statistics for debugging.
     * 
     * @return String with cache status info
     */
    public static String getStats() {
        List<ResContainer> cached = cachedSubFiles.get();
        return String.format(
            "ResourceCache[status=%s, subfiles=%d, loading=%b, error=%s]",
            getStatus(),
            cached != null ? cached.size() : 0,
            isLoading.get(),
            loadError.get()
        );
    }
}
