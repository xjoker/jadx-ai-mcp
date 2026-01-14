package com.zin.jadxaimcp.utils;

import jadx.api.ResourceFile;
import jadx.core.xmlgen.ResContainer;
import jadx.gui.JadxWrapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Unified cache manager for resources.arsc parsing results.
 * 
 * Solves the timeout problem on large APKs by:
 * 1. Background loading resources.arsc once
 * 2. Sharing the parsed result across multiple endpoints
 * 3. Thread-safe access with proper synchronization
 * 
 * Usage:
 * - Call initCache(wrapper) to start background loading
 * - Use getSubFiles() to access cached subfiles
 * - Call clearCache() when APK changes
 */
public class ResourceCacheManager {
    
    private static final Logger logger = LoggerFactory.getLogger(ResourceCacheManager.class);
    
    // Cache state
    private static final AtomicReference<List<ResContainer>> cachedSubFiles = new AtomicReference<>(null);
    private static final AtomicBoolean isLoading = new AtomicBoolean(false);
    private static final AtomicReference<String> loadError = new AtomicReference<>(null);
    private static final Object cacheLock = new Object();
    
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
    public static boolean initCache(JadxWrapper wrapper) {
        if (wrapper == null) {
            logger.warn("Cannot init cache: wrapper is null");
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
            final List<ResourceFile> resources = wrapper.getResources();
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
     * Load resources.arsc in background thread.
     * 
     * @param resources List of resource files from JADX
     */
    private static void loadResourcesArsc(List<ResourceFile> resources) {
        try {
            List<ResContainer> allSubFiles = new ArrayList<>();
            
            for (ResourceFile resFile : resources) {
                if (resFile == null) continue;
                
                String name = resFile.getDeobfName();
                if (name == null) continue;
                
                try {
                    if ("resources.arsc".equals(name)) {
                        ResContainer content = resFile.loadContent();
                        if (content != null) {
                            List<ResContainer> subFiles = content.getSubFiles();
                            if (subFiles != null) {
                                // Filter out null entries
                                for (ResContainer sub : subFiles) {
                                    if (sub != null && sub.getFileName() != null) {
                                        allSubFiles.add(sub);
                                    }
                                }
                            }
                        }
                        // Only process first resources.arsc found
                        break;
                    }
                } catch (Exception e) {
                    logger.warn("Error loading resource file '{}': {}", name, e.getMessage());
                }
            }
            
            // Atomically update cache
            synchronized (cacheLock) {
                if (allSubFiles.isEmpty()) {
                    loadError.set("resources.arsc contains no subfiles");
                    logger.warn("resources.arsc parsed but contains no subfiles");
                } else {
                    // Make immutable for thread safety
                    cachedSubFiles.set(Collections.unmodifiableList(allSubFiles));
                    logger.info("Resource cache loaded: {} subfiles", allSubFiles.size());
                }
                isLoading.set(false);
            }
            
        } catch (Exception e) {
            synchronized (cacheLock) {
                loadError.set("Failed to parse resources.arsc: " + e.getMessage());
                isLoading.set(false);
            }
            logger.error("Error loading resource cache", e);
        }
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
