# 安装指南

[English](installation.md) | **简体中文**

---

> 📖 本安装指南是专为 AI 智能体设计的双语文档，请参阅 [installation.md](installation.zh-cn.md)。
> 
> AI 会根据你的语言偏好自动使用中文进行引导。

---

## 快速开始

如果你想直接开始，请使用以下命令：

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  xjoker/jadx-ai-mcp:latest
```

然后访问 http://localhost:6080

---

## AI 引导安装

发送以下内容给 Claude/ChatGPT：

```
按照这里的说明指导我安装：
https://raw.githubusercontent.com/xjoker/jadx-ai-mcp/jadx-ai/docs/getting-started/installation.md
```

AI 会根据你的系统和偏好，用中文一步步引导你完成安装。

---

## 手动安装步骤

如果你希望手动安装，请参考以下步骤：

### 1. 检查 Docker

```bash
docker --version
```

如未安装：https://www.docker.com/products/docker-desktop/

### 2. 创建 APK 目录

```bash
mkdir -p ~/apks
```

### 3. 启动容器

**macOS / Linux:**
```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8650:8650 -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

**Windows PowerShell:**
```powershell
docker run -d --name jadx `
  -p 6080:6080 -p 8650:8650 -p 8651:8651 `
  -v $HOME\apks:/apks `
  -v jadx-cache:/root/.cache `
  xjoker/jadx-ai-mcp:latest
```

### 4. 访问 JADX

打开浏览器：http://localhost:6080

### 5. 配置 AI 客户端

**Claude Desktop** (`claude_desktop_config.json`):

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

### 6. 测试

在 Claude 中询问：

> 列出这个 APK 的 MainActivity

如果成功返回结果，安装完成！🎉

---

## 常见问题

| 问题 | 解决方案 |
|:-----|:---------|
| 容器名称冲突 | `docker rm -f jadx` 然后重新运行 |
| 端口被占用 | 使用 `-p 6081:6080` 映射到其他端口 |
| APK 看不到 | 确保 APK 在 `~/apks` 目录中 |

---

## 相关文档

- [Docker 部署](../deployment/docker.zh-cn.md)
- [AI 集成指南](../guides/ai-integration.zh-cn.md)
- [常见问题](../troubleshooting/faq.zh-cn.md)
