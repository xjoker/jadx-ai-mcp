# Quick Start Guide

[English](#english) | [简体中文](#简体中文)

---

## 简体中文

### 📋 系统要求

| 组件 | 版本要求 |
|:-----|:---------|
| Java | 11+ (推荐 17) |
| Python | 3.10+ |
| Docker | 20.10+ (仅 Docker 方式) |

### 🛠️ 方式 A：本地安装（详细步骤）

#### 步骤 1：安装 JADX

**macOS:**
```bash
brew install jadx
```

**Windows/Linux:**
从 [JADX Releases](https://github.com/skylot/jadx/releases) 下载

#### 步骤 2：安装 JADX-AI-MCP 插件

```bash
jadx plugins --install "github:xjoker:jadx-ai-mcp"
```

验证安装：
```bash
jadx plugins --list
# 应该看到 jadx-ai-mcp
```

#### 步骤 3：安装 MCP Server

**推荐方式（uv）：**
```bash
# 安装 uv 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 MCP Server
uv tool install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"
```

**备选方式（pip）：**
```bash
pip install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"
```

#### 步骤 4：启动

```bash
# 终端 1：打开 APK
jadx-gui /path/to/your-app.apk

# 终端 2：启动 MCP Server
jadx_mcp_server
```

#### 步骤 5：配置 AI 客户端

**Claude Desktop** - 编辑 `claude_desktop_config.json`：

| 系统 | 配置文件位置 |
|:-----|:------------|
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

重启 Claude Desktop 后生效。

---

### 🐳 方式 B：Docker 部署（详细步骤）

#### 步骤 1：拉取镜像

```bash
docker pull xjoker/jadx-ai-mcp:latest
```

#### 步骤 2：启动容器

**基础启动：**
```bash
docker run -d --name jadx \
  -p 6080:6080 \
  -p 8651:8651 \
  -v $(pwd)/apks:/apks \
  xjoker/jadx-ai-mcp:latest
```

**推荐启动（带缓存）：**
```bash
docker run -d --name jadx \
  -p 6080:6080 \
  -p 8651:8651 \
  -v $(pwd)/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

#### 步骤 3：访问 JADX

1. 浏览器打开 http://localhost:6080
2. 点击 File → Open
3. 输入 `/apks/your-app.apk`

#### 步骤 4：配置 AI

同上，将 `http://localhost:8651/mcp` 添加到 Claude Desktop。

---

### ❓ 常见问题

#### 插件安装失败
```bash
# 手动下载安装
wget https://github.com/xjoker/jadx-ai-mcp/releases/latest/download/jadx-ai-mcp.jar
jadx plugins --install-jar jadx-ai-mcp.jar
```

#### MCP Server 连接失败
```bash
# 检查 JADX 是否启动
curl http://localhost:8650/health
# 应该返回 {"status":"ok"}
```

#### Claude 看不到工具
1. 确保 MCP Server 正在运行：`jadx_mcp_server`
2. 检查 config.json 格式正确
3. 重启 Claude Desktop

---

## English

### 📋 Requirements

| Component | Version |
|:----------|:--------|
| Java | 11+ (17 recommended) |
| Python | 3.10+ |
| Docker | 20.10+ (Docker only) |

### 🛠️ Option A: Local Installation

#### Step 1: Install JADX

**macOS:**
```bash
brew install jadx
```

**Windows/Linux:**
Download from [JADX Releases](https://github.com/skylot/jadx/releases)

#### Step 2: Install Plugin

```bash
jadx plugins --install "github:xjoker:jadx-ai-mcp"
```

#### Step 3: Install MCP Server

```bash
uv tool install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"
```

#### Step 4: Start

```bash
# Terminal 1
jadx-gui /path/to/app.apk

# Terminal 2
jadx_mcp_server
```

#### Step 5: Configure Claude

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jadx": { "type": "http", "url": "http://localhost:8651/mcp" }
  }
}
```

---

### 🐳 Option B: Docker

```bash
docker run -d -p 6080:6080 -p 8651:8651 -v $(pwd)/apks:/apks xjoker/jadx-ai-mcp:latest
```

Access http://localhost:6080, then File → Open → `/apks/your-app.apk`

---

## 🔗 Related Docs

- [Docker Deployment](DOCKER.zh-cn.md)
- [FAQ / Troubleshooting](FAQ.md)
- [Tools Reference](TOOLS.md)
