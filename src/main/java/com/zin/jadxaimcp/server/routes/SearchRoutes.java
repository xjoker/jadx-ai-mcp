package com.zin.jadxaimcp.server.routes;

import io.javalin.http.Context;

import jadx.api.JavaClass;
import jadx.gui.JadxWrapper;
import jadx.gui.ui.MainWindow;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.BitSet;
import java.util.concurrent.Callable;
import java.util.concurrent.CancellationException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import com.zin.jadxaimcp.utils.PaginationUtils;
import com.zin.jadxaimcp.utils.JadxAIMCPPluginError;
import com.zin.jadxaimcp.utils.JadxSearchLock;
import com.zin.jadxaimcp.utils.ClassCacheManager;
import com.zin.jadxaimcp.utils.CodeContentIndex;
import com.zin.jadxaimcp.utils.CodeSearchCoordinator;
import com.zin.jadxaimcp.utils.JadxApiAdapter;

/**
 * Handles all search-related MCP endpoints.
 *
 * <p>Covers: {@code /search-classes-by-keyword} and all supporting helpers —
 * parallel batch search, trigram pre-filter, name-index exact-match, and the
 * {@link CodeSearchCoordinator} leader/follower deduplication protocol.</p>
 *
 * <p>Also owns the shared {@code searchExecutor} thread pool.  {@link ClassRoutes}
 * holds a reference to this instance and delegates {@code submitWarmupTask} to
 * keep the {@code PluginServer} call-site unchanged.</p>
 */
public class SearchRoutes {
    private static final Logger logger = LoggerFactory.getLogger(SearchRoutes.class);

    // Thread pool for parallel batch search (also used for warmup tasks via ClassRoutes delegation)
    final ExecutorService searchExecutor = Executors.newFixedThreadPool(
        Math.max(2, Runtime.getRuntime().availableProcessors() - 1));

    // Pattern to detect jadx obfuscated package names (e.g., p000, p001, p123)
    private static final Pattern OBFUSCATED_PACKAGE_PATTERN = Pattern.compile("^p\\d+$");

    // Search optimization constants
    private static final int DEFAULT_RESULT_LIMIT = 50;   // Default results per page
    private static final int MAX_RESULT_LIMIT = 200;      // Maximum results per page
    private static final int SEARCH_TIMEOUT_SECONDS = 60; // Timeout for search operations (leader)
    private static final int SEARCH_FOLLOWER_TIMEOUT_SECONDS = Integer.parseInt(
        System.getenv().getOrDefault("JADX_MCP_SEARCH_FOLLOWER_TIMEOUT_SECONDS", "15")
    ); // Follower bail-out timeout; configurable via JADX_MCP_SEARCH_FOLLOWER_TIMEOUT_SECONDS
    // Per-class decompile timeout: if a single getCode() blocks longer than this,
    // the search thread is interrupted so the write lock can eventually be released.
    private static final int PER_CLASS_DECOMPILE_TIMEOUT_SECONDS = Integer.parseInt(
        System.getenv().getOrDefault("JADX_MCP_PER_CLASS_TIMEOUT", "30")
    );
    // Single-thread watchdog that fires an interrupt when one getCode() call stalls.
    private static final ScheduledExecutorService DECOMPILE_WATCHDOG =
        Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "jadx-decompile-watchdog");
            t.setDaemon(true);
            return t;
        });
    private static final String SEARCH_DECOMPILATION_BUSY_MESSAGE = "Search/decompilation operation in progress";

    /**
     * Enum for specifying search locations in handleSearchClassesByKeyword.
     * Supports searching in different parts of decompiled code.
     */
    public enum SearchLocation {
        CLASS_NAME, // Search classes by class name containing keyword
        METHOD_NAME, // Search classes by method name/constructor/parameter types containing keyword
        FIELD_NAME, // Search classes by field name containing keyword
        CODE, // Search code containing keyword (default)
        COMMENT // Search comments containing keyword (searches for // and /* */ patterns)
    }

    // Map lowercase search location names to enum values for URL-friendly parameter parsing
    private static final Map<String, SearchLocation> SEARCH_LOCATION_MAP = new HashMap<>();
    static {
        SEARCH_LOCATION_MAP.put("class", SearchLocation.CLASS_NAME);
        SEARCH_LOCATION_MAP.put("class_name", SearchLocation.CLASS_NAME);
        SEARCH_LOCATION_MAP.put("method", SearchLocation.METHOD_NAME);
        SEARCH_LOCATION_MAP.put("method_name", SearchLocation.METHOD_NAME);
        SEARCH_LOCATION_MAP.put("field", SearchLocation.FIELD_NAME);
        SEARCH_LOCATION_MAP.put("field_name", SearchLocation.FIELD_NAME);
        SEARCH_LOCATION_MAP.put("code", SearchLocation.CODE);
        SEARCH_LOCATION_MAP.put("comment", SearchLocation.COMMENT);
    }

    private final MainWindow mainWindow;
    private final PaginationUtils paginationUtils;

    public SearchRoutes(MainWindow mainWindow, PaginationUtils paginationUtils) {
        this.mainWindow = mainWindow;
        this.paginationUtils = paginationUtils;
    }

    public void shutdownSearchExecutor() {
        searchExecutor.shutdownNow();
    }

    /**
     * Submits a single warmup decompile task to the shared search executor pool.
     * Called via delegation from {@link ClassRoutes#submitWarmupTask(JavaClass)}.
     */
    public Future<?> submitWarmupTask(JavaClass cls) {
        return searchExecutor.submit(() -> {
            try {
                cls.getCode();
            } catch (Exception ignored) {
                // Warmup decompile failures are non-fatal
            }
        });
    }

    // ------------------------------- Request Handlers --------------------------

    /**
     * Handles {@code /search-classes-by-keyword}.
     *
     * <p>Request parameters:</p>
     * <ul>
     *   <li>{@code search_term} (required): The keyword to search for</li>
     *   <li>{@code package} (optional): Limit search to a specific package</li>
     *   <li>{@code search_in} (optional): Comma-separated search locations (default: CODE)</li>
     *   <li>{@code exclude} (optional): Comma-separated package prefixes to exclude</li>
     * </ul>
     */
    /**
     * Supported match modes for metadata searches (class_name / method_name / field_name).
     * Code searches always use substring matching to avoid performance issues.
     */
    public enum MatchMode {
        SUBSTRING, EXACT, PREFIX, REGEX
    }

    public void handleSearchClassesByKeyword(Context ctx) {
        String searchTerm = ctx.queryParam("search_term");
        if (searchTerm == null || searchTerm.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing 'search_term' parameter.", logger);
            return;
        }

        // Parse optional package filter parameter
        String packageFilter = ctx.queryParam("package");
        String searchInParam = ctx.queryParam("search_in");

        // Parse optional exclude parameter
        String excludeParam = ctx.queryParam("exclude");
        List<String> excludePrefixes = new ArrayList<>();
        if (excludeParam != null && !excludeParam.isEmpty()) {
            for (String prefix : excludeParam.split(",")) {
                String trimmed = prefix.trim();
                if (!trimmed.isEmpty()) {
                    excludePrefixes.add(trimmed);
                }
            }
        }

        // Parse match_mode (applies to metadata searches: class/method/field name)
        MatchMode matchMode = parseMatchMode(ctx.queryParam("match_mode"));

        // Parse search locations, default to CODE if not specified
        Set<SearchLocation> searchLocations = parseSearchLocations(searchInParam);

        // Check if code/comment search (requires getCode() - expensive)
        boolean isCodeSearch = searchLocations.contains(SearchLocation.CODE)
            || searchLocations.contains(SearchLocation.COMMENT);

        // Pre-compile regex pattern for REGEX mode to detect errors early
        Pattern regexPattern = null;
        if (matchMode == MatchMode.REGEX && !isCodeSearch) {
            try {
                regexPattern = Pattern.compile(searchTerm, Pattern.CASE_INSENSITIVE);
            } catch (java.util.regex.PatternSyntaxException e) {
                JadxAIMCPPluginError.handleError(ctx, 400,
                    "Invalid regex pattern: " + e.getMessage(), logger);
                return;
            }
        }
        final Pattern compiledRegex = regexPattern;

        // Parse pagination parameters - limit results per page
        int offset = paginationUtils.getIntParam(ctx, "offset", 0);
        int count = paginationUtils.getIntParam(ctx, "count", DEFAULT_RESULT_LIMIT);
        count = Math.min(count, MAX_RESULT_LIMIT);

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();
            List<JavaClass> filteredClasses = filterSearchClasses(allClasses, packageFilter, excludePrefixes);

            if (isCodeSearch) {
                // Code searches always use substring — pass through with match_mode echoed in response
                handleCoordinatedCodeSearch(
                    ctx,
                    wrapper,
                    allClasses,
                    filteredClasses,
                    searchTerm,
                    packageFilter,
                    excludeParam,
                    searchInParam,
                    searchLocations,
                    offset,
                    count,
                    matchMode
                );
                return;
            }

            // Fast-path: attempt O(1) exact-match lookup via pre-built name indices.
            // Only available for EXACT mode (the index uses exact equality).
            if (matchMode == MatchMode.EXACT || matchMode == MatchMode.SUBSTRING) {
                CodeSearchCoordinator.SearchResult indexResult = tryExactNameIndexSearch(
                    searchTerm, searchLocations, packageFilter, excludePrefixes, allClasses);
                if (indexResult != null && matchMode == MatchMode.EXACT) {
                    ctx.json(buildSearchResponse(indexResult, offset, count, matchMode));
                    return;
                }
                // For SUBSTRING, only use index when it returns results (exact hit also covers substring)
                if (indexResult != null && matchMode == MatchMode.SUBSTRING) {
                    ctx.json(buildSearchResponse(indexResult, offset, count, matchMode));
                    return;
                }
            }

            SearchExecution searchExecution = executeSearchWithMatchMode(
                wrapper,
                allClasses,
                filteredClasses,
                searchTerm,
                searchLocations,
                false,
                offset + count + 1,
                matchMode,
                compiledRegex
            );
            ctx.json(buildSearchResponse(searchExecution.getResult(), offset, count, matchMode));
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx,
                    "Internal error in search: " + e.getMessage(), e, logger);
        }
    }

    /**
     * Parses the {@code match_mode} query parameter into a {@link MatchMode} enum value.
     * Defaults to {@code SUBSTRING} for unrecognized or absent values.
     */
    private MatchMode parseMatchMode(String raw) {
        if (raw == null || raw.isBlank()) {
            return MatchMode.SUBSTRING;
        }
        switch (raw.toLowerCase().trim()) {
            case "exact":   return MatchMode.EXACT;
            case "prefix":  return MatchMode.PREFIX;
            case "regex":   return MatchMode.REGEX;
            case "substring":
            default:        return MatchMode.SUBSTRING;
        }
    }

    /**
     * Returns true if {@code candidate} matches {@code term} according to {@code mode}.
     * Both strings should already be lowercased when {@code mode} is SUBSTRING or PREFIX.
     * EXACT uses case-insensitive comparison. REGEX uses the pre-compiled pattern.
     */
    private boolean nameMatches(String candidate, String term, MatchMode mode, Pattern compiledRegex) {
        if (candidate == null) return false;
        switch (mode) {
            case EXACT:     return candidate.equalsIgnoreCase(term);
            case PREFIX:    return candidate.toLowerCase().startsWith(term.toLowerCase());
            case REGEX:     return compiledRegex != null && compiledRegex.matcher(candidate).find();
            case SUBSTRING:
            default:        return candidate.toLowerCase().contains(term.toLowerCase());
        }
    }

    // ------------------------------- Search Helpers ----------------------------

    /**
     * Attempts an O(1) exact-name lookup via the pre-built name indices in
     * {@link ClassCacheManager}.
     *
     * <p>Returns a {@link CodeSearchCoordinator.SearchResult} when the index is available AND
     * the search term is a plain exact name (no wildcards / spaces / regex syntax).
     * Returns {@code null} to signal that the caller should fall back to the normal
     * full-scan path.</p>
     */
    private CodeSearchCoordinator.SearchResult tryExactNameIndexSearch(
        String searchTerm,
        Set<SearchLocation> searchLocations,
        String packageFilter,
        List<String> excludePrefixes,
        List<JavaClass> allClasses
    ) {
        // Exact-match only: reject terms that look like substrings or regex
        if (searchTerm == null || searchTerm.isEmpty()
                || searchTerm.contains("*") || searchTerm.contains("?")
                || searchTerm.contains(" ") || searchTerm.contains(".")) {
            return null;
        }
        // Only handle single-location metadata searches
        if (searchLocations.size() != 1) {
            return null;
        }
        SearchLocation loc = searchLocations.iterator().next();
        String kind;
        switch (loc) {
            case CLASS_NAME:  kind = "class";  break;
            case METHOD_NAME: kind = "method"; break;
            case FIELD_NAME:  kind = "field";  break;
            default: return null; // CODE / COMMENT — skip
        }

        List<JavaClass> bucket = ClassCacheManager.findByExactName(kind, searchTerm);
        if (bucket == null) {
            return null; // Index not ready yet — fall back to scan
        }

        // Apply package / exclude filters if present
        List<String> matchedNames = new ArrayList<>();
        boolean applyPackage = packageFilter != null && !packageFilter.isEmpty();
        Set<JavaClass> allClassesSet = applyPackage ? new HashSet<>(allClasses) : null;
        for (JavaClass cls : bucket) {
            if (applyPackage && (allClassesSet == null || !allClassesSet.contains(cls))) {
                continue;
            }
            if (applyPackage && !matchesPackageFilter(cls, packageFilter)) {
                continue;
            }
            if (!excludePrefixes.isEmpty()) {
                boolean excluded = false;
                for (String prefix : excludePrefixes) {
                    if (cls.getFullName().startsWith(prefix)) {
                        excluded = true;
                        break;
                    }
                }
                if (excluded) {
                    continue;
                }
            }
            matchedNames.add(cls.getFullName());
        }

        Map<String, Object> searchInfo = new HashMap<>();
        searchInfo.put("total_found", matchedNames.size());
        searchInfo.put("total_classes", allClasses.size());
        searchInfo.put("filtered_classes", matchedNames.size());
        searchInfo.put("elapsed_seconds", 0L);
        searchInfo.put("timed_out", false);
        searchInfo.put("parallel_batches", 0);
        searchInfo.put("search_locations", searchLocations.toString());
        searchInfo.put("index_hit", true);

        logger.debug("[JAI] Name-index exact hit: kind={} term='{}' → {} classes",
            kind, searchTerm, matchedNames.size());

        return new CodeSearchCoordinator.SearchResult(matchedNames, searchInfo);
    }

    private void handleCoordinatedCodeSearch(
        Context ctx,
        JadxWrapper wrapper,
        List<JavaClass> allClasses,
        List<JavaClass> filteredClasses,
        String searchTerm,
        String packageFilter,
        String excludeParam,
        String searchInParam,
        Set<SearchLocation> searchLocations,
        int offset,
        int count,
        MatchMode matchMode
    ) throws Exception {
        CodeSearchCoordinator.SearchReservation reservation = CodeSearchCoordinator.reserve(
            wrapper,
            searchTerm,
            packageFilter,
            excludeParam,
            searchInParam
        );

        if (reservation.hasCachedResult()) {
            ctx.json(buildSearchResponse(reservation.getCachedResult(), offset, count, matchMode));
            return;
        }

        if (reservation.isFollower()) {
            CompletableFuture<CodeSearchCoordinator.SearchResult> leaderFuture = reservation.getFuture();
            CompletableFuture<Object> followerFuture = leaderFuture
                .orTimeout(SEARCH_FOLLOWER_TIMEOUT_SECONDS, TimeUnit.SECONDS)
                .handle((value, ex) -> {
                    if (ex != null) {
                        Throwable cause = (ex instanceof ExecutionException) ? ex.getCause() : ex;
                        if (cause instanceof TimeoutException) {
                            return (Object) java.util.Map.of(
                                "status", "still_searching",
                                "message", "Search still in progress (follower timeout). Retry shortly.",
                                "retry_after_seconds", 5
                            );
                        }
                        if (cause instanceof CancellationException) {
                            return (Object) java.util.Map.of(
                                "status", "cancelled",
                                "message", "Search cancelled by concurrent invalidation. Retry.",
                                "retry_after_seconds", 1
                            );
                        }
                        return (Object) java.util.Map.of(
                            "status", "error",
                            "message", cause != null && cause.getMessage() != null
                                ? cause.getMessage() : ex.getClass().getSimpleName()
                        );
                    }
                    return (Object) buildSearchResponse(value, offset, count, matchMode);
                });
            ctx.future(() -> followerFuture);
            return;
        }

        CompletableFuture<CodeSearchCoordinator.SearchResult> future = reservation.getFuture();
        CodeSearchCoordinator.SearchKey key = reservation.getKey();
        if (future == null || key == null) {
            sendCodeSearchBusyResponse(ctx, "Search coordinator state is unavailable", 0.0);
            return;
        }

        // No outer write lock here. Each getCode() call in classMatchesAnyContentLocation()
        // acquires and releases the write lock per-class with a per-class watchdog timeout.
        // Holding the write lock for the entire search (potentially hundreds of classes)
        // was the root cause of multi-minute lock stalls blocking all requests.
        try {
            SearchExecution execution = executeSearch(
                wrapper,
                allClasses,
                filteredClasses,
                searchTerm,
                searchLocations,
                true,
                Integer.MAX_VALUE
            );
            if (execution.isTimedOut()) {
                CodeSearchCoordinator.completeFailure(
                    key,
                    future,
                    new TimeoutException("Code search exceeded timeout window")
                );
            } else {
                CodeSearchCoordinator.completeSuccess(
                    key,
                    future,
                    execution.getResult(),
                    execution.getElapsedMs()
                );
            }
            ctx.json(buildSearchResponse(execution.getResult(), offset, count, matchMode));
        } catch (Exception e) {
            CodeSearchCoordinator.completeFailure(key, future, e);
            throw e;
        }
    }

    // ------------------------------- Async Submit/Poll Handlers ---------------

    /**
     * POST /submit-code-search — submits a code search as a background task.
     * Returns a ticket ID immediately; use GET /code-search-status?ticket=... to poll.
     */
    public void handleSubmitCodeSearch(Context ctx) {
        String searchTerm = ctx.queryParam("search_term");
        if (searchTerm == null || searchTerm.isEmpty()) {
            JadxAIMCPPluginError.handleError(ctx, 400, "Missing 'search_term' parameter.", logger);
            return;
        }

        String packageFilter = ctx.queryParam("package");
        String searchInParam = ctx.queryParam("search_in");
        String excludeParam = ctx.queryParam("exclude");
        MatchMode matchMode = parseMatchMode(ctx.queryParam("match_mode"));

        List<String> excludePrefixes = new ArrayList<>();
        if (excludeParam != null && !excludeParam.isEmpty()) {
            for (String prefix : excludeParam.split(",")) {
                String trimmed = prefix.trim();
                if (!trimmed.isEmpty()) {
                    excludePrefixes.add(trimmed);
                }
            }
        }

        Set<SearchLocation> searchLocations = parseSearchLocations(searchInParam);
        boolean isCodeSearch = searchLocations.contains(SearchLocation.CODE)
            || searchLocations.contains(SearchLocation.COMMENT);
        if (!isCodeSearch) {
            ctx.status(400).json(Map.of("error",
                "submit-code-search only supports search_in=code|comment. Use /search-classes-by-keyword for metadata searches."));
            return;
        }

        try {
            JadxWrapper wrapper = mainWindow.getWrapper();
            List<JavaClass> allClasses = wrapper.getIncludedClassesWithInners();
            List<JavaClass> filteredClasses = filterSearchClasses(allClasses, packageFilter, excludePrefixes);

            CodeSearchCoordinator.SearchReservation reservation = CodeSearchCoordinator.reserve(
                wrapper, searchTerm, packageFilter, excludeParam, searchInParam);

            // Cache hit: register a pre-completed future so poll returns "done" immediately
            if (reservation.hasCachedResult()) {
                CompletableFuture<CodeSearchCoordinator.SearchResult> preDone =
                    CompletableFuture.completedFuture(reservation.getCachedResult());
                String ticket = CodeSearchCoordinator.registerTicket(preDone);
                ctx.json(Map.of("ticket", ticket, "status", "done", "retry_after_seconds", 0));
                return;
            }

            CompletableFuture<CodeSearchCoordinator.SearchResult> future = reservation.getFuture();
            String ticket = CodeSearchCoordinator.registerTicket(future);

            if (reservation.isLeader()) {
                CodeSearchCoordinator.SearchKey key = reservation.getKey();
                final List<JavaClass> allClassesFinal = allClasses;
                final List<JavaClass> filteredClassesFinal = filteredClasses;
                final Set<SearchLocation> locationsFinal = searchLocations;
                searchExecutor.submit(() -> {
                    try {
                        SearchExecution execution = executeSearch(
                            wrapper, allClassesFinal, filteredClassesFinal,
                            searchTerm, locationsFinal, true, Integer.MAX_VALUE);
                        if (execution.isTimedOut()) {
                            CodeSearchCoordinator.completeFailure(
                                key, future, new TimeoutException("Code search exceeded timeout window"));
                        } else {
                            CodeSearchCoordinator.completeSuccess(
                                key, future, execution.getResult(), execution.getElapsedMs());
                        }
                    } catch (Exception e) {
                        CodeSearchCoordinator.completeFailure(key, future, e);
                    }
                });
            }
            // Follower: another identical search is already running; ticket is bound to the same future

            ctx.json(Map.of("ticket", ticket, "status", "submitted", "retry_after_seconds", 5));
        } catch (Exception e) {
            JadxAIMCPPluginError.handleError(ctx, "Failed to submit code search: " + e.getMessage(), e, logger);
        }
    }

    /**
     * GET /code-search-status?ticket=...&offset=...&count=... — polls a submitted search task.
     */
    public void handleCodeSearchStatus(Context ctx) {
        String ticket = ctx.queryParam("ticket");
        if (ticket == null || ticket.isEmpty()) {
            ctx.status(400).json(Map.of("error", "Missing 'ticket' parameter"));
            return;
        }

        int offset = paginationUtils.getIntParam(ctx, "offset", 0);
        int count = Math.min(paginationUtils.getIntParam(ctx, "count", DEFAULT_RESULT_LIMIT), MAX_RESULT_LIMIT);
        MatchMode matchMode = parseMatchMode(ctx.queryParam("match_mode"));

        CodeSearchCoordinator.TicketPollResult poll = CodeSearchCoordinator.pollByTicket(ticket);

        switch (poll.getStatus()) {
            case DONE:
                ctx.json(buildSearchResponse(poll.getResult(), offset, count, matchMode));
                break;
            case RUNNING:
                ctx.json(Map.of("status", "running", "retry_after_seconds", 5,
                    "message", "Search in progress. Poll again shortly."));
                break;
            case TIMED_OUT:
                ctx.json(Map.of("status", "timed_out", "retry_after_seconds", 0,
                    "message", poll.getMessage()));
                break;
            case CANCELLED:
                ctx.json(Map.of("status", "cancelled", "retry_after_seconds", 1,
                    "message", poll.getMessage()));
                break;
            case NOT_FOUND:
                ctx.status(404).json(Map.of("status", "not_found",
                    "message", poll.getMessage()));
                break;
            case ERROR:
            default:
                ctx.status(500).json(Map.of("status", "error", "message", poll.getMessage()));
                break;
        }
    }

    private List<JavaClass> filterSearchClasses(
        List<JavaClass> allClasses,
        String packageFilter,
        List<String> excludePrefixes
    ) {
        boolean applyPackageFilter = isValidPackageFilter(packageFilter);
        if (!applyPackageFilter && excludePrefixes.isEmpty()) {
            return allClasses;
        }

        List<JavaClass> filteredClasses = new ArrayList<>();
        for (JavaClass cls : allClasses) {
            if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                continue;
            }
            if (!excludePrefixes.isEmpty()) {
                boolean excluded = false;
                for (String prefix : excludePrefixes) {
                    if (cls.getFullName().startsWith(prefix)) {
                        excluded = true;
                        break;
                    }
                }
                if (excluded) {
                    continue;
                }
            }
            filteredClasses.add(cls);
        }
        return filteredClasses;
    }

    SearchExecution executeSearch(
        JadxWrapper wrapper,
        List<JavaClass> allClasses,
        List<JavaClass> filteredClasses,
        String searchTerm,
        Set<SearchLocation> searchLocations,
        boolean collectAllResults,
        int resultsNeeded
    ) {
        final String term = searchTerm.toLowerCase();
        final Set<String> matchedClasses = ConcurrentHashMap.newKeySet();
        final AtomicInteger totalMatches = new AtomicInteger(0);
        final AtomicBoolean cancelled = new AtomicBoolean(false);

        long startTimeMs = System.currentTimeMillis();
        long deadlineNanos = System.nanoTime() + TimeUnit.SECONDS.toNanos(SEARCH_TIMEOUT_SECONDS);
        boolean timedOut = false;
        int batchCount = 0;
        boolean requiresContentSearch = requiresContentSearch(searchLocations);

        // --- Trigram pre-filter ---
        // Three-way result from CodeContentIndex.candidatesForTerm():
        //   non-null non-empty → only these classes can match (fast path)
        //   non-null empty    → term definitively absent from all indexed classes;
        //                       skip indexed classes in fallback, only scan non-indexed large classes
        //   null              → index can't help (disabled / trigram missing); full scan required
        final Set<JavaClass> trigramCandidates;
        final boolean trigramDefinitivelyEmpty;
        if (requiresContentSearch && searchLocations.contains(SearchLocation.CODE)) {
            BitSet candidateBits = CodeContentIndex.candidatesForTerm(term);
            if (candidateBits != null && !candidateBits.isEmpty()) {
                Set<JavaClass> tc = new HashSet<>();
                for (int bit = candidateBits.nextSetBit(0); bit >= 0; bit = candidateBits.nextSetBit(bit + 1)) {
                    JavaClass resolved = CodeContentIndex.resolveClass(bit);
                    if (resolved != null) {
                        tc.add(resolved);
                    }
                }
                trigramCandidates = tc.isEmpty() ? null : tc;
                trigramDefinitivelyEmpty = false;
                if (trigramCandidates != null) {
                    logger.debug("[JAI] Trigram pre-filter: '{}' → {} candidates (down from {} filtered)",
                            term, trigramCandidates.size(), filteredClasses.size());
                }
            } else if (candidateBits != null) {
                // Empty BitSet: all trigrams present in index but intersection is zero.
                // Term is definitively absent from every indexed class — only non-indexed large
                // classes remain as candidates, cutting the fallback scan significantly.
                trigramCandidates = null;
                trigramDefinitivelyEmpty = true;
                logger.debug("[JAI] Trigram pre-filter: '{}' → 0 indexed candidates (definitive); "
                        + "fallback limited to non-indexed classes only", term);
            } else {
                // null: index disabled or a trigram had no entries — full fallback scan required
                trigramCandidates = null;
                trigramDefinitivelyEmpty = false;
            }
        } else {
            trigramCandidates = null;
            trigramDefinitivelyEmpty = false;
        }

        if (collectAllResults && filteredClasses.size() > 100) {
            List<JavaClass> topClasses = new ArrayList<>();
            for (JavaClass cls : filteredClasses) {
                if (!cls.isInner()) {
                    topClasses.add(cls);
                }
            }

            List<List<JavaClass>> batches = wrapper.buildDecompileBatches(topClasses);
            batchCount = batches.size();
            logger.info("JADX AI MCP: Code search '{}' using {} parallel batches", searchTerm, batchCount);

            Set<JavaClass> includedSet = new HashSet<>(filteredClasses);
            List<Future<?>> futures = new ArrayList<>();
            ConcurrentLinkedQueue<JavaClass> contentCandidates = new ConcurrentLinkedQueue<>();

            for (List<JavaClass> batch : batches) {
                Future<?> future = searchExecutor.submit(() -> {
                    for (JavaClass cls : batch) {
                        if (cancelled.get() || Thread.currentThread().isInterrupted()) {
                            return;
                        }
                        if (System.nanoTime() >= deadlineNanos) {
                            cancelled.set(true);
                            return;
                        }
                        if (!includedSet.contains(cls) && !cls.isInner()) {
                            continue;
                        }

                        try {
                            if (classMatchesAnyMetadataLocation(cls, term, searchLocations)) {
                                if (matchedClasses.add(cls.getFullName())) {
                                    int total = totalMatches.incrementAndGet();
                                    if (!collectAllResults && total >= resultsNeeded) {
                                        cancelled.set(true);
                                        return;
                                    }
                                }
                            } else if (requiresContentSearch) {
                                contentCandidates.add(cls);
                            }
                        } catch (Exception ignored) {
                            // Skip failed classes and continue scanning remaining classes.
                        }
                    }
                });
                futures.add(future);
            }

            for (Future<?> future : futures) {
                try {
                    long remainingNanos = deadlineNanos - System.nanoTime();
                    if (remainingNanos <= 0) {
                        timedOut = true;
                        future.cancel(true);
                        continue;
                    }
                    future.get(remainingNanos, TimeUnit.NANOSECONDS);
                } catch (TimeoutException e) {
                    timedOut = true;
                    cancelled.set(true);
                    future.cancel(true);
                } catch (Exception ignored) {
                    // Ignore individual batch failures and keep any partial matches found.
                }
            }

            if (!timedOut && requiresContentSearch) {
                for (JavaClass cls : contentCandidates) {
                    if (cancelled.get()) {
                        break;
                    }
                    if (System.nanoTime() >= deadlineNanos) {
                        timedOut = true;
                        cancelled.set(true);
                        break;
                    }
                    if (trigramCandidates != null && !trigramCandidates.contains(cls)) {
                        continue;
                    }
                    if (trigramDefinitivelyEmpty && CodeContentIndex.isIndexed(cls)) {
                        continue; // Indexed class definitively doesn't contain this term
                    }
                    if (classMatchesAnyContentLocation(cls, term, searchLocations)
                            && matchedClasses.add(cls.getFullName())) {
                        int total = totalMatches.incrementAndGet();
                        if (!collectAllResults && total >= resultsNeeded) {
                            cancelled.set(true);
                            break;
                        }
                    }
                }
            }
        } else {
            for (JavaClass cls : filteredClasses) {
                if (cancelled.get()) {
                    break;
                }
                if (System.nanoTime() >= deadlineNanos) {
                    timedOut = true;
                    break;
                }
                boolean metadataMatched = classMatchesAnyMetadataLocation(cls, term, searchLocations);
                if (metadataMatched) {
                    if (matchedClasses.add(cls.getFullName())) {
                        int total = totalMatches.incrementAndGet();
                        if (!collectAllResults && total >= resultsNeeded) {
                            cancelled.set(true);
                        }
                    }
                } else if (requiresContentSearch) {
                    if (trigramCandidates != null && !trigramCandidates.contains(cls)) {
                        continue;
                    }
                    if (trigramDefinitivelyEmpty && CodeContentIndex.isIndexed(cls)) {
                        continue; // Indexed class definitively doesn't contain this term
                    }
                    if (classMatchesAnyContentLocation(cls, term, searchLocations)
                            && matchedClasses.add(cls.getFullName())) {
                        int total = totalMatches.incrementAndGet();
                        if (!collectAllResults && total >= resultsNeeded) {
                            cancelled.set(true);
                        }
                    }
                }
            }
        }

        long elapsedMs = Math.max(0L, System.currentTimeMillis() - startTimeMs);
        Map<String, Object> searchInfo = new HashMap<>();
        searchInfo.put("total_found", totalMatches.get());
        searchInfo.put("total_classes", allClasses.size());
        searchInfo.put("filtered_classes", filteredClasses.size());
        searchInfo.put("elapsed_seconds", TimeUnit.MILLISECONDS.toSeconds(elapsedMs));
        searchInfo.put("timed_out", timedOut);
        searchInfo.put("parallel_batches", batchCount);
        searchInfo.put("search_locations", searchLocations.toString());
        if (requiresContentSearch && trigramCandidates != null) {
            searchInfo.put("trigram_pre_filter_candidates", trigramCandidates.size());
        }
        if (requiresContentSearch) {
            searchInfo.put("trigram_definitively_empty", trigramDefinitivelyEmpty);
        }
        searchInfo.put("trigram_index_size", CodeContentIndex.trigramCount());
        searchInfo.put("trigram_indexed_classes", CodeContentIndex.indexedClassCount());

        CodeSearchCoordinator.SearchResult result = new CodeSearchCoordinator.SearchResult(
            buildOrderedMatchList(filteredClasses, matchedClasses),
            searchInfo
        );

        logger.info(
            "JADX AI MCP: Search '{}' completed in {}s - found {} matches (batches: {}, timed_out: {})",
            searchTerm,
            TimeUnit.MILLISECONDS.toSeconds(elapsedMs),
            totalMatches.get(),
            batchCount,
            timedOut
        );

        return new SearchExecution(result, elapsedMs, timedOut);
    }

    private boolean classMatchesAnyLocation(
        JavaClass cls,
        String term,
        Set<SearchLocation> searchLocations
    ) {
        return classMatchesAnyMetadataLocation(cls, term, searchLocations)
            || classMatchesAnyContentLocation(cls, term, searchLocations);
    }

    private Map<String, Object> buildSearchResponse(
        CodeSearchCoordinator.SearchResult result,
        int offset,
        int count
    ) {
        return buildSearchResponse(result, offset, count, MatchMode.SUBSTRING);
    }

    private Map<String, Object> buildSearchResponse(
        CodeSearchCoordinator.SearchResult result,
        int offset,
        int count,
        MatchMode matchMode
    ) {
        List<String> matches = result.getMatches();
        List<String> paginatedResults = new ArrayList<>();
        for (int i = offset; i < Math.min(offset + count, matches.size()); i++) {
            paginatedResults.add(matches.get(i));
        }

        Map<String, Object> response = new HashMap<>();
        response.put("type", "class-list");
        response.put("classes", paginatedResults);
        response.put("offset", offset);
        response.put("count", paginatedResults.size());
        response.put("has_more", matches.size() > offset + paginatedResults.size());
        response.put("next_offset", offset + paginatedResults.size());
        response.put("search_info", result.getSearchInfo());
        response.put("match_mode", matchMode.name().toLowerCase());
        return response;
    }

    private void sendCodeSearchBusyResponse(Context ctx, String message, double waitedSeconds) {
        Map<String, Object> busyResponse = new HashMap<>();
        busyResponse.put("error", message);
        busyResponse.put("retry_after", JadxSearchLock.RETRY_AFTER_SECONDS);
        busyResponse.put("busy", true);
        busyResponse.put("lock_held_seconds", JadxSearchLock.getLockHeldSeconds());
        if (waitedSeconds > 0.0) {
            busyResponse.put("waited_seconds", waitedSeconds);
        }
        ctx.status(503).json(busyResponse);
    }

    void sendSearchDecompilationBusyResponse(Context ctx) {
        ctx.status(503).json(Map.of(
            "error", SEARCH_DECOMPILATION_BUSY_MESSAGE,
            "retry_after", JadxSearchLock.RETRY_AFTER_SECONDS
        ));
    }

    static final class SearchExecution {
        private final CodeSearchCoordinator.SearchResult result;
        private final long elapsedMs;
        private final boolean timedOut;

        SearchExecution(
            CodeSearchCoordinator.SearchResult result,
            long elapsedMs,
            boolean timedOut
        ) {
            this.result = result;
            this.elapsedMs = elapsedMs;
            this.timedOut = timedOut;
        }

        public CodeSearchCoordinator.SearchResult getResult() {
            return result;
        }

        public long getElapsedMs() {
            return elapsedMs;
        }

        public boolean isTimedOut() {
            return timedOut;
        }
    }

    /**
     * Variant of {@link #executeSearch} that applies {@code matchMode} for metadata
     * searches (class/method/field name). Code searches always use substring matching.
     */
    SearchExecution executeSearchWithMatchMode(
        JadxWrapper wrapper,
        List<JavaClass> allClasses,
        List<JavaClass> filteredClasses,
        String searchTerm,
        Set<SearchLocation> searchLocations,
        boolean collectAllResults,
        int resultsNeeded,
        MatchMode matchMode,
        Pattern compiledRegex
    ) {
        if (matchMode == null || matchMode == MatchMode.SUBSTRING) {
            // Default path — delegate to the existing method unchanged.
            return executeSearch(wrapper, allClasses, filteredClasses, searchTerm,
                searchLocations, collectAllResults, resultsNeeded);
        }

        // For non-default modes apply custom name matching for metadata searches.
        final String term = searchTerm.toLowerCase();
        final java.util.Set<String> matchedClasses = java.util.concurrent.ConcurrentHashMap.newKeySet();
        final AtomicInteger totalMatches = new AtomicInteger(0);
        final AtomicBoolean cancelled = new AtomicBoolean(false);

        long startTimeMs = System.currentTimeMillis();
        long deadlineNanos = System.nanoTime() + TimeUnit.SECONDS.toNanos(SEARCH_TIMEOUT_SECONDS);
        boolean timedOut = false;

        for (JavaClass cls : filteredClasses) {
            if (cancelled.get()) break;
            if (System.nanoTime() >= deadlineNanos) {
                timedOut = true;
                break;
            }
            try {
                boolean matched = classMatchesInLocationWithMode(cls, searchTerm, term, searchLocations, matchMode, compiledRegex);
                if (matched && matchedClasses.add(cls.getFullName())) {
                    int total = totalMatches.incrementAndGet();
                    if (!collectAllResults && total >= resultsNeeded) {
                        cancelled.set(true);
                    }
                }
            } catch (Exception ignored) {
                // Skip failed classes
            }
        }

        long elapsedMs = Math.max(0L, System.currentTimeMillis() - startTimeMs);
        Map<String, Object> searchInfo = new HashMap<>();
        searchInfo.put("total_found", totalMatches.get());
        searchInfo.put("total_classes", allClasses.size());
        searchInfo.put("filtered_classes", filteredClasses.size());
        searchInfo.put("elapsed_seconds", TimeUnit.MILLISECONDS.toSeconds(elapsedMs));
        searchInfo.put("timed_out", timedOut);
        searchInfo.put("parallel_batches", 0);
        searchInfo.put("search_locations", searchLocations.toString());

        CodeSearchCoordinator.SearchResult result = new CodeSearchCoordinator.SearchResult(
            buildOrderedMatchList(filteredClasses, matchedClasses),
            searchInfo
        );
        return new SearchExecution(result, elapsedMs, timedOut);
    }

    /**
     * Checks whether {@code cls} matches {@code searchTerm} in any of the given
     * metadata locations using the specified {@code matchMode}.
     */
    private boolean classMatchesInLocationWithMode(
        JavaClass cls,
        String searchTerm,
        String termLower,
        Set<SearchLocation> searchLocations,
        MatchMode matchMode,
        Pattern compiledRegex
    ) {
        for (SearchLocation location : searchLocations) {
            if (location == SearchLocation.CODE || location == SearchLocation.COMMENT) {
                continue; // code searches always use substring; handled by existing path
            }
            switch (location) {
                case CLASS_NAME:
                    if (nameMatches(cls.getName(), searchTerm, matchMode, compiledRegex)) return true;
                    break;
                case METHOD_NAME:
                    for (JadxApiAdapter.MethodInfoSnapshot ms : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                        if (nameMatches(ms.getName(), searchTerm, matchMode, compiledRegex)) return true;
                    }
                    break;
                case FIELD_NAME:
                    for (JadxApiAdapter.FieldInfoSnapshot fs : JadxApiAdapter.getDeclaredFieldInfos(cls)) {
                        if (nameMatches(fs.getName(), searchTerm, matchMode, compiledRegex)) return true;
                    }
                    break;
                default:
                    break;
            }
        }
        return false;
    }

    /**
     * Check if a class matches the search term in the specified location.
     * For CODE and COMMENT, this triggers decompilation.
     */
    private boolean classMatchesInLocation(JavaClass cls, String term, SearchLocation location) {
        try {
            switch (location) {
                case CLASS_NAME:
                    return cls.getName().toLowerCase().contains(term);

                case METHOD_NAME:
                    for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                        if (methodSnapshot.getName().toLowerCase().contains(term)) {
                            return true;
                        }
                    }
                    return false;

                case FIELD_NAME:
                    for (JadxApiAdapter.FieldInfoSnapshot fieldSnapshot : JadxApiAdapter.getDeclaredFieldInfos(cls)) {
                        if (fieldSnapshot.getName().toLowerCase().contains(term)) {
                            return true;
                        }
                    }
                    return false;

                default:
                    return false;
            }
        } catch (Exception e) {
            return false;
        }
    }

    private boolean classMatchesAnyMetadataLocation(
        JavaClass cls,
        String term,
        Set<SearchLocation> searchLocations
    ) {
        for (SearchLocation location : searchLocations) {
            if (location == SearchLocation.CODE || location == SearchLocation.COMMENT) {
                continue;
            }
            if (classMatchesInLocation(cls, term, location)) {
                return true;
            }
        }
        return false;
    }

    private boolean classMatchesAnyContentLocation(
        JavaClass cls,
        String term,
        Set<SearchLocation> searchLocations
    ) {
        if (!requiresContentSearch(searchLocations)) {
            return false;
        }

        try {
            // Fast path: code already cached in JADX ICodeCache — no lock needed
            String cached = ClassCacheManager.getCachedCodeDirect(cls);
            String normalizedCode;

            if (cached != null) {
                normalizedCode = cached.toLowerCase();
                CodeContentIndex.index(cls, normalizedCode);
            } else {
                // Must decompile. Acquire write lock per-class (not per-search) so that
                // a single stuck class cannot block all requests for multiple minutes.
                // A watchdog interrupts the search thread if getCode() stalls.
                Thread searchThread = Thread.currentThread();
                ScheduledFuture<?> watchdog = DECOMPILE_WATCHDOG.schedule(
                    () -> {
                        logger.warn("[JAI] getCode() exceeded {}s for {}, interrupting search thread",
                            PER_CLASS_DECOMPILE_TIMEOUT_SECONDS, cls.getFullName());
                        searchThread.interrupt();
                    },
                    PER_CLASS_DECOMPILE_TIMEOUT_SECONDS,
                    TimeUnit.SECONDS
                );

                if (!JadxSearchLock.tryAcquire(PER_CLASS_DECOMPILE_TIMEOUT_SECONDS)) {
                    watchdog.cancel(false);
                    return false;
                }

                try {
                    normalizedCode = ClassCacheManager.getCodeAndIndex(cls);
                } finally {
                    JadxSearchLock.release();
                    watchdog.cancel(false);
                    Thread.interrupted(); // clear flag if watchdog fired
                }
            }

            if (normalizedCode == null) {
                return false;
            }

            if (searchLocations.contains(SearchLocation.CODE) && normalizedCode.contains(term)) {
                return true;
            }
            if (searchLocations.contains(SearchLocation.COMMENT)) {
                // getCachedCodeDirect is safe here: getCode() was already called above
                String originalCode = ClassCacheManager.getCachedCodeDirect(cls);
                if (originalCode != null) {
                    return matchesCommentSearch(originalCode, term);
                }
            }
            return false;
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * Returns {@code true} when {@code term} appears inside a comment block in {@code code}.
     */
    private boolean matchesCommentSearch(String code, String term) {
        return CodeSearchCoordinator.matchesCommentContent(code, term);
    }

    private boolean requiresContentSearch(Set<SearchLocation> searchLocations) {
        return searchLocations.contains(SearchLocation.CODE)
            || searchLocations.contains(SearchLocation.COMMENT);
    }

    private List<String> buildOrderedMatchList(List<JavaClass> filteredClasses, Set<String> matchedClasses) {
        List<String> orderedMatches = new ArrayList<>();
        for (JavaClass cls : filteredClasses) {
            String fullName = cls.getFullName();
            if (matchedClasses.contains(fullName)) {
                orderedMatches.add(fullName);
            }
        }
        return orderedMatches;
    }

    /**
     * Parse the search_in parameter into a set of SearchLocation enums.
     * Accepts lowercase values like "class,method,code" for URL-friendly usage.
     */
    private Set<SearchLocation> parseSearchLocations(String searchIn) {
        Set<SearchLocation> locations = EnumSet.noneOf(SearchLocation.class);

        if (searchIn == null || searchIn.trim().isEmpty()) {
            locations.add(SearchLocation.CODE);
            return locations;
        }

        String[] parts = searchIn.toLowerCase().split(",");
        for (String part : parts) {
            String trimmed = part.trim();
            SearchLocation loc = SEARCH_LOCATION_MAP.get(trimmed);
            if (loc != null) {
                locations.add(loc);
            } else {
                logger.warn("JADX AI MCP: Invalid search location '{}', ignoring. Valid values: {}",
                        trimmed, SEARCH_LOCATION_MAP.keySet());
            }
        }

        if (locations.isEmpty()) {
            locations.add(SearchLocation.CODE);
        }

        return locations;
    }

    /**
     * Check if package filter is valid and should be applied.
     * Returns false for jadx obfuscated package names (p000, p001, etc.)
     */
    private boolean isValidPackageFilter(String packageFilter) {
        if (packageFilter == null || packageFilter.trim().isEmpty()) {
            return false;
        }
        if (packageFilter.equals("defpackage")) {
            return false;
        }

        String firstPart = packageFilter.split("\\.")[0];
        if (OBFUSCATED_PACKAGE_PATTERN.matcher(firstPart).matches()) {
            return false;
        }

        return true;
    }

    /**
     * Check if a class belongs to the specified package.
     */
    private boolean matchesPackageFilter(JavaClass cls, String packageFilter) {
        if (packageFilter == null || packageFilter.trim().isEmpty()) {
            return true;
        }
        String fullName = cls.getFullName();
        return fullName.startsWith(packageFilter + ".") || fullName.equals(packageFilter);
    }

    /**
     * Search for keyword in the specified location.
     */
    private Set<JavaClass> searchInLocation(List<JavaClass> allClasses,
            String term, SearchLocation location,
            String packageFilter, boolean applyPackageFilter) {
        switch (location) {
            case CLASS_NAME:
                return searchByClassName(allClasses, term, packageFilter, applyPackageFilter);
            case METHOD_NAME:
                return searchByMethodName(allClasses, term, packageFilter, applyPackageFilter);
            case FIELD_NAME:
                return searchByFieldName(allClasses, term, packageFilter, applyPackageFilter);
            case CODE:
                return searchByCode(allClasses, term, packageFilter, applyPackageFilter);
            case COMMENT:
                return searchByComment(allClasses, term, packageFilter, applyPackageFilter);
            default:
                return new HashSet<>();
        }
    }

    private Set<JavaClass> searchByClassName(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        return allClasses.parallelStream()
                .filter(cls -> {
                    if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                        return false;
                    }
                    String className = cls.getName().toLowerCase();
                    return className.contains(term);
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    private Set<JavaClass> searchByMethodName(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        return allClasses.parallelStream()
                .filter(cls -> {
                    if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                        return false;
                    }
                    for (JadxApiAdapter.MethodInfoSnapshot methodSnapshot : JadxApiAdapter.getDeclaredMethodInfos(cls)) {
                        String mthName = methodSnapshot.getName().toLowerCase();
                        if (mthName.contains(term)) {
                            return true;
                        }
                        if (methodSnapshot.isConstructor()) {
                            String classSimpleName = cls.getName().toLowerCase();
                            if (classSimpleName.contains(term)) {
                                return true;
                            }
                        }
                    }
                    return false;
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    private Set<JavaClass> searchByFieldName(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        return allClasses.parallelStream()
                .filter(cls -> {
                    if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                        return false;
                    }
                    for (JadxApiAdapter.FieldInfoSnapshot fieldSnapshot : JadxApiAdapter.getDeclaredFieldInfos(cls)) {
                        if (fieldSnapshot.getName().toLowerCase().contains(term)) {
                            return true;
                        }
                    }
                    return false;
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    /**
     * Search classes by code containing the keyword.
     * Uses sequential stream to avoid JADX internal state race conditions.
     */
    private Set<JavaClass> searchByCode(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        return allClasses.stream()
                .filter(cls -> {
                    try {
                        if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                            return false;
                        }
                        String code = cls.getCode();
                        return code != null && code.toLowerCase().contains(term);
                    } catch (Exception e) {
                        return false;
                    }
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    private Set<JavaClass> searchByComment(List<JavaClass> allClasses, String term,
            String packageFilter, boolean applyPackageFilter) {
        return allClasses.parallelStream()
                .filter(cls -> {
                    try {
                        if (applyPackageFilter && !matchesPackageFilter(cls, packageFilter)) {
                            return false;
                        }
                        String code = cls.getCode();
                        if (code == null) {
                            return false;
                        }
                        return CodeSearchCoordinator.matchesCommentContent(code, term);
                    } catch (Exception e) {
                        return false;
                    }
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }
}
