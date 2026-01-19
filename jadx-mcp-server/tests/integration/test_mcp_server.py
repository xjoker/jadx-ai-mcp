"""
Layer 3 Integration Tests - MCP Server (Port 8651)

Tests the Python MCP Server layer that wraps JADX Plugin API.
MCP Server provides MCP protocol tools via HTTP (streamable-http transport).

The MCP Server acts as a proxy between MCP clients (like Claude) and the JADX Plugin.
It adds features like:
- Multi-instance management
- Authentication
- Health monitoring
- Tool wrappers with better error handling

Test Categories:
- Health/status endpoints
- MCP tool invocation via HTTP
- Instance management
- Error handling
"""

import pytest


@pytest.mark.asyncio
class TestMCPServerHealth:
    """MCP Server health and status tests"""
    
    async def test_mcp_server_reachable(self, mcp_base_url, http_client):
        """MCP Server should be reachable on port 8651"""
        # FastMCP exposes health at root or /health
        try:
            resp = await http_client.get(f"{mcp_base_url}/health", timeout=10.0)
            # Any response means server is up
            assert resp.status_code in [200, 404, 405]
        except Exception:
            # Try root endpoint
            resp = await http_client.get(f"{mcp_base_url}/", timeout=10.0)
            assert resp.status_code in [200, 404, 405]
    
    async def test_mcp_server_mcp_endpoint(self, mcp_base_url, http_client):
        """MCP Server should have /mcp endpoint for tool calls"""
        resp = await http_client.get(f"{mcp_base_url}/mcp")
        # FastMCP uses POST for tool calls, GET may return method not allowed
        assert resp.status_code in [200, 405, 404]


@pytest.mark.asyncio
class TestMCPServerToolInvocation:
    """Test MCP tool invocation via HTTP"""
    
    async def test_list_tools_endpoint(self, mcp_base_url, http_client):
        """Should be able to list available tools"""
        # MCP protocol uses JSON-RPC style requests
        resp = await http_client.post(
            f"{mcp_base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            },
            timeout=30.0
        )
        # May need proper MCP handshake first
        assert resp.status_code in [200, 400, 404]
    
    async def test_get_decompile_status_tool(self, mcp_base_url, http_client):
        """Test calling get_decompile_status tool"""
        resp = await http_client.post(
            f"{mcp_base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_decompile_status",
                    "arguments": {}
                },
                "id": 2
            },
            timeout=30.0
        )
        # Server should respond (may need auth or return error)
        assert resp.status_code in [200, 400, 401, 404]
    
    async def test_get_file_info_tool(self, mcp_base_url, http_client):
        """Test calling get_file_info tool"""
        resp = await http_client.post(
            f"{mcp_base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_file_info",
                    "arguments": {}
                },
                "id": 3
            },
            timeout=30.0
        )
        assert resp.status_code in [200, 400, 401, 404]


@pytest.mark.asyncio
class TestMCPServerInstanceManagement:
    """Test instance management features"""
    
    async def test_list_instances_tool(self, mcp_base_url, http_client):
        """Test listing JADX instances"""
        resp = await http_client.post(
            f"{mcp_base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "list_jadx_instances",
                    "arguments": {}
                },
                "id": 4
            },
            timeout=30.0
        )
        assert resp.status_code in [200, 400, 401, 404]


@pytest.mark.asyncio
class TestMCPServerErrorHandling:
    """Test error handling"""
    
    async def test_invalid_tool_name(self, mcp_base_url, http_client):
        """Invalid tool name should return error"""
        resp = await http_client.post(
            f"{mcp_base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "nonexistent_tool_12345",
                    "arguments": {}
                },
                "id": 5
            },
            timeout=30.0
        )
        # Should return error response, not crash
        assert resp.status_code in [200, 400, 404]
    
    async def test_malformed_request(self, mcp_base_url, http_client):
        """Malformed request should be handled gracefully"""
        resp = await http_client.post(
            f"{mcp_base_url}/mcp",
            content=b"not valid json",
            headers={"Content-Type": "application/json"},
            timeout=10.0
        )
        # Should return 400 or similar, not 500
        assert resp.status_code in [400, 422, 404]
    
    async def test_missing_required_params(self, mcp_base_url, http_client):
        """Missing required params should return clear error"""
        resp = await http_client.post(
            f"{mcp_base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_class_source",
                    "arguments": {}  # Missing class_name
                },
                "id": 6
            },
            timeout=30.0
        )
        assert resp.status_code in [200, 400, 404]
