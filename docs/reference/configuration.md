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

| Variable | Description | Default |
|:---------|:------------|:--------|
| `JADX_MCP_AUTH_TOKEN` | Authentication token for MCP | (none) |
| `JADX_HOST` | Default JADX host | `127.0.0.1` |
| `JADX_PORT` | Default JADX port | `8650` |

### Configuration Priority

1. **Environment variables** (highest)
2. **Command line arguments**
3. **Configuration file**
4. **Default values** (lowest)
