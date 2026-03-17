# AI 集成指南

[English](ai-clients.md) | **简体中文**

---

### 支持的 AI 客户端

| 客户端 | 连接方式 | 状态 |
|:-------|:---------|:----:|
| **Claude Desktop** | HTTP/MCP | ✅ 推荐 |
| **Claude Code** | HTTP/MCP | ✅ 推荐 |
| **OpenAI Codex CLI** | HTTP/MCP | ✅ 支持 |
| **Cursor** | HTTP/MCP | ✅ 支持 |
| **Continue** | HTTP/MCP | ✅ 支持 |
| **ChatGPT** (Custom GPT) | HTTP | ⚠️ 有限 |
| **其他 MCP 客户端** | HTTP/MCP | ✅ 支持 |

---

### Claude Desktop 配置

#### 步骤 1：找到配置文件

| 系统 | 配置文件位置 |
|:-----|:------------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Linux** | `~/.config/Claude/claude_desktop_config.json` |

#### 步骤 2：添加 MCP Server

**基础配置（无认证）：**
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

**带认证：**
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

**远程服务器：**
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

#### 步骤 3：重启 Claude

1. 完全关闭 Claude Desktop
2. 重新打开 Claude Desktop
3. 查看 UI 中的 MCP 指示器

#### 步骤 4：验证连接

问 Claude：
> "能列出可用的 JADX 工具吗？"

如果连接成功，Claude 会显示 45 个 MCP 工具。

---

### Claude Code 配置

```bash
claude mcp add --transport http jadx http://localhost:8651/mcp \
  --header "Authorization:Bearer your-secret-token"
```

**远程服务器：**
```bash
claude mcp add --transport http jadx http://your-server.com:8651/mcp \
  --header "Authorization:Bearer your-secret-token"
```

---

### OpenAI Codex CLI 配置

在 `~/.codex/config.toml`（全局）或 `.codex/config.toml`（项目级）中添加：

```toml
[mcp_servers.jadx]
url = "http://localhost:8651/mcp"
http_headers = { Authorization = "Bearer your-secret-token" }
```

**远程服务器：**
```toml
[mcp_servers.jadx]
url = "http://your-server.com:8651/mcp"
http_headers = { Authorization = "Bearer your-secret-token" }
```

验证配置：
```bash
codex mcp list
```

---

### 故障排查

#### "无法连接到 MCP 服务器"

1. **检查 JADX 是否运行**：
   ```bash
   curl http://localhost:8651/health
   ```

2. **检查防火墙**：确保端口 8651 开放

3. **查看日志**：
   ```bash
   docker logs jadx  # Docker
   # 或查看本地终端输出
   ```

#### "工具不显示"

1. 完全重启 Claude Desktop
2. 验证 JSON 语法正确
3. 检查配置文件位置正确

#### "认证失败"

1. 验证 token 与 `jadx-config.toml` 匹配
2. 检查 `Authorization: Bearer ` 格式（注意空格）

---

## 相关文档

- [配置参考](../reference/configuration.zh-cn.md)
- [Docker 部署](../deployment/docker.zh-cn.md)
- [常见问题](../troubleshooting/common-issues.zh-cn.md)
