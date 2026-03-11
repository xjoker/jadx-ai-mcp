"""
Deployment-level integration tests for the all-in-one container.

These tests verify that the embedded JADX plugin API and the MCP server stay in
sync when the container auto-loads an APK from /apks/target.apk.
"""

from __future__ import annotations

import asyncio

import pytest
from fastmcp import Client


def tool_payload(result):
    """Extract structured tool output from FastMCP client responses."""
    payload = getattr(result, "structured_content", None)
    if payload is None:
        raise AssertionError(f"Expected structured_content, got: {result!r}")
    return payload


@pytest.mark.asyncio
class TestAllInOneDeployment:
    async def test_status_requires_auth_when_token_configured(self, mcp_base_url, http_client, mcp_auth_token):
        """Deployment should enforce auth on the status page when users are configured."""
        if not mcp_auth_token:
            pytest.skip("MCP auth token not configured for deployment test")

        unauthenticated = await http_client.get(f"{mcp_base_url}/status.json")
        assert unauthenticated.status_code == 401

        authenticated = await http_client.get(
            f"{mcp_base_url}/status.json",
            headers={"Authorization": f"Bearer {mcp_auth_token}"},
        )
        assert authenticated.status_code == 200

    async def test_plugin_and_status_page_report_same_loaded_apk(
        self,
        jadx_base_url,
        mcp_base_url,
        http_client,
        status_headers,
    ):
        """Plugin and MCP status should agree on the loaded APK metadata."""
        plugin_resp = await http_client.get(f"{jadx_base_url}/apk-info")
        assert plugin_resp.status_code == 200
        plugin_apk = plugin_resp.json()
        assert plugin_apk.get("loaded") is True

        status_resp = await http_client.get(f"{mcp_base_url}/status.json", headers=status_headers)
        assert status_resp.status_code == 200
        status = status_resp.json()

        assert status["summary"]["total_instances"] >= 1
        instance = status["instances"][0]
        assert instance["status"] == "connected"
        assert instance["apk_info"]["loaded"] is True
        assert instance["apk_info"]["apk_package"] == plugin_apk["apk_package"]
        assert instance["apk_info"]["version_name"] == plugin_apk["version_name"]
        assert instance["apk_info"]["class_count"] == plugin_apk["class_count"]

    async def test_mcp_tools_match_plugin_state(
        self,
        jadx_base_url,
        mcp_transport_url,
        http_client,
        mcp_auth_token,
    ):
        """MCP tools should expose the same loaded file and instance state as the plugin API."""
        if not mcp_auth_token:
            pytest.skip("MCP auth token not configured for deployment test")

        apk_info_resp = await http_client.get(f"{jadx_base_url}/apk-info")
        file_info_resp = await http_client.get(f"{jadx_base_url}/file-info")
        main_activity_resp = await http_client.get(f"{jadx_base_url}/main-activity")
        classes_resp = await http_client.get(f"{jadx_base_url}/all-classes?count=1")

        assert apk_info_resp.status_code == 200
        assert file_info_resp.status_code == 200
        assert main_activity_resp.status_code == 200
        assert classes_resp.status_code == 200

        plugin_apk_info = apk_info_resp.json()
        plugin_file_info = file_info_resp.json()
        class_name = main_activity_resp.json().get("name")
        if not class_name:
            class_names = classes_resp.json().get("classes", [])
            assert class_names, "Expected at least one class from the loaded APK"
            class_name = class_names[0]

        async with Client(mcp_transport_url, auth=mcp_auth_token) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}
            assert "list_jadx_instances" in tool_names
            assert "get_file_info" in tool_names
            assert "get_class_source" in tool_names

            instances = tool_payload(await client.call_tool("list_jadx_instances", {}))
            assert instances["count"] >= 1
            assert instances["default_instance"]
            assert instances["instances"][0]["status"] == "connected"
            assert instances["instances"][0]["apk_info"]["apk_package"] == plugin_apk_info["apk_package"]

            mcp_file_info = tool_payload(await client.call_tool("get_file_info", {}))
            assert mcp_file_info["loaded"] is True
            assert mcp_file_info["file_type"] == plugin_file_info["file_type"]
            assert mcp_file_info["class_count"] == plugin_file_info["class_count"]

            mcp_decompile_status = tool_payload(await client.call_tool("get_decompile_status", {}))
            assert mcp_decompile_status["total_classes"] >= plugin_apk_info["class_count"]
            assert "search_coordinator" in mcp_decompile_status

            class_source = tool_payload(
                await client.call_tool("get_class_source", {"class_name": class_name, "chunk": 0})
            )
            assert len(class_source["response"]) > 50
            assert "class " in class_source["response"] or "interface " in class_source["response"]

    async def test_plugin_code_search_uses_coordinator_cache(
        self,
        jadx_base_url,
        http_client,
    ):
        """Repeated direct plugin code searches should expose coordinator cache telemetry."""
        main_activity_resp = await http_client.get(f"{jadx_base_url}/main-activity")
        classes_resp = await http_client.get(f"{jadx_base_url}/all-classes?count=1")

        assert main_activity_resp.status_code == 200
        assert classes_resp.status_code == 200

        class_name = main_activity_resp.json().get("name")
        if not class_name:
            class_names = classes_resp.json().get("classes", [])
            assert class_names, "Expected at least one class from the loaded APK"
            class_name = class_names[0]

        search_term = class_name.rsplit(".", 1)[-1].split("$", 1)[0]
        package_filter = class_name.rsplit(".", 1)[0] if "." in class_name else ""
        params = {"search_term": search_term, "search_in": "code", "package": package_filter, "count": 5}

        first, second = await asyncio.gather(
            http_client.get(f"{jadx_base_url}/search-classes-by-keyword", params=params, timeout=120.0),
            http_client.get(f"{jadx_base_url}/search-classes-by-keyword", params=params, timeout=120.0),
        )
        cached = await http_client.get(f"{jadx_base_url}/search-classes-by-keyword", params=params, timeout=120.0)
        status = await http_client.get(f"{jadx_base_url}/decompile-status", timeout=120.0)

        for response in (first, second, cached):
            assert response.status_code == 200
            payload = response.json()
            assert "classes" in payload
            assert payload["search_info"]["timed_out"] is False

        assert status.status_code == 200
        decompile_status = status.json()
        coordinator = decompile_status.get("search_coordinator", {})
        assert coordinator.get("cache_entries", 0) >= 1
        assert coordinator.get("cache_hits", 0) >= 1
