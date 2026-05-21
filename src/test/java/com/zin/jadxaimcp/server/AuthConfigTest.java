package com.zin.jadxaimcp.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 单元测试 - AuthConfig token 验证逻辑。
 *
 * AuthConfig.CONFIG_DIR 是 static final 常量，在类加载时已绑定 user.home，
 * 因此无法通过 System.setProperty 隔离。
 *
 * 测试策略：
 * - 使用双参数构造函数 AuthConfig(envToken, envEnabled) 注入受控值
 * - 覆盖 validateToken / isAuthEnabled / token 管理的核心路径
 * - 默认构造函数测试（authDisabledByDefault）依赖本机 auth.enabled=false 配置
 */
class AuthConfigTest {

    @TempDir
    Path tempDir; // 保留以备将来使用

    // -------------------------------------------------------------------------
    // auth 禁用时行为（通过 env 覆盖强制禁用，不依赖本机配置文件）
    // -------------------------------------------------------------------------

    @Test
    void authDisabled_validateTokenAlwaysTrue() {
        // envEnabled=false 强制禁用，不依赖本机 auth.properties
        AuthConfig config = new AuthConfig(null, false);
        assertFalse(config.isAuthEnabled(), "env 强制禁用时 isAuthEnabled 应为 false");
        assertTrue(config.validateToken(null), "认证禁用时 null token 应通过");
        assertTrue(config.validateToken(""), "认证禁用时空 token 应通过");
        assertTrue(config.validateToken("any-random-value"), "认证禁用时任意 token 应通过");
    }

    // -------------------------------------------------------------------------
    // auth 启用后的 token 验证
    // -------------------------------------------------------------------------

    @Test
    void authEnabled_correctTokenValidates() {
        AuthConfig config = new AuthConfig();
        config.setAuthEnabled(true);

        String token = config.getAuthToken();
        assertTrue(config.validateToken(token), "正确 token 应验证通过");
    }

    @Test
    void authEnabled_wrongTokenFails() {
        AuthConfig config = new AuthConfig();
        config.setAuthEnabled(true);

        assertFalse(config.validateToken("wrong-token"), "错误 token 应验证失败");
    }

    @Test
    void authEnabled_nullTokenFails() {
        AuthConfig config = new AuthConfig();
        config.setAuthEnabled(true);

        assertFalse(config.validateToken(null), "null token 应验证失败");
    }

    @Test
    void authEnabled_emptyTokenFails() {
        AuthConfig config = new AuthConfig();
        config.setAuthEnabled(true);

        assertFalse(config.validateToken(""), "空 token 应验证失败");
    }

    // -------------------------------------------------------------------------
    // 环境变量覆盖
    // -------------------------------------------------------------------------

    @Test
    void envTokenOverride_usesEnvToken() {
        String envToken = "env-provided-token-xyz";
        AuthConfig config = new AuthConfig(envToken, null);

        assertEquals(envToken, config.getAuthToken(), "env token 应覆盖生成的 token");
    }

    @Test
    void envEnabledOverride_enablesAuth() {
        String envToken = "env-token-for-enabled-test";
        AuthConfig config = new AuthConfig(envToken, true);

        assertTrue(config.isAuthEnabled(), "env enabled=true 应启用认证");
        assertTrue(config.validateToken(envToken), "env token 应验证通过");
    }

    @Test
    void envDisabledOverride_disablesAuth() {
        AuthConfig config = new AuthConfig(null, false);
        assertFalse(config.isAuthEnabled(), "env enabled=false 应禁用认证");
        assertTrue(config.validateToken("any-token"), "认证禁用时任意 token 应通过");
    }

    // -------------------------------------------------------------------------
    // token 再生成
    // -------------------------------------------------------------------------

    @Test
    void regenerateToken_changesToken() {
        AuthConfig config = new AuthConfig();
        config.setAuthEnabled(true);

        String originalToken = config.getAuthToken();
        config.regenerateToken();
        String newToken = config.getAuthToken();

        // 极小概率相同，但理论上应不同
        assertNotNull(newToken);
        assertNotEquals(originalToken, newToken, "再生成的 token 应与原 token 不同");
    }

    @Test
    void regenerateToken_oldTokenNoLongerValid() {
        AuthConfig config = new AuthConfig();
        config.setAuthEnabled(true);

        String oldToken = config.getAuthToken();
        config.regenerateToken();

        assertFalse(config.validateToken(oldToken), "旧 token 在再生成后应失效");
    }

    // -------------------------------------------------------------------------
    // setAuthToken
    // -------------------------------------------------------------------------

    @Test
    void setAuthToken_customToken_validatesCorrectly() {
        AuthConfig config = new AuthConfig();
        config.setAuthEnabled(true);
        config.setAuthToken("my-custom-token-12345");

        assertTrue(config.validateToken("my-custom-token-12345"), "自定义 token 应验证通过");
        assertFalse(config.validateToken("wrong"), "其他 token 应验证失败");
    }

    @Test
    void setAuthToken_nullOrEmpty_doesNotChangeToken() {
        AuthConfig config = new AuthConfig();
        String originalToken = config.getAuthToken();

        config.setAuthToken(null);
        assertEquals(originalToken, config.getAuthToken(), "null token 不应修改现有 token");

        config.setAuthToken("");
        assertEquals(originalToken, config.getAuthToken(), "空 token 不应修改现有 token");
    }

    // -------------------------------------------------------------------------
    // getConfigFilePath
    // -------------------------------------------------------------------------

    @Test
    void getConfigFilePath_containsExpectedDirectory() {
        AuthConfig config = new AuthConfig();
        String path = config.getConfigFilePath();
        assertNotNull(path);
        assertTrue(path.contains("jadx-ai-mcp"), "配置文件路径应包含 jadx-ai-mcp 目录名");
        assertTrue(path.endsWith("auth.properties"), "配置文件应以 auth.properties 结尾");
    }

    // -------------------------------------------------------------------------
    // 文件挂载 (JADX_MCP_AUTH_TOKEN_FILE) 支持
    // -------------------------------------------------------------------------

    @Test
    void fileMountHappyPath_readsAndTrimsToken(@TempDir Path tmpDir) throws IOException {
        // 写入带尾部换行的 token（模拟 Docker secret 文件行为）
        Path secretFile = tmpDir.resolve("jadx_token");
        String expectedToken = "my-file-token-abc123";
        Files.writeString(secretFile, expectedToken + "\n", StandardCharsets.UTF_8);

        AuthConfig config = new AuthConfig(null, null, secretFile.toString());

        assertEquals(expectedToken, config.getAuthToken(), "文件 token 应被读取并去除尾部换行");
        assertTrue(config.isExternallyManaged(), "文件挂载时 isExternallyManaged 应为 true");
    }

    @Test
    void fileMountUnreadablePath_throwsRuntimeException() {
        String nonExistentPath = "/tmp/definitely-does-not-exist-jadx-test-token-file";
        assertThrows(RuntimeException.class,
            () -> new AuthConfig(null, null, nonExistentPath),
            "不可读文件路径应抛出 RuntimeException（fast-fail）");
    }

    @Test
    void fileMountRegenerateToken_rejected(@TempDir Path tmpDir) throws IOException {
        Path secretFile = tmpDir.resolve("jadx_token");
        Files.writeString(secretFile, "file-token-regen-test", StandardCharsets.UTF_8);

        AuthConfig config = new AuthConfig(null, null, secretFile.toString());
        String tokenBefore = config.getAuthToken();

        boolean result = config.regenerateToken();

        assertFalse(result, "外部管理时 regenerateToken 应返回 false");
        assertEquals(tokenBefore, config.getAuthToken(), "外部管理时 token 不应被修改");
    }

    @Test
    void fileMountSetAuthToken_rejected(@TempDir Path tmpDir) throws IOException {
        Path secretFile = tmpDir.resolve("jadx_token");
        Files.writeString(secretFile, "file-token-set-test", StandardCharsets.UTF_8);

        AuthConfig config = new AuthConfig(null, null, secretFile.toString());
        String tokenBefore = config.getAuthToken();

        boolean result = config.setAuthToken("new-manual-token");

        assertFalse(result, "外部管理时 setAuthToken 应返回 false");
        assertEquals(tokenBefore, config.getAuthToken(), "外部管理时 token 不应被修改");
    }

    @Test
    void isExternallyManaged_trueWhenFilePathSet(@TempDir Path tmpDir) throws IOException {
        Path secretFile = tmpDir.resolve("jadx_token");
        Files.writeString(secretFile, "check-external-token", StandardCharsets.UTF_8);

        AuthConfig config = new AuthConfig(null, null, secretFile.toString());
        assertTrue(config.isExternallyManaged(), "设置文件路径后 isExternallyManaged 应为 true");
    }

    @Test
    void isExternallyManaged_falseWhenNoFilePath() {
        AuthConfig config = new AuthConfig("some-env-token", null, null);
        assertFalse(config.isExternallyManaged(), "未设置文件路径时 isExternallyManaged 应为 false");
    }

    @Test
    void envPrecedence_fileOverEnvToken(@TempDir Path tmpDir) throws IOException {
        // 文件 token 应优先于 env token
        Path secretFile = tmpDir.resolve("jadx_token");
        String fileToken = "token-from-file";
        String envToken  = "token-from-env";
        Files.writeString(secretFile, fileToken, StandardCharsets.UTF_8);

        AuthConfig config = new AuthConfig(envToken, null, secretFile.toString());

        assertEquals(fileToken, config.getAuthToken(), "_FILE 应优先于 _TOKEN env var");
        assertTrue(config.isExternallyManaged());
    }
}
