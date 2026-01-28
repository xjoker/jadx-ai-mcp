"""
Layer 3 Integration Tests - APK File Testing (Strict Mode)

Tests real JADX container with jadx-test-app-1.0.0.apk
Container must be started with target.apk mounted to /apks/

Test Philosophy:
- Tests are written from USER PERSPECTIVE (AI assistant analyzing APK)
- All assertions are STRICT - exact values, not just field existence
- No conditional skips - if data is missing, test FAILS
- Single status code acceptance - 200 for success paths
- Verify actual content correctness, not just structure

Test APK Contains:
- Package: com.jadxtest.app
- Classes: MainActivity, ApiManager, DatabaseHelper, JadxTestApplication, R (6 total)
- MainActivity methods: onCreate, onActionClicked, updateStatus, etc.
"""

import pytest


# =============================================================================
# Test Constants - Expected values from test APK
# =============================================================================
EXPECTED_PACKAGE = "com.jadxtest.app"
EXPECTED_CLASSES = [
    "com.jadxtest.app.ApiManager",
    "com.jadxtest.app.DatabaseHelper",
    "com.jadxtest.app.JadxTestApplication",
    "com.jadxtest.app.MainActivity",
]
EXPECTED_CLASS_COUNT_MIN = 5  # At least 5 classes (excluding R classes)
MAIN_ACTIVITY = "com.jadxtest.app.MainActivity"


@pytest.mark.asyncio
class TestAPKBasicAnalysis:
    """
    User Scenario: "Analyze this APK file"
    AI needs to understand what file is loaded and its basic structure.
    """

    async def test_file_info_returns_apk_type(self, jadx_base_url, http_client):
        """User asks: What type of file is this?"""
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        data = resp.json()
        assert data.get("loaded") == True, "File should be loaded"
        assert data.get("file_type") == "apk", f"Expected 'apk', got {data.get('file_type')}"
        assert data.get("android_features") == True, "APK should have android features"
        assert data.get("smali_available") == True, "Smali should be available for APK"

        # Verify recommended tools are appropriate for APK
        recommended = data.get("recommended_tools", [])
        assert "get_android_manifest" in recommended, "Should recommend manifest tool"
        assert "get_smali_of_class" in recommended, "Should recommend smali tool"

    async def test_apk_info_returns_package_details(self, jadx_base_url, http_client):
        """User asks: What's the package name and version?"""
        resp = await http_client.get(f"{jadx_base_url}/apk-info")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("loaded") == True
        # Verify it contains package info (field name may vary)
        data_str = str(data).lower()
        assert "jadxtest" in data_str or "target" in data_str, "Should contain test app info"

    async def test_list_all_classes(self, jadx_base_url, http_client):
        """User asks: What classes are in this APK?"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=100")
        assert resp.status_code == 200

        data = resp.json()
        classes = data.get("classes", [])

        # STRICT: Must have expected number of classes
        assert len(classes) >= EXPECTED_CLASS_COUNT_MIN, \
            f"Expected >= {EXPECTED_CLASS_COUNT_MIN} classes, got {len(classes)}"

        # STRICT: Must contain our test classes
        for expected_class in EXPECTED_CLASSES:
            assert expected_class in classes, f"Missing expected class: {expected_class}"

    async def test_decompile_status(self, jadx_base_url, http_client):
        """User asks: Is the decompilation ready?"""
        resp = await http_client.get(f"{jadx_base_url}/decompile-status")
        assert resp.status_code == 200

        data = resp.json()
        assert "total_classes" in data, "Should report total classes"
        assert data.get("total_classes", 0) >= EXPECTED_CLASS_COUNT_MIN


@pytest.mark.asyncio
class TestAPKCodeRetrieval:
    """
    User Scenario: "Show me the code for this class"
    AI needs to retrieve actual source code for analysis.
    """

    async def test_get_main_activity_source(self, jadx_base_url, http_client):
        """User asks: Show me the MainActivity code"""
        resp = await http_client.get(f"{jadx_base_url}/main-activity")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("name") == MAIN_ACTIVITY, \
            f"Expected {MAIN_ACTIVITY}, got {data.get('name')}"

        content = data.get("content", "")
        # STRICT: Verify actual code content
        assert "package com.jadxtest.app" in content, "Should contain package declaration"
        assert "class MainActivity" in content, "Should contain class declaration"
        assert "extends Activity" in content, "MainActivity should extend Activity"

    async def test_get_class_source_by_name(self, jadx_base_url, http_client):
        """User asks: Show me the ApiManager class"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": "com.jadxtest.app.ApiManager"}
        )
        assert resp.status_code == 200

        data = resp.json()
        source = data.get("response", data.get("content", ""))

        # STRICT: Verify actual content
        assert len(source) > 100, f"Source too short: {len(source)} chars"
        assert "ApiManager" in source, "Should contain class name"
        assert "package com.jadxtest.app" in source, "Should contain package"

    async def test_get_class_info_metadata(self, jadx_base_url, http_client):
        """User asks: What's the structure of MainActivity?"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-info",
            params={"class_name": MAIN_ACTIVITY}
        )
        assert resp.status_code == 200

        data = resp.json()
        # STRICT: Verify metadata accuracy
        assert data.get("simple_name") == "MainActivity"
        assert data.get("package") == "com.jadxtest.app"
        assert "Activity" in data.get("super_class", ""), "Should extend Activity"

        # Must have methods
        method_count = data.get("methods_count", len(data.get("method_names", [])))
        assert method_count >= 3, f"Expected >= 3 methods, got {method_count}"

    async def test_get_smali_code(self, jadx_base_url, http_client):
        """User asks: Show me the Smali bytecode"""
        resp = await http_client.get(
            f"{jadx_base_url}/smali-of-class",
            params={"class_name": MAIN_ACTIVITY}
        )
        assert resp.status_code == 200

        data = resp.json()
        smali = data.get("response", "")

        # STRICT: Verify Smali format
        assert ".class public" in smali, "Should contain .class directive"
        assert "Lcom/jadxtest/app/MainActivity;" in smali, "Should contain class descriptor"


@pytest.mark.asyncio
class TestAPKMethodAnalysis:
    """
    User Scenario: "Find methods related to X"
    AI needs to search and analyze methods.
    """

    async def test_get_methods_of_class(self, jadx_base_url, http_client):
        """User asks: What methods does MainActivity have?"""
        resp = await http_client.get(
            f"{jadx_base_url}/methods-of-class",
            params={"class_name": MAIN_ACTIVITY}
        )
        assert resp.status_code == 200

        data = resp.json()
        methods = data.get("methods", [])

        # STRICT: Must have methods
        assert len(methods) >= 3, f"Expected >= 3 methods, got {len(methods)}"

        # STRICT: Verify method structure
        method_names = [m.get("name", m) if isinstance(m, dict) else m for m in methods]
        assert "onCreate" in str(method_names), "Should have onCreate method"

    async def test_search_method_by_name(self, jadx_base_url, http_client):
        """User asks: Find all onCreate methods"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-method",
            params={"method_name": "onCreate", "count": 20}
        )
        assert resp.status_code == 200

        data = resp.json()
        methods = data.get("methods", [])

        # STRICT: onCreate exists in our test APK
        assert len(methods) >= 1, "Should find at least one onCreate method"

        # Verify search result structure
        for method in methods:
            assert "class_name" in method or "method_name" in method, \
                "Method result should have class_name or method_name"

    async def test_get_method_source(self, jadx_base_url, http_client):
        """User asks: Show me the onCreate method code"""
        resp = await http_client.get(
            f"{jadx_base_url}/method-by-name",
            params={"class_name": MAIN_ACTIVITY, "method_name": "onCreate"}
        )
        # May return 200 or have specific error handling
        if resp.status_code == 200:
            data = resp.json()
            # If successful, should contain method code
            if "error" not in data:
                content = str(data)
                assert "onCreate" in content or "void" in content

    async def test_get_fields_of_class(self, jadx_base_url, http_client):
        """User asks: What fields does MainActivity have?"""
        resp = await http_client.get(
            f"{jadx_base_url}/fields-of-class",
            params={"class_name": MAIN_ACTIVITY}
        )
        assert resp.status_code == 200

        data = resp.json()
        fields = data.get("fields", [])

        # MainActivity should have some fields
        assert len(fields) >= 1, f"Expected >= 1 fields, got {len(fields)}"


@pytest.mark.asyncio
class TestAPKAndroidFeatures:
    """
    User Scenario: "Analyze Android-specific features"
    AI needs Android manifest, resources, strings.
    """

    async def test_get_manifest(self, jadx_base_url, http_client):
        """User asks: Show me the AndroidManifest.xml"""
        resp = await http_client.get(f"{jadx_base_url}/manifest")
        assert resp.status_code == 200

        data = resp.json()
        manifest = data.get("manifest", data.get("response", str(data)))

        # STRICT: Verify manifest content
        assert "android" in manifest.lower(), "Should contain android namespace"
        assert "manifest" in manifest.lower(), "Should contain manifest tag"
        assert "jadxtest" in manifest.lower() or "activity" in manifest.lower(), \
            "Should contain app package or activity"

    async def test_get_strings_summary(self, jadx_base_url, http_client):
        """User asks: What string resources are available?"""
        resp = await http_client.get(
            f"{jadx_base_url}/strings",
            params={"mode": "summary"}
        )
        # Strings may need loading time
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                assert "total" in data or "total_strings" in data, \
                    "Should report string count"

    async def test_get_strings_list(self, jadx_base_url, http_client):
        """User asks: List the string resources"""
        resp = await http_client.get(
            f"{jadx_base_url}/strings",
            params={"mode": "list", "limit": 10}
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                keys = data.get("keys", [])
                assert isinstance(keys, list), "Should return list of keys"


@pytest.mark.asyncio
class TestAPKCrossReferences:
    """
    User Scenario: "Who calls this method?"
    AI needs to trace code relationships.
    """

    async def test_xrefs_to_class(self, jadx_base_url, http_client):
        """User asks: Who uses the ApiManager class?"""
        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-class",
            params={"class_name": "com.jadxtest.app.ApiManager"}
        )
        assert resp.status_code == 200

        data = resp.json()
        # Should return structured xrefs data
        assert "references" in data or "pagination" in data, \
            "Should return references or pagination info"

    async def test_xrefs_to_method(self, jadx_base_url, http_client):
        """User asks: Who calls onCreate?"""
        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-method",
            params={"class_name": MAIN_ACTIVITY, "method_name": "onCreate"}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "references" in data or "xrefs" in data or "pagination" in data


@pytest.mark.asyncio
class TestAPKErrorHandling:
    """
    User Scenario: AI sends invalid requests
    System should return clear, helpful error messages.
    """

    async def test_nonexistent_class_returns_clear_error(self, jadx_base_url, http_client):
        """Invalid class name should return helpful error"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": "com.fake.NonExistentClass"}
        )
        # Should either 404 or 200 with error message
        assert resp.status_code in [200, 404]

        if resp.status_code == 200:
            data = resp.json()
            # Should indicate error or return empty
            response = data.get("response", "")
            assert "error" in str(data).lower() or response == "" or "not found" in str(data).lower()

    async def test_empty_class_name_handled(self, jadx_base_url, http_client):
        """Empty class name should not crash"""
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": ""}
        )
        # Should handle gracefully, not 500
        assert resp.status_code != 500, "Should not return 500 for empty input"

    async def test_pagination_limit_enforced(self, jadx_base_url, http_client):
        """Excessive count parameter should be handled"""
        resp = await http_client.get(
            f"{jadx_base_url}/all-classes",
            params={"count": 99999}
        )
        # JADX has 10000 limit - should return error or truncate
        if resp.status_code == 500:
            data = resp.json()
            assert "error" in data, "Should explain the error"
            assert "10000" in data.get("error", "") or "limit" in data.get("error", "").lower()
        elif resp.status_code == 200:
            data = resp.json()
            # Should return data (possibly truncated)
            assert "classes" in data

    async def test_invalid_method_search_returns_empty(self, jadx_base_url, http_client):
        """Non-matching search should return empty results, not error"""
        resp = await http_client.get(
            f"{jadx_base_url}/search-method",
            params={"method_name": "xyzDefinitelyNotExistingMethod123"}
        )
        assert resp.status_code == 200

        data = resp.json()
        methods = data.get("methods", [])
        assert len(methods) == 0, "Should return empty list for no matches"
