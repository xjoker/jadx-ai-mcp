package com.zin.jadxaimcp.utils;

import java.util.concurrent.locks.ReentrantLock;

/**
 * Global lock for JADX search and decompilation operations.
 * 
 * JADX internal state is not thread-safe for concurrent decompilation.
 * This singleton lock ensures that only one search/decompilation operation
 * runs at a time across all route handlers, preventing state corruption
 * and intermittent empty results.
 * 
 * Usage:
 * <pre>
 * JadxSearchLock.lock();
 * try {
 *     // search/decompilation code
 * } finally {
 *     JadxSearchLock.unlock();
 * }
 * </pre>
 *
 * @author JADX AI MCP Team
 */
public final class JadxSearchLock {
    
    // Singleton ReentrantLock shared by all routes
    private static final ReentrantLock LOCK = new ReentrantLock();
    
    private JadxSearchLock() {
        // Prevent instantiation
    }
    
    /**
     * Acquire the global search lock.
     * Blocks if another thread holds the lock.
     */
    public static void lock() {
        LOCK.lock();
    }
    
    /**
     * Release the global search lock.
     * Must be called in a finally block after lock().
     */
    public static void unlock() {
        LOCK.unlock();
    }
    
    /**
     * Check if the lock is currently held by any thread.
     * Useful for debugging/monitoring.
     */
    public static boolean isLocked() {
        return LOCK.isLocked();
    }
    
    /**
     * Check if current thread holds the lock.
     */
    public static boolean isHeldByCurrentThread() {
        return LOCK.isHeldByCurrentThread();
    }
}
