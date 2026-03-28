package com.zin.jadxaimcp.utils;

import io.javalin.http.Context;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

/**
 * 单元测试 - PaginationUtils 核心分页逻辑。
 * 使用 Mockito mock Javalin Context，无需启动 HTTP 服务。
 */
class PaginationUtilsTest {

    private PaginationUtils pagination;
    private Context ctx;

    @BeforeEach
    void setUp() {
        pagination = new PaginationUtils();
        ctx = Mockito.mock(Context.class);
    }

    // 辅助方法：设置 query 参数
    private void mockQueryParams(String offset, String limit, String count) {
        when(ctx.queryParam(eq("offset"))).thenReturn(offset);
        when(ctx.queryParam(eq("limit"))).thenReturn(limit);
        when(ctx.queryParam(eq("count"))).thenReturn(count);
    }

    private List<String> buildList(int size) {
        String[] arr = new String[size];
        for (int i = 0; i < size; i++) {
            arr[i] = "item" + i;
        }
        return Arrays.asList(arr);
    }

    // -------------------------------------------------------------------------
    // 正常分页
    // -------------------------------------------------------------------------

    @Test
    void normalPagination_firstPage_returnItemsAndMeta() throws PaginationUtils.PaginationException {
        mockQueryParams(null, "10", null);
        List<String> items = buildList(50);

        Map<String, Object> result = pagination.handlePagination(ctx, items, "test", "items");

        assertEquals("test", result.get("type"));
        @SuppressWarnings("unchecked")
        List<Object> returned = (List<Object>) result.get("items");
        assertEquals(10, returned.size());

        @SuppressWarnings("unchecked")
        Map<String, Object> paginationMeta = (Map<String, Object>) result.get("pagination");
        assertEquals(50, paginationMeta.get("total"));
        assertEquals(0, paginationMeta.get("offset"));
        assertEquals(true, paginationMeta.get("has_more"));
        assertEquals(10, paginationMeta.get("next_offset"));
    }

    @Test
    void normalPagination_withOffset_returnsCorrectSlice() throws PaginationUtils.PaginationException {
        mockQueryParams("20", "10", null);
        List<String> items = buildList(50);

        Map<String, Object> result = pagination.handlePagination(ctx, items, "test", "items");

        @SuppressWarnings("unchecked")
        List<Object> returned = (List<Object>) result.get("items");
        assertEquals(10, returned.size());
        assertEquals("item20", returned.get(0).toString());

        @SuppressWarnings("unchecked")
        Map<String, Object> paginationMeta = (Map<String, Object>) result.get("pagination");
        assertEquals(20, paginationMeta.get("offset"));
        assertEquals(30, paginationMeta.get("next_offset"));
    }

    @Test
    void lastPage_hasMoreFalse() throws PaginationUtils.PaginationException {
        mockQueryParams("45", "10", null);
        List<String> items = buildList(50);

        Map<String, Object> result = pagination.handlePagination(ctx, items, "test", "items");

        @SuppressWarnings("unchecked")
        List<Object> returned = (List<Object>) result.get("items");
        assertEquals(5, returned.size()); // 只剩 5 个

        @SuppressWarnings("unchecked")
        Map<String, Object> paginationMeta = (Map<String, Object>) result.get("pagination");
        assertEquals(false, paginationMeta.get("has_more"));
        assertFalse(paginationMeta.containsKey("next_offset"));
    }

    // -------------------------------------------------------------------------
    // 边界：limit=0（返回全部剩余）
    // -------------------------------------------------------------------------

    @Test
    void limitZero_returnsAllRemainingItems() throws PaginationUtils.PaginationException {
        mockQueryParams("10", "0", null);
        List<String> items = buildList(30);

        Map<String, Object> result = pagination.handlePagination(ctx, items, "test", "items");

        @SuppressWarnings("unchecked")
        List<Object> returned = (List<Object>) result.get("items");
        assertEquals(20, returned.size()); // 30 - offset 10 = 20
    }

    // -------------------------------------------------------------------------
    // 边界：负数 offset 应抛异常
    // -------------------------------------------------------------------------

    @Test
    void negativeOffset_throwsPaginationException() {
        mockQueryParams("-1", null, null);
        List<String> items = buildList(10);

        assertThrows(PaginationUtils.PaginationException.class,
            () -> pagination.handlePagination(ctx, items, "test", "items"));
    }

    // -------------------------------------------------------------------------
    // 边界：offset 超过列表长度
    // -------------------------------------------------------------------------

    @Test
    void offsetBeyondTotal_returnsEmptyItems() throws PaginationUtils.PaginationException {
        mockQueryParams("100", "10", null);
        List<String> items = buildList(10);

        Map<String, Object> result = pagination.handlePagination(ctx, items, "test", "items");

        @SuppressWarnings("unchecked")
        List<Object> returned = (List<Object>) result.get("items");
        assertTrue(returned.isEmpty());

        @SuppressWarnings("unchecked")
        Map<String, Object> paginationMeta = (Map<String, Object>) result.get("pagination");
        assertEquals(false, paginationMeta.get("has_more"));
    }

    // -------------------------------------------------------------------------
    // 空列表
    // -------------------------------------------------------------------------

    @Test
    void emptyList_returnsEmptyResultWithZeroTotal() throws PaginationUtils.PaginationException {
        mockQueryParams(null, null, null);
        List<String> items = Collections.emptyList();

        Map<String, Object> result = pagination.handlePagination(ctx, items, "test", "items");

        @SuppressWarnings("unchecked")
        List<Object> returned = (List<Object>) result.get("items");
        assertTrue(returned.isEmpty());

        @SuppressWarnings("unchecked")
        Map<String, Object> paginationMeta = (Map<String, Object>) result.get("pagination");
        assertEquals(0, paginationMeta.get("total"));
        assertEquals(false, paginationMeta.get("has_more"));
    }

    @Test
    void nullList_treatedAsEmptyList() throws PaginationUtils.PaginationException {
        mockQueryParams(null, null, null);

        // null 列表不应抛出 NPE
        Map<String, Object> result = pagination.handlePagination(ctx, null, "test", "items");

        @SuppressWarnings("unchecked")
        List<Object> returned = (List<Object>) result.get("items");
        assertTrue(returned.isEmpty());
    }

    // -------------------------------------------------------------------------
    // count=0（等同于 limit=0）
    // -------------------------------------------------------------------------

    @Test
    void countParamZero_returnsAllItems() throws PaginationUtils.PaginationException {
        mockQueryParams(null, null, "0");
        List<String> items = buildList(15);

        Map<String, Object> result = pagination.handlePagination(ctx, items, "test", "items");

        @SuppressWarnings("unchecked")
        List<Object> returned = (List<Object>) result.get("items");
        assertEquals(15, returned.size());
    }

    // -------------------------------------------------------------------------
    // 分页元数据：页码计算
    // -------------------------------------------------------------------------

    @Test
    void pageCalculation_isCorrect() throws PaginationUtils.PaginationException {
        mockQueryParams("10", "10", null);
        List<String> items = buildList(50);

        Map<String, Object> result = pagination.handlePagination(ctx, items, "test", "items");

        @SuppressWarnings("unchecked")
        Map<String, Object> paginationMeta = (Map<String, Object>) result.get("pagination");
        assertEquals(2, paginationMeta.get("current_page")); // offset=10, limit=10 => page 2
        assertEquals(5, paginationMeta.get("total_pages"));  // 50 / 10 = 5
        // prev_offset = max(0, offset - limit) = max(0, 10-10) = 0
        assertEquals(0, paginationMeta.get("prev_offset"));
    }

    // -------------------------------------------------------------------------
    // item transformer
    // -------------------------------------------------------------------------

    @Test
    void itemTransformer_isApplied() throws PaginationUtils.PaginationException {
        mockQueryParams(null, "3", null);
        List<Integer> items = Arrays.asList(1, 2, 3, 4, 5);

        Map<String, Object> result = pagination.handlePagination(ctx, items, "numbers", "values",
            n -> n * 10);

        @SuppressWarnings("unchecked")
        List<Object> returned = (List<Object>) result.get("values");
        assertEquals(3, returned.size());
        assertEquals(10, returned.get(0));
        assertEquals(20, returned.get(1));
        assertEquals(30, returned.get(2));
    }
}
