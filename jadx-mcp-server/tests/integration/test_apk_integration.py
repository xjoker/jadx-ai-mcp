"""
Layer 3 Integration Tests - APK File Testing

Tests real JADX container with jadx-test-app-1.0.0.apk
"""

import pytest


@pytest.mark.asyncio
class TestAPKIntegration:
    """Integration tests for APK file analysis"""
    
    async def test_upload_and_load_apk(self, upload_apk, jadx_base_url, http_client):
        """Upload APK and verify it loads successfully"""
        # Verify file info
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["file_type"] == "APK"
        assert "jadx-test-app" in data.get("file_name", "")
    
    async def test_apk_list_classes(self, upload_apk, jadx_base_url, http_client):
        """List all classes in APK (expects 5 classes)"""
        resp = await http_client.get(f"{jadx_base_url}/classes?count=0")
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        
        # APK should have at least 5 app classes
        assert len(classes) >= 5, f"Expected >= 5 classes, got {len(classes)}"
        
        # Verify expected classes exist
        class_names = [c["class_name"] for c in classes]
        expected_classes = [
            "com.jadxtest.app.MainActivity",
            "com.jadxtest.app.ApiManager",
            "com.jadxtest.app.DatabaseHelper",
            "com.jadxtest.app.JadxTestApplication"
        ]
        
        for expected in expected_classes:
            assert any(expected in cn for cn in class_names), f"Class {expected} not found"
    
    async def test_apk_get_manifest(self, upload_apk, jadx_base_url, http_client):
        """Get AndroidManifest.xml"""
        resp = await http_client.get(f"{jadx_base_url}/manifest")
        assert resp.status_code == 200
        
        data = resp.json()
        manifest = data.get("manifest", "")
        
        # Verify manifest content
        assert "com.jadxtest.app" in manifest
        assert "MainActivity" in manifest
        assert "android:name" in manifest
    
    async def test_apk_get_main_activity(self, upload_apk, jadx_base_url, http_client):
        """Get main activity class"""
        resp = await http_client.get(f"{jadx_base_url}/main-activity")
        assert resp.status_code == 200
        
        data = resp.json()
        class_name = data.get("class_name", "")
        
        # Should return MainActivity
        assert "MainActivity" in class_name
    
    async def test_apk_get_class_source(self, upload_apk, jadx_base_url, http_client):
        """Get source code of MainActivity"""
        class_name = "com.jadxtest.app.MainActivity"
        resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/source")
        assert resp.status_code == 200
        
        data = resp.json()
        source = data.get("source", "")
        
        # Verify source contains expected content
        assert "MainActivity" in source
        assert "onCreate" in source or "class " in source
    
    async def test_apk_get_methods(self, upload_apk, jadx_base_url, http_client):
        """Get methods of MainActivity"""
        class_name = "com.jadxtest.app.MainActivity"
        resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/methods")
        assert resp.status_code == 200
        
        data = resp.json()
        methods = data.get("methods", [])
        
        # MainActivity should have onCreate method
        method_names = [m["method_name"] for m in methods]
        assert "onCreate" in method_names
    
    async def test_apk_get_fields(self, upload_apk, jadx_base_url, http_client):
        """Get fields of ApiManager class"""
        class_name = "com.jadxtest.app.ApiManager"
        resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/fields")
        assert resp.status_code == 200
        
        data = resp.json()
        fields = data.get("fields", [])
        
        # ApiManager should have API-related fields
        field_names = [f["field_name"] for f in fields]
        # At least some fields should be present
        assert len(field_names) > 0
    
    async def test_apk_search_by_code(self, upload_apk, jadx_base_url, http_client):
        """Search code for 'CREATE TABLE' - should find DatabaseHelper"""
        resp = await http_client.get(
            f"{jadx_base_url}/search",
            params={"q": "CREATE TABLE", "search_in": "code", "count": 20}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        
        # Should find DatabaseHelper with SQL code
        class_names = [c["class_name"] for c in classes]
        assert any("DatabaseHelper" in cn for cn in class_names), "SQL not found in DatabaseHelper"
    
    async def test_apk_search_api_domain(self, upload_apk, jadx_base_url, http_client):
        """Search for 'jadxtest.com' - should find ApiManager"""
        resp = await http_client.get(
            f"{jadx_base_url}/search",
            params={"q": "jadxtest.com", "search_in": "code", "count": 20}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        
        # Should find ApiManager with API domain
        class_names = [c["class_name"] for c in classes]
        assert any("ApiManager" in cn for cn in class_names), "API domain not found"
    
    async def test_apk_get_strings(self, upload_apk, jadx_base_url, http_client):
        """Get strings from APK resources"""
        resp = await http_client.get(f"{jadx_base_url}/strings/summary")
        assert resp.status_code == 200
        
        data = resp.json()
        # Should have string resources info
        assert "total_strings" in data or "strings" in data
    
    async def test_apk_get_smali(self, upload_apk, jadx_base_url, http_client):
        """Get Smali code for MainActivity"""
        class_name = "com.jadxtest.app.MainActivity"
        resp = await http_client.get(f"{jadx_base_url}/class/{class_name}/smali")
        assert resp.status_code == 200
        
        data = resp.json()
        smali = data.get("smali", "")
        
        # Smali should contain Dalvik bytecode
        assert ".class" in smali or "smali" in smali.lower()
        assert len(smali) > 100  # Should have substantial content
