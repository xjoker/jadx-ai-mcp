#!/bin/bash
set -e

echo "================================================"
echo "  JADX-AI-MCP Docker Container Starting..."
echo "================================================"

# Start supervisor to manage all services
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
