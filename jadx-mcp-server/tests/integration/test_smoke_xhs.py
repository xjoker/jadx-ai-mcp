"""
Layer 1 Smoke Tests - XHS APK on Production Server

Targets: http://10.0.5.31:8650 (JADX Java plugin)
Loaded APK: xhs (237,931 classes, fully warmed)

Test Philosophy:
- One happy-path call per endpoint, no strict value assertions
- Only assert: HTTP 200 + no "error" key in response body
- Full suite must complete within 2 minutes
- Security scan is @pytest.mark.slow and skipped by default

Run all smoke tests:
    pytest tests/integration/test_smoke_xhs.py -m "integration and smoke"

Run excluding slow:
    pytest tests/integration/test_smoke_xhs.py -m "integration and smoke and not slow"
"""

import asyncio

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.smoke]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_ok(resp, data):
    """Common assertions: 200 status and no top-level error key."""
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}. Body: {resp.text[:300]}"
    )
    if isinstance(data, dict):
        assert data.get("error") is None, f"Response contained error: {data.get('error')}"


# ---------------------------------------------------------------------------
# Class tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_file_info(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /file-info — APK should be loaded."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/file-info",
        headers=xhs_auth_headers,
    )
    data = resp.json()
    _assert_ok(resp, data)
    assert data.get("loaded") is True, f"Expected loaded=true, got: {data.get('loaded')}"


@pytest.mark.asyncio
async def test_all_classes(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /all-classes — should return a non-empty list."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/all-classes",
        headers=xhs_auth_headers,
        params={"offset": 0, "count": 5},
    )
    data = resp.json()
    _assert_ok(resp, data)
    classes = data.get("classes", [])
    assert isinstance(classes, list), f"Expected 'classes' to be a list, got {type(classes)}"
    assert len(classes) > 0, "Expected at least one class in response"


@pytest.mark.asyncio
async def test_class_source(xhs_jadx_url, xhs_auth_headers, xhs_http_client, xhs_first_class):
    """GET /class-source — should return non-empty source content."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/class-source",
        headers=xhs_auth_headers,
        params={"class_name": xhs_first_class},
    )
    data = resp.json()
    _assert_ok(resp, data)
    content = data.get("response", data.get("content", ""))
    assert len(content) > 0, "Expected non-empty class source"


@pytest.mark.asyncio
async def test_class_info(xhs_jadx_url, xhs_auth_headers, xhs_http_client, xhs_first_class):
    """GET /class-info — should include simple_name."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/class-info",
        headers=xhs_auth_headers,
        params={"class_name": xhs_first_class},
    )
    data = resp.json()
    _assert_ok(resp, data)
    assert "simple_name" in data, f"Expected 'simple_name' in response, got keys: {list(data.keys())}"


@pytest.mark.asyncio
async def test_smali_of_class(xhs_jadx_url, xhs_auth_headers, xhs_http_client, xhs_first_class):
    """GET /smali-of-class — should return non-empty smali."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/smali-of-class",
        headers=xhs_auth_headers,
        params={"class_name": xhs_first_class},
    )
    data = resp.json()
    _assert_ok(resp, data)
    smali = data.get("response", "")
    assert len(smali) > 0, "Expected non-empty smali output"


@pytest.mark.asyncio
async def test_decompile_status(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /decompile-status — total_classes should be > 0."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/decompile-status",
        headers=xhs_auth_headers,
    )
    data = resp.json()
    _assert_ok(resp, data)
    total = data.get("total_classes", 0)
    assert total > 0, f"Expected total_classes > 0, got {total}"


# ---------------------------------------------------------------------------
# Search tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_classes_by_keyword(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /search-classes-by-keyword — should return results list."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/search-classes-by-keyword",
        headers=xhs_auth_headers,
        params={"search_term": "Activity", "search_in": "class", "limit": 5},
    )
    data = resp.json()
    _assert_ok(resp, data)


@pytest.mark.asyncio
async def test_method_by_name(xhs_jadx_url, xhs_auth_headers, xhs_http_client, xhs_first_class):
    """GET /method-by-name — should not crash (200 or 404 acceptable)."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/method-by-name",
        headers=xhs_auth_headers,
        params={"class_name": xhs_first_class, "method_name": ""},
    )
    assert resp.status_code in (200, 400, 404), (
        f"Expected 200/400/404, got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_search_native_methods(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /search-native-methods — should not error."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/search-native-methods",
        headers=xhs_auth_headers,
        params={"count": 5},
    )
    data = resp.json()
    _assert_ok(resp, data)


# ---------------------------------------------------------------------------
# Xrefs tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_xrefs_to_class(xhs_jadx_url, xhs_auth_headers, xhs_http_client, xhs_first_class):
    """GET /xrefs-to-class — should return references field."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/xrefs-to-class",
        headers=xhs_auth_headers,
        params={"class_name": xhs_first_class},
    )
    data = resp.json()
    _assert_ok(resp, data)
    assert "references" in data or "pagination" in data, (
        f"Expected 'references' or 'pagination' in response, got keys: {list(data.keys())}"
    )


# ---------------------------------------------------------------------------
# Resource tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manifest(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /manifest — should return non-empty manifest content."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/manifest",
        headers=xhs_auth_headers,
    )
    data = resp.json()
    _assert_ok(resp, data)
    manifest = data.get("manifest", data.get("response", str(data)))
    assert len(manifest) > 0, "Expected non-empty manifest"


@pytest.mark.asyncio
async def test_strings_summary(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /strings?mode=summary — should not error."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/strings",
        headers=xhs_auth_headers,
        params={"mode": "summary"},
    )
    data = resp.json()
    _assert_ok(resp, data)


@pytest.mark.asyncio
async def test_all_resource_file_names(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /list-all-resource-files-names — should not error."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/list-all-resource-files-names",
        headers=xhs_auth_headers,
    )
    data = resp.json()
    _assert_ok(resp, data)


# ---------------------------------------------------------------------------
# Index / Diagnostics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_index_stats(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /index-stats — should include trigram_index field."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/index-stats",
        headers=xhs_auth_headers,
    )
    data = resp.json()
    _assert_ok(resp, data)
    assert "trigram_index" in data, (
        f"Expected 'trigram_index' in response, got keys: {list(data.keys())}"
    )


# ---------------------------------------------------------------------------
# Warmup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_warmup_status(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """GET /cache/warmup-status — should include phase field."""
    resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/cache/warmup-status",
        headers=xhs_auth_headers,
    )
    data = resp.json()
    _assert_ok(resp, data)
    assert "phase" in data, (
        f"Expected 'phase' in response, got keys: {list(data.keys())}"
    )


# ---------------------------------------------------------------------------
# Search async (submit + poll)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_and_poll_code_search(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """POST /submit-code-search then GET /code-search-status — should return ticket and status."""
    # Submit search (submit-code-search only supports search_in=code|comment)
    submit_resp = await xhs_http_client.post(
        f"{xhs_jadx_url}/submit-code-search",
        headers=xhs_auth_headers,
        params={"search_term": "onCreate", "search_in": "code"},
    )
    submit_data = submit_resp.json()
    _assert_ok(submit_resp, submit_data)

    ticket = (
        submit_data.get("ticket")
        or submit_data.get("task_id")
        or submit_data.get("id")
    )
    assert ticket is not None, f"Expected a ticket in response, got: {submit_data}"

    # Poll status (single check — just verify the field exists)
    status_resp = await xhs_http_client.get(
        f"{xhs_jadx_url}/code-search-status",
        headers=xhs_auth_headers,
        params={"ticket": ticket},
    )
    status_data = status_resp.json()
    _assert_ok(status_resp, status_data)
    assert "status" in status_data, (
        f"Expected 'status' in poll response, got keys: {list(status_data.keys())}"
    )


# ---------------------------------------------------------------------------
# Security scan async (slow — skipped by default)
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.asyncio
async def test_security_scan_secrets(xhs_jadx_url, xhs_auth_headers, xhs_http_client):
    """Security scan smoke — via MCP Python layer (port 8651), not direct Java plugin.

    Marked @pytest.mark.slow — skip with: -m "not slow"
    Security scan is submitted through Python MCP server (submit_security_scan tool),
    not via the Java plugin's HTTP API directly.
    This test is intentionally skipped in direct-Java-plugin smoke mode.
    """
    pytest.skip(
        "Security scan goes through Python MCP layer (port 8651), not direct Java API. "
        "Use test_stress_baseline.py::TestBaselineCapture for end-to-end scan testing."
    )
