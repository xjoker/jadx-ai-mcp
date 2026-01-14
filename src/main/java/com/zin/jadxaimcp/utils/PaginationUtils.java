package com.zin.jadxaimcp.utils;

import io.javalin.http.Context;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;
import java.util.prefs.Preferences;
import java.util.function.Function;

// Utility class for handling pagination across different MCP tools
public class PaginationUtils {

    private static final Logger logger = LoggerFactory.getLogger(PaginationUtils.class);

    // Configuration constants
    public final int DEFAULT_PAGE_SIZE = 100;
    public final int MAX_PAGE_SIZE = 10000;
    public final int MAX_OFFSET = 1000000;

    /**
     * Helper method to parse integer query parameters with a default value.
     */
    public int getIntParam(Context ctx, String paramName, int defaultValue) {
        String param = ctx.queryParam(paramName);
        if (param == null || param.isEmpty()) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(param.trim());
        } catch (NumberFormatException e) {
            logger.warn("Invalid integer parameter '{}': '{}', using default: {}", paramName, param, defaultValue);
            return defaultValue;
        }
    }

    /**
     * @param ctx The HTTP request context containing pagination parameters
     * @param allItems The complete list of items to paginate
     * @param dataType A string identifying the type of data being paginated
     * @param itemsKey The key name for the items array in the response JSON
     * @return Map The paginated response with metadata
     * @throws PaginationException If pagination parameters are invalid
     * 
     * This method handles pagination for endpoints with default string transformation.
     * It delegates to the overloaded method with item.toString() as the transformer.
     * 
     * This is a convenience method for simple string-based pagination.
     */
    public <T> Map<String, Object> handlePagination(
            Context ctx,
            List<T> allItems,
            String dataType,
            String itemsKey) throws PaginationException {

        return handlePagination(ctx, allItems, dataType, itemsKey, item -> item.toString());
    }

    /**
     * @param ctx The HTTP request context containing pagination parameters
     * @param allItems The complete list of items to paginate
     * @param dataType A string identifying the type of data being paginated
     * @param itemsKey The key name for the items array in the response JSON
     * @param itemTransformer A function to transform each item before including in response
     * @return Map The paginated response with comprehensive metadata
     * @throws PaginationException If pagination parameters are invalid
     * 
     * This method provides generic pagination for any list of items.
     * 1. It parses and validates pagination parameters (offset, limit/count)
     * 2. It calculates pagination boundaries (start, end, hasMore)
     * 3. It transforms items using the provided function
     * 4. It builds a comprehensive response including:
     *    - Paginated data subset
     *    - Total count and current page info
     *    - Navigation helpers (next_offset, prev_offset)
     *    - Page calculations (current_page, total_pages)
     * 
     * Supports both 'limit' and 'count' parameters for backward compatibility.
     */
    public <T> Map<String, Object> handlePagination(
            Context ctx,
            List<T> allItems,
            String dataType,
            String itemsKey,
            Function<T, Object> itemTransformer) throws PaginationException {

        if (allItems == null) {
            allItems = new ArrayList<>();
        }

        int totalItems = allItems.size();

        // Parse pagination parameters
        PaginationParams params = parsePaginationParams(ctx, totalItems);

        // Calculate bounds
        PaginationBounds bounds = calculatePaginationBounds(params, totalItems);

        // Transform and extract paginated subset
        List<Object> transformedItems = allItems.subList(bounds.startIndex, bounds.endIndex)
                .stream()
                .map(itemTransformer)
                .collect(Collectors.toList());

        // Build response
        return buildPaginationResponse(transformedItems, params, bounds, totalItems, dataType, itemsKey);
    }

    /**
     * @param ctx The HTTP request context
     * @param totalItems The total number of items in the dataset
     * @return PaginationParams Object containing validated pagination parameters
     * @throws PaginationException If parameters are invalid or out of bounds
     * 
     * This method parses and validates pagination parameters from the request.
     * 1. It extracts 'offset', 'limit', and 'count' (legacy) query parameters
     * 2. It validates offset is non-negative and within MAX_OFFSET (1,000,000)
     * 3. It validates limit is non-negative and within MAX_PAGE_SIZE (10,000)
     * 4. It determines effective limit:
     *    - If no limit specified: uses DEFAULT_PAGE_SIZE (100) or remaining items
     *    - If limit is 0: returns all remaining items from offset
     *    - Otherwise: uses requested limit
     * 5. It ensures the effective limit doesn't exceed available items
     * 
     * The 'count' parameter is supported for backward compatibility.
     */
    private PaginationParams parsePaginationParams(Context ctx, int totalItems) throws PaginationException {
        String offsetParam = ctx.queryParam("offset");
        String limitParam = ctx.queryParam("limit");
        String countParam = ctx.queryParam("count"); // Legacy support

        // Use 'limit' if provided, otherwise fall back to 'count'
        String pageSizeParam = limitParam != null ? limitParam : countParam;

        int offset = 0;
        int requestedLimit = 0;
        boolean hasCustomLimit = pageSizeParam != null && !pageSizeParam.isEmpty();

        // Parse offset
        if (offsetParam != null && !offsetParam.isEmpty()) {
            try {
                offset = Integer.parseInt(offsetParam.trim());
                if (offset < 0) {
                    throw new PaginationException("Offset must be non-negative, got: " + offset);
                }
                if (offset > MAX_OFFSET) {
                    throw new PaginationException("Offset too large, maximum: " + MAX_OFFSET);
                }
            } catch (NumberFormatException e) {
                throw new PaginationException("Invalid offset format: '" + offsetParam + "'");
            }
        }

        // Parse limit/count
        if (hasCustomLimit) {
            try {
                requestedLimit = Integer.parseInt(pageSizeParam.trim());
                if (requestedLimit < 0) {
                    throw new PaginationException("Limit must be non-negative, got: " + requestedLimit);
                }
                if (requestedLimit > MAX_PAGE_SIZE) {
                    throw new PaginationException("Limit too large, maximum: " + MAX_PAGE_SIZE);
                }
            } catch (NumberFormatException e) {
                throw new PaginationException("Invalid limit format: '" + pageSizeParam + "'");
            }
        }

        // Determine effective limit
        int effectiveLimit;
        if (hasCustomLimit) {
            effectiveLimit = requestedLimit == 0 ? Math.max(0, totalItems - offset) : requestedLimit;
        } else {
            effectiveLimit = Math.min(DEFAULT_PAGE_SIZE, Math.max(0, totalItems - offset));
        }

        effectiveLimit = Math.max(0, Math.min(effectiveLimit, totalItems - offset));

        return new PaginationParams(offset, effectiveLimit, requestedLimit, hasCustomLimit);
    }

    /**
     * @param params The validated pagination parameters
     * @param totalItems The total number of items in the dataset
     * @return PaginationBounds Object containing calculated boundaries
     * 
     * This method calculates the actual boundaries for data extraction.
     * 1. It checks if offset exceeds total items (returns empty bounds)
     * 2. It calculates startIndex from offset
     * 3. It calculates endIndex ensuring it doesn't exceed total items
     * 4. It determines if there are more items beyond the current page
     * 5. It calculates the next offset for navigation (or -1 if no more items)
     * 
     * Returns empty bounds (0, 0) when offset is beyond available data.
     */
    private PaginationBounds calculatePaginationBounds(PaginationParams params, int totalItems) {
        if (params.offset >= totalItems) {
            return new PaginationBounds(0, 0, false, totalItems);
        }

        int startIndex = params.offset;
        int endIndex = Math.min(startIndex + params.limit, totalItems);
        boolean hasMore = endIndex < totalItems;
        int nextOffset = hasMore ? endIndex : -1;

        return new PaginationBounds(startIndex, endIndex, hasMore, nextOffset);
    }

    /**
     * @param data The paginated data subset
     * @param params The pagination parameters used
     * @param bounds The calculated pagination boundaries
     * @param totalItems The total number of items in the dataset
     * @param dataType A string identifying the type of data
     * @param itemsKey The key name for the items array in the response
     * @return Map The comprehensive pagination response
     * 
     * This method constructs a complete pagination response with metadata.
     * 1. It includes the data type and paginated items
     * 2. It adds pagination metadata:
     *    - total: Total items in dataset
     *    - offset: Current offset position
     *    - limit: Items per page
     *    - count: Actual items returned in this page
     *    - has_more: Boolean indicating more pages exist
     * 3. It adds navigation helpers:
     *    - next_offset: Offset for next page (if has_more)
     *    - prev_offset: Offset for previous page (if offset > 0)
     * 4. It adds page calculations (if limit > 0):
     *    - current_page: Current page number (1-indexed)
     *    - total_pages: Total number of pages
     *    - page_size: Items per page
     * 5. It includes requested_count for legacy compatibility
     * 
     * This provides comprehensive information for client-side pagination controls.
     */
    private Map<String, Object> buildPaginationResponse(
            List<Object> data,
            PaginationParams params,
            PaginationBounds bounds,
            int totalItems,
            String dataType,
            String itemsKey) {

        Map<String, Object> result = new HashMap<>();

        // Core data
        result.put("type", dataType);
        result.put(itemsKey, data);

        // Pagination metadata
        Map<String, Object> pagination = new HashMap<>();
        pagination.put("total", totalItems);
        pagination.put("offset", params.offset);
        pagination.put("limit", params.limit);
        pagination.put("count", data.size());
        pagination.put("has_more", bounds.hasMore);

        // Navigation helpers
        if (bounds.hasMore) {
            pagination.put("next_offset", bounds.nextOffset);
        }

        if (params.offset > 0) {
            int prevOffset = Math.max(0, params.offset - params.limit);
            pagination.put("prev_offset", prevOffset);
        }

        // Page calculations
        if (params.limit > 0) {
            int currentPage = (params.offset / params.limit) + 1;
            int totalPages = (int) Math.ceil((double) totalItems / params.limit);
            pagination.put("current_page", currentPage);
            pagination.put("total_pages", totalPages);
            pagination.put("page_size", params.limit);
        }

        // Legacy compatibility
        result.put("requested_count", params.requestedLimit);
        result.put("pagination", pagination);

        return result;
    }

    // Helper classes remain the same as before
    private class PaginationParams {
        final int offset;
        final int limit;
        final int requestedLimit;
        final boolean hasCustomLimit;

        PaginationParams(int offset, int limit, int requestedLimit, boolean hasCustomLimit) {
            this.offset = offset;
            this.limit = limit;
            this.requestedLimit = requestedLimit;
            this.hasCustomLimit = hasCustomLimit;
        }
    }

    private class PaginationBounds {
        final int startIndex;
        final int endIndex;
        final boolean hasMore;
        final int nextOffset;

        PaginationBounds(int startIndex, int endIndex, boolean hasMore, int nextOffset) {
            this.startIndex = startIndex;
            this.endIndex = endIndex;
            this.hasMore = hasMore;
            this.nextOffset = nextOffset;
        }
    }

    public class PaginationException extends Exception {
        public PaginationException(String message) {
            super(message);
        }
    }
}