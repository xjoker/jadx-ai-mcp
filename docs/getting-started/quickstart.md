# Quick Start Guide

**English** | [简体中文](quickstart.zh-cn.md)

---

> ⏱️ Get started in 5 minutes with Docker!

## Prerequisites

- Docker installed ([download](https://docker.com))
- APK or JAR file to analyze

---

## 🚀 One-Command Start

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  xjoker/jadx-ai-mcp:latest
```

**Access Points:**
- 🌐 **JADX Desktop**: http://localhost:6080
- 🤖 **MCP Server**: http://localhost:8651

---

## 📱 Load Your APK

1. Copy APK to `~/apks/` folder
2. Open http://localhost:6080 in browser
3. In JADX: **File → Open → /apks/your-app.apk**

> 💡 Tip: Name your file `target.apk` for auto-loading

---

## 🔌 Connect AI Client

### Claude Desktop

Edit `claude_desktop_config.json`:

| OS | Path |
|:---|:-----|
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

Restart Claude Desktop.

### Cursor

Settings → MCP → Add Server:
- Name: `jadx`
- Type: `HTTP`
- URL: `http://localhost:8651/mcp`

---

## ✅ Test

Ask Claude:

> "List the main activity of this APK"

If successful, you're done! 🎉

---

## 🔗 Next Steps

- [Docker Options](../deployment/docker.md) - Cache, config volumes
- [Docker Compose](../deployment/docker-compose.md) - Multi-instance setup
- [Local Installation](../deployment/local.md) - Without Docker
- [AI Integration](../guides/ai-integration.md) - More AI clients
