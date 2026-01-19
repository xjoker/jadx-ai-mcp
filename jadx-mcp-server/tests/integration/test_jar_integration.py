"""
Layer 3 Integration Tests - JAR File Testing

Tests real JADX container with jadx-test-library-1.0.0.jar
"""

import pytest


@pytest.mark.asyncio
class TestJARIntegration:
    """Integration tests for JAR file analysis"""
    
    async def test_upload_and_load_jar(self, upload_jar, jadx_base_url, http_client):
        """Upload JAR and verify it loads successfully"""
        # Verify file info
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["file_type"] == "JAR"
        assert "jadx-test-library" in data.get("file_name", "")
    
    async def test_jar_list_classes(self, upload_jar, jadx_base_url, http_client):
        """List all classes in JAR (expects 5 classes)"""
        resp = await http_client.get(f"{jadx_base_url}/classes?count=0")
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        
        # JAR should have 5 classes
        assert len(classes) >= 5, f"Expected >= 5 classes, got {len(classes)}"
        
        # Verify expected classes exist
        class_names = [c["class_name"] for c in classes]
        expected_classes = [
            "com.jadxtest.library.Calculator",
            "com.jadxtest.library.StringUtils",
            "com.jadxtest.library.io.FileProcessor",
            "com.jadxtest.library.network.HttpClient",
            "com.jadxtest.library.model.User"
        ]
        
        for expected in expected_classes:
            assert any(expected in cn for cn in class_names), f"Class {expected} not found"
    
    async def test_jar_get_class_source(self, upload_jar, jadx_base_url, http_client):
        """Get source code of Calculator class"""
        class_name = "com.jadxtest.library.Calculator"
        resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/source")
        assert resp.status_code == 200
        
        data = resp.json()
        source = data.get("source", "")
        
        # Verify source contains expected content
        assert "class Calculator" in source
        assert "public int add(" in source or "add(" in source
        assert "public int multiply(" in source or "multiply(" in source
    
    async def test_jar_get_methods(self, upload_jar, jadx_base_url, http_client):
        """Get methods of Calculator class"""
        class_name = "com.jadxtest.library.Calculator"
        resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/methods")
        assert resp.status_code == 200
        
        data = resp.json()
        methods = data.get("methods", [])
        
        # Calculator should have add, subtract, multiply, divide methods
        method_names = [m["method_name"] for m in methods]
        assert "add" in method_names
        assert "multiply" in method_names
    
    async def test_jar_get_fields(self, upload_jar, jadx_base_url, http_client):
        """Get fields of User class"""
        class_name = "com.jadxtest.library.model.User"
        resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/fields")
        assert resp.status_code == 200
        
        data = resp.json()
        fields = data.get("fields", [])
        
        # User POJO should have name, email fields
        field_names = [f["field_name"] for f in fields]
        assert any("name" in fn.lower() for fn in field_names)
        assert any("email" in fn.lower() or "mail" in fn.lower() for fn in field_names)
    
    async def test_jar_search_by_code(self, upload_jar, jadx_base_url, http_client):
        """Search code for 'API_KEY' - should find HttpClient"""
        resp = await http_client.get(
            f"{jadx_base_url}/search",
            params={"q": "API_KEY", "search_in": "code", "count": 20}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        
        # Should find HttpClient containing API_KEY
        class_names = [c["class_name"] for c in classes]
        assert any("HttpClient" in cn for cn in class_names), "API_KEY not found in HttpClient"
    
    async def test_jar_search_encrypt(self, upload_jar, jadx_base_url, http_client):
        """Search for 'encrypt' - should find StringUtils"""
        resp = await http_client.get(
            f"{jadx_base_url}/search",
            params={"q": "encrypt", "search_in": "code", "count": 20}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        
        # Should find StringUtils with encrypt method
        class_names = [c["class_name"] for c in classes]
        assert any("StringUtils" in cn for cn in class_names), "encrypt not found in StringUtils"
    
    async def test_jar_get_manifest(self, upload_jar, jadx_base_url, http_client):
        """Get JAR MANIFEST.MF"""
        resp = await http_client.get(f"{jadx_base_url}/jar/manifest")
        assert resp.status_code == 200
        
        data = resp.json()
        # JAR manifest should have Implementation-Title
        assert "JADX Test Library" in str(data) or "implementation" in str(data).lower()
    
    async def test_jar_get_entry_points(self, upload_jar, jadx_base_url, http_client):
        """Get JAR entry points"""
        resp = await http_client.get(f"{jadx_base_url}/jar/entry-points")
        assert resp.status_code == 200
        
        data = resp.json()
        # Should find at least some entry point info
        assert isinstance(data, dict)
    
    async def test_jar_get_bytecode(self, upload_jar, jadx_base_url, http_client):
        """Get bytecode for Calculator class"""
        class_name = "com.jadxtest.library.Calculator"
        resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/bytecode")
        assert resp.status_code == 200
        
        data = resp.json()
        bytecode = data.get("bytecode", "")
        
        # Bytecode should contain class structure info
        assert "Calculator" in bytecode
        assert len(bytecode) > 100  # Should have substantial content
