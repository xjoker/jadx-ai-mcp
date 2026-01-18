<div align="center">

# JADX-AI-MCP

> 🔱 基于 [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp) 增强开发

⚡ 让 AI 直接分析 Android APK 和 Java JAR 文件

![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)

[📖 完整文档](docs/index.zh-cn.md) | [English](README.md)

</div>

---

## ⚡ 30 秒快速开始

```bash
# 一键启动
docker run -d --name jadx -p 6080:6080 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest

# 打开浏览器
open http://localhost:6080
```

**完成！** 将你的 APK 或 JAR 放入 `~/apks/`，在 JADX 中打开，让 AI 帮你分析。

> 💡 **让 AI 指导安装？** 发送给 Claude/ChatGPT：
> ```
> 按照这里的说明指导我安装：https://raw.githubusercontent.com/xjoker/jadx-ai-mcp/jadx-ai/docs/getting-started/installation.md
> ```

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

## 🚀 部署方式

| 方式 | 适用场景 | 指南 |
|:-----|:---------|:-----|
| **Docker**（推荐）| 快速开始，个人使用 | [→ Docker 指南](docs/deployment/docker.zh-cn.md) |
| **Docker Compose** | 多实例，团队使用 | [→ Compose 指南](docs/deployment/docker-compose.zh-cn.md) |
| **本地安装** | 开发调试，定制修改 | [→ 本地指南](docs/deployment/local.zh-cn.md) |

### 端口说明

| 端口 | 服务 | 说明 |
|:----:|:-----|:-----|
| **6080** | noVNC | JADX GUI 网页访问 |
| **8650** | JADX 插件 | 内部 API |
| **8651** | MCP Server | AI 客户端连接点 |

### 推荐 Docker 命令（带缓存）

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

> 📦 缓存卷可显著加速后续分析。

---

## 📖 文档

### 入门指南

| 文档 | 说明 |
|:-----|:-----|
| [快速开始](docs/getting-started/quickstart.zh-cn.md) | 5 分钟 Docker 部署 |
| [详细安装](docs/getting-started/installation.md) | 全平台详细安装 |

### 参考文档

| 文档 | 说明 |
|:-----|:-----|
| [工具参考](docs/reference/tools.zh-cn.md) | 完整的 51 个 MCP 工具矩阵 |
| [配置说明](docs/reference/configuration.zh-cn.md) | 所有配置项 |
| [常见问题](docs/troubleshooting/faq.zh-cn.md) | 常见问题解答 |

### 其他

| 文档 | 说明 |
|:-----|:-----|
| [安全说明](docs/security/security.zh-cn.md) | 认证与权限 |
| [更新日志](docs/changelog/CHANGELOG.zh-cn.md) | 版本历史 |

---

## 🛠️ MCP 工具概览

**51 个工具** 用于 APK/JAR 分析：

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
