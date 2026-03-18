"""
Deployment-level integration tests for multiple MCP clients connected to the
same all-in-one container.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastmcp import Client


def tool_payload(result):
    payload = getattr(result, "structured_content", None)
    if payload is None:
        raise AssertionError(f"Expected structured_content, got: {result!r}")
    return payload


async def call_tool_with_busy_retry(client: Client, tool_name: str, arguments: dict, retries: int = 8) -> dict:
    """Retry transient INSTANCE_BUSY responses during concurrent multi-client tests."""
    last_payload = None
    for attempt in range(retries):
        result = await client.call_tool(tool_name, arguments)
        payload = tool_payload(result)
        if payload.get("error") != "INSTANCE_BUSY":
            return payload
        last_payload = payload
        await asyncio.sleep(0.2 * (attempt + 1))

    raise AssertionError(f"{tool_name} kept returning INSTANCE_BUSY: {last_payload}")


async def run_client_session(mcp_transport_url: str, token: str, class_name: str) -> dict:
    async with Client(mcp_transport_url, auth=token) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        assert "list_jadx_instances" in tool_names
        assert "get_file_info" in tool_names
        assert "get_class_source" in tool_names

        instances = tool_payload(await client.call_tool("list_jadx_instances", {}))
        file_info = await call_tool_with_busy_retry(client, "get_file_info", {})
        class_source = await call_tool_with_busy_retry(
            client,
            "get_class_source",
            {"class_name": class_name, "chunk": 0},
        )

        return {
            "instances": instances,
            "file_info": file_info,
            "class_source": class_source,
        }


async def run_file_info_session(mcp_transport_url: str, token: str) -> dict:
    async with Client(mcp_transport_url, auth=token) as client:
        return tool_payload(await client.call_tool("get_file_info", {}))


async def run_class_source_session(mcp_transport_url: str, token: str, class_name: str) -> dict:
    async with Client(mcp_transport_url, auth=token) as client:
        return tool_payload(
            await client.call_tool("get_class_source", {"class_name": class_name, "chunk": 0})
        )


@pytest.mark.asyncio
class TestMultiClientDeployment:
    async def test_concurrent_file_info_calls_do_not_return_instance_busy(
        self,
        mcp_transport_url,
        mcp_auth_token,
        mcp_secondary_auth_token,
    ):
        """Metadata-only tools should stay available under concurrent multi-client access."""
        if not mcp_auth_token or not mcp_secondary_auth_token:
            pytest.skip("Primary and secondary MCP auth tokens are required for multi-client deployment tests")

        payloads = await asyncio.gather(
            run_file_info_session(mcp_transport_url, mcp_auth_token),
            run_file_info_session(mcp_transport_url, mcp_secondary_auth_token),
            run_file_info_session(mcp_transport_url, mcp_auth_token),
        )

        for payload in payloads:
            assert payload["loaded"] is True
            assert payload["file_type"] == "apk"
            assert "error" not in payload

    async def test_multiple_clients_can_share_one_all_in_one_server(
        self,
        jadx_base_url,
        mcp_base_url,
        mcp_transport_url,
        mcp_auth_token,
        mcp_secondary_auth_token,
        http_client,
    ):
        """Multiple authenticated clients should be able to read from the same server concurrently."""
        if not mcp_auth_token or not mcp_secondary_auth_token:
            pytest.skip("Primary and secondary MCP auth tokens are required for multi-client deployment tests")

        apk_info_resp = await http_client.get(f"{jadx_base_url}/apk-info")
        main_activity_resp = await http_client.get(f"{jadx_base_url}/main-activity")
        classes_resp = await http_client.get(f"{jadx_base_url}/all-classes?count=1")

        assert apk_info_resp.status_code == 200
        assert main_activity_resp.status_code == 200
        assert classes_resp.status_code == 200

        apk_info = apk_info_resp.json()
        class_name = main_activity_resp.json().get("name")
        if not class_name:
            classes = classes_resp.json().get("classes", [])
            assert classes, "Expected at least one class in the loaded APK"
            class_name = classes[0]

        tokens = [mcp_auth_token, mcp_secondary_auth_token, mcp_auth_token]
        client_results = await asyncio.gather(
            *(run_client_session(mcp_transport_url, token, class_name) for token in tokens)
        )

        async def fetch_status(token: str) -> dict:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{mcp_base_url}/status.json",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 200
                return response.json()

        status_results = await asyncio.gather(*(fetch_status(token) for token in tokens))

        for result in client_results:
            assert result["instances"]["count"] >= 1
            assert result["instances"]["instances"][0]["status"] == "connected"
            assert result["instances"]["instances"][0]["apk_info"]["apk_package"] == apk_info["apk_package"]

            assert result["file_info"]["loaded"] is True
            assert result["file_info"]["apk_package"] == apk_info["apk_package"]
            assert result["file_info"]["class_count"] == apk_info["class_count"]

            assert len(result["class_source"]["response"]) > 50
            assert "class " in result["class_source"]["response"] or "interface " in result["class_source"]["response"]

        viewer_names = [status["viewer"]["name"] for status in status_results]
        assert viewer_names.count("viewer") >= 2
        assert "admin" in viewer_names

        for status in status_results:
            assert status["summary"]["total_instances"] >= 1
            assert status["instances"][0]["status"] == "connected"
            assert status["instances"][0]["apk_package"] == apk_info["apk_package"]

    async def test_concurrent_class_source_calls_complete_without_instance_busy(
        self,
        jadx_base_url,
        mcp_transport_url,
        mcp_auth_token,
        mcp_secondary_auth_token,
        http_client,
    ):
        """Small code-read requests should queue instead of failing under multi-client concurrency."""
        if not mcp_auth_token or not mcp_secondary_auth_token:
            pytest.skip("Primary and secondary MCP auth tokens are required for multi-client deployment tests")

        main_activity_resp = await http_client.get(f"{jadx_base_url}/main-activity")
        classes_resp = await http_client.get(f"{jadx_base_url}/all-classes?count=1")
        assert main_activity_resp.status_code == 200
        assert classes_resp.status_code == 200

        class_name = main_activity_resp.json().get("name")
        if not class_name:
            classes = classes_resp.json().get("classes", [])
            assert classes, "Expected at least one class in the loaded APK"
            class_name = classes[0]

        payloads = await asyncio.gather(
            run_class_source_session(mcp_transport_url, mcp_auth_token, class_name),
            run_class_source_session(mcp_transport_url, mcp_secondary_auth_token, class_name),
            run_class_source_session(mcp_transport_url, mcp_auth_token, class_name),
        )

        for payload in payloads:
            assert payload.get("error") != "INSTANCE_BUSY"
            assert len(payload["response"]) > 50
