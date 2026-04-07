# AI Integration Guide

**English** | [简体中文](ai-clients.zh-cn.md)

---

### Supported AI Clients

| Client | Connection Type | Status |
|:-------|:----------------|:------:|
| **Claude Desktop** | HTTP/MCP | ✅ Recommended |
| **Claude Code** | HTTP/MCP | ✅ Recommended |
| **OpenAI Codex CLI** | HTTP/MCP | ✅ Supported |
| **Cursor** | HTTP/MCP | ✅ Supported |
| **Continue** | HTTP/MCP | ✅ Supported |
| **ChatGPT** (Custom GPT) | HTTP | ⚠️ Limited |
| **Other MCP Clients** | HTTP/MCP | ✅ Supported |

---

### Claude Desktop Setup

#### Step 1: Locate Config File

| OS | Config Location |
|:---|:----------------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Linux** | `~/.config/Claude/claude_desktop_config.json` |

#### Step 2: Add MCP Server

**Basic (no authentication):**
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

**With Authentication:**
```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp",
      "headers": {
        "Authorization": "Bearer your-secret-token"
      }
    }
  }
}
```

**Remote Server:**
```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://your-server.com:8651/mcp",
      "headers": {
        "Authorization": "Bearer your-token"
      }
    }
  }
}
```

#### Step 3: Restart Claude

1. Completely close Claude Desktop
2. Reopen Claude Desktop
3. Look for the MCP indicator in the UI

#### Step 4: Verify Connection

Ask Claude:
> "Can you list the available JADX tools?"

If connected, Claude will show 68 MCP tools.

---

### Claude Code Setup

```bash
claude mcp add --transport http jadx http://localhost:8651/mcp \
  --header "Authorization:Bearer your-secret-token"
```

**Remote Server:**
```bash
claude mcp add --transport http jadx http://your-server.com:8651/mcp \
  --header "Authorization:Bearer your-secret-token"
```

---

### OpenAI Codex CLI Setup

Add to `~/.codex/config.toml` (global) or `.codex/config.toml` (project):

```toml
[mcp_servers.jadx]
url = "http://localhost:8651/mcp"
http_headers = { Authorization = "Bearer your-secret-token" }
```

**Remote Server:**
```toml
[mcp_servers.jadx]
url = "http://your-server.com:8651/mcp"
http_headers = { Authorization = "Bearer your-secret-token" }
```

Verify with:
```bash
codex mcp list
```

---

### Cursor Setup

#### Configuration

Add to Cursor settings (`.cursor/mcp.json`):

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

---

### Continue Setup

Add to Continue config (`~/.continue/config.json`):

```json
{
  "models": [...],
  "mcpServers": [
    {
      "name": "jadx",
      "transport": {
        "type": "http",
        "url": "http://localhost:8651/mcp"
      }
    }
  ]
}
```

---

### Multi-Instance Configuration

When connecting to multiple JADX instances:

```json
{
  "mcpServers": {
    "jadx-main": {
      "type": "http",
      "url": "http://localhost:8651/mcp",
      "headers": { "Authorization": "Bearer token-main" }
    },
    "jadx-dev": {
      "type": "http",
      "url": "http://dev-server:8651/mcp",
      "headers": { "Authorization": "Bearer token-dev" }
    }
  }
}
```

---

### Troubleshooting

#### "Cannot connect to MCP server"

1. **Check JADX is running**: 
   ```bash
   curl http://localhost:8651/health
   ```

2. **Check firewall**: Ensure port 8651 is open

3. **Check logs**:
   ```bash
   docker logs jadx  # Docker
   # or check terminal output for local
   ```

#### "Tools not showing"

1. Restart Claude Desktop completely
2. Verify JSON syntax is correct
3. Check config file location is correct

#### "Authentication failed"

1. Verify token matches `jadx-config.toml`
2. Check `Authorization: Bearer ` format (note the space)
