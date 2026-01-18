# 本地部署

[English](local.md) | **简体中文**

---

### 系统要求

| 组件 | 版本 | 检查命令 |
|:-----|:-----|:---------|
| Java | 11+ (推荐 17) | `java -version` |
| Python | 3.10+ | `python3 --version` |
| JADX | 最新版 | `jadx --version` |

### 步骤 1：安装 JADX

**macOS (Homebrew):**
```bash
brew install jadx
```

**Windows / Linux:**
从 [JADX Releases](https://github.com/skylot/jadx/releases) 下载

### 步骤 2：安装 JADX-AI-MCP 插件

```bash
jadx plugins --install "github:xjoker:jadx-ai-mcp"
```

验证：
```bash
jadx plugins --list
# 应该显示: jadx-ai-mcp
```

**如果插件安装失败：**
```bash
# 手动下载
wget https://github.com/xjoker/jadx-ai-mcp/releases/latest/download/jadx-ai-mcp.jar
jadx plugins --install-jar jadx-ai-mcp.jar
```

### 步骤 3：安装 MCP Server

**推荐方式 (uv):**
```bash
# 安装 uv 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 MCP Server
uv tool install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"
```

**备选方式 (pip):**
```bash
pip install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"
```

### 步骤 4：启动服务

**终端 1 - 打开 JADX：**
```bash
jadx-gui /path/to/your-app.apk
```

**终端 2 - 启动 MCP Server：**
```bash
jadx_mcp_server
```

### 步骤 5：配置 AI 客户端

编辑 `claude_desktop_config.json`：

| 系统 | 位置 |
|:-----|:-----|
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

重启 Claude Desktop。

---

## Windows Specific Notes / Windows 特别说明

### Python Command
- Windows may use `python` instead of `python3`
- Or use `py -3` for Python 3

### JADX Installation
1. Download `jadx-x.x.x.zip` from releases
2. Extract to a folder (e.g., `C:\jadx`)
3. Add to PATH: `C:\jadx\bin`

---

## Next Steps / 下一步

- [Docker Deployment](docker.md) / [Docker 部署](docker.md)
- [Tools Reference](../reference/tools.md) / [工具参考](../reference/tools.zh-cn.md)
