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

| 变量 | 说明 | 默认值 |
|:-----|:-----|:-------|
| `JADX_MCP_AUTH_TOKEN` | MCP 认证 Token | (无) |
| `JADX_HOST` | 默认 JADX 主机 | `127.0.0.1` |
| `JADX_PORT` | 默认 JADX 端口 | `8650` |

### 配置优先级

1. **环境变量**（最高）
2. **命令行参数**
3. **配置文件**
4. **默认值**（最低）

---

## Related / 相关

- [Security](../security/security.zh-cn.md)
- [Multi-Instance Deployment](../deployment/docker-compose.zh-cn.md)
