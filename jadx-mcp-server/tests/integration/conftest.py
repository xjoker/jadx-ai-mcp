"""
Layer 3 Integration Tests - Shared Fixtures

Provides fixtures for real JADX container integration testing.
"""

import pytest
import pytest_asyncio
import httpx
import asyncio
from pathlib import Path


# Test fixtures locations
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"
TEST_JAR = FIXTURES_DIR / "jadx-test-library-1.0.0.jar"
TEST_APK = FIXTURES_DIR / "jadx-test-app-1.0.0.apk"


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
    """Shared HTTP client for all integration tests"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


async def wait_for_decompile(jadx_base_url: str, client: httpx.AsyncClient, timeout: int = 30):
    """Wait for JADX to finish decompiling"""
    for _ in range(timeout // 2):
        try:
            resp = await client.get(f"{jadx_base_url}/decompile-status")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("cached_percentage", 0) > 50:
                    return
        except Exception:
            pass
        await asyncio.sleep(2)


@pytest_asyncio.fixture
async def upload_jar(jadx_base_url, http_client):
    """Upload test JAR to JADX and wait for decompilation"""
    if not TEST_JAR.exists():
        pytest.skip(f"Test JAR not found: {TEST_JAR}")
    
    # Upload JAR
    with open(TEST_JAR, "rb") as f:
        files = {"file": ("jadx-test-library-1.0.0.jar", f, "application/java-archive")}
        resp = await http_client.post(f"{jadx_base_url}/upload", files=files)
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
    
    await wait_for_decompile(jadx_base_url, http_client)
    return "jadx-test-library-1.0.0.jar"


@pytest_asyncio.fixture
async def upload_apk(jadx_base_url, http_client):
    """Upload test APK to JADX and wait for decompilation"""
    if not TEST_APK.exists():
        pytest.skip(f"Test APK not found: {TEST_APK}")
    
    # Upload APK
    with open(TEST_APK, "rb") as f:
        files = {"file": ("jadx-test-app-1.0.0.apk", f, "application/vnd.android.package-archive")}
        resp = await http_client.post(f"{jadx_base_url}/upload", files=files)
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
    
    await wait_for_decompile(jadx_base_url, http_client)
    return "jadx-test-app-1.0.0.apk"
