package com.zin.jadxaimcp.utils;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Global lock for JADX search and decompilation operations.
 * 
 * JADX internal state is not thread-safe for concurrent decompilation.
 * This singleton lock ensures that only one search/decompilation operation
 * runs at a time across all route handlers, preventing state corruption
 * and intermittent empty results.
 * 
 * Usage (fast-fail pattern):
 * <pre>
 * if (!JadxSearchLock.tryAcquire()) {
 *     ctx.status(503).json(Map.of(
 *         "error", "Search operation in progress",
 *         "retry_after", 10
 *     ));
 *     return;
 * }
 * try {
 *     // search/decompilation code
 * } finally {
 *     JadxSearchLock.release();
 * }
 * </pre>
 *
 * @author JADX AI MCP Team
 */
public final class JadxSearchLock {
    
    // Singleton ReentrantLock shared by all routes
    private static final ReentrantLock LOCK = new ReentrantLock();
    
    // Recommended retry interval in seconds
    public static final int RETRY_AFTER_SECONDS = 10;
    
    private JadxSearchLock() {
        // Prevent instantiation
    }
    
    /**
     * Try to acquire the lock immediately (non-blocking).
     * Use this for fast-fail pattern.
     * 
     * @return true if lock acquired, false if busy
     */
    public static boolean tryAcquire() {
        return LOCK.tryLock();
    }
    
    /**
     * Try to acquire the lock with timeout.
     * 
     * @param timeoutSeconds maximum time to wait
     * @return true if lock acquired, false if timeout
     */
    public static boolean tryAcquire(int timeoutSeconds) {
        try {
            return LOCK.tryLock(timeoutSeconds, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }
    
    /**
     * Acquire the global search lock (blocking).
     * Blocks indefinitely if another thread holds the lock.
     * @deprecated Use tryAcquire() for fast-fail pattern
     */
    @Deprecated
    public static void lock() {
        LOCK.lock();
    }
    
    /**
     * Release the global search lock.
     * Must be called in a finally block after tryAcquire()/lock().
     */
    public static void release() {
        if (LOCK.isHeldByCurrentThread()) {
            LOCK.unlock();
        }
    }
    
    /**
     * @deprecated Use release() instead
     */
    @Deprecated
    public static void unlock() {
        release();
    }
    
    /**
     * Check if the lock is currently held by any thread.
     * Useful for status checking.
     */
    public static boolean isBusy() {
        return LOCK.isLocked();
    }
    
    /**
     * Check if current thread holds the lock.
     */
    public static boolean isHeldByCurrentThread() {
        return LOCK.isHeldByCurrentThread();
    }
}
