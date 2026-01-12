# JADX AI MCP - Authentication Guide

## Overview

JADX AI MCP now supports **Token-based authentication** to secure the connection between the JADX plugin and the MCP server. This prevents unauthorized access when the plugin is exposed on a network.

## 🔐 How Authentication Works

1. **Token Generation**: When the JADX AI MCP Plugin starts, it automatically generates a secure random authentication token
2. **Token Storage**: The token is stored in `~/.jadx-ai-mcp/auth.properties`
3. **Authentication State**: By default, authentication is **DISABLED** for backward compatibility
4. **Token Validation**: When enabled, all API requests (except `/health`) must include a valid Bearer token

## 🚀 Quick Start

### Step 1: Enable Authentication in JADX Plugin

1. Open JADX GUI with the JADX AI MCP Plugin installed
2. Navigate to menu: **Plugins → JADX AI MCP Server → Authentication Settings...**
3. Click **"Enable Auth"** button
4. **Copy** the authentication token (click the "Copy" button)
5. Click **"Restart Server"** from the menu

![Authentication Settings Dialog](../docs/assets/auth-dialog.png)

### Step 2: Configure MCP Server with Token

#### Method 1: Command Line (Recommended)

```bash
uv run jadx_mcp_server.py --auth-token "YOUR_TOKEN_HERE"
```

#### Method 2: Claude Desktop Configuration

Edit your Claude Desktop config file:

**Linux/macOS**: `~/.config/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "jadx-mcp-server": {
      "command": "/path/to/uv",
      "args": [
        "--directory",
        "/path/to/jadx-ai-mcp/jadx-mcp-server/",
        "run",
        "jadx_mcp_server.py",
        "--auth-token",
        "YOUR_TOKEN_HERE"
      ]
    }
  }
}
```

#### Method 3: HTTP Stream Mode

```bash
uv run jadx_mcp_server.py --http --port 8651 --auth-token "YOUR_TOKEN_HERE"
```

## 🌐 Remote Access Configuration

If you want to access JADX from a remote machine:

### Configure JADX Plugin Host Binding

Currently, the plugin binds to `127.0.0.1` by default. To enable remote access, you would need to modify the plugin source code to bind to `0.0.0.0` or a specific network interface IP.

> **⚠️ Security Warning**: When binding to `0.0.0.0`, ALWAYS enable authentication to prevent unauthorized access!

### Configure MCP Server for Remote JADX

```bash
# Connect to JADX running on a remote host
uv run jadx_mcp_server.py \
  --jadx-host 192.168.1.100 \
  --jadx-port 8650 \
  --auth-token "YOUR_TOKEN_HERE"
```

### Bind MCP Server to Network Interface

```bash
# Allow MCP server to accept connections from network
uv run jadx_mcp_server.py \
  --http \
  --host 0.0.0.0 \
  --port 8651 \
  --auth-token "YOUR_TOKEN_HERE"
```

## 🛠️ Command Line Options

### jadx_mcp_server.py Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--http` | False | Enable HTTP stream mode (vs stdio) |
| `--host` | `127.0.0.1` | Bind address for MCP server |
| `--port` | `8651` | Port for HTTP mode |
| `--jadx-host` | `127.0.0.1` | JADX plugin host address |
| `--jadx-port` | `8650` | JADX plugin port |
| `--auth-token` | `None` | Authentication token (if auth enabled) |

### Examples

```bash
# Basic usage (localhost only, no auth)
uv run jadx_mcp_server.py

# With authentication
uv run jadx_mcp_server.py --auth-token "abcd1234..."

# Remote JADX with auth
uv run jadx_mcp_server.py \
  --jadx-host 192.168.1.100 \
  --jadx-port 8650 \
  --auth-token "abcd1234..."

# HTTP mode with auth, accessible from network
uv run jadx_mcp_server.py \
  --http \
  --host 0.0.0.0 \
  --port 8651 \
  --auth-token "abcd1234..."
```

## 🔧 Managing Authentication

### View Current Token

In JADX GUI:
- **Plugins → JADX AI MCP Server → Authentication Settings...**
- Token is displayed and can be copied to clipboard

Or check the file directly:
```bash
cat ~/.jadx-ai-mcp/auth.properties
```

### Regenerate Token

1. Open **Authentication Settings** in JADX
2. Click **"Regenerate Token"**
3. Copy the new token
4. Update your `jadx_mcp_server.py` configuration
5. Restart both JADX server and MCP server

### Disable Authentication

1. Open **Authentication Settings** in JADX
2. Click **"Disable Auth"**
3. Restart the JADX server
4. Remove `--auth-token` parameter from MCP server

## 🔒 Security Best Practices

### ✅ DO:
- **Enable authentication** when exposing the plugin on any network
- **Use strong tokens** (auto-generated tokens are cryptographically secure)
- **Regenerate tokens periodically** especially if you suspect compromise
- **Use HTTPS/TLS** when accessing MCP server over the internet (consider a reverse proxy)
- **Restrict network access** using firewalls when possible

### ❌ DON'T:
- **Don't share tokens** publicly or commit them to version control
- **Don't expose unauthenticated plugins** to untrusted networks
- **Don't use `0.0.0.0` binding** without authentication enabled
- **Don't transmit tokens** over unencrypted channels in production

## 🐛 Troubleshooting

### "Authentication failed" Error

**Symptoms**: MCP tools return 401 Unauthorized errors

**Solutions**:
1. Verify token is correctly copied (no extra spaces)
2. Check that authentication is enabled in JADX
3. Ensure token matches between JADX and MCP server config
4. Restart both JADX plugin and MCP server after changes

### Health Check Succeeds, But Tools Fail

**Cause**: Health check endpoint (`/health`) doesn't require authentication, but other endpoints do

**Solution**: Verify `--auth-token` parameter is provided to `jadx_mcp_server.py`

### Cannot Connect to Remote JADX

**Check**:
1. Network connectivity: `telnet <jadx-host> <jadx-port>`
2. Firewall rules allowing the port
3. JADX plugin is running and bound to correct interface
4. Use `--jadx-host` parameter with correct IP address

## 📝 Configuration File Location

Authentication token is stored in:

- **Linux/macOS**: `~/.jadx-ai-mcp/auth.properties`
- **Windows**: `%USERPROFILE%\.jadx-ai-mcp\auth.properties`

File format:
```properties
auth.token=<base64-encoded-token>
auth.enabled=true
```

## 🆘 Need Help?

- **Issues**: https://github.com/zinja-coder/jadx-ai-mcp/issues
- **Documentation**: https://jadx-ai-mcp.readthedocs.io/
- **Community**: Join our discussions on GitHub

---

**Version**: 6.0.0
**Last Updated**: 2026-01-12
