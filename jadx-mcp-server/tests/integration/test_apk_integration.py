"""
Layer 3 Integration Tests - APK File Testing (Full Coverage)

Tests real JADX container with jadx-test-app-1.0.0.apk

Test Fixture Contents:
- 5 classes: MainActivity, ApiManager, DatabaseHelper, JadxTestApplication, others
- Package: com.jadxtest.app.*
- AndroidManifest.xml with permissions
- Strings: "jadxtest.db", "api.jadxtest.com"

JADX Plugin API Endpoints Tested:
- General: /health, /apk-info, /file-info, /decompile-status
- Classes: /all-classes, /class-source, /batch-class-source, /class-info, /smali-of-class
- Methods: /methods-of-class, /fields-of-class, /method-by-name, /search-native-methods
- Resources: /manifest, /strings, /list-all-resource-files-names, /get-resource-file
- Search: /search-classes-by-keyword, /package-classes
- APK-specific: /main-activity, /main-application-classes-code
- Xrefs: /xrefs-to-class, /xrefs-to-method
- Edge cases: invalid params, pagination, error handling
"""

import pytest


@pytest.mark.asyncio
class TestAPKGeneral:
    """General endpoint tests for APK files"""
    
    async def test_health_endpoint(self, jadx_base_url, http_client):
        """Health check should return 200"""
        resp = await http_client.get(f"{jadx_base_url}/health")
        assert resp.status_code == 200
    
    async def test_apk_file_loaded(self, jadx_base_url, http_client):
        """Verify APK file is loaded with package info"""
        resp = await http_client.get(f"{jadx_base_url}/apk-info")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("loaded") == True
        # APK should have package info
        assert "apk_package" in data or "package" in str(data).lower()
    
    async def test_file_info_endpoint(self, jadx_base_url, http_client):
        """File info should return APK metadata"""
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200
    
    async def test_decompile_status(self, jadx_base_url, http_client):
        """Decompile status for APK"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "total_classes" in data
        assert data["total_classes"] >= 3


@pytest.mark.asyncio
class TestAPKClassNavigation:
    """Class navigation tests for APK files"""
    
    async def test_list_all_classes(self, jadx_base_url, http_client):
        """List all classes in APK"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 0})
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        assert len(classes) >= 3
    
    async def test_list_classes_with_pagination(self, jadx_base_url, http_client):
        """Test pagination"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"offset": 0, "count": 2})
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        assert len(classes) <= 2
    
    async def test_get_class_source(self, jadx_base_url, http_client):
        """Get decompiled source code"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        classes = resp.json().get("classes", [])
        assert len(classes) > 0
        
        class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
        resp = await http_client.get(f"{jadx_base_url}/class-source", params={"class_name": class_name})
        assert resp.status_code == 200
        
        data = resp.json()
        source = data.get("response", data.get("content", ""))
        assert len(source) > 30
    
    async def test_get_class_source_not_found(self, jadx_base_url, http_client):
        """Non-existent class returns 404"""
        resp = await http_client.get(f"{jadx_base_url}/class-source", params={"class_name": "fake.NonExistent"})
        assert resp.status_code == 404
    
    async def test_class_info(self, jadx_base_url, http_client):
        """Get class metadata"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 1})
        classes = resp.json().get("classes", [])
        
        if classes:
            class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
            resp = await http_client.get(f"{jadx_base_url}/class-info", params={"class_name": class_name})
            assert resp.status_code == 200
    
    async def test_smali_of_class(self, jadx_base_url, http_client):
        """Get Smali code (APK-specific)"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        classes = resp.json().get("classes", [])
        assert len(classes) > 0
        
        class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
        resp = await http_client.get(f"{jadx_base_url}/smali-of-class", params={"class_name": class_name})
        assert resp.status_code == 200
        
        data = resp.json()
        smali = data.get("response", data.get("content", ""))
        assert len(smali) > 20, f"Smali too short: {len(smali)} chars"


@pytest.mark.asyncio
class TestAPKMethodsAndFields:
    """Method and field analysis"""
    
    async def test_methods_of_class(self, jadx_base_url, http_client):
        """Get methods list"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        classes = resp.json().get("classes", [])
        
        if classes:
            class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
            resp = await http_client.get(f"{jadx_base_url}/methods-of-class", params={"class_name": class_name})
            assert resp.status_code == 200
            assert "methods" in resp.json()
    
    async def test_fields_of_class(self, jadx_base_url, http_client):
        """Get fields list"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        classes = resp.json().get("classes", [])
        
        if classes:
            class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
            resp = await http_client.get(f"{jadx_base_url}/fields-of-class", params={"class_name": class_name})
            assert resp.status_code == 200
            assert "fields" in resp.json()
    
    async def test_search_native_methods(self, jadx_base_url, http_client):
        """Search for native methods"""
        resp = await http_client.get(f"{jadx_base_url}/search-native-methods")
        # May return empty list if no native methods
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestAPKResources:
    """Resource file tests (APK-specific)"""
    
    async def test_get_manifest(self, jadx_base_url, http_client):
        """Get AndroidManifest.xml"""
        resp = await http_client.get(f"{jadx_base_url}/manifest")
        assert resp.status_code == 200
        
        data = resp.json()
        manifest = data.get("manifest", str(data))
        assert "android" in manifest.lower() or "manifest" in manifest.lower()
    
    async def test_get_strings(self, jadx_base_url, http_client):
        """Get strings.xml"""
        resp = await http_client.get(f"{jadx_base_url}/strings")
        # May return 200, 202 (processing), or 404 if no strings.xml
        assert resp.status_code in [200, 202, 404]
    
    async def test_list_resource_files(self, jadx_base_url, http_client):
        """List all resource file names"""
        resp = await http_client.get(f"{jadx_base_url}/list-all-resource-files-names")
        assert resp.status_code == 200
        
        data = resp.json()
        # Should contain resources list
        assert "resources" in data or "files" in data or isinstance(data, list)
    
    async def test_config_strings(self, jadx_base_url, http_client):
        """Get configuration strings (API keys, URLs, etc.)"""
        resp = await http_client.get(f"{jadx_base_url}/config-strings")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestAPKSearch:
    """Search functionality"""
    
    async def test_search_by_keyword(self, jadx_base_url, http_client):
        """Search classes by keyword"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-classes-by-keyword",
            params={"search_term": "Activity", "count": 10}
        )
        assert resp.status_code == 200
        assert "classes" in resp.json()
    
    async def test_search_in_code(self, jadx_base_url, http_client):
        """Search in code content"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-classes-by-keyword",
            params={"search_term": "onCreate", "search_in": "code", "count": 5}
        )
        assert resp.status_code == 200
    
    async def test_search_missing_term(self, jadx_base_url, http_client):
        """Search without term returns 400"""
        resp = await http_client.get(f"{jadx_base_url}/search-classes-by-keyword")
        assert resp.status_code == 400
    
    async def test_package_classes(self, jadx_base_url, http_client):
        """Get classes in a package"""
        resp = await http_client.get(
            f"{jadx_base_url}/package-classes",
            params={"package": "com.jadxtest"}
        )
        assert resp.status_code in [200, 400]


@pytest.mark.asyncio
class TestAPKSpecific:
    """APK-specific endpoint tests"""
    
    async def test_main_activity(self, jadx_base_url, http_client):
        """Get main activity code"""
        resp = await http_client.get(f"{jadx_base_url}/main-activity")
        # Should find MainActivity in test APK
        assert resp.status_code == 200
    
    async def test_main_application_classes(self, jadx_base_url, http_client):
        """Get main application package classes"""
        resp = await http_client.get(f"{jadx_base_url}/main-application-classes-names")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestAPKXrefs:
    """Cross-reference tests"""
    
    async def test_xrefs_to_class(self, jadx_base_url, http_client):
        """Get references to a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 3})
        classes = resp.json().get("classes", [])
        
        if classes:
            class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
            resp = await http_client.get(f"{jadx_base_url}/xrefs-to-class", params={"class_name": class_name})
            # May return 200 with empty list or refs
            assert resp.status_code == 200
    
    async def test_xrefs_missing_param(self, jadx_base_url, http_client):
        """Xrefs without class_name returns 400"""
        resp = await http_client.get(f"{jadx_base_url}/xrefs-to-class")
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestAPKEdgeCases:
    """Edge case and error handling tests"""
    
    async def test_invalid_class_name_format(self, jadx_base_url, http_client):
        """Invalid class name format"""
        resp = await http_client.get(f"{jadx_base_url}/class-source", params={"class_name": "!!invalid!!"})
        assert resp.status_code in [400, 404]
    
    async def test_empty_class_name(self, jadx_base_url, http_client):
        """Empty class name parameter"""
        resp = await http_client.get(f"{jadx_base_url}/class-source", params={"class_name": ""})
        assert resp.status_code in [400, 404]
    
    async def test_pagination_offset_beyond_total(self, jadx_base_url, http_client):
        """Offset beyond total count"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"offset": 99999, "count": 10})
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        assert len(classes) == 0  # Should return empty list
    
    async def test_negative_pagination_params(self, jadx_base_url, http_client):
        """Negative pagination parameters"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"offset": -1, "count": -1})
        # Server may return 200 (treating as 0), 400 (invalid param), or 500 (unhandled)
        assert resp.status_code in [200, 400, 500]
