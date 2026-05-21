package com.zin.jadxaimcp.utils;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.locks.StampedLock;

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
 * <p>Uses {@link StampedLock} instead of {@link java.util.concurrent.locks.ReentrantReadWriteLock}
 * because {@code StampedLock.tryUnlockWrite()} can be called from <em>any</em> thread. This
 * enables {@link #forceRelease(String)} — called by the global watchdog in {@code PluginServer}
 * after {@code JADX_MCP_LOCK_FORCE_RELEASE_SECONDS} — to break a lock held by a JADX thread
 * that does not respond to {@code Thread.interrupt()}.</p>
 */
public final class JadxSearchLock {

    private static final Logger logger = LoggerFactory.getLogger(JadxSearchLock.class);

    // StampedLock: tryUnlockWrite() can release from any thread (unlike ReentrantReadWriteLock)
    private static final StampedLock STAMPED_LOCK = new StampedLock();

    // Per-thread write stamp storage so release() knows which stamp to pass to unlockWrite()
    private static final ThreadLocal<Long> writeStampTL = new ThreadLocal<>();

    // Per-thread read stamp storage for releaseRead()
    private static final ThreadLocal<Long> readStampTL = new ThreadLocal<>();

    // Track when the write lock was acquired (0 means not held)
    private static final AtomicLong lockAcquireTime = new AtomicLong(0);

    // Track the thread currently holding the write lock (null means not held)
    private static final AtomicReference<Thread> holdingThread = new AtomicReference<>(null);

    // Recommended retry interval in seconds
    public static final int RETRY_AFTER_SECONDS = 10;

    // Soft timeout: after this many seconds the holding thread is interrupted
    public static final int LOCK_TIMEOUT_SECONDS = 60;

    private JadxSearchLock() {}

    // ========== Write Lock (exclusive — for decompilation operations) ==========

    /**
     * Try to acquire the write lock immediately (non-blocking).
     * If the write lock has been held > LOCK_TIMEOUT_SECONDS, interrupts the holding thread.
     *
     * @return true if write lock acquired, false if busy
     */
    public static boolean tryAcquire() {
        maybeSoftInterrupt();

        long stamp = STAMPED_LOCK.tryWriteLock();
        if (stamp != 0L) {
            writeStampTL.set(stamp);
            lockAcquireTime.set(System.currentTimeMillis());
            holdingThread.set(Thread.currentThread());
            return true;
        }
        return false;
    }

    /**
     * Try to acquire the write lock with timeout.
     *
     * @param timeoutSeconds maximum time to wait
     * @return true if write lock acquired, false if timeout
     */
    public static boolean tryAcquire(int timeoutSeconds) {
        try {
            long stamp = STAMPED_LOCK.tryWriteLock(timeoutSeconds, TimeUnit.SECONDS);
            if (stamp != 0L) {
                writeStampTL.set(stamp);
                lockAcquireTime.set(System.currentTimeMillis());
                holdingThread.set(Thread.currentThread());
                return true;
            }
            return false;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    /**
     * Release the write lock held by the current thread.
     * Must be called in a finally block after tryAcquire().
     */
    public static void release() {
        Long stamp = writeStampTL.get();
        if (stamp != null && stamp != 0L) {
            writeStampTL.remove();
            holdingThread.set(null);
            lockAcquireTime.set(0);
            try {
                STAMPED_LOCK.unlockWrite(stamp);
            } catch (IllegalMonitorStateException e) {
                // Stamp no longer valid — already force-released by watchdog; safe to ignore
                logger.debug("release(): stamp no longer valid (already force-released)");
            }
        }
    }

    /**
     * Force-release the write lock from any thread, including a watchdog thread.
     *
     * <p>Called when the lock has been held beyond the hard timeout and the holding thread
     * did not respond to {@link Thread#interrupt()}. Uses
     * {@link StampedLock#tryUnlockWrite()} which is explicitly documented as safe to call
     * from any thread for error recovery.</p>
     *
     * <p><b>Risk:</b> JADX may be in a partially-mutated state when this fires. The
     * decompiled class may be incomplete or incorrect. Subsequent requests will re-trigger
     * decompilation. This is preferable to leaving the entire system in a 503 state.</p>
     *
     * @param reason human-readable explanation logged at WARN level
     */
    public static void forceRelease(String reason) {
        long heldSeconds = getLockHeldSeconds();
        logger.warn("[JAI] Force-releasing write lock (held {}s): {}", heldSeconds, reason);
        holdingThread.set(null);
        lockAcquireTime.set(0);
        // tryUnlockWrite() is documented as safe to call from any thread for error recovery.
        // It returns false if the lock was not write-locked (no-op).
        boolean released = STAMPED_LOCK.tryUnlockWrite();
        logger.warn("[JAI] Force-release result: lock_was_held={}", released);
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
        long stamp = STAMPED_LOCK.tryReadLock();
        if (stamp != 0L) {
            readStampTL.set(stamp);
            return true;
        }
        return false;
    }

    /**
     * Try to acquire the read lock with timeout.
     *
     * @param timeoutSeconds maximum time to wait
     * @return true if read lock acquired, false if timeout
     */
    public static boolean tryAcquireRead(int timeoutSeconds) {
        try {
            long stamp = STAMPED_LOCK.tryReadLock(timeoutSeconds, TimeUnit.SECONDS);
            if (stamp != 0L) {
                readStampTL.set(stamp);
                return true;
            }
            return false;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    /**
     * Release the read lock held by the current thread.
     * Must be called in a finally block after tryAcquireRead().
     */
    public static void releaseRead() {
        Long stamp = readStampTL.get();
        if (stamp != null && stamp != 0L) {
            readStampTL.remove();
            try {
                STAMPED_LOCK.unlockRead(stamp);
            } catch (IllegalMonitorStateException e) {
                logger.debug("releaseRead(): stamp no longer valid");
            }
        }
    }

    // ========== Status / Monitoring ==========

    /** Check if the write lock is currently held by any thread. */
    public static boolean isBusy() {
        return STAMPED_LOCK.isWriteLocked();
    }

    /** Check if current thread holds the write lock. */
    public static boolean isHeldByCurrentThread() {
        return holdingThread.get() == Thread.currentThread();
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

    /** Get the number of threads currently holding the read lock. */
    public static int getReadLockCount() {
        return STAMPED_LOCK.getReadLockCount();
    }

    /** Get lock status information for monitoring. */
    public static java.util.Map<String, Object> getStatus() {
        java.util.Map<String, Object> status = new java.util.HashMap<>();
        status.put("write_locked", STAMPED_LOCK.isWriteLocked());
        status.put("read_lock_count", STAMPED_LOCK.getReadLockCount());
        status.put("write_held_seconds", getLockHeldSeconds());
        status.put("timeout_seconds", LOCK_TIMEOUT_SECONDS);
        // Backward compatibility
        status.put("locked", STAMPED_LOCK.isWriteLocked());
        status.put("held_seconds", getLockHeldSeconds());
        return status;
    }

    // ========== Internal helpers ==========

    /**
     * If the write lock has been held beyond LOCK_TIMEOUT_SECONDS, interrupt the holder.
     * This is the "soft" first attempt before forceRelease() (the hard second attempt).
     */
    private static void maybeSoftInterrupt() {
        long acquireTime = lockAcquireTime.get();
        if (acquireTime > 0 && STAMPED_LOCK.isWriteLocked()) {
            long heldSeconds = (System.currentTimeMillis() - acquireTime) / 1000;
            if (heldSeconds > LOCK_TIMEOUT_SECONDS) {
                Thread staleThread = holdingThread.get();
                if (staleThread != null) {
                    logger.warn("[JAI] Write lock held for {}s (timeout: {}s), interrupting holding thread [{}]",
                        heldSeconds, LOCK_TIMEOUT_SECONDS, staleThread.getName());
                    staleThread.interrupt();
                } else {
                    logger.warn("[JAI] Write lock held for {}s (timeout: {}s), holding thread unknown",
                        heldSeconds, LOCK_TIMEOUT_SECONDS);
                }
            }
        }
    }
}
