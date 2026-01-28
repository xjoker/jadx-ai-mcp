"""
Layer 3 Integration Tests - APK File Testing

Tests real JADX container with jadx-test-app-1.0.0.apk
Note: Container must be started with target.apk mounted to /apks/

Test Coverage:
- Basic APK loading and class analysis
- Android-specific tools (manifest, smali, strings)
- Unified interface tools (get_file_info, get_class_info)
- Cross-reference tools (xrefs)
- Negative tests (invalid inputs, error handling)
"""

import pytest


@pytest.mark.asyncio
class TestAPKIntegration:
    """Integration tests for APK file analysis"""
    
    async def test_apk_file_loaded(self, jadx_base_url, http_client):
        """Verify APK file is loaded and accessible"""
        resp = await http_client.get(f"{jadx_base_url}/apk-info")
        assert resp.status_code == 200
        
        data = resp.json()
        # Verify it's an APK with package info
        assert "apk_package" in data or "jadxtest" in str(data).lower()
    
    async def test_apk_get_manifest(self, jadx_base_url, http_client):
        """Get AndroidManifest.xml"""
        resp = await http_client.get(f"{jadx_base_url}/manifest")
        assert resp.status_code == 200
        
        data = resp.json()
        manifest = data.get("manifest", str(data))
        
        # Verify manifest content
        assert "android" in manifest.lower() or "manifest" in manifest.lower()
    
    async def test_apk_list_classes(self, jadx_base_url, http_client):
        """List all classes in APK"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=0")
        assert resp.status_code == 200

        data = resp.json()
        classes = data.get("classes", [])

        # APK should have at least some classes
        assert len(classes) >= 3, f"Expected >= 3 classes, got {len(classes)}"
    
    async def test_apk_get_class_source(self, jadx_base_url, http_client):
        """Get source code of a class"""
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
            assert len(source) > 30
    
    async def test_apk_get_methods(self, jadx_base_url, http_client):
        """Get methods of a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=5")
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])

        if classes:
            class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
            resp = await http_client.get(f"{jadx_base_url}/methods-of-class?class_name={class_name}")
            assert resp.status_code == 200
    
    async def test_apk_search_by_code(self, jadx_base_url, http_client):
        """Search code in APK"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-method",
            params={"method_name": "onCreate", "count": 10}
        )
        assert resp.status_code == 200
    
    async def test_apk_get_smali(self, jadx_base_url, http_client):
        """Get Smali code for a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=5")
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])

        if classes:
            class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
            resp = await http_client.get(f"{jadx_base_url}/smali-of-class?class_name={class_name}")
            assert resp.status_code == 200
    
    async def test_apk_decompile_status(self, jadx_base_url, http_client):
        """Check decompile status"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestAPKSpecificTools:
    """Tests for Android-specific tools"""

    async def test_apk_get_file_info(self, jadx_base_url, http_client):
        """Test file type detection for APK"""
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("loaded") == True
        assert data.get("file_type") == "apk"
        assert data.get("android_features") == True
        assert "recommended_tools" in data

    async def test_apk_get_class_info(self, jadx_base_url, http_client):
        """Test class metadata retrieval"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-info",
            params={"class_name": "com.jadxtest.app.MainActivity"}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "super_class" in data
        assert "methods_count" in data or "method_names" in data
        assert data.get("simple_name") == "MainActivity"

    async def test_apk_get_fields(self, jadx_base_url, http_client):
        """Test fields retrieval for a class"""
        resp = await http_client.get(
            f"{jadx_base_url}/fields-of-class",
            params={"class_name": "com.jadxtest.app.MainActivity"}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "fields" in data


@pytest.mark.asyncio
class TestXrefsTools:
    """Tests for cross-reference tools"""

    async def test_xrefs_to_class(self, jadx_base_url, http_client):
        """Test cross-references to a class"""
        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-class",
            params={"class_name": "com.jadxtest.app.MainActivity"}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "references" in data or "xrefs" in data or "pagination" in data

    async def test_xrefs_to_method(self, jadx_base_url, http_client):
        """Test cross-references to a method"""
        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-method",
            params={"class_name": "com.jadxtest.app.MainActivity", "method_name": "onCreate"}
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestAPKNegativeCases:
    """Negative tests for APK error handling"""

    async def test_invalid_class_name(self, jadx_base_url, http_client):
        """Test error handling for non-existent class"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": "com.nonexistent.FakeClass"}
        )
        assert resp.status_code in [200, 404]
        if resp.status_code == 200:
            data = resp.json()
            assert "error" in data or data.get("response", "") == ""

    async def test_empty_class_name(self, jadx_base_url, http_client):
        """Test error handling for empty class name"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": ""}
        )
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
        assert len(methods) == 0

    async def test_smali_for_nonexistent_class(self, jadx_base_url, http_client):
        """Test Smali retrieval for non-existent class"""
        resp = await http_client.get(
            f"{jadx_base_url}/smali-of-class",
            params={"class_name": "com.fake.NonExistent"}
        )
        assert resp.status_code in [200, 404]

    async def test_large_count_parameter(self, jadx_base_url, http_client):
        """Test handling of large count parameter - JADX has 10000 limit"""
        resp = await http_client.get(
            f"{jadx_base_url}/all-classes",
            params={"count": 99999}
        )
        assert resp.status_code in [200, 400, 500]
        if resp.status_code == 500:
            data = resp.json()
            assert "error" in data
            assert "10000" in data.get("error", "") or "limit" in data.get("error", "").lower()
