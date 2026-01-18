<div align="center">

# JADX-AI-MCP

> 🔱 基于 [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp) 增强开发

⚡ 让 AI 直接分析 Android APK 和 Java JAR 文件

![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)

[English](README.md) | [详细文档](docs/README.zh-cn.md)

</div>

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

## 🚀 快速开始

### Docker 部署（推荐 ⭐）

```bash
# 1. 创建工作目录
mkdir -p ~/jadx-ai-mcp/apks && cd ~/jadx-ai-mcp

# 2. 启动容器
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/jadx-ai-mcp/apks:/apks \
  xjoker/jadx-ai-mcp:latest

# 3. 将 APK/JAR 放入 ~/jadx-ai-mcp/apks/
```

**访问方式：**
- 🌐 浏览器：http://localhost:6080（JADX 桌面）
- 📂 在 JADX 中：File → Open → `/apks/你的应用.apk`

> 💡 **让 AI 指导安装？** 发送给 AI：
> ```
> 按照这里的说明指导我安装：https://raw.githubusercontent.com/xjoker/jadx-ai-mcp/jadx-ai/docs/INSTALL_GUIDE.md
> ```

---

## 📖 文档

| 文档 | 说明 |
|:-----|:-----|
| [快速开始](docs/QUICK_START.zh-cn.md) | Docker 部署指南 |
| [工具参考](docs/TOOLS.md) | 51 个 MCP 工具 |
| [详细文档](docs/README.zh-cn.md) | 完整中文文档 |
| [安全说明](docs/SECURITY.zh-cn.md) | 认证与权限 |
| [更新日志](docs/CHANGELOG.zh-cn.md) | 版本历史 |

---

## 🙏 致谢

- 原项目：[@zinja-coder](https://github.com/zinja-coder/jadx-ai-mcp)
- JADX 反编译器：[skylot/jadx](https://github.com/skylot/jadx)

---

## 📜 许可证

Apache 2.0 - 见 [LICENSE](LICENSE)
