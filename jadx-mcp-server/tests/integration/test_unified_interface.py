"""
Layer 3 Integration Tests - Unified Interface Testing

Tests that APK and JAR files behave consistently through unified interfaces.
Requires switching between APK and JAR containers to verify both paths.

Test Philosophy:
- Same tool should work for both file types
- Response structure should be consistent
- File-type-specific features should return appropriate NOT_APPLICABLE
"""

import pytest


@pytest.mark.asyncio
class TestUnifiedFileInfo:
    """
    Verify get_file_info works correctly for both APK and JAR.
    Run this test twice: once with APK container, once with JAR container.
    """

    async def test_file_info_structure(self, jadx_base_url, http_client):
        """Both APK and JAR should return consistent structure"""
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200

        data = resp.json()
        # Required fields for all file types
        assert "loaded" in data, "Should have loaded field"
        assert "file_type" in data, "Should have file_type field"
        assert "recommended_tools" in data, "Should have recommended_tools"

        # Verify file type is valid
        assert data["file_type"] in ["apk", "jar", "aar", "dex"], \
            f"Invalid file_type: {data['file_type']}"

    async def test_file_info_recommends_appropriate_tools(self, jadx_base_url, http_client):
        """Recommended tools should match file type"""
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200

        data = resp.json()
        file_type = data["file_type"]
        recommended = data.get("recommended_tools", [])

        if file_type == "apk":
            assert "get_android_manifest" in recommended
            assert "get_smali_of_class" in recommended
        elif file_type == "jar":
            assert "jar_get_manifest" in recommended
            assert "get_class_source" in recommended


@pytest.mark.asyncio
class TestUnifiedClassOperations:
    """
    Verify class operations work consistently for both file types.
    """

    async def test_all_classes_returns_list(self, jadx_base_url, http_client):
        """Both file types should return class list"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=10")
        assert resp.status_code == 200

        data = resp.json()
        assert "classes" in data, "Should have classes field"
        assert isinstance(data["classes"], list), "classes should be a list"
        assert len(data["classes"]) > 0, "Should have at least one class"

    async def test_class_source_returns_java(self, jadx_base_url, http_client):
        """Both file types should return Java source"""
        # First get a class name
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=1")
        assert resp.status_code == 200
        classes = resp.json().get("classes", [])
        assert len(classes) > 0, "Need at least one class"

        # Get source for that class
        resp = await http_client.get(
            f"{jadx_base_url}/class-source",
            params={"class_name": classes[0]}
        )
        assert resp.status_code == 200

        data = resp.json()
        source = data.get("response", data.get("content", ""))
        assert len(source) > 50, "Should return substantial source code"
        assert "class " in source or "interface " in source, \
            "Should contain Java class/interface declaration"

    async def test_class_info_returns_metadata(self, jadx_base_url, http_client):
        """Both file types should return class metadata"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=1")
        classes = resp.json().get("classes", [])
        assert len(classes) > 0

        resp = await http_client.get(
            f"{jadx_base_url}/class-info",
            params={"class_name": classes[0]}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "simple_name" in data, "Should have simple_name"
        assert "package" in data, "Should have package"


@pytest.mark.asyncio
class TestUnifiedSearchOperations:
    """
    Verify search operations work for both file types.
    """

    async def test_methods_of_class_works(self, jadx_base_url, http_client):
        """Getting methods of a class should work for both"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=1")
        classes = resp.json().get("classes", [])
        assert len(classes) > 0

        resp = await http_client.get(
            f"{jadx_base_url}/methods-of-class",
            params={"class_name": classes[0]}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "methods" in data, "Should have methods field"


@pytest.mark.asyncio
class TestFileTypeSpecificBehavior:
    """
    Verify file-type-specific tools return NOT_APPLICABLE appropriately.
    """

    async def test_android_manifest_behavior(self, jadx_base_url, http_client):
        """Manifest should work for APK, return NOT_APPLICABLE for JAR"""
        resp = await http_client.get(f"{jadx_base_url}/manifest")
        assert resp.status_code == 200

        data = resp.json()
        # Check file type first
        file_info = await http_client.get(f"{jadx_base_url}/file-info")
        file_type = file_info.json().get("file_type")

        if file_type == "apk":
            manifest = data.get("manifest", data.get("response", str(data)))
            assert "android" in manifest.lower() or "manifest" in manifest.lower()
        else:
            # JAR should indicate not applicable
            assert data.get("status") == "NOT_APPLICABLE" or "jar" in str(data).lower()

    async def test_jar_manifest_behavior(self, jadx_base_url, http_client):
        """JAR manifest should work for JAR, return NOT_APPLICABLE for APK"""
        resp = await http_client.get(f"{jadx_base_url}/jar-manifest")
        assert resp.status_code == 200

        data = resp.json()
        file_info = await http_client.get(f"{jadx_base_url}/file-info")
        file_type = file_info.json().get("file_type")

        if file_type == "jar":
            assert data.get("status") == "success"
            assert "all_attributes" in data
        else:
            # APK should indicate not applicable
            assert data.get("status") == "NOT_APPLICABLE"

    async def test_smali_behavior(self, jadx_base_url, http_client):
        """Smali should work for APK, not available for JAR"""
        resp = await http_client.get(f"{jadx_base_url}/all-classes?count=1")
        classes = resp.json().get("classes", [])
        assert len(classes) > 0

        resp = await http_client.get(
            f"{jadx_base_url}/smali-of-class",
            params={"class_name": classes[0]}
        )
        assert resp.status_code == 200

        data = resp.json()
        file_info = await http_client.get(f"{jadx_base_url}/file-info")
        file_type = file_info.json().get("file_type")

        if file_type == "apk":
            smali = data.get("response", "")
            assert ".class" in smali, "APK should return Smali bytecode"
        else:
            # JAR has no Smali
            response = data.get("response", "")
            assert response == "" or "not available" in str(data).lower()
