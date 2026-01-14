#!/bin/bash
set -e

echo "================================================"
echo "  JADX-AI-MCP Docker Container Starting..."
echo "================================================"
echo ""
echo "  noVNC Web Desktop: http://localhost:6080"
echo "  JADX Plugin API:   http://localhost:8650"
echo "  MCP Server:        http://localhost:8651"
echo ""
echo "  Connect Claude/Gemini/ChatGPT to MCP Server:"
echo "  claude mcp add --transport http jadx http://<host>:8651"
echo ""

# Start supervisor to manage all services
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

