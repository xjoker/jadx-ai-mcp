#!/bin/bash
set -e

echo "================================================"
echo "  JADX-AI-MCP Docker Container Starting..."
echo "================================================"
echo ""
echo "  Ports:"
echo "    6080  - noVNC Web Desktop (VNC viewer)"
echo "    8650  - JADX Plugin API"
echo "    8651  - MCP Server (connect AI clients here)"
echo ""
echo "  Default admin token: admin-secret-token"
echo "  (Change it in jadx-config.toml for production use)"
echo ""
echo "  Quick Connect:"
echo "    Browser:  http://localhost:6080"
echo "    Claude:   claude mcp add --transport http jadx http://<host>:8651/mcp \\"
echo "      --header \"Authorization:Bearer admin-secret-token\""
echo ""
echo "================================================"
echo ""

# Start supervisor to manage all services
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
