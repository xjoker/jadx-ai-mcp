"""
Layer 3 Integration Tests - raw_name Consistency and Rename Mappings

Tests real JADX container with jadx-test-library-1.0.0.jar.

Focus:
- Endpoints returning class/method/field identities must expose both alias and raw names.
- For the non-obfuscated JAR fixture, alias names should match raw names.
- Rename mapping APIs should report an empty mapping set for an untouched fixture.
"""

import httpx
import pytest


pytestmark = pytest.mark.integration


TEST_CLASS = "com.jadxtest.library.Calculator"
TEST_METHOD = "add"
EXPECTED_CLASSES = {
    "com.jadxtest.library.Calculator",
    "com.jadxtest.library.FileProcessor",
    "com.jadxtest.library.StringUtils",
    "com.jadxtest.library.model.User",
    "com.jadxtest.library.network.HttpClient",
}
EXPECTED_METHODS = {"add", "subtract", "multiply", "divide", "getLastResult"}
EXPECTED_FIELDS = {"lastResult", "VERSION"}


async def assert_loaded_jar(jadx_base_url: str, http_client: httpx.AsyncClient) -> dict:
    resp = await http_client.get(f"{jadx_base_url}/file-info")
    assert resp.status_code == 200, f"Expected 200 from /file-info, got {resp.status_code}"

    data = resp.json()
    assert data.get("loaded") is True, "Fixture should be loaded"
    assert data.get("file_type") == "jar", f"Expected JAR fixture, got {data.get('file_type')}"
    return data


def assert_string_field(data: dict, field: str) -> str:
    assert field in data, f"Missing '{field}' in {data}"
    value = data[field]
    assert isinstance(value, str), f"Expected '{field}' to be str, got {type(value).__name__}"
    assert value, f"Expected '{field}' to be non-empty"
    return value


def assert_alias_raw_pair(data: dict, alias_field: str = "name", raw_field: str = "raw_name") -> tuple[str, str]:
    alias_value = assert_string_field(data, alias_field)
    raw_value = assert_string_field(data, raw_field)
    assert alias_value == raw_value, (
        f"Expected {alias_field} and {raw_field} to match for non-obfuscated JAR: "
        f"{alias_value!r} != {raw_value!r}"
    )
    return alias_value, raw_value


def assert_method_alias_raw_pair(data: dict, alias_field: str = "name", raw_field: str = "raw_name") -> tuple[str, str]:
    alias_value = assert_string_field(data, alias_field)
    raw_value = assert_string_field(data, raw_field)

    if data.get("is_constructor"):
        assert raw_value in {alias_value, "<init>"}, (
            "Constructor raw_name should either match alias or keep the JVM constructor name"
        )
    else:
        assert alias_value == raw_value, (
            f"Expected {alias_field} and {raw_field} to match for non-obfuscated JAR: "
            f"{alias_value!r} != {raw_value!r}"
        )

    return alias_value, raw_value


@pytest.mark.asyncio
class TestRawNameConsistency:
    async def test_all_classes_include_name_and_raw_name(self, jadx_base_url, http_client):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 100})
        assert resp.status_code == 200

        data = resp.json()
        classes = data.get("classes")
        assert isinstance(classes, list), "Expected /all-classes to return a classes list"
        assert len(classes) == len(EXPECTED_CLASSES), (
            f"Expected {len(EXPECTED_CLASSES)} classes, got {len(classes)}"
        )

        alias_names = set()
        raw_names = set()
        for class_info in classes:
            alias_name, raw_name = assert_alias_raw_pair(class_info)
            alias_names.add(alias_name)
            raw_names.add(raw_name)

        assert alias_names == EXPECTED_CLASSES
        assert raw_names == EXPECTED_CLASSES

    async def test_methods_of_class_include_name_and_raw_name(self, jadx_base_url, http_client):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/methods-of-class",
            params={"class_name": TEST_CLASS},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == TEST_CLASS
        assert data.get("raw_class_name") == TEST_CLASS

        methods = data.get("methods")
        assert isinstance(methods, list), "Expected /methods-of-class to return a methods list"
        assert methods, "Calculator should expose at least one method"

        discovered_methods = set()
        raw_methods = set()
        for method in methods:
            alias_name, raw_name = assert_method_alias_raw_pair(method)
            if not method.get("is_constructor"):
                discovered_methods.add(alias_name)
                raw_methods.add(raw_name)

        assert EXPECTED_METHODS.issubset(discovered_methods)
        assert EXPECTED_METHODS.issubset(raw_methods)

    async def test_fields_of_class_include_name_and_raw_name(self, jadx_base_url, http_client):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/fields-of-class",
            params={"class_name": TEST_CLASS},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == TEST_CLASS
        assert data.get("raw_class_name") == TEST_CLASS

        fields = data.get("fields")
        assert isinstance(fields, list), "Expected /fields-of-class to return a fields list"
        assert len(fields) == len(EXPECTED_FIELDS), (
            f"Expected {len(EXPECTED_FIELDS)} fields, got {len(fields)}"
        )

        alias_names = set()
        raw_names = set()
        for field in fields:
            alias_name, raw_name = assert_alias_raw_pair(field)
            alias_names.add(alias_name)
            raw_names.add(raw_name)

        assert alias_names == EXPECTED_FIELDS
        assert raw_names == EXPECTED_FIELDS

    async def test_class_info_includes_raw_class_method_and_field_names(self, jadx_base_url, http_client):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/class-info",
            params={"class_name": TEST_CLASS},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == TEST_CLASS
        assert data.get("raw_class_name") == TEST_CLASS

        method_names = data.get("method_names")
        raw_method_names = data.get("raw_method_names")
        field_names = data.get("field_names")
        raw_field_names = data.get("raw_field_names")

        assert isinstance(method_names, list), "Expected method_names list"
        assert isinstance(raw_method_names, list), "Expected raw_method_names list"
        assert isinstance(field_names, list), "Expected field_names list"
        assert isinstance(raw_field_names, list), "Expected raw_field_names list"

        assert EXPECTED_METHODS.issubset(set(method_names))
        assert EXPECTED_METHODS.issubset(set(raw_method_names))
        assert set(field_names) == EXPECTED_FIELDS
        assert set(raw_field_names) == EXPECTED_FIELDS

    async def test_main_application_classes_names_include_name_and_raw_name_when_available(
        self, jadx_base_url, http_client
    ):
        file_info = await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(f"{jadx_base_url}/main-application-classes-names")
        data = resp.json()

        if file_info.get("android_features"):
            assert resp.status_code == 200
            classes = data.get("classes")
            assert isinstance(classes, list), "Expected classes list from /main-application-classes-names"
            assert classes, "Expected at least one main application class"
            for class_info in classes:
                assert_alias_raw_pair(class_info)
        else:
            assert resp.status_code == 404, (
                "JAR fixtures are expected to report /main-application-classes-names as not applicable"
            )
            assert "AndroidManifest.xml" in data.get("error", "")

    async def test_search_native_methods_exposes_raw_names(self, jadx_base_url, http_client):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/search-native-methods",
            params={"package": "com.jadxtest.library", "count": 50},
        )
        assert resp.status_code == 200

        data = resp.json()
        native_methods = data.get("native_methods")
        assert isinstance(native_methods, list), "Expected native_methods list"
        assert data.get("total_found") == 0, "Test JAR should not contain native methods"
        assert data.get("count") == 0, "No native methods should be returned for the test JAR"

        for native_method in native_methods:
            assert_string_field(native_method, "class_name")
            assert_string_field(native_method, "raw_class_name")
            assert_string_field(native_method, "method_name")
            assert_string_field(native_method, "raw_method_name")
            assert native_method["class_name"] == native_method["raw_class_name"]
            assert native_method["method_name"] == native_method["raw_method_name"]

    async def test_xrefs_to_class_expose_raw_class_and_raw_method(self, jadx_base_url, http_client):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-class",
            params={"class_name": TEST_CLASS},
        )
        assert resp.status_code == 200

        data = resp.json()
        references = data.get("references")
        assert isinstance(references, list), "Expected references list from /xrefs-to-class"

        for reference in references:
            class_name = assert_string_field(reference, "class")
            raw_class_name = assert_string_field(reference, "raw_class")
            assert class_name == raw_class_name

            assert "raw_method" in reference, f"Missing 'raw_method' in {reference}"
            raw_method_name = reference["raw_method"]
            assert isinstance(raw_method_name, str), "Expected raw_method to be a string"

            method_name = reference.get("method", "")
            if method_name:
                assert raw_method_name in {method_name, "<init>", "<clinit>"}, (
                    "raw_method should match alias method for non-obfuscated names, "
                    "with JVM special names allowed for init methods"
                )

    async def test_method_by_name_includes_raw_class_and_method_name(self, jadx_base_url, http_client):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/method-by-name",
            params={"class_name": TEST_CLASS, "method_name": TEST_METHOD},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == TEST_CLASS
        assert data.get("raw_class_name") == TEST_CLASS
        assert data.get("method_name") == TEST_METHOD
        assert data.get("raw_method_name") == TEST_METHOD
        code = data.get("code")
        assert isinstance(code, str) and code, "Expected /method-by-name to return method source code"
        assert "lastResult" in code

    async def test_method_signature_includes_raw_class_and_method_name(self, jadx_base_url, http_client):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/method-signature",
            params={"class_name": TEST_CLASS, "method_name": TEST_METHOD},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == TEST_CLASS
        assert data.get("raw_class_name") == TEST_CLASS
        assert data.get("method_name") == TEST_METHOD
        assert data.get("raw_method_name") == TEST_METHOD

        signatures = data.get("signatures")
        assert isinstance(signatures, list), "Expected signatures list from /method-signature"
        assert signatures, "Expected at least one signature for Calculator.add"

        for signature in signatures:
            assert signature.get("method_name") == TEST_METHOD
            assert signature.get("raw_method_name") == TEST_METHOD


@pytest.mark.asyncio
class TestRenameMappings:
    async def test_export_rename_mappings_returns_empty_array_for_unmodified_jar(
        self, jadx_base_url, http_client
    ):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.get(f"{jadx_base_url}/export-rename-mappings")
        assert resp.status_code == 200

        data = resp.json()
        mappings = data.get("mappings")
        assert isinstance(mappings, list), "Expected mappings to be a list"
        assert data.get("total") == 0, "Unmodified test JAR should export no rename mappings"
        assert mappings == [], "Unmodified test JAR should have an empty rename mapping array"

        for mapping in mappings:
            assert_string_field(mapping, "type")
            assert_string_field(mapping, "original_name")
            assert_string_field(mapping, "new_name")

    async def test_import_rename_mappings_accepts_empty_mapping_array(self, jadx_base_url, http_client):
        await assert_loaded_jar(jadx_base_url, http_client)

        resp = await http_client.post(
            f"{jadx_base_url}/import-rename-mappings",
            json={"mappings": []},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("success") is True
        assert data.get("total") == 0
        assert data.get("applied") == 0
        assert data.get("failed") == 0
        assert data.get("errors") == []
