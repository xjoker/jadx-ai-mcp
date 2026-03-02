# 快速开始

[English](quickstart.md) | **简体中文**

---

> ⏱️ 5 分钟 Docker 快速开始！

## 前置要求

- 已安装 Docker ([下载](https://docker.com))
- 要分析的 APK 或 JAR 文件

---

## 🚀 一键启动

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  xjoker/jadx-ai-mcp:latest
```

**访问地址：**
- 🌐 **JADX 桌面**: http://localhost:6080
- 🤖 **MCP Server**: http://localhost:8651

---

## 📱 加载 APK

> ⚠️ **关键步骤**：必须先在 JADX 中加载文件，AI 才能连接！
>
> **原因**：JADX 插件采用延迟加载机制，只有在打开 APK/JAR/AAR/DEX 文件后才会初始化。未加载文件时，插件未启动，MCP Server 无法连接到 JADX（连接会失败）。

### 方式 1: 自动加载（推荐）

将文件命名为 `target.apk`、`target.jar`、`target.aar` 或 `target.dex` 放入 `~/apks/` 目录，JADX 启动时自动加载。

**优先级**：JAR > APK > AAR > DEX

```bash
# 示例
cp my-app.apk ~/apks/target.apk
```

### 方式 2: 手动加载

1. 将 APK 复制到 `~/apks/` 目录
2. 浏览器打开 http://localhost:6080
3. JADX 中: **File → Open → /apks/你的应用.apk**

---

## 🔌 连接 AI 客户端

### Claude Desktop（推荐）

编辑 `claude_desktop_config.json`：

| 系统 | 路径 |
|:-----|:-----|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |

**基础配置（无认证）**：
```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp"
    }
  }
}
```

重启 Claude Desktop。

> 💡 **提示**：更多客户端配置（Cursor、Continue、带认证等）请参阅 [AI 客户端配置指南](../guides/ai-clients.zh-cn.md)

---

## ✅ 测试

在 Claude 中询问：

> "列出这个 APK 的主 Activity"

如果成功返回结果，安装完成！🎉

---

## 💡 让 AI 指导安装？

如果你遇到问题，可以让 AI 一步步引导你完成安装：

发送给 Claude/ChatGPT：

```
按照以下文档逐步指导我安装 JADX-AI-MCP：
https://raw.githubusercontent.com/xjoker/jadx-ai-mcp/jadx-ai/docs/getting-started/quickstart.md

规则：
1. 每次只问我一个问题，等待我的回复后再继续
2. 只使用文档中的命令，不要创造新命令
3. 每一步后，让我粘贴输出结果再继续
4. 如果出现问题，帮我排查后再继续
```

> **如果 AI 无法访问 URL**：从 [quickstart.md](quickstart.md) 复制内容直接粘贴到对话中。

---

## 🔗 下一步

- [系统架构](../overview/architecture.zh-cn.md) - 理解端口和组件通信
- [Docker 完整指南](../deployment/docker.zh-cn.md) - 缓存、配置卷、多平台命令
- [Docker Compose](../deployment/docker-compose.zh-cn.md) - 多实例部署
- [AI 客户端配置](../guides/ai-clients.zh-cn.md) - 所有客户端的完整配置
- [常见问题](../troubleshooting/common-issues.zh-cn.md) - 故障排查
