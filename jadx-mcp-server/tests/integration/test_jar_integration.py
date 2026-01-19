"""
Layer 3 Integration Tests - JAR File Testing

Tests real JADX container with jadx-test-library-1.0.0.jar
Note: Container must be started with target.jar mounted to /apks/

JADX Plugin API Endpoints:
- /all-classes?count=N - List classes
- /class-source?class_name=X - Get class source
- /methods-of-class?class_name=X - Get methods of class
- /search-classes-by-keyword?keyword=X - Search classes
- /decompile-status - Get decompile status
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
        assert data.get("loaded") == True, "JAR file should be loaded"
        # Verify it's a JAR file
        file_type = data.get("file_type", "").lower()
        assert "jar" in file_type or "jar" in str(data).lower(), f"Expected JAR file type, got: {file_type}"
    
    async def test_jar_list_classes(self, jadx_base_url, http_client):
        """List all classes in JAR (expects at least 5 classes)"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 0})
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        
        # JAR should have at least 5 classes
        assert len(classes) >= 5, f"Expected >= 5 classes, got {len(classes)}"
        
        # Verify expected classes exist
        class_names = str(classes)
        assert "Calculator" in class_names or "jadxtest" in class_names.lower(), \
            f"Expected 'Calculator' or 'jadxtest' in class names, got: {class_names[:200]}"
    
    async def test_jar_get_class_source(self, jadx_base_url, http_client):
        """Get source code of a class"""
        # First get class list
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 10})
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])
        
        assert len(classes) > 0, "Should have at least one class to test"
        
        class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
        resp = await http_client.get(f"{jadx_base_url}/class-source", params={"class_name": class_name})
        assert resp.status_code == 200, f"Failed to get source for class: {class_name}"
        
        data = resp.json()
        source = data.get("source", data.get("code", ""))
        assert len(source) > 50, f"Source code should be substantial, got {len(source)} chars"
    
    async def test_jar_get_methods(self, jadx_base_url, http_client):
        """Get methods of a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])
        
        assert len(classes) > 0, "Should have at least one class to test"
        
        class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
        resp = await http_client.get(f"{jadx_base_url}/methods-of-class", params={"class_name": class_name})
        assert resp.status_code == 200, f"Failed to get methods for class: {class_name}"
        
        data = resp.json()
        # Verify response structure is valid
        assert "methods" in data or "error" not in data, f"Unexpected response: {data}"
    
    async def test_jar_search_by_keyword(self, jadx_base_url, http_client):
        """Search classes by keyword in JAR"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-classes-by-keyword",
            params={"keyword": "Calculator", "count": 10}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        # Should return classes list
        assert "classes" in data, f"Expected 'classes' in response, got: {list(data.keys())}"
    
    async def test_jar_decompile_status(self, jadx_base_url, http_client):
        """Check decompile status"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "total_classes" in data, f"Expected 'total_classes' in response, got: {list(data.keys())}"
        assert data["total_classes"] >= 5, f"Expected at least 5 classes, got {data['total_classes']}"
