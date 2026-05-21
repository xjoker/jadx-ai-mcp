package com.zin.jadxaimcp.utils;

import com.zin.jadxaimcp.utils.FilePathSandbox.SandboxViolation;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for {@link FilePathSandbox}: positive resolution, ".." traversal
 * rejection, symlink escape rejection, and disabled-state semantics.
 */
class FilePathSandboxTest {

    @Test
    void disabledSandboxRejectsAnyPath(@TempDir Path tmp) {
        FilePathSandbox sandbox = new FilePathSandbox(null);
        assertFalse(sandbox.isEnabled());
        SandboxViolation ex = assertThrows(SandboxViolation.class,
                () -> sandbox.resolveWithinRoot("anything.apk"));
        assertTrue(ex.getMessage().contains("disabled"));
    }

    @Test
    void relativePathResolvesInsideRoot(@TempDir Path tmp) throws IOException {
        Path apk = Files.createFile(tmp.resolve("hello.apk"));
        FilePathSandbox sandbox = new FilePathSandbox(tmp.toRealPath());
        Path resolved = assertDoesNotThrow(() -> sandbox.resolveWithinRoot("hello.apk"));
        assertEquals(apk.toRealPath(), resolved);
    }

    @Test
    void absolutePathInsideRootAccepted(@TempDir Path tmp) throws IOException {
        Path apk = Files.createFile(tmp.resolve("hello.apk"));
        FilePathSandbox sandbox = new FilePathSandbox(tmp.toRealPath());
        Path resolved = assertDoesNotThrow(() -> sandbox.resolveWithinRoot(apk.toString()));
        assertEquals(apk.toRealPath(), resolved);
    }

    @Test
    void parentTraversalRejected(@TempDir Path tmp) throws IOException {
        // tmp/root/  vs  tmp/outside.apk — relative ../outside.apk must be rejected.
        Path root = Files.createDirectory(tmp.resolve("root"));
        Path outside = Files.createFile(tmp.resolve("outside.apk"));
        FilePathSandbox sandbox = new FilePathSandbox(root.toRealPath());
        SandboxViolation ex = assertThrows(SandboxViolation.class,
                () -> sandbox.resolveWithinRoot("../outside.apk"));
        assertTrue(ex.getMessage().contains("escapes sandbox root"), ex.getMessage());
        assertTrue(Files.exists(outside), "test setup sanity");
    }

    @Test
    void absoluteOutsideRootRejected(@TempDir Path tmp) throws IOException {
        Path root = Files.createDirectory(tmp.resolve("root"));
        Path outside = Files.createFile(tmp.resolve("outside.apk"));
        FilePathSandbox sandbox = new FilePathSandbox(root.toRealPath());
        SandboxViolation ex = assertThrows(SandboxViolation.class,
                () -> sandbox.resolveWithinRoot(outside.toString()));
        assertTrue(ex.getMessage().contains("escapes sandbox root"), ex.getMessage());
    }

    @Test
    void symlinkEscapeRejected(@TempDir Path tmp) throws IOException {
        Path root = Files.createDirectory(tmp.resolve("root"));
        Path target = Files.createFile(tmp.resolve("real.apk"));
        Path link = root.resolve("link.apk");
        try {
            Files.createSymbolicLink(link, target);
        } catch (UnsupportedOperationException | IOException e) {
            // Symlinks unavailable (e.g. Windows without privilege) — skip.
            return;
        }
        FilePathSandbox sandbox = new FilePathSandbox(root.toRealPath());
        SandboxViolation ex = assertThrows(SandboxViolation.class,
                () -> sandbox.resolveWithinRoot("link.apk"));
        assertTrue(ex.getMessage().contains("escapes sandbox root"), ex.getMessage());
    }

    @Test
    void missingFileReportsNotFound(@TempDir Path tmp) throws IOException {
        FilePathSandbox sandbox = new FilePathSandbox(tmp.toRealPath());
        SandboxViolation ex = assertThrows(SandboxViolation.class,
                () -> sandbox.resolveWithinRoot("ghost.apk"));
        assertTrue(ex.getMessage().contains("not found"), ex.getMessage());
    }

    @Test
    void emptyPathRejected(@TempDir Path tmp) throws IOException {
        FilePathSandbox sandbox = new FilePathSandbox(tmp.toRealPath());
        assertThrows(SandboxViolation.class, () -> sandbox.resolveWithinRoot(""));
        assertThrows(SandboxViolation.class, () -> sandbox.resolveWithinRoot(null));
    }
}
