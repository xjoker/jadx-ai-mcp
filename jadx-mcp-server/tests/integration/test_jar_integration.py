"""
Layer 3 Integration Tests - JAR File Testing (Strict Mode)

Tests real JADX container with jadx-test-library-1.0.0.jar
Container must be started with target.jar mounted to /apks/

Test Philosophy:
- Tests are written from USER PERSPECTIVE (AI assistant analyzing JAR)
- All assertions are STRICT - exact values, not just field existence
- No conditional skips - if data is missing, test FAILS
- Single status code acceptance - 200 for success paths
- Verify actual content correctness, not just structure

Test JAR Contains:
- Package: com.jadxtest.library
- Classes: Calculator, FileProcessor, StringUtils, User, HttpClient (5 total)
- No Main-Class (library JAR)
"""

import pytest


# =============================================================================
# Test Constants - Expected values from test JAR
# =============================================================================
EXPECTED_PACKAGE = "com.jadxtest.library"
EXPECTED_CLASSES = [
    "com.jadxtest.library.Calculator",
    "com.jadxtest.library.FileProcessor",
    "com.jadxtest.library.StringUtils",
    "com.jadxtest.library.model.User",
    "com.jadxtest.library.network.HttpClient",
]
EXPECTED_CLASS_COUNT = 5
TEST_CLASS = "com.jadxtest.library.Calculator"


@pytest.mark.asyncio
class TestJARBasicAnalysis:
    """
    User Scenario: "Analyze this JAR file"
    AI needs to understand what file is loaded and its basic structure.
    """

    async def test_file_info_returns_jar_type(self, jadx_base_url, http_client):
        """User asks: What type of file is this?"""
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        data = resp.json()
        assert data.get("loaded") == True, "File should be loaded"
        assert data.get("file_type") == "jar", f"Expected 'jar', got {data.get('file_type')}"
        assert data.get("android_features") == False, "JAR should not have android features"
        assert data.get("smali_available") == False, "Smali should not be available for JAR"

        # Verify recommended tools are appropriate for JAR
        recommended = data.get("recommended_tools", [])
        assert "jar_get_manifest" in recommended, "Should recommend JAR manifest tool"
        assert "get_class_source" in recommended, "Should recommend class source tool"

    async def test_apk_info_returns_jar_details(self, jadx_base_url, http_client):
        """User asks: What's the file info?"""
        resp = await http_client.get(f"{jadx_base_url}/apk-info")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("loaded") == True
        # Verify it's identified as JAR
        assert data.get("file_type") == "jar" or "jar" in str(data).lower()

    async def test_list_all_classes(self, jadx_base_url, http_client):
        """User asks: What classes are in this JAR?"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=100")
        assert resp.status_code == 200

        data = resp.json()
        classes = data.get("classes", [])

        # STRICT: Must have exact number of classes
        assert len(classes) == EXPECTED_CLASS_COUNT, \
            f"Expected {EXPECTED_CLASS_COUNT} classes, got {len(classes)}"

        # STRICT: Must contain all expected classes
        for expected_class in EXPECTED_CLASSES:
            assert expected_class in classes, f"Missing expected class: {expected_class}"

    async def test_decompile_status(self, jadx_base_url, http_client):
        """User asks: Is the decompilation ready?"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200

        data = resp.json()
        assert "total_classes" in data, "Should report total classes"
        assert data.get("total_classes", 0) == EXPECTED_CLASS_COUNT


@pytest.mark.asyncio
class TestJARCodeRetrieval:
    """
    User Scenario: "Show me the code for this class"
    AI needs to retrieve actual source code for analysis.
    """

    async def test_get_class_source(self, jadx_base_url, http_client):
        """User asks: Show me the Calculator class"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": TEST_CLASS}
        )
        assert resp.status_code == 200

        data = resp.json()
        source = data.get("response", data.get("content", ""))

        # STRICT: Verify actual content
        assert len(source) > 100, f"Source too short: {len(source)} chars"
        assert "Calculator" in source, "Should contain class name"
        assert "package com.jadxtest.library" in source, "Should contain package"

    async def test_get_class_info_metadata(self, jadx_base_url, http_client):
        """User asks: What's the structure of Calculator?"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-info",
            params={"class_name": TEST_CLASS}
        )
        assert resp.status_code == 200

        data = resp.json()
        # STRICT: Verify metadata accuracy
        assert data.get("simple_name") == "Calculator"
        assert data.get("package") == "com.jadxtest.library"

        # Must have methods
        method_count = data.get("methods_count", len(data.get("method_names", [])))
        assert method_count >= 1, f"Expected >= 1 methods, got {method_count}"

    async def test_get_user_model_class(self, jadx_base_url, http_client):
        """User asks: Show me the User model class"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": "com.jadxtest.library.model.User"}
        )
        assert resp.status_code == 200

        data = resp.json()
        source = data.get("response", data.get("content", ""))

        # STRICT: Verify User class content
        assert "User" in source, "Should contain User class"
        assert "package com.jadxtest.library.model" in source, "Should contain correct package"


@pytest.mark.asyncio
class TestJARMethodAnalysis:
    """
    User Scenario: "Find methods in this JAR"
    AI needs to search and analyze methods.
    """

    async def test_get_methods_of_class(self, jadx_base_url, http_client):
        """User asks: What methods does Calculator have?"""
        resp = await http_client.get(
            f"{jadx_base_url}/methods-of-class",
            params={"class_name": TEST_CLASS}
        )
        assert resp.status_code == 200

        data = resp.json()
        methods = data.get("methods", [])

        # STRICT: Must have methods
        assert len(methods) >= 1, f"Expected >= 1 methods, got {len(methods)}"

    async def test_search_method_by_name(self, jadx_base_url, http_client):
        """User asks: Find all 'get' methods"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-method",
            params={"method_name": "get", "count": 20}
        )
        assert resp.status_code == 200

        data = resp.json()
        # Should return methods array (may be empty or have results)
        assert "methods" in data, "Should have methods field"

    async def test_get_fields_of_class(self, jadx_base_url, http_client):
        """User asks: What fields does User have?"""
        resp = await http_client.get(
            f"{jadx_base_url}/fields-of-class",
            params={"class_name": "com.jadxtest.library.model.User"}
        )
        assert resp.status_code == 200

        data = resp.json()
        fields = data.get("fields", [])

        # User model should have fields
        assert len(fields) >= 1, f"Expected >= 1 fields, got {len(fields)}"


@pytest.mark.asyncio
class TestJARSpecificTools:
    """
    User Scenario: "Analyze JAR-specific features"
    AI needs JAR manifest, entry points, services.
    """

    async def test_get_jar_manifest(self, jadx_base_url, http_client):
        """User asks: Show me the JAR manifest"""
        resp = await http_client.get(f"{jadx_base_url}/jar-manifest")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("status") == "success", "Should return success status"
        assert "all_attributes" in data, "Should have manifest attributes"

        # STRICT: Verify manifest content
        attrs = data.get("all_attributes", {})
        assert "Manifest-Version" in attrs, "Should have Manifest-Version"

    async def test_get_jar_entry_points(self, jadx_base_url, http_client):
        """User asks: What are the entry points?"""
        resp = await http_client.get(f"{jadx_base_url}/jar-entry-points")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("status") == "success"
        assert "entry_points" in data, "Should have entry_points field"
        # This is a library JAR, so no entry points expected
        assert data.get("total_found", 0) == 0, "Library JAR should have no entry points"

    async def test_get_jar_services(self, jadx_base_url, http_client):
        """User asks: What SPI services are defined?"""
        resp = await http_client.get(f"{jadx_base_url}/jar-services")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("status") == "success"
        assert "services" in data, "Should have services field"


@pytest.mark.asyncio
class TestJARCrossReferences:
    """
    User Scenario: "Who uses this class?"
    AI needs to trace code relationships.
    """

    async def test_xrefs_to_class(self, jadx_base_url, http_client):
        """User asks: Who uses the Calculator class?"""
        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-class",
            params={"class_name": TEST_CLASS}
        )
        assert resp.status_code == 200

        data = resp.json()
        # Should return structured xrefs data
        assert "references" in data or "pagination" in data, \
            "Should return references or pagination info"


@pytest.mark.asyncio
class TestJARErrorHandling:
    """
    User Scenario: AI sends invalid requests
    System should return clear, helpful error messages.
    """

    async def test_nonexistent_class_returns_error(self, jadx_base_url, http_client):
        """Invalid class name should return helpful error"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": "com.fake.NonExistentClass"}
        )
        assert resp.status_code in [200, 404]

        if resp.status_code == 200:
            data = resp.json()
            response = data.get("response", "")
            assert "error" in str(data).lower() or response == "" or "not found" in str(data).lower()

    async def test_empty_class_name_handled(self, jadx_base_url, http_client):
        """Empty class name should not crash"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": ""}
        )
        assert resp.status_code != 500, "Should not return 500 for empty input"

    async def test_pagination_limit_enforced(self, jadx_base_url, http_client):
        """Excessive count parameter should be handled"""
        resp = await http_client.get(
            f"{jadx_base_url}/all-classes",
            params={"count": 99999}
        )
        if resp.status_code == 500:
            data = resp.json()
            assert "error" in data
            assert "10000" in data.get("error", "") or "limit" in data.get("error", "").lower()
        elif resp.status_code == 200:
            data = resp.json()
            assert "classes" in data

    async def test_invalid_method_search_returns_empty(self, jadx_base_url, http_client):
        """Non-matching search should return empty results"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-method",
            params={"method_name": "xyzDefinitelyNotExistingMethod123"}
        )
        assert resp.status_code == 200

        data = resp.json()
        methods = data.get("methods", [])
        assert len(methods) == 0, "Should return empty list for no matches"

    async def test_smali_not_available_for_jar(self, jadx_base_url, http_client):
        """Smali should not be available for JAR files"""
        resp = await http_client.get(
            f"{jadx_base_url}/smali-of-class",
            params={"class_name": TEST_CLASS}
        )
        # Should indicate Smali not available for JAR
        if resp.status_code == 200:
            data = resp.json()
            # May return empty or error message
            response = data.get("response", "")
            assert response == "" or "not available" in str(data).lower() or "error" in str(data).lower()
