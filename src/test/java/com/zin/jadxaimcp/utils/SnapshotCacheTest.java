package com.zin.jadxaimcp.utils;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 单元测试 — JadxApiAdapter 快照缓存逻辑。
 *
 * JavaClass 是 final 类，无法在没有完整 JADX 环境的情况下实例化或 mock，
 * 因此测试集中于：
 * 1. null 防护：null 入参返回空集合，不抛异常。
 * 2. 返回列表不可变性：返回的 List 不支持 add 操作。
 * 3. invalidateSnapshots(null) 不抛异常。
 * 4. clearAllSnapshotCaches() 不抛异常。
 */
class SnapshotCacheTest {

    @BeforeEach
    void clearCaches() {
        JadxApiAdapter.clearAllSnapshotCaches();
    }

    // ------------------------------------------------------------------
    // getDeclaredMethodInfos — null guard
    // ------------------------------------------------------------------

    @Test
    void getDeclaredMethodInfos_nullClass_returnsEmptyList() {
        List<JadxApiAdapter.MethodInfoSnapshot> result = JadxApiAdapter.getDeclaredMethodInfos(null);
        assertNotNull(result);
        assertTrue(result.isEmpty());
    }

    @Test
    void getDeclaredFieldInfos_nullClass_returnsEmptyList() {
        List<JadxApiAdapter.FieldInfoSnapshot> result = JadxApiAdapter.getDeclaredFieldInfos(null);
        assertNotNull(result);
        assertTrue(result.isEmpty());
    }

    // ------------------------------------------------------------------
    // Returned list must be unmodifiable
    // ------------------------------------------------------------------

    @Test
    void getDeclaredMethodInfos_returnedList_isUnmodifiable() {
        List<JadxApiAdapter.MethodInfoSnapshot> result = JadxApiAdapter.getDeclaredMethodInfos(null);
        assertThrows(UnsupportedOperationException.class,
                () -> result.add(null),
                "Returned list should be unmodifiable");
    }

    @Test
    void getDeclaredFieldInfos_returnedList_isUnmodifiable() {
        List<JadxApiAdapter.FieldInfoSnapshot> result = JadxApiAdapter.getDeclaredFieldInfos(null);
        assertThrows(UnsupportedOperationException.class,
                () -> result.add(null),
                "Returned list should be unmodifiable");
    }

    // ------------------------------------------------------------------
    // invalidateSnapshots — null safety
    // ------------------------------------------------------------------

    @Test
    void invalidateSnapshots_nullClass_doesNotThrow() {
        assertDoesNotThrow(() -> JadxApiAdapter.invalidateSnapshots(null));
    }

    @Test
    void invalidateSnapshots_nullTwice_doesNotThrow() {
        assertDoesNotThrow(() -> {
            JadxApiAdapter.invalidateSnapshots(null);
            JadxApiAdapter.invalidateSnapshots(null);
        });
    }

    // ------------------------------------------------------------------
    // clearAllSnapshotCaches — must not throw even when already empty
    // ------------------------------------------------------------------

    @Test
    void clearAllSnapshotCaches_emptyState_doesNotThrow() {
        assertDoesNotThrow(() -> JadxApiAdapter.clearAllSnapshotCaches());
    }

    @Test
    void clearAllSnapshotCaches_calledTwice_doesNotThrow() {
        assertDoesNotThrow(() -> {
            JadxApiAdapter.clearAllSnapshotCaches();
            JadxApiAdapter.clearAllSnapshotCaches();
        });
    }
}
