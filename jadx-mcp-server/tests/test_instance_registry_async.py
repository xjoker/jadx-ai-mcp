"""
Layer 2 Unit Tests: Instance Registry Async Operations

Tests async operations with mocked HTTP calls using respx.
No real JADX container required.
"""

import pytest
import respx
from httpx import Response

from server.instance_registry import InstanceRegistry


class TestInstanceRegistryAsync:
    """Tests for async InstanceRegistry operations with HTTP mocking"""

    @respx.mock
    @pytest.mark.asyncio
    async def test_add_instance_success(self):
        """Successfully add instance with mocked /apk-info response"""
        # Mock the JADX /apk-info endpoint
        respx.get("http://192.168.1.10:8650/apk-info").mock(
            return_value=Response(200, json={
                "apk_package": "com.example.app",
                "version_name": "1.0.0",
                "version_code": 100,
                "instance_name": "example-v1",
                "plugin_version": "dev"
            })
        )
        
        result = await InstanceRegistry.add_instance(
            host="192.168.1.10",
            port=8650,
            owner="alice",
            is_dynamic=True,
            registration_source="ai_dynamic"
        )
        
        assert result["success"] == True
        assert result["instance"]["name"] == "example-v1"
        assert result["instance"]["owner"] == "alice"
        assert result["instance"]["status"] == "connected"
        assert result["instance"]["registration_source"] == "ai_dynamic"

    @respx.mock
    @pytest.mark.asyncio
    async def test_add_instance_with_custom_name(self):
        """Add instance with custom name overriding auto-generated name"""
        respx.get("http://127.0.0.1:8650/apk-info").mock(
            return_value=Response(200, json={
                "apk_package": "com.example.app",
                "version_name": "2.0.0",
                "instance_name": "auto-name"
            })
        )
        
        result = await InstanceRegistry.add_instance(
            host="127.0.0.1",
            port=8650,
            name="my-custom-name",
            owner="bob"
        )
        
        assert result["success"] == True
        assert result["instance"]["name"] == "my-custom-name"

    @respx.mock
    @pytest.mark.asyncio
    async def test_add_instance_connection_failed(self):
        """Add instance should fail gracefully when connection fails"""
        # Mock connection error
        respx.get("http://unreachable:8650/apk-info").mock(side_effect=Exception("Connection refused"))
        
        result = await InstanceRegistry.add_instance(
            host="unreachable",
            port=8650,
            name="will-fail"
        )
        
        assert result["success"] == False
        assert "Failed" in result["message"] or "failed" in result["message"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_add_instance_duplicate_name_fails(self):
        """Adding instance with duplicate name should fail"""
        # First add succeeds
        respx.get("http://127.0.0.1:8650/apk-info").mock(
            return_value=Response(200, json={"instance_name": "dup-name"})
        )
        result1 = await InstanceRegistry.add_instance(host="127.0.0.1", port=8650)
        assert result1["success"] == True
        
        # Second add with same name should fail
        respx.get("http://127.0.0.1:8651/apk-info").mock(
            return_value=Response(200, json={"instance_name": "dup-name"})
        )
        result2 = await InstanceRegistry.add_instance(host="127.0.0.1", port=8651)
        assert result2["success"] == False
        assert "exists" in result2["message"].lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_add_instance_preserves_token(self):
        """Instance should store the provided token"""
        respx.get("http://127.0.0.1:8650/apk-info").mock(
            return_value=Response(200, json={"instance_name": "token-test"})
        )
        
        InstanceRegistry.set_auth_token("global-token")
        
        result = await InstanceRegistry.add_instance(
            host="127.0.0.1",
            port=8650,
            token="instance-specific-token"
        )
        
        assert result["success"] == True
        instance = InstanceRegistry.get_instance("token-test")
        assert instance.token == "instance-specific-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Health check should update instance statuses"""
        # Register instances
        InstanceRegistry.register_pending_instance("healthy", "127.0.0.1", 8650)
        InstanceRegistry.register_pending_instance("unhealthy", "127.0.0.1", 8651)
        
        # Mock health endpoints
        respx.get("http://127.0.0.1:8650/health").mock(return_value=Response(200))
        respx.get("http://127.0.0.1:8651/health").mock(return_value=Response(500))
        
        result = await InstanceRegistry.health_check_all()
        
        assert result["total"] == 2
        assert result["healthy"] == 1
        
        # Verify individual statuses
        status_map = {inst["name"]: inst["status"] for inst in result["instances"]}
        assert status_map["healthy"] == "connected"
        assert status_map["unhealthy"] == "disconnected"
