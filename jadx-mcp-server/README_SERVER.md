# JADX MCP Server

Python-based MCP (Model Context Protocol) server for JADX AI MCP Plugin.

## Quick Start

```bash
# Install dependencies
uv pip install httpx fastmcp

# Run in stdio mode (for Claude Desktop)
uv run jadx_mcp_server.py

# Run in HTTP mode
uv run jadx_mcp_server.py --http --port 8651
```

## Features

✨ **30+ MCP Tools** for Android APK analysis
🔐 **Token Authentication** for secure access
🌐 **Remote Connection Support** via `--jadx-host`
📡 **HTTP Stream Mode** for web-based clients
🔧 **Flexible Configuration** via command-line args

## Configuration

### Basic Usage

```bash
uv run jadx_mcp_server.py
```

### With Authentication

```bash
# Get token from JADX GUI: Plugins → JADX AI MCP Server → Authentication Settings
uv run jadx_mcp_server.py --auth-token "YOUR_TOKEN_HERE"
```

### Remote JADX Connection

```bash
uv run jadx_mcp_server.py \
  --jadx-host 192.168.1.100 \
  --jadx-port 8650 \
  --auth-token "YOUR_TOKEN_HERE"
```

### HTTP Stream Mode

```bash
uv run jadx_mcp_server.py \
  --http \
  --host 0.0.0.0 \
  --port 8651 \
  --auth-token "YOUR_TOKEN_HERE"
```

## Command Line Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--http` | False | Enable HTTP stream transport |
| `--host` | `127.0.0.1` | Bind address for MCP server |
| `--port` | `8651` | Port for HTTP mode |
| `--jadx-host` | `127.0.0.1` | JADX plugin host address |
| `--jadx-port` | `8650` | JADX plugin port |
| `--auth-token` | None | Authentication token |

## Claude Desktop Configuration

Edit `~/.config/Claude/claude_desktop_config.json`:

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

## Available MCP Tools

### Class Analysis
- `fetch_current_class()` - Get currently selected class
- `get_all_classes()` - List all classes (paginated)
- `get_class_source()` - Get class source code
- `get_methods_of_class()` - List class methods
- `get_fields_of_class()` - List class fields
- `get_smali_of_class()` - Get smali bytecode

### Search
- `search_method_by_name()` - Find methods by name
- `search_classes_by_keyword()` - Search code by keyword
- `get_method_by_name()` - Get specific method

### Resources
- `get_android_manifest()` - Get AndroidManifest.xml
- `get_strings()` - Get strings.xml content
- `get_all_resource_file_names()` - List resource files
- `get_resource_file()` - Get specific resource

### Refactoring
- `rename_class()` - Rename a class
- `rename_method()` - Rename a method
- `rename_field()` - Rename a field
- `rename_package()` - Rename a package

### Debugging
- `debug_get_stack_frames()` - Get call stack
- `debug_get_threads()` - List threads
- `debug_get_variables()` - Get variables

### Cross-References
- `get_xrefs_to_class()` - Find class references
- `get_xrefs_to_method()` - Find method references
- `get_xrefs_to_field()` - Find field references

## Authentication

See [AUTHENTICATION.md](AUTHENTICATION.md) for detailed security guide.

## Requirements

- Python 3.10+
- httpx
- fastmcp
- JADX AI MCP Plugin running

## Project Structure

```
jadx-mcp-server/
├── jadx_mcp_server.py    # Main entry point
├── src/
│   ├── banner.py          # ASCII banner
│   └── server/
│       ├── config.py      # Configuration & HTTP client
│       └── tools/         # MCP tool implementations
│           ├── class_tools.py
│           ├── search_tools.py
│           ├── resource_tools.py
│           ├── refactor_tools.py
│           ├── debug_tools.py
│           └── xrefs_tools.py
├── pyproject.toml
├── requirements.txt
└── AUTHENTICATION.md
```

## Troubleshooting

### "Could not connect to JADX plugin"

1. Ensure JADX GUI is running
2. Verify JADX AI MCP Plugin is installed
3. Check plugin is listening on correct port
4. If using non-default host, use `--jadx-host`
5. If auth enabled, provide `--auth-token`

### "Authentication failed"

1. Verify token is correctly copied
2. Check auth is enabled in JADX
3. Ensure token matches between plugin and server
4. Restart both JADX plugin and MCP server

## License

Apache 2.0 - See LICENSE file

## Links

- **Main Project**: https://github.com/zinja-coder/jadx-ai-mcp
- **Documentation**: https://jadx-ai-mcp.readthedocs.io/
- **Issues**: https://github.com/zinja-coder/jadx-ai-mcp/issues

---

**Version**: 6.0.0
