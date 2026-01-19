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
default = true

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

#### MCP Server (Python) 环境变量

| 变量 | 说明 | 默认值 |
|:-----|:-----|:-------|
| `JADX_MCP_HOST` | MCP Server 绑定地址 | `0.0.0.0` |
| `JADX_HOST` | 默认 JADX 插件主机 | `127.0.0.1` |
| `JADX_PORT` | 默认 JADX 插件端口 | `8650` |

### 配置优先级

1. **环境变量**（最高）
2. **命令行参数**
3. **配置文件**
4. **默认值**（最低）

---

## 相关文档

- [安全配置](../security/security.zh-cn.md)
- [多实例部署](../deployment/docker-compose.zh-cn.md)
