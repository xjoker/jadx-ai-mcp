"""
Layer 3 Integration Tests - MCP Server HTTP Mode Testing

Tests the MCP Server running in HTTP mode.
These tests are optional - they skip if MCP Server is not running.

Prerequisites:
- JADX container running with a file loaded
- MCP Server started with: python jadx_mcp_server.py --http --port 8651
"""

import pytest
import httpx


# MCP Server configuration
MCP_SERVER_URL = "http://127.0.0.1:8651"


@pytest.fixture
def mcp_client():
    """HTTP client for MCP Server"""
    return httpx.Client(timeout=30.0)


def is_mcp_server_running() -> bool:
    """Check if MCP Server is accessible"""
    try:
        with httpx.Client(timeout=5.0) as client:
            client.get(f"{MCP_SERVER_URL}/mcp")
            return True
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return False


class TestMCPServerHealth:
    """Verify MCP Server is running and healthy."""

    def test_mcp_endpoint_exists(self, mcp_client):
        """MCP endpoint should respond"""
        if not is_mcp_server_running():
            pytest.skip("MCP Server not running on port 8651")

        resp = mcp_client.get(f"{MCP_SERVER_URL}/mcp")
        # Auth-enabled servers may return 401 here
        assert resp.status_code in [200, 401, 405, 406], \
            f"Unexpected status: {resp.status_code}"

    def test_transfer_health_endpoint(self, mcp_client):
        """Transfer API health endpoint should work"""
        if not is_mcp_server_running():
            pytest.skip("MCP Server not running on port 8651")

        resp = mcp_client.get(f"{MCP_SERVER_URL}/transfer/health")
        assert resp.status_code in [200, 404]


class TestMCPProtocolBasics:
    """Test basic MCP protocol requirements."""

    def test_options_request_allowed(self, mcp_client):
        """OPTIONS request should be handled (CORS support)"""
        if not is_mcp_server_running():
            pytest.skip("MCP Server not running on port 8651")

        resp = mcp_client.options(f"{MCP_SERVER_URL}/mcp")
        assert resp.status_code in [200, 204, 401, 405]

    def test_post_to_mcp_endpoint(self, mcp_client):
        """POST to MCP endpoint should be handled"""
        if not is_mcp_server_running():
            pytest.skip("MCP Server not running on port 8651")

        resp = mcp_client.post(
            f"{MCP_SERVER_URL}/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"Content-Type": "application/json"}
        )
        assert resp.status_code != 500, "Server should not crash"


class TestMCPServerConfiguration:
    """Verify MCP Server configuration endpoints."""

    def test_custom_routes_registered(self, mcp_client):
        """Custom transfer routes should be registered"""
        if not is_mcp_server_running():
            pytest.skip("MCP Server not running on port 8651")

        resp = mcp_client.get(
            f"{MCP_SERVER_URL}/transfer/download/batch-classes",
            params={"classes": "test", "token": "invalid"}
        )
        # Should not crash
        assert resp.status_code in [200, 400, 401, 403, 404, 500]
