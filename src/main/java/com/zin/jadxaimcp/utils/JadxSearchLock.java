package com.zin.jadxaimcp.utils;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.locks.ReentrantReadWriteLock;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Global lock for JADX search and decompilation operations.
 *
 * JADX internal state is not thread-safe for concurrent decompilation.
 * This lock provides two levels of access:
 *
 * <ul>
 *   <li><b>Write lock</b> ({@link #tryAcquire()}/{@link #release()}): exclusive access for
 *       decompilation operations (getCode, getSmali, rename). Only one writer at a time,
 *       blocks all readers.</li>
 *   <li><b>Read lock</b> ({@link #tryAcquireRead()}/{@link #releaseRead()}): shared access for
 *       metadata-only operations (class iteration, method listing, field listing). Multiple
 *       concurrent readers allowed, but blocked while a writer holds the lock.</li>
 * </ul>
 *
 * Features:
 * - Write lock timeout detection: if held > 60s, interrupts holding thread
 * - Write lock hold time tracking for monitoring
 *
 * Usage (write lock, fast-fail pattern — for decompilation):
 * <pre>
 * if (!JadxSearchLock.tryAcquire()) {
 *     ctx.status(503).json(Map.of(
 *         "error", "Search operation in progress",
 *         "retry_after", 10
 *     ));
 *     return;
 * }
 * try {
 *     // decompilation/code search
 * } finally {
 *     JadxSearchLock.release();
 * }
 * </pre>
 *
 * Usage (read lock, fast-fail pattern — for metadata queries):
 * <pre>
 * if (!JadxSearchLock.tryAcquireRead()) {
 *     ctx.status(503).json(Map.of(
 *         "error", "Decompilation operation in progress",
 *         "retry_after", 5
 *     ));
 *     return;
 * }
 * try {
 *     // metadata-only read (ClassNode iteration, method listing, etc.)
 * } finally {
 *     JadxSearchLock.releaseRead();
 * }
 * </pre>
 *
 * @author JADX AI MCP Team
 */
public final class JadxSearchLock {

    private static final Logger logger = LoggerFactory.getLogger(JadxSearchLock.class);

    // ReadWriteLock: multiple concurrent readers OR one exclusive writer
    private static final ReentrantReadWriteLock RW_LOCK = new ReentrantReadWriteLock();

    // Track when the write lock was acquired (0 means not held)
    private static final AtomicLong lockAcquireTime = new AtomicLong(0);

    // Track the thread currently holding the write lock (null means not held)
    private static final AtomicReference<Thread> holdingThread = new AtomicReference<>(null);

    // Recommended retry interval in seconds
    public static final int RETRY_AFTER_SECONDS = 10;

    // Maximum write lock hold time before allowing new requests (60 seconds)
    public static final int LOCK_TIMEOUT_SECONDS = 60;

    private JadxSearchLock() {
        // Prevent instantiation
    }

    // ========== Write Lock (exclusive — for decompilation operations) ==========

    /**
     * Try to acquire the write lock immediately (non-blocking).
     * If the write lock has been held for more than LOCK_TIMEOUT_SECONDS,
     * interrupts the holding thread and waits briefly for release.
     *
     * @return true if write lock acquired, false if busy
     */
    public static boolean tryAcquire() {
        // Check for stale write lock (held too long) and interrupt the holding thread
        long acquireTime = lockAcquireTime.get();
        boolean interrupted = false;
        if (acquireTime > 0 && RW_LOCK.isWriteLocked()) {
            long heldSeconds = (System.currentTimeMillis() - acquireTime) / 1000;
            if (heldSeconds > LOCK_TIMEOUT_SECONDS) {
                Thread staleThread = holdingThread.get();
                if (staleThread != null) {
                    logger.warn("Write lock held for {}s (timeout: {}s), interrupting holding thread [{}]",
                        heldSeconds, LOCK_TIMEOUT_SECONDS, staleThread.getName());
                    staleThread.interrupt();
                    interrupted = true;
                } else {
                    logger.warn("Write lock held for {}s (timeout: {}s), but holding thread unknown",
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
                boolean acquired = RW_LOCK.writeLock().tryLock(500, TimeUnit.MILLISECONDS);
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

        boolean acquired = RW_LOCK.writeLock().tryLock();
        if (acquired) {
            lockAcquireTime.set(System.currentTimeMillis());
            holdingThread.set(Thread.currentThread());
        }
        return acquired;
    }

    /**
     * Try to acquire the write lock with timeout.
     *
     * @param timeoutSeconds maximum time to wait
     * @return true if write lock acquired, false if timeout
     */
    public static boolean tryAcquire(int timeoutSeconds) {
        try {
            boolean acquired = RW_LOCK.writeLock().tryLock(timeoutSeconds, TimeUnit.SECONDS);
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
     * Release the global write lock.
     * Must be called in a finally block after tryAcquire().
     */
    public static void release() {
        if (RW_LOCK.isWriteLockedByCurrentThread()) {
            holdingThread.set(null);
            lockAcquireTime.set(0);
            RW_LOCK.writeLock().unlock();
        }
    }

    // ========== Read Lock (shared — for metadata-only operations) ==========

    /**
     * Try to acquire the read lock immediately (non-blocking).
     * Multiple threads can hold the read lock concurrently.
     * Blocked only when a writer holds the write lock.
     *
     * @return true if read lock acquired, false if a write operation is in progress
     */
    public static boolean tryAcquireRead() {
        return RW_LOCK.readLock().tryLock();
    }

    /**
     * Try to acquire the read lock with timeout.
     *
     * @param timeoutSeconds maximum time to wait
     * @return true if read lock acquired, false if timeout
     */
    public static boolean tryAcquireRead(int timeoutSeconds) {
        try {
            return RW_LOCK.readLock().tryLock(timeoutSeconds, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    /**
     * Release the read lock.
     * Must be called in a finally block after tryAcquireRead().
     */
    public static void releaseRead() {
        // ReentrantReadWriteLock.readLock() does not expose isHeldByCurrentThread(),
        // but unlock() on a lock not held by this thread throws IllegalMonitorStateException.
        // We catch that to stay safe, matching the defensive pattern of release().
        try {
            RW_LOCK.readLock().unlock();
        } catch (IllegalMonitorStateException e) {
            // Current thread does not hold the read lock — nothing to release
            logger.debug("releaseRead() called but current thread does not hold the read lock");
        }
    }

    // ========== Status / Monitoring ==========

    /**
     * Check if the write lock is currently held by any thread.
     * Useful for status checking.
     */
    public static boolean isBusy() {
        return RW_LOCK.isWriteLocked();
    }

    /**
     * Check if current thread holds the write lock.
     */
    public static boolean isHeldByCurrentThread() {
        return RW_LOCK.isWriteLockedByCurrentThread();
    }

    /**
     * Get how long the write lock has been held in seconds.
     * Returns 0 if write lock is not currently held.
     */
    public static long getLockHeldSeconds() {
        long acquireTime = lockAcquireTime.get();
        if (acquireTime == 0) {
            return 0;
        }
        return (System.currentTimeMillis() - acquireTime) / 1000;
    }

    /**
     * Get the number of threads currently holding the read lock.
     * Useful for monitoring concurrent metadata operations.
     */
    public static int getReadLockCount() {
        return RW_LOCK.getReadLockCount();
    }

    /**
     * Get lock status information for monitoring.
     */
    public static java.util.Map<String, Object> getStatus() {
        java.util.Map<String, Object> status = new java.util.HashMap<>();
        status.put("write_locked", RW_LOCK.isWriteLocked());
        status.put("read_lock_count", RW_LOCK.getReadLockCount());
        status.put("write_held_seconds", getLockHeldSeconds());
        status.put("timeout_seconds", LOCK_TIMEOUT_SECONDS);
        // Backward compatibility
        status.put("locked", RW_LOCK.isWriteLocked());
        status.put("held_seconds", getLockHeldSeconds());
        return status;
    }
}
