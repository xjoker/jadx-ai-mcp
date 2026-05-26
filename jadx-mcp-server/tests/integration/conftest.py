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


# =============================================================================
# XHS smoke test fixtures (Layer 1) - production server at 10.0.5.31
# =============================================================================

@pytest.fixture(scope="session")
def xhs_jadx_url():
    """XHS production JADX Plugin API base URL"""
    return os.getenv("JADX_BASE_URL", "http://10.0.5.31:8650")


@pytest.fixture(scope="session")
def xhs_mcp_url():
    """XHS production MCP Server base URL"""
    return os.getenv("MCP_BASE_URL", "http://10.0.5.31:8651")


@pytest.fixture(scope="session")
def xhs_auth_headers():
    """Authorization headers for XHS JADX plugin"""
    token = os.getenv("JADX_AUTH_TOKEN", "jadx-plugin-secret-token")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def xhs_http_client():
    """HTTP client for XHS smoke tests (longer timeout for large APK)"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def xhs_first_class(xhs_jadx_url, xhs_auth_headers):
    """动态获取第一个类名，避免硬编码"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{xhs_jadx_url}/all-classes",
            headers=xhs_auth_headers,
            params={"offset": 0, "count": 1}
        )
        data = resp.json()
        classes = data.get("classes", [])
        first = classes[0] if classes else {"name": "com.xingin.xhs.MainActivity"}
        return first.get("name") if isinstance(first, dict) else str(first)
