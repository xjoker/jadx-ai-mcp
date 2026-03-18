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
enabled = true

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

#### Docker Compose Environment Variables

| Variable | Description | Default |
|:---------|:------------|:--------|
| `TZ` | Timezone for all containers | `UTC` |

See `docker/.env.example` for a quick-start template.

#### MCP Server / Transfer API Environment Variables

| Variable | Description | Default |
|:---------|:------------|:--------|
| `MCP_SERVER_URL` | Public MCP Server URL used when generating Transfer API download links | `http://localhost:8651` fallback |

> The standalone MCP Server does not currently expose `JADX_HOST` / `JADX_PORT` environment variables. Configure bind address, default JADX endpoint, and multi-instance registration with CLI arguments or `jadx-config.toml`.

### HTTP Endpoints

| Endpoint | Auth | Description |
|:---------|:-----|:------------|
| `/mcp` | Bearer Token | MCP protocol (SSE transport) |
| `/health` | None | Lightweight health check (used by Docker healthcheck) |
| `/status` | Cookie | Human-readable status dashboard |
| `/status.json` | Cookie | Machine-readable status snapshot |
| `/transfer/download/batch-classes` | Transfer Token | Batch class download |

### Configuration Priority

1. **JADX plugin runtime**: environment variables → saved preferences → built-in defaults
2. **MCP Server bind address / default JADX endpoint**: command line arguments → configuration file → built-in defaults
3. **Transfer API public URL**: `MCP_SERVER_URL` → `[server].mcp_url` → `http://localhost:8651`
