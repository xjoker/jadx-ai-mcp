# 配置参考

[English](configuration.md) | **简体中文**

---

### 配置文件位置

| 部署方式 | 位置 |
|:---------|:-----|
| Docker | `/app/data/config/jadx-config.toml` |
| 本地 | `./data/config/jadx-config.toml` |

### 完整示例

```toml
# jadx-config.toml

# ============================================
# 安全设置
# ============================================
[security]
# 允许通过 MCP 工具动态添加实例
# 默认：false（生产环境推荐）
allow_dynamic_instances = false

# ============================================
# 默认设置
# ============================================
[defaults]
# JADX 插件认证 Token
jadx_token = ""

# 健康检查间隔（秒）
health_check_interval = 30

# ============================================
# 用户认证（多用户模式）
# ============================================
[[users]]
name = "alice"
token = "token-alice-xxxxx"

[[users]]
name = "admin"
token = "token-admin-zzzzz"
is_admin = true  # 可以管理实例

# ============================================
# JADX 实例
# ============================================
[[jadx_instances]]
name = "local"
host = "127.0.0.1"
port = 8650
enabled = true

[[jadx_instances]]
name = "remote-server"
host = "192.168.1.100"
port = 8650
```

### 环境变量

#### JADX 插件 (Java) 环境变量

| 变量 | 说明 | 默认值 |
|:-----|:-----|:-------|
| `JADX_MCP_BIND_ADDRESS` | 插件 HTTP 服务绑定地址 | `127.0.0.1` |
| `JADX_MCP_PORT` | 插件 HTTP 服务端口 | `8650` |
| `JADX_MCP_AUTH_TOKEN` | 插件认证 Token | (无) |
| `JADX_MCP_AUTH_ENABLED` | 启用认证 | `false` |

> 💡 设置 `JADX_MCP_BIND_ADDRESS=0.0.0.0` 允许远程连接（Docker 部署必需）。

#### Docker Compose 环境变量

| 变量 | 说明 | 默认值 |
|:-----|:-----|:-------|
| `TZ` | 所有容器的时区 | `UTC` |

参见 `docker/.env.example` 获取快速配置模板。

#### MCP Server / Transfer API 环境变量

| 变量 | 说明 | 默认值 |
|:-----|:-----|:-------|
| `MCP_SERVER_URL` | 生成 Transfer API 下载链接时使用的 MCP Server 对外地址 | 回退到 `http://localhost:8651` |

> 独立 MCP Server 当前没有公开 `JADX_HOST` / `JADX_PORT` 这类环境变量入口。绑定地址、默认 JADX 端点和多实例注册请使用命令行参数或 `jadx-config.toml`。

### HTTP 端点

| 端点 | 认证 | 说明 |
|:-----|:-----|:-----|
| `/mcp` | Bearer Token | MCP 协议（SSE 传输） |
| `/health` | 无 | 轻量级健康检查（Docker healthcheck 使用） |
| `/status` | Cookie | 可视化状态面板 |
| `/status.json` | Cookie | 机器可读状态快照 |
| `/transfer/download/batch-classes` | Transfer Token | 批量类下载 |

### 配置优先级

1. **JADX 插件运行时**：环境变量 → 已保存 Preferences → 内建默认值
2. **MCP Server 绑定地址 / 默认 JADX 端点**：命令行参数 → 配置文件 → 内建默认值
3. **Transfer API 对外地址**：`MCP_SERVER_URL` → 配置文件 `[server].mcp_url` → `http://localhost:8651`

---

## 相关文档

- [安全配置](../security/security.zh-cn.md)
- [多实例部署](../deployment/docker-compose.zh-cn.md)
