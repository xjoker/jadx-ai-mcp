"""
Layer 3 Integration Tests - Shared Fixtures

Simple fixtures for JADX container integration testing.
Note: Container should already have a file loaded (target.jar or target.apk)
"""

import pytest
import pytest_asyncio
import httpx


@pytest.fixture(scope="session")
def jadx_base_url():
    """JADX Plugin API base URL"""
    return "http://localhost:8650"


@pytest.fixture(scope="session")
def mcp_base_url():
    """MCP Server base URL"""
    return "http://localhost:8651"


@pytest_asyncio.fixture(scope="function")
async def http_client():
    """HTTP client for integration tests"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client
