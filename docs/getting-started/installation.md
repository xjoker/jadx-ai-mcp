# JADX-AI-MCP Installation Guide

> 🤖 This document is for AI agents to guide users through installation.
> 本文档供 AI 智能体读取，用于指导用户安装。

---

## Step 0: Language / 语言选择

**Ask the user directly / 直接询问用户：**

> "Would you prefer English or 中文 for this installation guide?"  
> "你希望使用 English 还是中文进行安装指导？"

Then respond in the user's chosen language throughout.

---

## Step 1: User Environment / 了解用户环境

Ask the user / 询问用户：

1. **What operating system are you using?** (macOS / Windows / Linux)  
   **你使用什么操作系统？**（macOS / Windows / Linux）

2. **Where would you like to install? Is the current directory okay?**  
   **你想安装在哪里？当前目录可以吗？**
   
   - If user specifies a path, use that path in all subsequent commands  
     如果用户指定了路径，后续命令都使用该路径
   - Replace `./apks` with user's chosen path + `/apks`  
     将 `./apks` 替换为用户选择的路径 + `/apks`

---

## Step 2: Check Docker / 检查 Docker

**Unix (macOS/Linux):**
```bash
docker --version
```

**Windows (PowerShell):**
```powershell
docker --version
```

If not installed, guide to / 如未安装，引导至：https://www.docker.com/products/docker-desktop/

---

## Step 2: Create APK Directory / 创建 APK 目录

Create an `apks` folder in user's chosen installation directory.  
在用户选择的安装目录下创建 `apks` 文件夹。

**⚠️ Replace `./apks` with user's specified path if they didn't choose current directory!**  
**⚠️ 如果用户指定了其他路径，请将 `./apks` 替换为用户指定的路径！**

**Unix (macOS/Linux):**
```bash
mkdir -p ./apks
```

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path .\apks
```

### APK Loading Options / APK 加载方式

**Option A: Auto-load `target.apk` / 自动加载**

If you name your APK as `target.apk`, JADX will load it automatically on startup.  
如果将 APK 命名为 `target.apk`，JADX 启动时会自动加载。

```bash
cp your-app.apk ./apks/target.apk
```

**Option B: Manual selection in noVNC / 在 noVNC 中手动选择**

Put any APK in `apks` folder, then in JADX Desktop: **File → Open → `/apks/your-app.apk`**  
将 APK 放入 `apks` 文件夹，然后在 JADX 桌面中：**File → Open → `/apks/你的应用.apk`**

---

## Step 4: Start Container / 启动容器

**⚠️ Adapt the volume path to user's chosen installation directory!**  
**⚠️ 请根据用户选择的安装目录调整卷映射路径！**

**⚠️ SECURITY: Default binds to localhost only. For network access, see Security section.**  
**⚠️ 安全提示：默认仅绑定 localhost。如需网络访问，请参阅安全章节。**

**Unix (macOS/Linux):**
```bash
docker run -d --name jadx \
  -p 127.0.0.1:6080:6080 \
  -p 127.0.0.1:8651:8651 \
  -v "$(pwd)/apks:/apks" \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

**Windows (PowerShell):**
```powershell
docker run -d --name jadx `
  -p 127.0.0.1:6080:6080 `
  -p 127.0.0.1:8651:8651 `
  -v "${PWD}\apks:/apks" `
  -v jadx-cache:/root/.cache `
  xjoker/jadx-ai-mcp:latest
```

**Windows (CMD):**
```cmd
docker run -d --name jadx -p 127.0.0.1:6080:6080 -p 127.0.0.1:8651:8651 -v "%cd%\apks:/apks" -v jadx-cache:/root/.cache xjoker/jadx-ai-mcp:latest
```

**Ports / 端口说明：**
- `6080`: noVNC Desktop (浏览器访问 JADX 桌面)
- `8651`: MCP Server (AI 客户端连接端口)

---

## Step 5: Access JADX Desktop / 访问 JADX 桌面

Tell user / 告诉用户：

1. Open browser / 打开浏览器：**http://localhost:6080**
2. If using `target.apk`, it loads automatically / 如果使用 `target.apk` 会自动加载
3. Otherwise: **File → Open → `/apks/your-app.apk`**  
   否则：**File → Open → `/apks/你的应用.apk`**

**Verify APK loaded / 验证 APK 已加载：**
- JADX window title should show the APK name / JADX 窗口标题应显示 APK 名称
- Class tree on the left should be populated / 左侧类列表应有内容

---

## Step 6: Verify Services / 验证服务

**Unix (macOS/Linux):**
```bash
docker ps | grep jadx
```
```bash
curl http://localhost:8651/health
```
Expected / 预期输出: `{"status":"ok"}`

**Windows (PowerShell):**
```powershell
docker ps | Select-String jadx
```
```powershell
Invoke-RestMethod http://localhost:8651/health
```
Expected / 预期输出: `@{status=ok}`

---

## About Authentication / 关于认证

**For local use (default), no token is required.**  
**本地使用（默认）不需要配置 Token。**

The All-in-One Docker image runs without authentication by default, which is fine for local development.  
All-in-One Docker 镜像默认不需要认证，适合本地开发使用。

**⚠️ For public/network deployment, configure authentication:**  
**⚠️ 如果在网络上公开部署，请配置认证：**

See [SECURITY.md](../security/security.md) for production security configuration.  
生产环境安全配置请参考 [SECURITY.md](../security/security.md)。

---

## Step 6: Configure AI Client / 配置 AI 客户端


### Claude Desktop

**⚠️ IMPORTANT: Backup config before editing! / 重要：编辑前请备份配置！**

Config file location / 配置文件位置：
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

**Step 6.1: Backup existing config / 备份现有配置**

**macOS:**
```bash
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json.bak
```

**Linux:**
```bash
cp ~/.config/claude/claude_desktop_config.json ~/.config/claude/claude_desktop_config.json.bak
```

**Windows (PowerShell):**
```powershell
Copy-Item "$env:APPDATA\Claude\claude_desktop_config.json" "$env:APPDATA\Claude\claude_desktop_config.json.bak"
```

**Step 6.2: Edit config / 编辑配置**

If config file is empty or doesn't exist, create with / 如果配置文件为空或不存在，创建：

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

If config already has `mcpServers`, ADD `jadx` to existing object (don't replace!):  
如果已有 `mcpServers`，将 `jadx` 添加到现有对象中（不要替换！）：

```json
{
  "mcpServers": {
    "existing-server": { ... },
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp"
    }
  }
}
```

**Step 6.3: Restart Claude Desktop / 重启 Claude Desktop**

---

### OpenAI Codex CLI

**Option A: Use CLI command / 使用命令行**

Codex CLI doesn't support adding HTTP servers via CLI directly. Use config.toml instead.  
Codex CLI 不支持通过命令行直接添加 HTTP 服务器，请使用 config.toml。

**Option B: Edit `~/.codex/config.toml` / 编辑配置文件**

Add the following to `~/.codex/config.toml`:  
将以下内容添加到 `~/.codex/config.toml`：

```toml
[mcp_servers.jadx]
url = "http://localhost:8651/mcp"
```

Verify in Codex TUI with `/mcp` command.  
在 Codex 中使用 `/mcp` 命令验证。

> 📖 Reference / 参考：https://developers.openai.com/codex/mcp

---


### Cursor

Open Cursor Settings → MCP → Add Server:
打开 Cursor 设置 → MCP → 添加服务器：

- **Name**: `jadx`
- **Type**: `HTTP`
- **URL**: `http://localhost:8651/mcp`

### Other MCP Clients / 其他 MCP 客户端

Connect to / 连接地址：`http://localhost:8651/mcp`

---

## Step 7: Final Test / 最终测试

Ask user to test / 让用户测试：

> "List the MainActivity of this APK"  
> "列出这个 APK 的 MainActivity"

If successful, installation is complete! 🎉  
如果成功返回结果，安装完成！🎉

---

## Troubleshooting / 常见问题

### Container name conflict / 容器名称冲突
```bash
docker rm -f jadx
# Then run Step 3 again / 然后重新执行步骤 3
```

### Port already in use / 端口被占用
```bash
docker run -d --name jadx -p 6081:6080 -p 8651:8651 ...
# Then access / 然后访问 http://localhost:6081
```

### APK not visible / APK 看不到
- Ensure APK is in `apks` folder / 确保 APK 在 `apks` 文件夹中
- In JADX path is `/apks/filename.apk` / JADX 中路径是 `/apks/文件名.apk`

### Config backup restore / 恢复配置备份
```bash
# Unix
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json.bak ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows PowerShell
Copy-Item "$env:APPDATA\Claude\claude_desktop_config.json.bak" "$env:APPDATA\Claude\claude_desktop_config.json"
```

---

## 🎉 Done! / 完成！

Tell user / 告诉用户：

**English:** "JADX-AI-MCP is installed! Ask me anything about this APK, like: 'Analyze the login flow'"

**中文：** "安装成功！现在你可以问我关于这个 APK 的任何问题，比如：'分析一下登录流程'"
