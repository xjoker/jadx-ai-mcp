#!/bin/bash
set -e

CONFIG_FILE="/opt/jadx/jadx-mcp-server/data/config/jadx-config.toml"

# ============================================================
# Auto-generate admin token if no users are configured
# ============================================================
# Check if the config file has any active (uncommented) [[users]] section
if ! grep -q '^\[\[users\]\]' "$CONFIG_FILE" 2>/dev/null; then
    # Generate a random token (32 hex chars)
    AUTO_TOKEN=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')

    # Also check for MCP_AUTH_TOKEN env var override
    if [ -n "$MCP_AUTH_TOKEN" ]; then
        AUTO_TOKEN="$MCP_AUTH_TOKEN"
        echo "[AUTH] Using MCP_AUTH_TOKEN from environment variable"
    else
        echo "[AUTH] No [[users]] found in config — generating default admin token"
    fi

    # Append admin user to config file
    cat >> "$CONFIG_FILE" << EOF

# Auto-generated admin user (created at container startup)
[[users]]
name = "admin"
token = "${AUTO_TOKEN}"
is_admin = true
EOF

    echo ""
    echo "========================================================"
    echo "  MCP Authentication Token (auto-generated)"
    echo "========================================================"
    echo ""
    echo "  Token: ${AUTO_TOKEN}"
    echo ""
    echo "  Connect with Claude Code:"
    echo "    claude mcp add --transport http jadx http://<host>:8651/mcp \\"
    echo "      --header \"Authorization:Bearer ${AUTO_TOKEN}\""
    echo ""
    echo "  To use a custom token, restart with:"
    echo "    docker run -e MCP_AUTH_TOKEN=your-token ..."
    echo ""
    echo "  Or mount a config file with [[users]] section."
    echo "========================================================"
    echo ""
else
    echo "[AUTH] Users configured in ${CONFIG_FILE}"
fi

echo "================================================"
echo "  JADX-AI-MCP Docker Container Starting..."
echo "================================================"
echo ""
echo "  Ports:"
echo "    6080  - noVNC Web Desktop (VNC viewer)"
echo "    8650  - JADX Plugin API"
echo "    8651  - MCP Server (connect AI clients here)"
echo ""
echo "================================================"
echo ""

# Start supervisor to manage all services
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
