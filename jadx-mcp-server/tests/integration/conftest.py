"""
Layer 3 Integration Tests - Shared Fixtures

Simple fixtures for JADX container integration testing.
Note: Container should already have a file loaded (target.jar or target.apk)

Run integration tests explicitly with:
    pytest tests/integration -m integration
"""

import os

import pytest
import pytest_asyncio
import httpx

# All integration tests require a running service
pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def jadx_base_url():
    """JADX Plugin API base URL"""
    return os.getenv("JADX_BASE_URL", "http://localhost:8650")


@pytest.fixture(scope="session")
def mcp_base_url():
    """MCP Server base URL"""
    return os.getenv("MCP_BASE_URL", "http://localhost:8651")


@pytest.fixture(scope="session")
def mcp_transport_url(mcp_base_url):
    """MCP transport endpoint URL"""
    return f"{mcp_base_url.rstrip('/')}/mcp"


@pytest.fixture(scope="session")
def mcp_auth_token():
    """Primary MCP/status auth token for deployment tests"""
    return os.getenv("MCP_AUTH_TOKEN", "")


@pytest.fixture(scope="session")
def mcp_secondary_auth_token():
    """Secondary MCP auth token for multi-client tests"""
    return os.getenv("MCP_SECONDARY_AUTH_TOKEN", "")


@pytest.fixture(scope="session")
def status_headers(mcp_auth_token):
    """Authorization headers for status page JSON"""
    if not mcp_auth_token:
        return {}
    return {"Authorization": f"Bearer {mcp_auth_token}"}


@pytest_asyncio.fixture(scope="function")
async def http_client():
    """HTTP client for integration tests"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client
