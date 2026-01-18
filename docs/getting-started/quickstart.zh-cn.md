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

1. 将 APK 复制到 `~/apks/` 目录
2. 浏览器打开 http://localhost:6080
3. JADX 中: **File → Open → /apks/你的应用.apk**

> 💡 提示：将文件命名为 `target.apk` 可自动加载

---

## 🔌 连接 AI 客户端

### Claude Desktop

编辑 `claude_desktop_config.json`:

| 系统 | 路径 |
|:-----|:-----|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |

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

### Cursor

设置 → MCP → 添加服务器:
- Name: `jadx`
- Type: `HTTP`
- URL: `http://localhost:8651/mcp`

---

## ✅ 测试

在 Claude 中询问：

> "列出这个 APK 的主 Activity"

如果成功返回结果，安装完成！🎉

---

## 🔗 下一步

- [Docker 选项](../deployment/docker.zh-cn.md) - 缓存、配置卷
- [Docker Compose](../deployment/docker-compose.zh-cn.md) - 多实例部署
- [本地安装](../deployment/local.zh-cn.md) - 无 Docker 安装
- [AI 集成](../guides/ai-integration.zh-cn.md) - 更多 AI 客户端
