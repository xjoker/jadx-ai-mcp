<div align="center">

# JADX-AI-MCP

> 🔱 基于 [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp) 增强开发

⚡ 让 AI 直接分析 Android APK 和 Java JAR 文件

![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)

<a href="https://buymeacoffee.com/xjoker" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" width="217" height="60"></a>

**[English](README.md)** | [📖 文档](docs/index.zh-cn.md)

</div>

---

## 🌟 本 Fork 的独特优势

相比原版，本 Fork 提供**重大功能增强**：

| 特性 | 说明 |
|:-----|:-----|
| 🚀 **智能批量优化** | 4 层分级策略，避免 60-120 秒无效反编译。大响应（>8KB）自动分块传输。 |
| 🔄 **Transfer API** | HTTP 直接下载突破 MCP 约 16KB 限制。已验证支持 32.2 万类规模。 |
| 💼 **完整 JVM 支持** | APK、JAR、AAR、DEX 全支持。5 个 JAR 专用工具（manifest、入口点、依赖、服务、字节码）。 |
| ⚡ **ClassCacheManager** | 后台缓存 + 自动失效，重复分析快 10-50 倍。 |
| 🐳 **All-in-One Docker** | 一键部署 GUI + AI 服务器。多平台支持（amd64/arm64）。 |

> 📚 **44 篇中英双语指南**，涵盖部署、工具、故障排查和 AI 测试提示词。

---

## ⚡ 快速开始

> **前置条件**：已安装并运行 [Docker](https://docs.docker.com/get-docker/)。

**第 1 步：启动服务**

```bash
docker run -d --name jadx -p 6080:6080 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest
```

验证服务是否正常：

```bash
curl http://localhost:8651/health
# 预期输出: {"status": "ok", ...}
```

**第 2 步：加载文件**

浏览器打开 `http://localhost:6080`，将 APK/JAR 放入 `~/apks/` 并在 JADX 中打开。

> 💡 **自动加载**：将文件命名为 `target.apk`、`target.jar`、`target.aar` 或 `target.dex`，JADX 启动时自动加载。
>
> ⚠️ AI 连接前**必须**先在 JADX 中加载文件。插件只有在加载文件后才会初始化。

**第 3 步：连接 AI 客户端**

默认 MCP 认证 Token 为 `admin-secret-token`。

<details open>
<summary><b>Claude Code</b>（一行命令）</summary>

```bash
claude mcp add --transport http jadx http://localhost:8651/mcp \
  --header "Authorization:Bearer admin-secret-token"
```

</details>

<details>
<summary><b>OpenAI Codex CLI</b></summary>

添加到 `~/.codex/config.toml`：

```toml
[mcp_servers.jadx]
url = "http://localhost:8651/mcp"
http_headers = { Authorization = "Bearer admin-secret-token" }
```

验证：`codex mcp list`

</details>

<details>
<summary><b>Claude Desktop</b></summary>

添加到[配置文件](docs/guides/ai-clients.zh-cn.md#claude-desktop-setup)：

```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp",
      "headers": {
        "Authorization": "Bearer admin-secret-token"
      }
    }
  }
}
```

</details>

<details>
<summary><b>Cursor / 其他 MCP 客户端</b></summary>

添加到 `.cursor/mcp.json` 或你的客户端 MCP 配置文件：

```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp",
      "headers": {
        "Authorization": "Bearer admin-secret-token"
      }
    }
  }
}
```

详见 [AI 客户端配置](docs/guides/ai-clients.zh-cn.md)。

</details>

> ⚠️ **默认凭据** — 生产环境务必更换！详见 [安全策略](docs/security/security.zh-cn.md)。
>
> | Token | 默认值 |
> |:------|:------|
> | MCP 管理 Token | `admin-secret-token` |
> | JADX 插件 Token | `jadx-plugin-secret-token` |
>
> 通过环境变量或 `jadx-config.toml` 覆盖。

---

## 📖 文档导航

### 🚀 快速入门

| 文档 | 说明 |
|:-----|:-----|
| **[项目介绍](docs/overview/introduction.zh-cn.md)** | 了解核心概念、能力矩阵、适用场景 |
| **[系统架构](docs/overview/architecture.zh-cn.md)** | 理解三层架构、端口职责、组件通信 |
| **[5 分钟快速开始](docs/getting-started/quickstart.zh-cn.md)** | Docker 一键部署 |

### 🐳 部署指南

| 文档 | 说明 |
|:-----|:-----|
| **[Docker 完全指南](docs/deployment/docker.zh-cn.md)** | 单容器、多容器、独立 MCP Server |
| [Docker Compose](docs/deployment/docker-compose.zh-cn.md) | 多实例部署（团队协作、版本对比） |
| [本地安装](docs/deployment/local.zh-cn.md) | 无 Docker 安装 |

### 🔧 配置与集成

| 文档 | 说明 |
|:-----|:-----|
| **[AI 客户端配置](docs/guides/ai-clients.zh-cn.md)** | Claude、Cursor、Continue 等客户端配置 |
| [多实例管理](docs/guides/multi-instance.zh-cn.md) | 并行分析多个 APK |
| [AI 测试提示词](docs/guides/ai-prompts.zh-cn.md) | 自动化测试模板 |

### 📚 参考文档

| 文档 | 说明 |
|:-----|:-----|
| [工具参考](docs/reference/tools.zh-cn.md) | 完整的 45 个 MCP 工具矩阵 |
| [配置参考](docs/reference/configuration.zh-cn.md) | 所有配置项详解 |
| [安全策略](docs/security/security.zh-cn.md) | 认证、权限、SSRF 防护 |

### 🛠️ 故障排查

| 文档 | 说明 |
|:-----|:-----|
| **[常见问题](docs/troubleshooting/common-issues.zh-cn.md)** | FAQ + Windows/Linux/macOS 专项问题 |
| [更新日志](docs/changelog/CHANGELOG.zh-cn.md) | 版本历史 |

---

## 🧠 AI 技能

为 Claude Code、Cursor 等 AI 助手安装专业分析技能：

```bash
# 安装所有技能
npx skills add xjoker/jadx-ai-mcp

# 安装特定技能
npx skills add xjoker/jadx-ai-mcp --skill security-audit
```

**6 个可用技能**：quickstart、logic-tracing、security-audit、crypto-analysis、frida-hooks、refactoring

> 详见 [项目介绍 - AI 技能系统](docs/overview/introduction.zh-cn.md#ai-技能系统)

---

## 🙏 致谢

- 原项目：[@zinja-coder](https://github.com/zinja-coder/jadx-ai-mcp)
- JADX 反编译器：[skylot/jadx](https://github.com/skylot/jadx)

---

## 📜 许可证

Apache 2.0 - 见 [LICENSE](LICENSE)

---

> **说明**：仓库源码里的版本号是开发占位值。正式发布时由 GitHub Actions 在构建阶段把版本写入产物、`pom.xml`、Java Banner 和 Python Server Banner。
