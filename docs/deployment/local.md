# Local Deployment / 本地部署

**English** | [简体中文](local.zh-cn.md)

---

### Prerequisites

| Component | Version | Check Command |
|:----------|:--------|:--------------|
| Java | 11+ (17 recommended) | `java -version` |
| Python | 3.10+ | `python3 --version` |
| JADX | Latest | `jadx --version` |

### Step 1: Install JADX

**macOS (Homebrew):**
```bash
brew install jadx
```

**Windows / Linux:**
Download from [JADX Releases](https://github.com/skylot/jadx/releases)

### Step 2: Install JADX-AI-MCP Plugin

```bash
jadx plugins --install "github:xjoker:jadx-ai-mcp"
```

Verify:
```bash
jadx plugins --list
# Should show: jadx-ai-mcp
```

**If plugin install fails:**
```bash
# Manual download
wget https://github.com/xjoker/jadx-ai-mcp/releases/latest/download/jadx-ai-mcp.jar
jadx plugins --install-jar jadx-ai-mcp.jar
```

### Step 3: Install MCP Server

**Recommended (uv):**
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install MCP Server
uv tool install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"
```

**Alternative (pip):**
```bash
pip install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"
```

### Step 4: Start Services

**Terminal 1 - Open JADX with APK:**
```bash
jadx-gui /path/to/your-app.apk
```

**Terminal 2 - Start MCP Server:**
```bash
jadx_mcp_server
```

### Step 5: Configure AI Client

Edit `claude_desktop_config.json`:

| OS | Location |
|:---|:---------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

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
