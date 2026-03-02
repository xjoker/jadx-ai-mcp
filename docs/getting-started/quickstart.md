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

> ⚠️ **Critical Step**: You MUST load a file in JADX before AI can connect!
>
> **Reason**: The JADX plugin uses lazy initialization and only starts after opening an APK/JAR/AAR/DEX file. Without a loaded file, the plugin is not running, and MCP Server cannot connect to JADX (connection will fail).

### Method 1: Auto-load (Recommended)

Name your file `target.apk`, `target.jar`, `target.aar`, or `target.dex` and place it in `~/apks/`. JADX will load it automatically on startup.

**Priority**: JAR > APK > AAR > DEX

```bash
# Example
cp my-app.apk ~/apks/target.apk
```

### Method 2: Manual Load

1. Copy APK to `~/apks/` folder
2. Open http://localhost:6080 in browser
3. In JADX: **File → Open → /apks/your-app.apk**

---

## 🔌 Connect AI Client

### Claude Desktop (Recommended)

Edit `claude_desktop_config.json`:

| OS | Path |
|:---|:-----|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |

**Basic Configuration (no authentication)**:
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

> 💡 **Tip**: For more clients (Cursor, Continue, with authentication, etc.), see the [AI Client Configuration Guide](../guides/ai-clients.md)

---

## ✅ Test

Ask Claude:

> "List the main activity of this APK"

If successful, you're done! 🎉

---

## 💡 Let AI Guide Your Installation?

If you encounter issues, have AI guide you step-by-step:

Send this to Claude/ChatGPT:

```
Guide me through installing JADX-AI-MCP step by step using this document:
https://raw.githubusercontent.com/xjoker/jadx-ai-mcp/jadx-ai/docs/getting-started/quickstart.md

Rules:
1. Ask me one question at a time, wait for my response before proceeding
2. Only use commands from the document, do not invent new ones
3. After each step, ask me to paste the output before continuing
4. If something fails, help me troubleshoot before moving on
```

> **If AI cannot access URLs**: Copy the content from [quickstart.md](quickstart.md) and paste it directly into the chat.

---

## 🔗 Next Steps

- [System Architecture](../overview/architecture.md) - Understand ports and component communication
- [Docker Complete Guide](../deployment/docker.md) - Cache, config volumes, multi-platform commands
- [Docker Compose](../deployment/docker-compose.md) - Multi-instance setup
- [AI Client Configuration](../guides/ai-clients.md) - Complete configuration for all clients
- [Common Issues](../troubleshooting/common-issues.md) - Troubleshooting
