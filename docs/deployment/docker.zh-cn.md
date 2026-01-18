# Docker 部署

[English](docker.md) | **简体中文**

---

## 快速开始

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  xjoker/jadx-ai-mcp:latest
```

## 访问方式

- **JADX 界面**: http://localhost:6080
- **MCP 端点**: http://localhost:8651/mcp

## 端口说明

| 端口 | 服务 | 说明 |
|:----:|:-----|:-----|
| **6080** | noVNC | JADX GUI 网页访问 |
| **8650** | JADX 插件 | 内部 API（默认不暴露） |
| **8651** | MCP Server | AI 客户端连接点 |

## 推荐：带缓存卷

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  -v jadx-config:/root/.jadx-gui \
  xjoker/jadx-ai-mcp:latest
```

| 卷 | 用途 |
|:---|:-----|
| `~/apks:/apks` | 你的 APK/JAR 文件 |
| `jadx-cache:/root/.cache` | 反编译缓存（加速重复分析） |
| `jadx-config:/root/.jadx-gui` | JADX GUI 配置 |

## 平台专用命令

**macOS / Linux:**
```bash
mkdir -p ~/apks
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

**Windows PowerShell:**
```powershell
mkdir $HOME\apks -Force
docker run -d --name jadx `
  -p 6080:6080 -p 8651:8651 `
  -v $HOME\apks:/apks `
  -v jadx-cache:/root/.cache `
  xjoker/jadx-ai-mcp:latest
```

**Windows CMD:**
```cmd
mkdir %USERPROFILE%\apks
docker run -d --name jadx ^
  -p 6080:6080 -p 8651:8651 ^
  -v %USERPROFILE%\apks:/apks ^
  -v jadx-cache:/root/.cache ^
  xjoker/jadx-ai-mcp:latest
```

## 配置 AI 客户端

**Claude Desktop** (`claude_desktop_config.json`):

| 系统 | 配置文件位置 |
|:-----|:------------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

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

## 常用操作

```bash
# 查看日志
docker logs -f jadx

# 停止容器
docker stop jadx

# 启动容器
docker start jadx

# 删除容器
docker rm -f jadx

# 更新到最新版
docker pull xjoker/jadx-ai-mcp:latest
docker rm -f jadx
# 然后重新运行
```

---

## 下一步

- [配置多实例](docker-compose.zh-cn.md)
- [工具参考](../reference/tools.md)
- [常见问题](../troubleshooting/faq.md)
