package com.zin.jadxaimcp.utils;

import jadx.gui.JadxWrapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.concurrent.CancellationException;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

public final class CodeSearchCoordinator {
    private static final Logger logger = LoggerFactory.getLogger(CodeSearchCoordinator.class);

    public static final int CACHE_TTL_SECONDS = 45;
    public static final int MAX_CACHE_ENTRIES = 32;

    private static final Object CACHE_LOCK = new Object();
    private static final ConcurrentHashMap<SearchKey, CompletableFuture<SearchResult>> IN_FLIGHT = new ConcurrentHashMap<>();
    private static final LinkedHashMap<SearchKey, CacheEntry> CACHE =
        new LinkedHashMap<SearchKey, CacheEntry>(32, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<SearchKey, CacheEntry> eldest) {
                return size() > MAX_CACHE_ENTRIES;
            }
        };

    private static final AtomicLong cacheHits = new AtomicLong();
    private static final AtomicLong cacheMisses = new AtomicLong();
    private static final AtomicLong lastSearchMs = new AtomicLong();
    private static final AtomicLong generation = new AtomicLong();
    private static final AtomicReference<String> lastCacheHit = new AtomicReference<>("false");
    private static final AtomicReference<String> lastFileSignature = new AtomicReference<>("");

    private CodeSearchCoordinator() {
    }

    public static SearchReservation reserve(
        JadxWrapper wrapper,
        String searchTerm,
        String packageFilter,
        String exclude,
        String searchIn
    ) {
        String fileSignature = buildFileSignature(wrapper);
        rotateFileSignature(fileSignature);
        SearchKey key = new SearchKey(
            generation.get(),
            fileSignature,
            normalize(searchTerm),
            normalize(packageFilter),
            normalize(exclude),
            normalizeSearchIn(searchIn)
        );

        synchronized (CACHE_LOCK) {
            pruneExpiredLocked();
            CacheEntry cached = CACHE.get(key);
            if (cached != null) {
                cacheHits.incrementAndGet();
                lastCacheHit.set("true");
                return SearchReservation.cached(key, cached.result);
            }
        }

        cacheMisses.incrementAndGet();
        lastCacheHit.set("false");

        CompletableFuture<SearchResult> future = new CompletableFuture<>();
        CompletableFuture<SearchResult> existing = IN_FLIGHT.putIfAbsent(key, future);
        if (existing != null) {
            return SearchReservation.join(existing);
        }
        return SearchReservation.leader(key, future);
    }

    public static void completeSuccess(
        SearchKey key,
        CompletableFuture<SearchResult> future,
        SearchResult result,
        long elapsedMs
    ) {
        if (future.isDone() || key.generation != generation.get()) {
            IN_FLIGHT.remove(key, future);
            return;
        }
        lastSearchMs.set(Math.max(0L, elapsedMs));
        synchronized (CACHE_LOCK) {
            pruneExpiredLocked();
            CACHE.put(key, new CacheEntry(result, System.currentTimeMillis()));
        }
        IN_FLIGHT.remove(key, future);
        future.complete(result);
    }

    public static void completeFailure(
        SearchKey key,
        CompletableFuture<SearchResult> future,
        Throwable error
    ) {
        IN_FLIGHT.remove(key, future);
        if (!future.isDone()) {
            future.completeExceptionally(error);
        }
    }

    public static void clearCache() {
        List<CompletableFuture<SearchResult>> cancelled;
        synchronized (CACHE_LOCK) {
            CACHE.clear();
            cancelled = new ArrayList<>(IN_FLIGHT.values());
        }
        IN_FLIGHT.clear();
        for (CompletableFuture<SearchResult> future : cancelled) {
            future.completeExceptionally(new CancellationException("Search cache invalidated"));
        }
        synchronized (CACHE_LOCK) {
            lastCacheHit.set("false");
        }
        generation.incrementAndGet();
        lastFileSignature.set("");
    }

    public static Map<String, Object> getStatus() {
        synchronized (CACHE_LOCK) {
            pruneExpiredLocked();
            Map<String, Object> status = new LinkedHashMap<>();
            status.put("active", IN_FLIGHT.size());
            status.put("inflight_keys", getInflightKeyIds());
            status.put("cache_entries", CACHE.size());
            status.put("cache_hits", cacheHits.get());
            status.put("cache_misses", cacheMisses.get());
            status.put("last_search_ms", lastSearchMs.get());
            status.put("last_cache_hit", Boolean.parseBoolean(lastCacheHit.get()));
            return status;
        }
    }

    private static List<String> getInflightKeyIds() {
        List<String> ids = new ArrayList<>();
        for (SearchKey key : IN_FLIGHT.keySet()) {
            ids.add(key.shortId());
        }
        Collections.sort(ids);
        return ids;
    }

    private static void rotateFileSignature(String signature) {
        String previous = lastFileSignature.getAndSet(signature);
        if (!previous.isEmpty() && !previous.equals(signature)) {
            logger.info("Code search cache invalidated due to loaded file change");
            clearCache();
            lastFileSignature.set(signature);
        }
    }

    private static void pruneExpiredLocked() {
        long now = System.currentTimeMillis();
        CACHE.entrySet().removeIf(entry -> (now - entry.getValue().createdAtMs) > (CACHE_TTL_SECONDS * 1000L));
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase();
    }

    private static String normalizeSearchIn(String value) {
        if (value == null || value.trim().isEmpty()) {
            return "code";
        }
        String[] parts = value.toLowerCase().split(",");
        List<String> normalized = new ArrayList<>();
        for (String part : parts) {
            String trimmed = part.trim();
            if (!trimmed.isEmpty()) {
                normalized.add(trimmed);
            }
        }
        Collections.sort(normalized);
        return String.join(",", normalized);
    }

    private static String buildFileSignature(JadxWrapper wrapper) {
        StringBuilder signature = new StringBuilder();
        signature.append("wrapper@").append(System.identityHashCode(wrapper));
        try {
            Object project = wrapper.getProject();
            signature.append("|project@").append(project != null ? System.identityHashCode(project) : 0);
            List<Path> filePaths = project != null ? wrapper.getProject().getFilePaths() : null;
            if (filePaths == null || filePaths.isEmpty()) {
                signature.append("|no-input");
                return signature.toString();
            }
            for (Path path : filePaths) {
                signature.append('|').append(path.toAbsolutePath());
                try {
                    signature.append('|').append(Files.size(path));
                    signature.append('|').append(Files.getLastModifiedTime(path).toMillis());
                } catch (Exception ignored) {
                    signature.append("|na|na");
                }
                signature.append(';');
            }
            return signature.toString();
        } catch (Exception e) {
            signature.append("|unknown-input");
            return signature.toString();
        }
    }

    public static final class SearchReservation {
        private final SearchKey key;
        private final CompletableFuture<SearchResult> future;
        private final SearchResult cachedResult;
        private final boolean leader;

        private SearchReservation(SearchKey key, CompletableFuture<SearchResult> future, SearchResult cachedResult, boolean leader) {
            this.key = key;
            this.future = future;
            this.cachedResult = cachedResult;
            this.leader = leader;
        }

        public static SearchReservation cached(SearchKey key, SearchResult result) {
            return new SearchReservation(key, null, result, false);
        }

        public static SearchReservation join(CompletableFuture<SearchResult> future) {
            return new SearchReservation(null, future, null, false);
        }

        public static SearchReservation leader(SearchKey key, CompletableFuture<SearchResult> future) {
            return new SearchReservation(key, future, null, true);
        }

        public boolean hasCachedResult() {
            return cachedResult != null;
        }

        public SearchResult getCachedResult() {
            return cachedResult;
        }

        public boolean isLeader() {
            return leader;
        }

        public boolean isFollower() {
            return future != null && !leader && cachedResult == null;
        }

        public SearchKey getKey() {
            return key;
        }

        public CompletableFuture<SearchResult> getFuture() {
            return future;
        }
    }

    public static final class SearchResult {
        private final List<String> matches;
        private final Map<String, Object> searchInfo;

        public SearchResult(List<String> matches, Map<String, Object> searchInfo) {
            this.matches = List.copyOf(matches);
            this.searchInfo = Map.copyOf(searchInfo);
        }

        public List<String> getMatches() {
            return matches;
        }

        public Map<String, Object> getSearchInfo() {
            return searchInfo;
        }
    }

    public static final class SearchKey {
        private final long generation;
        private final String fileSignature;
        private final String searchTerm;
        private final String packageFilter;
        private final String exclude;
        private final String searchIn;

        public SearchKey(long generation, String fileSignature, String searchTerm, String packageFilter, String exclude, String searchIn) {
            this.generation = generation;
            this.fileSignature = fileSignature;
            this.searchTerm = searchTerm;
            this.packageFilter = packageFilter;
            this.exclude = exclude;
            this.searchIn = searchIn;
        }

        public String shortId() {
            return Integer.toHexString(hashCode());
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) {
                return true;
            }
            if (!(obj instanceof SearchKey)) {
                return false;
            }
            SearchKey other = (SearchKey) obj;
            return generation == other.generation
                && Objects.equals(fileSignature, other.fileSignature)
                && Objects.equals(searchTerm, other.searchTerm)
                && Objects.equals(packageFilter, other.packageFilter)
                && Objects.equals(exclude, other.exclude)
                && Objects.equals(searchIn, other.searchIn);
        }

        @Override
        public int hashCode() {
            return Objects.hash(generation, fileSignature, searchTerm, packageFilter, exclude, searchIn);
        }
    }

    private static final class CacheEntry {
        private final SearchResult result;
        private final long createdAtMs;

        private CacheEntry(SearchResult result, long createdAtMs) {
            this.result = result;
            this.createdAtMs = createdAtMs;
        }
    }
}
