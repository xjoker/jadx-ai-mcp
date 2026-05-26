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
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class CodeSearchCoordinator {
    private static final Logger logger = LoggerFactory.getLogger(CodeSearchCoordinator.class);

    public static final int CACHE_TTL_SECONDS = 45;
    public static final int MAX_CACHE_ENTRIES = 32;

    /** Async ticket registry: maps opaque ticket ID → in-flight future for submit-then-poll. */
    private static final ConcurrentHashMap<String, TicketEntry> TICKET_REGISTRY = new ConcurrentHashMap<>();
    /** How long a ticket stays valid after it was issued (seconds). */
    public static final int TICKET_TTL_SECONDS = 600;

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

    // TODO: Future migration — replace this custom comment matcher with jadx-gui's
    //   jadx.gui.search.SearchTask / SearchSettings when those classes become
    //   available on the classpath (currently only in jadx-gui internals, not
    //   exported by jadx-all:1.5.5). At that point, SearchSettings.searchInComments
    //   can be set to true and the manual regex below can be removed.
    //
    //   Verify availability first:
    //     Class.forName("jadx.gui.search.SearchTask")  // throws if absent
    //     Class.forName("jadx.gui.search.SearchSettings")

    /** Single-line comment pattern: captures text after // until end-of-line. */
    private static final Pattern SINGLE_LINE_COMMENT = Pattern.compile("//([^\r\n]*)");

    /** Multi-line comment pattern: captures the full block delimited by slash-star ... star-slash. */
    private static final Pattern MULTI_LINE_COMMENT =
            Pattern.compile("/\\*[^*]*\\*+(?:[^/*][^*]*\\*+)*/", Pattern.DOTALL);

    /**
     * Returns {@code true} when {@code term} (already lower-cased) appears inside
     * at least one comment block in {@code code}.
     *
     * <p>Comment content is extracted precisely so that keywords that happen to
     * appear only in non-comment code do <em>not</em> trigger a false match.
     *
     * @param code decompiled source text (original casing)
     * @param term search keyword in lower-case
     */
    public static boolean matchesCommentContent(String code, String term) {
        if (code == null || term == null || term.isEmpty()) {
            return false;
        }
        // Check single-line comments: // ...
        Matcher slMatcher = SINGLE_LINE_COMMENT.matcher(code);
        while (slMatcher.find()) {
            String commentText = slMatcher.group(1);
            if (commentText.toLowerCase().contains(term)) {
                return true;
            }
        }
        // Check multi-line comments: /* ... */
        Matcher mlMatcher = MULTI_LINE_COMMENT.matcher(code);
        while (mlMatcher.find()) {
            String commentBlock = mlMatcher.group();
            if (commentBlock.toLowerCase().contains(term)) {
                return true;
            }
        }
        return false;
    }

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

    // ------------------------------- Async Ticket API --------------------------

    /**
     * Registers a CompletableFuture under a new opaque ticket ID.
     * Used by the submit-then-poll async search path.
     *
     * @param future the future that will be completed (or exceptionally completed) by the search
     * @return a 16-char hex ticket ID the caller can use to poll via {@link #pollByTicket}
     */
    public static String registerTicket(CompletableFuture<SearchResult> future) {
        pruneExpiredTickets();
        String ticket = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        TICKET_REGISTRY.put(ticket, new TicketEntry(future, System.currentTimeMillis()));
        return ticket;
    }

    /**
     * Polls the result of a previously submitted async search.
     *
     * @param ticket the ticket ID returned by {@link #registerTicket}
     * @return a {@link TicketPollResult} describing the current status
     */
    public static TicketPollResult pollByTicket(String ticket) {
        pruneExpiredTickets();
        TicketEntry entry = TICKET_REGISTRY.get(ticket);
        if (entry == null) {
            return TicketPollResult.notFound();
        }
        CompletableFuture<SearchResult> future = entry.future;
        if (!future.isDone()) {
            return TicketPollResult.running();
        }
        TICKET_REGISTRY.remove(ticket);
        try {
            SearchResult result = future.getNow(null);
            if (result != null) {
                return TicketPollResult.done(result);
            }
            return TicketPollResult.error("Search returned null result");
        } catch (CompletionException e) {
            Throwable cause = e.getCause() != null ? e.getCause() : e;
            if (cause instanceof TimeoutException) {
                return TicketPollResult.timedOut();
            }
            if (cause instanceof CancellationException) {
                return TicketPollResult.cancelled();
            }
            return TicketPollResult.error(cause.getMessage());
        } catch (CancellationException e) {
            return TicketPollResult.cancelled();
        } catch (Exception e) {
            return TicketPollResult.error(e.getMessage());
        }
    }

    private static void pruneExpiredTickets() {
        long now = System.currentTimeMillis();
        TICKET_REGISTRY.entrySet().removeIf(e ->
            (now - e.getValue().createdAtMs) > (TICKET_TTL_SECONDS * 1000L)
        );
    }

    // ------------------------------- Inner Classes ----------------------------

    public static final class TicketPollResult {
        public enum Status { RUNNING, DONE, TIMED_OUT, CANCELLED, ERROR, NOT_FOUND }

        private final Status status;
        private final SearchResult result;
        private final String message;

        private TicketPollResult(Status status, SearchResult result, String message) {
            this.status = status;
            this.result = result;
            this.message = message;
        }

        public static TicketPollResult running()             { return new TicketPollResult(Status.RUNNING,    null,   null); }
        public static TicketPollResult done(SearchResult r)  { return new TicketPollResult(Status.DONE,       r,      null); }
        public static TicketPollResult timedOut()            { return new TicketPollResult(Status.TIMED_OUT,  null,   "Search exceeded server timeout (60s)"); }
        public static TicketPollResult cancelled()           { return new TicketPollResult(Status.CANCELLED,  null,   "Search invalidated by file change. Resubmit."); }
        public static TicketPollResult error(String msg)     { return new TicketPollResult(Status.ERROR,      null,   msg); }
        public static TicketPollResult notFound()            { return new TicketPollResult(Status.NOT_FOUND,  null,   "Ticket not found or expired"); }

        public Status getStatus()       { return status; }
        public SearchResult getResult() { return result; }
        public String getMessage()      { return message; }
    }

    private static final class TicketEntry {
        final CompletableFuture<SearchResult> future;
        final long createdAtMs;

        TicketEntry(CompletableFuture<SearchResult> future, long createdAtMs) {
            this.future = future;
            this.createdAtMs = createdAtMs;
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
