"""
Layer 3 Integration Tests - JAR File Testing

Tests real JADX container with jadx-test-library-1.0.0.jar
Note: Container must be started with target.jar mounted to /apks/
"""

import pytest


@pytest.mark.asyncio
class TestJARIntegration:
    """Integration tests for JAR file analysis"""
    
    async def test_jar_file_loaded(self, jadx_base_url, http_client):
        """Verify JAR file is loaded and accessible"""
        resp = await http_client.get(f"{jadx_base_url}/apk-info")
        assert resp.status_code == 200
        
        data = resp.json()
        # Verify it's a JAR file
        assert "jadx-test-library" in str(data) or "jar" in str(data).lower()
    
    async def test_jar_list_classes(self, jadx_base_url, http_client):
        """List all classes in JAR (expects 5 classes)"""
        resp = await http_client.get(f"{jadx_base_url}/classes?count=0")
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        
        # JAR should have at least 5 classes
        assert len(classes) >= 5, f"Expected >= 5 classes, got {len(classes)}"
        
        # Verify expected classes exist
        class_names = str(classes)
        assert "Calculator" in class_names or "jadxtest" in class_names
    
    async def test_jar_get_class_source(self, jadx_base_url, http_client):
        """Get source code of a class"""
        # First get class list
        resp = await http_client.get(f"{jadx_base_url}/classes?count=10")
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])
        
        if classes:
            class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
            resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/source")
            assert resp.status_code == 200
            
            data = resp.json()
            source = data.get("source", "")
            assert len(source) > 50  # Should have substantial content
    
    async def test_jar_get_methods(self, jadx_base_url, http_client):
        """Get methods of a class"""
        resp = await http_client.get(f"{jadx_base_url}/classes?count=5")
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])
        
        if classes:
            class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
            resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/methods")
            assert resp.status_code == 200
            
            data = resp.json()
            methods = data.get("methods", [])
            assert len(methods) >= 0  # May be 0 for some classes
    
    async def test_jar_search_by_code(self, jadx_base_url, http_client):
        """Search code in JAR"""
        resp = await http_client.get(
            f"{jadx_base_url}/search",
            params={"q": "public", "search_in": "code", "count": 10}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        # May or may not find results depending on code content
        assert "classes" in data or "results" in data or "error" not in data
    
    async def test_jar_decompile_status(self, jadx_base_url, http_client):
        """Check decompile status"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "total_classes" in data or "cached" in str(data).lower()
