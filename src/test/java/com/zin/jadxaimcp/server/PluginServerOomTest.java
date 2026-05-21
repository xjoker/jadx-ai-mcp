package com.zin.jadxaimcp.server;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for the OOM-detection predicate in {@link PluginServer}.
 *
 * <p>The OOM flag is stored in JVM-global {@link System#getProperties()} under the key
 * {@code "jadx-ai-mcp-oom-detected"} so it survives classloader reloads.  These tests
 * toggle the flag directly and verify {@link PluginServer#isOomDetected()} behaves
 * as the circuit-breaker middleware expects.</p>
 */
class PluginServerOomTest {

    private static final String JVM_OOM_KEY = "jadx-ai-mcp-oom-detected";

    @BeforeEach
    void clearFlag() {
        System.getProperties().remove(JVM_OOM_KEY);
    }

    @AfterEach
    void restoreFlag() {
        System.getProperties().remove(JVM_OOM_KEY);
    }

    @Test
    void oomNotDetectedByDefault() {
        assertFalse(PluginServer.isOomDetected(),
                "isOomDetected() must return false when the JVM property is absent");
    }

    @Test
    void oomDetectedAfterFlagSet() {
        System.getProperties().put(JVM_OOM_KEY, System.currentTimeMillis());
        assertTrue(PluginServer.isOomDetected(),
                "isOomDetected() must return true once the JVM property is present");
    }

    @Test
    void oomFlagSurvivesMultipleChecks() {
        System.getProperties().put(JVM_OOM_KEY, System.currentTimeMillis());
        // The flag is sticky; repeated reads must not clear it.
        assertTrue(PluginServer.isOomDetected());
        assertTrue(PluginServer.isOomDetected());
    }

    @Test
    void oomClearedAfterPropertyRemoved() {
        System.getProperties().put(JVM_OOM_KEY, System.currentTimeMillis());
        assertTrue(PluginServer.isOomDetected());
        System.getProperties().remove(JVM_OOM_KEY);
        assertFalse(PluginServer.isOomDetected(),
                "isOomDetected() must return false after property is removed");
    }
}
