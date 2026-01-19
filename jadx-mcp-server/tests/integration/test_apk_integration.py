"""
Layer 3 Integration Tests - APK File Testing

Tests real JADX container with jadx-test-app-1.0.0.apk
Note: Container must be started with target.apk mounted to /apks/

JADX Plugin API Endpoints:
- /apk-info - File info
- /manifest - AndroidManifest.xml
- /all-classes?count=N - List classes
- /class-source?class_name=X - Get class source
- /methods-of-class?class_name=X - Get methods of class
- /smali-of-class?class_name=X - Get Smali code
- /search-classes-by-keyword?keyword=X - Search classes
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
        
        if classes:
            class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
            resp = await http_client.get(f"{jadx_base_url}/class-source", params={"class_name": class_name})
            assert resp.status_code == 200
            
            data = resp.json()
            source = data.get("source", data.get("code", ""))
            assert len(source) > 30
    
    async def test_apk_get_methods(self, jadx_base_url, http_client):
        """Get methods of a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])
        
        if classes:
            class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
            resp = await http_client.get(f"{jadx_base_url}/methods-of-class", params={"class_name": class_name})
            assert resp.status_code == 200
    
    async def test_apk_search_by_code(self, jadx_base_url, http_client):
        """Search classes by keyword in APK"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-classes-by-keyword",
            params={"keyword": "Activity", "count": 10}
        )
        assert resp.status_code == 200
    
    async def test_apk_get_smali(self, jadx_base_url, http_client):
        """Get Smali code for a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        assert resp.status_code == 200
        data = resp.json()
        classes = data.get("classes", [])
        
        if classes:
            class_name = classes[0].get("class_name", classes[0]) if isinstance(classes[0], dict) else classes[0]
            resp = await http_client.get(f"{jadx_base_url}/smali-of-class", params={"class_name": class_name})
            assert resp.status_code == 200
    
    async def test_apk_decompile_status(self, jadx_base_url, http_client):
        """Check decompile status"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200
