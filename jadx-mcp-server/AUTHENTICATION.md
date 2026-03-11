# Authentication Guide

This server has two distinct authentication planes:

## 1. MCP Client Authentication

Used for `/mcp` and MCP tool calls.

Current implementation:

- FastMCP 3.1 HTTP auth
- Static token verification sourced from `[[users]]` or `--mcp-auth-token`
- User context is mapped into the project permission model

Example:

```toml
[[users]]
name = "viewer"
token = "viewer-secret-token"

[[users]]
name = "admin"
token = "admin-secret-token"
is_admin = true
```

Client usage:

```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp",
      "headers": {
        "Authorization": "Bearer viewer-secret-token"
      }
    }
  }
}
```

## 2. JADX Plugin Authentication

Used for MCP server to plugin HTTP calls.

Configure via:

- `[defaults].jadx_token`
- per-instance `token`
- `--auth-token`
- plugin-side `JADX_MCP_AUTH_TOKEN`

## 3. Status Page Authentication

`/status` and `/status.json` use the same configured user tokens, but through the
project status-page flow instead of FastMCP transport auth.

## Notes

- Anonymous MCP access is only allowed when no users are configured
- Pure pull mode is intentional; auth does not change the instance discovery model
- Auth hot-reload currently supports token/user updates only when the server stays
  in the same auth mode

For full security guidance, see:

- `https://github.com/xjoker/jadx-ai-mcp/blob/dev/docs/security/security.md`
- `https://github.com/xjoker/jadx-ai-mcp/blob/dev/docs/guides/ai-clients.md`
