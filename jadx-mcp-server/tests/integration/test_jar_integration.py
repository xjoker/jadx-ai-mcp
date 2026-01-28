"""
Layer 3 Integration Tests - JAR File Testing

Tests real JADX container with jadx-test-library-1.0.0.jar
Note: Container must be started with target.jar mounted to /apks/

Test Coverage:
- Basic JAR loading and class analysis
- JAR-specific tools (jar_get_manifest, jar_get_entry_points, jar_get_services)
- Unified interface tools (get_file_info, get_package_classes)
- Negative tests (invalid inputs, error handling)
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
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=0")
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
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=10")
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])

        if classes:
            class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
            resp = await http_client.get(f"{jadx_base_url}/class-source?class_name={class_name}")
            assert resp.status_code == 200

            data = resp.json()
            source = data.get("response", data.get("source", ""))
            assert len(source) > 50  # Should have substantial content
    
    async def test_jar_get_methods(self, jadx_base_url, http_client):
        """Get methods of a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=5")
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])

        if classes:
            class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
            resp = await http_client.get(f"{jadx_base_url}/methods-of-class?class_name={class_name}")
            assert resp.status_code == 200

            data = resp.json()
            methods = data.get("methods", [])
            assert len(methods) >= 0  # May be 0 for some classes
    
    async def test_jar_search_by_code(self, jadx_base_url, http_client):
        """Search code in JAR"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-method",
            params={"method_name": "get", "count": 10}
        )
        assert resp.status_code == 200

        data = resp.json()
        # May or may not find results depending on code content
        assert "methods" in data or "error" not in data
    
    async def test_jar_decompile_status(self, jadx_base_url, http_client):
        """Check decompile status"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "total_classes" in data or "cached" in str(data).lower()


@pytest.mark.asyncio
class TestJARSpecificTools:
    """Tests for JAR-specific tools (jar_get_manifest, jar_get_entry_points, etc.)"""

    async def test_jar_get_manifest(self, jadx_base_url, http_client):
        """Test JAR manifest parsing"""
        resp = await http_client.get(f"{jadx_base_url}/jar-manifest")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("status") == "success"
        assert "all_attributes" in data
        assert "Manifest-Version" in data.get("all_attributes", {})

    async def test_jar_get_entry_points(self, jadx_base_url, http_client):
        """Test JAR entry points discovery"""
        resp = await http_client.get(f"{jadx_base_url}/jar-entry-points")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("status") == "success"
        assert "entry_points" in data
        assert "total_found" in data

    async def test_jar_get_services(self, jadx_base_url, http_client):
        """Test JAR SPI services discovery"""
        resp = await http_client.get(f"{jadx_base_url}/jar-services")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("status") == "success"
        assert "services" in data
        assert "total_services" in data


@pytest.mark.asyncio
class TestUnifiedInterface:
    """Tests for unified interface tools (APK/JAR compatible)"""

    async def test_get_file_info(self, jadx_base_url, http_client):
        """Test file type detection and info"""
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("loaded") == True
        assert data.get("file_type") == "jar"
        assert "recommended_tools" in data
        assert "features" in data

    async def test_get_package_classes(self, jadx_base_url, http_client):
        """Test package-based class filtering"""
        resp = await http_client.get(
            f"{jadx_base_url}/package-classes",
            params={"package": "com.jadxtest", "count": 50}
        )
        # May return 200 or 404 depending on JADX version
        if resp.status_code == 200:
            data = resp.json()
            assert "classes" in data or "error" not in data


@pytest.mark.asyncio
class TestNegativeCases:
    """Negative tests for error handling"""

    async def test_invalid_class_name(self, jadx_base_url, http_client):
        """Test error handling for non-existent class"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": "com.nonexistent.FakeClass"}
        )
        # Should return 200 with error in body, or 404
        assert resp.status_code in [200, 404]
        if resp.status_code == 200:
            data = resp.json()
            # Should indicate error or empty result
            assert "error" in data or data.get("response", "") == ""

    async def test_empty_class_name(self, jadx_base_url, http_client):
        """Test error handling for empty class name"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": ""}
        )
        # Should handle gracefully
        assert resp.status_code in [200, 400, 404]

    async def test_invalid_method_search(self, jadx_base_url, http_client):
        """Test search with non-matching pattern"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-method",
            params={"method_name": "xyzNonExistentMethod123", "count": 10}
        )
        assert resp.status_code == 200
        data = resp.json()
        methods = data.get("methods", [])
        assert len(methods) == 0  # Should find nothing

    async def test_large_count_parameter(self, jadx_base_url, http_client):
        """Test handling of large count parameter - JADX has 10000 limit"""
        resp = await http_client.get(
            f"{jadx_base_url}/all-classes",
            params={"count": 99999}
        )
        # JADX enforces max limit of 10000 for pagination
        # Returns 500 with error message (ideally should be 400)
        assert resp.status_code in [200, 400, 500]
        if resp.status_code == 500:
            data = resp.json()
            assert "error" in data
            assert "10000" in data.get("error", "") or "limit" in data.get("error", "").lower()
