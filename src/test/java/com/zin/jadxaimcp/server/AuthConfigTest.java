package com.zin.jadxaimcp.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

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
}
