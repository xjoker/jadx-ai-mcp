<div align="center">

# JADX-AI-MCP

> 🔱 基于 [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp) 增强开发

⚡ 让 AI 直接分析 Android APK 和 Java JAR 文件

![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)

**[English](README.md)** | [📖 文档](docs/index.zh-cn.md) | [🚀 快速开始](#-30-秒快速开始) | [🛠️ 工具](docs/reference/tools.zh-cn.md)

</div>

## 🌟 本 Fork 的独特优势

相比原版，本 Fork 提供**重大功能增强**：

| 特性 | 说明 |
|:-----|:-----|
| 🚀 **智能批量优化** | 4 层分级策略，避免 60-120 秒无效反编译。大响应（>8KB）自动分块传输。 |
| 🔄 **Transfer API** | HTTP 直接下载突破 MCP 约 16KB 限制。已验证支持 32.2 万类规模。 |
| 💼 **完整 JVM 支持** | APK、JAR、AAR、DEX 全支持。5 个 JAR 专用工具用于 Spring Boot 分析。 |
| ⚡ **ClassCacheManager** | 后台缓存 + 自动失效，重复分析快 10-50 倍。 |
| 🐳 **All-in-One Docker** | 一键部署 GUI + AI 服务器。多平台支持（amd64/arm64）。 |

> 📚 **44 篇中英双语指南**，涵盖部署、工具、故障排查和 AI 测试提示词。[查看详情 →](docs/reference/tools.zh-cn.md)

---

## ⚡ 30 秒快速开始

```bash
# 一键启动（图形界面 + AI）
docker run -d --name jadx -p 6080:6080 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest

# 在浏览器中打开 JADX 图形界面
open http://localhost:6080
```

**完成！** 将你的 APK 或 JAR 放入 `~/apks/`，在 JADX 中打开，让 AI 帮你分析。

<details>
<summary><strong>其他部署场景</strong></summary>

**无头模式（仅 AI，无图形界面）：**
```bash
docker run -d --name jadx -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest
```

**多容器 / 开发模式（所有端口）：**
```bash
docker run -d --name jadx -p 6080:6080 -p 8650:8650 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest
```

</details>

> 💡 **自动加载**：将 `target.jar`、`target.apk`、`target.aar` 或 `target.dex` 放入 `/apks` 目录，JADX 启动时自动加载。优先级：JAR > APK > AAR > DEX。

<details>
<summary>💡 <strong>让 AI 指导安装？</strong></summary>

发送给 Claude/ChatGPT：

```
按照以下文档逐步指导我安装 JADX-AI-MCP：
https://raw.githubusercontent.com/xjoker/jadx-ai-mcp/jadx-ai/docs/getting-started/installation.md

规则：
1. 每次只问我一个问题，等待我的回复后再继续
2. 只使用文档中的命令，不要创造新命令
3. 每一步后，让我粘贴输出结果再继续
4. 如果出现问题，帮我排查后再继续
```

> **如果 AI 无法访问 URL**：从 [installation.md](docs/getting-started/installation.md) 复制内容直接粘贴到对话中。
</details>

---

## 🤖 这是什么？

**JADX-AI-MCP** 让 Claude、ChatGPT 等 AI **直接分析 Android APK 和 Java JAR**。

| 功能 | 示例 |
|:-----|:-----|
| 🔍 **代码搜索** | "找到所有加密相关的类" |
| 📖 **代码阅读** | "解释登录方法的实现" |
| 🔗 **引用追踪** | "谁调用了这个 API？" |
| 🛡️ **安全审计** | "检查硬编码密钥" |

### 支持的文件类型

| 类型 | 说明 |
|:-----|:-----|
| **APK** | Android 应用 |
| **JAR** | Java 库 / Spring Boot 应用 |
| **AAR** | Android 库 |
| **DEX** | Dalvik 字节码 |

---

## 🧠 AI 技能

为 Claude Code、Cursor 等 AI 助手安装专业分析技能：

```bash
# 安装所有技能
npx skills add xjoker/jadx-ai-mcp

# 安装特定技能
npx skills add xjoker/jadx-ai-mcp --skill logic-tracing
```

| 技能 | 用途 |
|:-----|:-----|
| **quickstart** | 入门指南、性能优化 |
| **logic-tracing** | 理解调用链、API 流程、功能实现 |
| **security-audit** | 漏洞挖掘、OWASP 检查、风险分析 |
| **crypto-analysis** | 加密算法、恶意软件分析、反调试 |
| **frida-hooks** | 生成 Frida 脚本进行动态插桩 |
| **refactoring** | 重命名混淆代码、提高可读性 |

> 浏览更多技能：[skills.sh](https://skills.sh)

---

## 🚀 部署方式

| 方式 | 适用场景 | 指南 |
|:-----|:---------|:-----|
| **Docker**（推荐）| 快速开始，个人使用 | [→ Docker 指南](docs/deployment/docker.zh-cn.md) |
| **Docker Compose** | 多实例，团队使用 | [→ Compose 指南](docs/deployment/docker-compose.zh-cn.md) |
| **本地安装** | 开发调试，定制修改 | [→ 本地指南](docs/deployment/local.zh-cn.md) |

### 端口说明

| 端口 | 服务 | 是否必需？ | 访问来源 | 说明 |
|:----:|:-----|:---------:|:---------|:-----|
| **6080** | noVNC | 可选 | 浏览器 | JADX 图形界面网页访问。无头模式可省略 `-p 6080:6080`。 |
| **8650** | JADX 插件 API | 否* | 容器内部 | 内部 HTTP API。仅在多容器部署或调试时需要暴露。 |
| **8651** | MCP Server | **必需** | AI 客户端 | **主要端点**，供 Claude、ChatGPT 等 AI 访问。始终需要。 |

> **\* 端口 8650** 仅在 MCP Server 独立容器运行时需要。单容器部署（默认）时，MCP Server 通过内部 `localhost:8650` 连接 JADX 插件。

### 不同场景的部署命令

<details open>
<summary><strong>🎯 标准模式（图形界面 + AI + 缓存）- 推荐</strong></summary>

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

访问地址：
- JADX 图形界面：http://localhost:6080
- AI 端点：http://localhost:8651/mcp

> 📦 缓存卷可将后续分析速度提升 10-50 倍。

</details>

<details>
<summary><strong>🤖 无头模式（仅 AI，无图形界面）</strong></summary>

```bash
docker run -d --name jadx \
  -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

访问地址：
- AI 端点：http://localhost:8651/mcp

</details>

<details>
<summary><strong>🔧 开发 / 多容器模式（所有端口）</strong></summary>

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8650:8650 -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

访问地址：
- JADX 图形界面：http://localhost:6080
- JADX 插件 API：http://localhost:8650
- AI 端点：http://localhost:8651/mcp

</details>

---

## 📖 文档

### 入门指南

| 文档 | 说明 |
|:-----|:-----|
| [快速开始](docs/getting-started/quickstart.zh-cn.md) | 5 分钟 Docker 部署 |
| [详细安装](docs/getting-started/installation.zh-cn.md) | 全平台详细安装 |

### 参考文档

| 文档 | 说明 |
|:-----|:-----|
| [工具参考](docs/reference/tools.zh-cn.md) | 完整的 45 个 MCP 工具矩阵 |
| [配置说明](docs/reference/configuration.zh-cn.md) | 所有配置项 |
| [常见问题](docs/troubleshooting/faq.zh-cn.md) | 常见问题解答 |

### 其他

| 文档 | 说明 |
|:-----|:-----|
| [安全说明](docs/security/security.zh-cn.md) | 认证与权限 |
| [更新日志](docs/changelog/CHANGELOG.zh-cn.md) | 版本历史 |

---

## 🛠️ MCP 工具概览

**45 个工具** 用于 APK/JAR 分析：

| 类别 | 工具 |
|:-----|:-----|
| **代码分析** | `get_class_source`, `get_method_by_name`, `get_class_info` |
| **搜索** | `search_classes_by_keyword`, `search_native_methods` |
| **交叉引用** | `get_xrefs_to_class`, `get_xrefs_to_method` |
| **批量操作** | `batch_get_class_source`, `batch_get_xrefs` |
| **Android** | `get_android_manifest`, `get_smali_of_class` |
| **JAR** | `jar_get_manifest`, `jar_get_entry_points` |
| **实例管理** | `list_jadx_instances`, `add_jadx_instance` |

> 完整矩阵见 [工具参考](docs/reference/tools.zh-cn.md)。

---

## 🙏 致谢

- 原项目：[@zinja-coder](https://github.com/zinja-coder/jadx-ai-mcp)
- JADX 反编译器：[skylot/jadx](https://github.com/skylot/jadx)

---

## 📜 许可证

Apache 2.0 - 见 [LICENSE](LICENSE)
