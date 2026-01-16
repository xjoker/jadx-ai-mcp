# JADX-AI-MCP

<div align="center">

**让 AI 直接分析 Android APK 的 JADX 插件**

> 🔱 基于 [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp) 增强开发

![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)

[English](README.md)

</div>

---

## 🤖 这是什么？

**JADX-AI-MCP** 是一个让 **Claude、ChatGPT 等 AI 直接分析 Android APK** 的工具。

### 它能做什么？

| 功能 | 示例 |
|:-----|:-----|
| 🔍 **代码搜索** | "找到所有加密相关的类" |
| 📖 **代码阅读** | "解释 MainActivity 的 onCreate 做了什么" |
| 🔗 **引用追踪** | "谁调用了这个登录方法？" |
| 🛡️ **安全审计** | "检查这个类有没有硬编码密钥" |
| ✏️ **逆向辅助** | "把这个混淆类重命名为有意义的名字" |

### 它解决什么问题？

传统逆向工作流：
```
打开 JADX → 手动搜索 → 复制代码 → 粘贴给 AI → 看回复 → 再搜索... 🔄
```

使用 JADX-AI-MCP：
```
打开 JADX → AI 自动分析 → 直接得到答案 ✅
```

**AI 可以直接访问整个 APK 的反编译代码**，不需要你手动复制粘贴！

---

## 🚀 快速开始

### 方式 A：Docker 一键部署（推荐 ⭐）

```bash
# 1. 创建工作目录
mkdir -p ~/jadx-ai-mcp/apks
cd ~/jadx-ai-mcp

# 2. 启动容器
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/jadx-ai-mcp/apks:/apks \
  xjoker/jadx-ai-mcp:latest

# 3. 将 APK 放入 ~/jadx-ai-mcp/apks/ 目录
```

**访问方式：**
- 🌐 浏览器打开 http://localhost:6080（JADX 桌面）
- 📂 在 JADX 中：File → Open → `/apks/你的应用.apk`

> 💡 **让 AI 指导你安装？** 将以下内容发给 AI：
> ```
> 按照这里的说明指导我安装 JADX-AI-MCP：https://raw.githubusercontent.com/xjoker/jadx-ai-mcp/jadx-ai/docs/INSTALL_GUIDE.md
> ```

---

### 方式 B：本地安装（需要 Java + Python）

<details>
<summary>点击展开本地安装步骤</summary>

```bash
# 1️⃣ 安装 JADX 插件
jadx plugins --install "github:xjoker:jadx-ai-mcp"

# 2️⃣ 安装 MCP Server
pip install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"

# 3️⃣ 启动
jadx-gui your-app.apk  # 打开 APK
jadx_mcp_server        # 启动 MCP Server（新终端）
```

</details>

---


### 🔌 配置 AI 客户端

**Claude Desktop** - 编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "jadx": { "type": "http", "url": "http://localhost:8651/mcp" }
  }
}
```

---

### ✅ 验证是否成功

在 AI 对话中说：

> "列出当前 APK 的所有 Activity"

如果返回 Activity 列表，配置成功！🎉

---

## 📚 文档

| 文档 | 说明 |
|:-----|:-----|
| [安装指南](docs/INSTALL_GUIDE.md) | AI 智能体使用的详细安装说明 |
| [快速开始](docs/QUICK_START.zh-cn.md) | 人类用户详细步骤 |
| [Docker 部署](docs/DOCKER.zh-cn.md) | 容器化部署 |
| [工具列表](docs/TOOLS.md) | 50+ MCP 工具 |
| [常见问题](docs/FAQ.md) | 故障排除 |
| [更新日志](docs/CHANGELOG.zh-cn.md) | 版本历史 |


---

## 🙏 致谢

- 原项目 [@zinja-coder](https://github.com/zinja-coder/jadx-ai-mcp)
- JADX 反编译器 [@skylot](https://github.com/skylot/jadx)

## 📄 许可证

Apache 2.0 License

---

<div align="center">
❤️ 为逆向工程社区而构建
</div>
