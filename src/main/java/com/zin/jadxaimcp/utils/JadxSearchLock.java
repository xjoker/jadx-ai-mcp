package com.zin.jadxaimcp.utils;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.locks.ReentrantLock;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Global lock for JADX search and decompilation operations.
 * 
 * JADX internal state is not thread-safe for concurrent decompilation.
 * This singleton lock ensures that only one search/decompilation operation
 * runs at a time across all route handlers, preventing state corruption
 * and intermittent empty results.
 * 
 * Features:
 * - Lock timeout detection: if lock is held > 60s, new requests can acquire it
 * - Lock hold time tracking for monitoring
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
    
    private static final Logger logger = LoggerFactory.getLogger(JadxSearchLock.class);
    
    // Singleton ReentrantLock shared by all routes
    private static final ReentrantLock LOCK = new ReentrantLock();
    
    // Track when the lock was acquired (0 means not held)
    private static final AtomicLong lockAcquireTime = new AtomicLong(0);

    // Track the thread currently holding the lock (null means not held)
    private static final AtomicReference<Thread> holdingThread = new AtomicReference<>(null);
    
    // Recommended retry interval in seconds
    public static final int RETRY_AFTER_SECONDS = 10;
    
    // Maximum lock hold time before allowing new requests (60 seconds)
    public static final int LOCK_TIMEOUT_SECONDS = 60;
    
    private JadxSearchLock() {
        // Prevent instantiation
    }
    
    /**
     * Try to acquire the lock immediately (non-blocking).
     * If the lock has been held for more than LOCK_TIMEOUT_SECONDS,
     * allows new requests to proceed (resets tracking).
     * 
     * @return true if lock acquired, false if busy
     */
    public static boolean tryAcquire() {
        // Check for stale lock (held too long) and interrupt the holding thread
        long acquireTime = lockAcquireTime.get();
        boolean interrupted = false;
        if (acquireTime > 0 && LOCK.isLocked()) {
            long heldSeconds = (System.currentTimeMillis() - acquireTime) / 1000;
            if (heldSeconds > LOCK_TIMEOUT_SECONDS) {
                Thread staleThread = holdingThread.get();
                if (staleThread != null) {
                    logger.warn("Search lock held for {}s (timeout: {}s), interrupting holding thread [{}]",
                        heldSeconds, LOCK_TIMEOUT_SECONDS, staleThread.getName());
                    staleThread.interrupt();
                    interrupted = true;
                } else {
                    logger.warn("Search lock held for {}s (timeout: {}s), but holding thread unknown",
                        heldSeconds, LOCK_TIMEOUT_SECONDS);
                }
                // Reset tracking so the lock can be re-acquired after release
                lockAcquireTime.set(0);
                holdingThread.set(null);
            }
        }

        // If we interrupted a stale thread, give it time to unwind and release the lock
        if (interrupted) {
            try {
                boolean acquired = LOCK.tryLock(500, TimeUnit.MILLISECONDS);
                if (acquired) {
                    lockAcquireTime.set(System.currentTimeMillis());
                    holdingThread.set(Thread.currentThread());
                }
                return acquired;
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }

        boolean acquired = LOCK.tryLock();
        if (acquired) {
            lockAcquireTime.set(System.currentTimeMillis());
            holdingThread.set(Thread.currentThread());
        }
        return acquired;
    }
    
    /**
     * Try to acquire the lock with timeout.
     * 
     * @param timeoutSeconds maximum time to wait
     * @return true if lock acquired, false if timeout
     */
    public static boolean tryAcquire(int timeoutSeconds) {
        try {
            boolean acquired = LOCK.tryLock(timeoutSeconds, TimeUnit.SECONDS);
            if (acquired) {
                lockAcquireTime.set(System.currentTimeMillis());
                holdingThread.set(Thread.currentThread());
            }
            return acquired;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }
    
    /**
     * Release the global search lock.
     * Must be called in a finally block after tryAcquire().
     */
    public static void release() {
        if (LOCK.isHeldByCurrentThread()) {
            holdingThread.set(null);
            lockAcquireTime.set(0);
            LOCK.unlock();
        }
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
    
    /**
     * Get how long the lock has been held in seconds.
     * Returns 0 if lock is not currently held.
     */
    public static long getLockHeldSeconds() {
        long acquireTime = lockAcquireTime.get();
        if (acquireTime == 0) {
            return 0;
        }
        return (System.currentTimeMillis() - acquireTime) / 1000;
    }
    
    /**
     * Get lock status information for monitoring.
     */
    public static java.util.Map<String, Object> getStatus() {
        java.util.Map<String, Object> status = new java.util.HashMap<>();
        status.put("locked", LOCK.isLocked());
        status.put("held_seconds", getLockHeldSeconds());
        status.put("timeout_seconds", LOCK_TIMEOUT_SECONDS);
        return status;
    }
}
