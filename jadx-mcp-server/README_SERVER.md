# JADX MCP Server

Standalone MCP server for the JADX AI plugin.

This package exposes the HTTP MCP endpoint used by Claude, Cursor, Continue,
and other MCP clients, while talking to one or more running JADX plugin
instances over the plugin HTTP API.

## What It Includes

- HTTP MCP endpoint at `/mcp`
- Status endpoints at `/status` and `/status.json`
- Transfer API endpoints under `/transfer/*`
- Pure pull multi-instance management for external JADX containers
- FastMCP 3.1 based HTTP transport with token authentication support

## Install

Use the pinned runtime dependencies from this directory:

```bash
uv sync --frozen
```

or:

```bash
pip install -r requirements.txt
```

## Run

Single-instance example:

```bash
uv run jadx_mcp_server --http --host 0.0.0.0 --port 8651 \
  --jadx-host 127.0.0.1 --jadx-port 8650
```

Config-file example:

```bash
uv run jadx_mcp_server --http --config data/config/jadx-config.toml
```

## Configuration

- MCP server bind address and default JADX endpoint: CLI arguments or `jadx-config.toml`
- Transfer API external URL: `MCP_SERVER_URL` or `[server].mcp_url`
- Multi-instance registration: `[[jadx_instances]]` or `--jadx-instances`
- MCP client auth: `[[users]]` or `--mcp-auth-token`

Pure pull mode is intentional: the MCP server does not auto-discover Docker
containers or reverse-register JADX instances.

## Authentication

- `/mcp` uses FastMCP token verification
- `/status*` uses the project status-page login/token flow
- JADX plugin auth is configured separately from MCP client auth

See:

- `AUTHENTICATION.md`
- `https://github.com/xjoker/jadx-ai-mcp/blob/dev/docs/security/security.md`
- `https://github.com/xjoker/jadx-ai-mcp/blob/dev/docs/reference/configuration.md`

## Versioning

Source files keep development placeholder versions.

Release builds inject the actual version into:

- `pom.xml`
- `src/main/java/com/zin/jadxaimcp/utils/JadxAIMCPBanner.java`
- `src/banner.py`

This is handled by GitHub Actions during release packaging.
