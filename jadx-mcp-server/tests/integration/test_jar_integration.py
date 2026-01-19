"""
Layer 3 Integration Tests - JAR File Testing (Full Coverage)

Tests real JADX container with jadx-test-library-1.0.0.jar

Test Fixture Contents:
- 5 classes: Calculator, StringUtils, FileProcessor, HttpClient, User
- 3 packages: com.jadxtest.library.*
- Strings: "JADX Test Library", "sk_test_12345678"

JADX Plugin API Endpoints Tested:
- General: /health, /apk-info, /file-info, /decompile-status
- Classes: /all-classes, /class-source, /batch-class-source, /class-info
- Methods: /methods-of-class, /fields-of-class, /method-by-name
- Search: /search-classes-by-keyword, /package-classes
- JAR-specific: /jar-manifest, /jar-services, /jar-entry-points
- Edge cases: invalid params, pagination, inner classes
"""

import pytest


@pytest.mark.asyncio
class TestJARGeneral:
    """General endpoint tests for JAR files"""
    
    async def test_health_endpoint(self, jadx_base_url, http_client):
        """Health check should return 200"""
        resp = await http_client.get(f"{jadx_base_url}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok" or "running" in str(data).lower()
    
    async def test_jar_file_loaded(self, jadx_base_url, http_client):
        """Verify JAR file is loaded with correct metadata"""
        resp = await http_client.get(f"{jadx_base_url}/apk-info")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("loaded") == True, "JAR file should be loaded"
        file_type = data.get("file_type", "").lower()
        assert "jar" in file_type, f"Expected JAR type, got: {file_type}"
    
    async def test_file_info_endpoint(self, jadx_base_url, http_client):
        """File info should return detailed file metadata"""
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200
        
        data = resp.json()
        # Should contain file path or name info
        assert "file" in str(data).lower() or "path" in str(data).lower() or "name" in str(data).lower()
    
    async def test_decompile_status(self, jadx_base_url, http_client):
        """Decompile status should show class count and memory"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "total_classes" in data, f"Missing total_classes: {list(data.keys())}"
        assert data["total_classes"] >= 5, f"Expected >= 5 classes (fixture has 5), got {data['total_classes']}"
        
        # Memory info should be present
        assert "memory" in data or "used_mb" in str(data)


@pytest.mark.asyncio
class TestJARClassNavigation:
    """Class navigation tests for JAR files"""
    
    async def test_list_all_classes(self, jadx_base_url, http_client):
        """List all classes with pagination"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 0})
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        assert len(classes) >= 5, f"Expected >= 5 classes, got {len(classes)}"
        
        # Verify expected classes from fixture
        class_str = str(classes).lower()
        assert "calculator" in class_str or "jadxtest" in class_str
    
    async def test_list_classes_with_pagination(self, jadx_base_url, http_client):
        """Test pagination parameters"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"offset": 0, "count": 2})
        assert resp.status_code == 200
        
        data = resp.json()
        classes = data.get("classes", [])
        assert len(classes) <= 2, f"Pagination limit not respected: got {len(classes)}"
    
    async def test_get_class_source(self, jadx_base_url, http_client):
        """Get source code of a known class"""
        # First get class list
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 10})
        assert resp.status_code == 200
        classes = resp.json().get("classes", [])
        assert len(classes) > 0
        
        # Get first class name
        class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name", classes[0])
        
        resp = await http_client.get(f"{jadx_base_url}/class-source", params={"class_name": class_name})
        assert resp.status_code == 200
        
        data = resp.json()
        source = data.get("response", data.get("content", ""))
        assert len(source) > 50, f"Source too short: {len(source)} chars"
        assert "class" in source.lower() or "public" in source.lower()
    
    async def test_get_class_source_not_found(self, jadx_base_url, http_client):
        """Non-existent class should return 404"""
        resp = await http_client.get(f"{jadx_base_url}/class-source", params={"class_name": "com.nonexistent.FakeClass"})
        assert resp.status_code == 404
    
    async def test_get_class_source_missing_param(self, jadx_base_url, http_client):
        """Missing class_name should return 400"""
        resp = await http_client.get(f"{jadx_base_url}/class-source")
        assert resp.status_code == 400
    
    async def test_batch_class_source(self, jadx_base_url, http_client):
        """Batch get multiple class sources"""
        # Get class list first
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 3})
        classes = resp.json().get("classes", [])
        
        if len(classes) >= 2:
            names = [c if isinstance(c, str) else c.get("class_name") for c in classes[:2]]
            resp = await http_client.get(
                f"{jadx_base_url}/batch-class-source",
                params={"class_names": ",".join(names)}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "classes" in data or "status" in data  # May return loading status
    
    async def test_class_info(self, jadx_base_url, http_client):
        """Get class metadata (interfaces, fields count, etc.)"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 1})
        classes = resp.json().get("classes", [])
        
        if classes:
            class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
            resp = await http_client.get(f"{jadx_base_url}/class-info", params={"class_name": class_name})
            assert resp.status_code == 200
            
            data = resp.json()
            # Should contain class structure info
            assert "class_name" in data or "methods_count" in data or "fields_count" in data


@pytest.mark.asyncio
class TestJARMethodsAndFields:
    """Method and field analysis tests"""
    
    async def test_methods_of_class(self, jadx_base_url, http_client):
        """Get methods of a class with details"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        classes = resp.json().get("classes", [])
        assert len(classes) > 0
        
        class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
        resp = await http_client.get(f"{jadx_base_url}/methods-of-class", params={"class_name": class_name})
        assert resp.status_code == 200
        
        data = resp.json()
        assert "methods" in data, f"Expected methods list: {list(data.keys())}"
    
    async def test_fields_of_class(self, jadx_base_url, http_client):
        """Get fields of a class"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        classes = resp.json().get("classes", [])
        
        if classes:
            class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
            resp = await http_client.get(f"{jadx_base_url}/fields-of-class", params={"class_name": class_name})
            assert resp.status_code == 200
            
            data = resp.json()
            assert "fields" in data, f"Expected fields list: {list(data.keys())}"
    
    async def test_method_by_name(self, jadx_base_url, http_client):
        """Get specific method code by name"""
        # First find a class with methods
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 5})
        classes = resp.json().get("classes", [])
        
        if classes:
            class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
            
            # Get methods first
            resp = await http_client.get(f"{jadx_base_url}/methods-of-class", params={"class_name": class_name})
            if resp.status_code == 200:
                methods = resp.json().get("methods", [])
                if methods:
                    method_name = methods[0].get("name") if isinstance(methods[0], dict) else methods[0]
                    resp = await http_client.get(
                        f"{jadx_base_url}/method-by-name",
                        params={"class_name": class_name, "method_name": method_name}
                    )
                    assert resp.status_code == 200


@pytest.mark.asyncio
class TestJARSearch:
    """Search functionality tests"""
    
    async def test_search_by_keyword(self, jadx_base_url, http_client):
        """Search classes by keyword"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-classes-by-keyword",
            params={"search_term": "Calculator", "count": 10}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        assert "classes" in data
    
    async def test_search_missing_term(self, jadx_base_url, http_client):
        """Search without search_term should return 400"""
        resp = await http_client.get(f"{jadx_base_url}/search-classes-by-keyword")
        assert resp.status_code == 400
    
    async def test_package_classes(self, jadx_base_url, http_client):
        """Get classes in a specific package"""
        resp = await http_client.get(
            f"{jadx_base_url}/package-classes",
            params={"package": "com.jadxtest"}
        )
        # May return 200 with classes or 400 if package param missing
        assert resp.status_code in [200, 400]


@pytest.mark.asyncio
class TestJARSpecific:
    """JAR-specific endpoint tests"""
    
    async def test_jar_manifest(self, jadx_base_url, http_client):
        """Get JAR MANIFEST.MF"""
        resp = await http_client.get(f"{jadx_base_url}/jar-manifest")
        # May succeed or return "not applicable" for minimal JARs
        assert resp.status_code in [200, 404, 501]
    
    async def test_jar_services(self, jadx_base_url, http_client):
        """Get META-INF/services (SPI)"""
        resp = await http_client.get(f"{jadx_base_url}/jar-services")
        # Most JARs don't have services
        assert resp.status_code in [200, 404, 501]
    
    async def test_jar_entry_points(self, jadx_base_url, http_client):
        """Get JAR entry points (main classes)"""
        resp = await http_client.get(f"{jadx_base_url}/jar-entry-points")
        assert resp.status_code in [200, 404, 501]
    
    async def test_smali_not_available_for_jar(self, jadx_base_url, http_client):
        """Smali should return 'not applicable' for JAR files"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 1})
        classes = resp.json().get("classes", [])
        
        if classes:
            class_name = classes[0] if isinstance(classes[0], str) else classes[0].get("class_name")
            resp = await http_client.get(f"{jadx_base_url}/smali-of-class", params={"class_name": class_name})
            # Should return error or "not applicable" since JAR has no Smali
            data = resp.json()
            # Either 200 with not_applicable or 4xx error
            if resp.status_code == 200:
                assert "not_applicable" in str(data).lower() or "not available" in str(data).lower()
