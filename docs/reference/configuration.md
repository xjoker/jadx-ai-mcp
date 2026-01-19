# Configuration Reference

**English** | [简体中文](configuration.zh-cn.md)

---

### Configuration File Location

| Deployment | Location |
|:-----------|:---------|
| Docker | `/app/data/config/jadx-config.toml` |
| Local | `./data/config/jadx-config.toml` |

### Complete Example

```toml
# jadx-config.toml

# ============================================
# Security Settings
# ============================================
[security]
# Allow dynamic instance addition via MCP tool
# Default: false (recommended for production)
allow_dynamic_instances = false

# ============================================
# Default Settings
# ============================================
[defaults]
# Token for JADX plugin authentication
jadx_token = ""

# Health check interval in seconds
health_check_interval = 30

# ============================================
# User Authentication (Multi-user mode)
# ============================================
[[users]]
name = "alice"
token = "token-alice-xxxxx"

[[users]]
name = "admin"
token = "token-admin-zzzzz"
is_admin = true  # Can manage instances

# ============================================
# JADX Instances
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

### Environment Variables

#### JADX Plugin (Java) Environment Variables

| Variable | Description | Default |
|:---------|:------------|:--------|
| `JADX_MCP_BIND_ADDRESS` | Plugin HTTP server bind address | `127.0.0.1` |
| `JADX_MCP_PORT` | Plugin HTTP server port | `8650` |
| `JADX_MCP_AUTH_TOKEN` | Plugin authentication token | (none) |
| `JADX_MCP_AUTH_ENABLED` | Enable authentication | `false` |

> 💡 Set `JADX_MCP_BIND_ADDRESS=0.0.0.0` to allow remote connections (Docker required).

#### MCP Server (Python) Environment Variables

| Variable | Description | Default |
|:---------|:------------|:--------|
| `JADX_MCP_HOST` | MCP Server bind address | `0.0.0.0` |
| `JADX_HOST` | Default JADX plugin host | `127.0.0.1` |
| `JADX_PORT` | Default JADX plugin port | `8650` |

### Configuration Priority

1. **Environment variables** (highest)
2. **Command line arguments**
3. **Configuration file**
4. **Default values** (lowest)
