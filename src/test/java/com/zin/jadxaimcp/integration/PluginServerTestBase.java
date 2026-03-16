package com.zin.jadxaimcp.integration;

import java.io.IOException;
import java.net.ServerSocket;
import java.nio.file.Files;
import java.nio.file.Path;

import jadx.api.JadxArgs;
import jadx.api.JadxDecompiler;
import jadx.gui.JadxWrapper;
import jadx.gui.events.types.JadxGuiEventsImpl;
import jadx.gui.ui.MainWindow;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.TestInstance;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.zin.jadxaimcp.server.PluginServer;

/**
 * Base class for integration tests that start a real PluginServer backed by
 * a mocked MainWindow + real JadxDecompiler loading a test JAR.
 *
 * Tests are skipped (via JUnit Assumptions) when the test JAR is absent.
 */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
public abstract class PluginServerTestBase {

    protected static final Path NEXUS_JAR = Path.of("temp/nexus-main.jar");

    protected PluginServer server;
    protected int port;
    protected OkHttpClient client;
    protected JadxDecompiler decompiler;

    @BeforeAll
    void setup() throws Exception {
        Assumptions.assumeTrue(
                Files.exists(NEXUS_JAR),
                "Test JAR not found at " + NEXUS_JAR + " — run scripts/fetch-nexus-jar.sh first"
        );

        // 1. Create JadxDecompiler and load the test JAR
        JadxArgs args = new JadxArgs();
        args.setInputFile(NEXUS_JAR.toFile());
        args.setSkipResources(true);
        decompiler = new JadxDecompiler(args);
        decompiler.load();

        // 2. Mock MainWindow with all required stubs
        JadxWrapper wrapper = mock(JadxWrapper.class);
        when(wrapper.getDecompiler()).thenReturn(decompiler);
        when(wrapper.getIncludedClassesWithInners()).thenReturn(decompiler.getClassesWithInners());
        when(wrapper.getResources()).thenReturn(decompiler.getResources());

        // JadxGuiEventsImpl has a no-arg constructor — use a real instance so that
        // PluginServer.setupCacheInvalidation() can register its rename listener.
        JadxGuiEventsImpl events = new JadxGuiEventsImpl();

        MainWindow mainWindow = mock(MainWindow.class);
        when(mainWindow.getWrapper()).thenReturn(wrapper);
        when(mainWindow.events()).thenReturn(events);

        // 3. Find a free port and start the server
        port = findFreePort();
        server = new PluginServer(mainWindow, port, "127.0.0.1");
        server.start();

        // 4. Create HTTP client
        client = new OkHttpClient.Builder()
                .followRedirects(false)
                .build();
    }

    @AfterAll
    void teardown() {
        if (server != null) {
            server.stop();
        }
        if (decompiler != null) {
            decompiler.close();
        }
        if (client != null) {
            client.dispatcher().executorService().shutdown();
            client.connectionPool().evictAll();
        }
    }

    /**
     * Perform a GET request against the test server.
     */
    protected Response get(String path) throws IOException {
        Request request = new Request.Builder()
                .url("http://127.0.0.1:" + port + path)
                .get()
                .build();
        return client.newCall(request).execute();
    }

    /**
     * Perform a POST request against the test server.
     */
    protected Response post(String path) throws IOException {
        Request request = new Request.Builder()
                .url("http://127.0.0.1:" + port + path)
                .post(okhttp3.RequestBody.create(new byte[0]))
                .build();
        return client.newCall(request).execute();
    }

    private static int findFreePort() throws IOException {
        try (ServerSocket socket = new ServerSocket(0)) {
            return socket.getLocalPort();
        }
    }
}
