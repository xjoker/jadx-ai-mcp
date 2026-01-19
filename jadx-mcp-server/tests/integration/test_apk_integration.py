"""
Layer 3 Integration Tests - APK File Testing

Tests real JADX container with jadx-test-app-1.0.0.apk
Note: Container must be started with target.apk mounted to /apks/

JADX Plugin API Reference:
- /apk-info - File info
- /manifest - AndroidManifest.xml
- /all-classes?count=N - List classes
- /class-source?class_name=X - Returns {"response": "code..."} or chunked
- /methods-of-class?class_name=X - Get methods of class
- /smali-of-class?class_name=X - Returns {"response": "smali..."} or chunked
- /search-classes-by-keyword?search_term=X - Search classes (NOT 'keyword')
- /decompile-status - Get decompile status
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
        assert data.get("loaded") == True, "APK file should be loaded"
        # Verify it's an APK with package info
        assert "apk_package" in data or "android" in str(data.get("file_type", "")).lower(), \
            f"Expected APK file type, got: {data}"
    
    async def test_apk_get_manifest(self, jadx_base_url, http_client):
        """Get AndroidManifest.xml"""
        resp = await http_client.get(f"{jadx_base_url}/manifest")
        assert resp.status_code == 200
        
        data = resp.json()
        manifest = data.get("manifest", str(data))
        
        # Verify manifest content has Android-specific tags
        assert "android" in manifest.lower() or "manifest" in manifest.lower(), \
            f"Expected Android manifest content, got: {manifest[:200]}"
    
    async def test_apk_list_classes(self, jadx_base_url, http_client):
        """List all classes in APK"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 0})
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        
        # APK should have at least some classes
        assert len(classes) >= 3, f"Expected >= 3 classes, got {len(classes)}"
    
    async def test_apk_get_class_source(self, jadx_base_url, http_client):
        """Get source code of a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 10})
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])
        
        assert len(classes) > 0, "Should have at least one class to test"
        
        class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
        resp = await http_client.get(f"{jadx_base_url}/class-source", params={"class_name": class_name})
        assert resp.status_code == 200, f"Failed to get source for class: {class_name}"
        
        data = resp.json()
        # SmartChunker returns "response" field
        source = data.get("response", data.get("content", data.get("source", data.get("code", ""))))
        assert len(source) > 30, f"Source code should be substantial, got {len(source)} chars. Keys: {list(data.keys())}"
    
    async def test_apk_get_methods(self, jadx_base_url, http_client):
        """Get methods of a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])
        
        assert len(classes) > 0, "Should have at least one class to test"
        
        class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
        resp = await http_client.get(f"{jadx_base_url}/methods-of-class", params={"class_name": class_name})
        assert resp.status_code == 200, f"Failed to get methods for class: {class_name}"
    
    async def test_apk_search_by_keyword(self, jadx_base_url, http_client):
        """Search classes by keyword in APK"""
        # Note: Parameter is 'search_term', not 'keyword'
        resp = await http_client.get(
            f"{jadx_base_url}/search-classes-by-keyword",
            params={"search_term": "Activity", "count": 10}
        )
        assert resp.status_code == 200, f"Search failed with status {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "classes" in data, f"Expected 'classes' in response, got: {list(data.keys())}"
    
    async def test_apk_get_smali(self, jadx_base_url, http_client):
        """Get Smali code for a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])
        
        assert len(classes) > 0, "Should have at least one class to test"
        
        class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
        resp = await http_client.get(f"{jadx_base_url}/smali-of-class", params={"class_name": class_name})
        assert resp.status_code == 200, f"Failed to get Smali for class: {class_name}"
        
        data = resp.json()
        # SmartChunker returns "response" field
        smali = data.get("response", data.get("content", data.get("smali", data.get("code", ""))))
        assert len(smali) > 20, f"Smali code should be substantial, got {len(smali)} chars. Keys: {list(data.keys())}"
    
    async def test_apk_decompile_status(self, jadx_base_url, http_client):
        """Check decompile status"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "total_classes" in data, f"Expected 'total_classes' in response, got: {list(data.keys())}"
