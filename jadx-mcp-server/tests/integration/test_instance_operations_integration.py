"""
Layer 3 Integration Tests - Instance Operations

Real tests for instance management (replace Layer 2 mock tests)
"""

import pytest


@pytest.mark.asyncio
class TestInstanceOperationsIntegration:
    """Integration tests for instance management with real JADX container"""
    
    async def test_add_instance_real(self, jadx_base_url, http_client):
        """Real test: Add instance by connecting to actual JADX container"""
        # This tests the real instance registry connecting to localhost:8650
        from server.instance_registry import InstanceRegistry
        
        result = await InstanceRegistry.add_instance(
            host="localhost",
            port=8650,
            name="test-jar-instance",
            owner="ci-test",
            is_dynamic=True
        )
        
        assert result["success"] is True
        assert result["instance"]["name"] == "test-jar-instance"
        assert result["instance"]["owner"] == "ci-test"
        assert result["instance"]["status"] == "connected"
    
    async def test_health_check_real(self, jadx_base_url, http_client):
        """Real test: Health check against actual JADX container"""
        from server.instance_registry import InstanceRegistry
        
        # Add instance first
        await InstanceRegistry.add_instance(
            host="localhost",
            port=8650,
            name="health-check-instance"
        )
        
        # Perform health check
        result = await InstanceRegistry.health_check_all()
        
        assert result["total"] >= 1
        assert result["healthy"] >= 1
        
        # Find our instance in the results
        instances = result["instances"]
        our_instance = next((i for i in instances if i["name"] == "health-check-instance"), None)
        assert our_instance is not None
        assert our_instance["status"] == "connected"
    
    async def test_get_instance_info(self, upload_jar, jadx_base_url, http_client):
        """Real test: Get file info from connected instance"""
        from server.instance_registry import InstanceRegistry
        
        # Add instance
        await InstanceRegistry.add_instance(
            host="localhost",
            port=8650,
            name="info-test-instance"
        )
        
        # Get instance info
        instance = InstanceRegistry.get_instance("info-test-instance")
        assert instance is not None
        assert instance.host == "localhost"
        assert instance.port == 8650
    
    async def test_concurrent_requests(self, upload_jar, jadx_base_url, http_client):
        """Real test: Multiple concurrent requests to same JADX instance"""
        import asyncio
        
        # Make 5 concurrent requests for class list
        tasks = [
            http_client.get(f"{jadx_base_url}/classes?count=10")
            for _ in range(5)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for resp in responses:
            assert resp.status_code == 200
            data = resp.json()
            assert "classes" in data
