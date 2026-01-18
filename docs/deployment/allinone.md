# All-in-One Deployment

**English** | [简体中文](allinone.zh-cn.md)

---

> 🐳 Production-ready single container with JADX GUI, noVNC, and MCP Server

## Overview

The All-in-One image combines:
- **JADX GUI** with MCP plugin
- **noVNC** for browser-based desktop access
- **MCP Server** for AI client connections

---

## Quick Start

```bash
docker run -d --name jadx-ai-mcp \
  -p 6080:6080 \
  -p 8650:8650 \
  -p 8651:8651 \
  -v $(pwd)/apks:/apks \
  -v $(pwd)/config:/app/data/config \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

---

## Ports

| Port | Service | Description |
|:-----|:--------|:------------|
| 6080 | noVNC | Browser desktop access |
| 8650 | Plugin API | JADX plugin HTTP API |
| 8651 | MCP Server | LLM client endpoint |

---

## Access

- **JADX Desktop**: http://localhost:6080
- **MCP Endpoint**: http://localhost:8651/mcp

---

## Volume Mounts

| Volume | Container Path | Purpose |
|:-------|:---------------|:--------|
| APK files | `/apks` | APK files to analyze |
| Config | `/app/data/config` | Configuration files |
| Cache | `/root/.cache` | Decompilation cache |
| GUI Settings | `/root/.jadx-gui` | GUI preferences |

---

## Authentication

For production use, enable authentication:

```toml
# config/jadx-config.toml
[[users]]
name = "admin"
token = "your-secure-token"
is_admin = true
```

See [Security](../security/security.md) for details.

---

## Related

- [Docker Deployment](docker.md)
- [Docker Compose](docker-compose.md)
- [Configuration Reference](../reference/configuration.md)
