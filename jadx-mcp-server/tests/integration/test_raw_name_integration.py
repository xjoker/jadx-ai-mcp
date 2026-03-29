"""
Layer 3 Integration Tests - raw_name Consistency and Rename Mappings

Tests the currently loaded JADX integration fixture.

Focus:
- Endpoints returning class/method/field identities must expose both alias and raw names.
- The loaded fixture may be either the test JAR or the test APK.
- Rename mapping APIs should report an empty mapping set for an untouched fixture.
"""

import pytest

from .helpers import detect_fixture_type, get_file_info, normalize_class_entry, resolve_fixture_context


pytestmark = pytest.mark.integration


def assert_string_field(data: dict, field: str) -> str:
    assert field in data, f"Missing '{field}' in {data}"
    value = data[field]
    assert isinstance(value, str), f"Expected '{field}' to be str, got {type(value).__name__}"
    assert value.strip(), f"Expected '{field}' to be non-empty"
    assert value == value.strip(), f"Expected '{field}' to be trimmed"
    return value


def assert_alias_raw_pair(data: dict, alias_field: str = "name", raw_field: str = "raw_name") -> tuple[str, str]:
    alias_value = assert_string_field(data, alias_field)
    raw_value = assert_string_field(data, raw_field)
    return alias_value, raw_value


def assert_method_alias_raw_pair(data: dict, alias_field: str = "name", raw_field: str = "raw_name") -> tuple[str, str]:
    alias_value = assert_string_field(data, alias_field)
    raw_value = assert_string_field(data, raw_field)
    return alias_value, raw_value


@pytest.mark.asyncio
class TestRawNameConsistency:
    async def test_all_classes_include_name_and_raw_name(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)
        assert context["file_type"] in {"jar", "apk"}

        resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 100})
        assert resp.status_code == 200

        data = resp.json()
        classes = data.get("classes")
        assert isinstance(classes, list), "Expected /all-classes to return a classes list"
        assert classes, "Expected /all-classes to return at least one class"

        alias_names = set()
        raw_names = set()
        for class_info in classes:
            alias_name, raw_name = assert_alias_raw_pair(normalize_class_entry(class_info))
            assert "." in alias_name, f"Expected fully qualified class alias, got {alias_name!r}"
            assert "." in raw_name, f"Expected fully qualified raw class name, got {raw_name!r}"
            alias_names.add(alias_name)
            raw_names.add(raw_name)

        assert context["class_name"] in alias_names
        assert context["class_name"] in context["class_names"]
        assert raw_names

    async def test_methods_of_class_include_name_and_raw_name(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/methods-of-class",
            params={"class_name": context["class_name"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == context["class_name"]
        assert_string_field(data, "raw_class_name")

        methods = data.get("methods")
        assert isinstance(methods, list), "Expected /methods-of-class to return a methods list"
        assert methods, "Expected target class to expose at least one method"

        discovered_methods = set()
        raw_methods = set()
        for method in methods:
            alias_name, raw_name = assert_method_alias_raw_pair(method)
            if not method.get("is_constructor"):
                discovered_methods.add(alias_name)
                raw_methods.add(raw_name)

        assert context["method_name"] in discovered_methods
        assert context["raw_method_name"] in raw_methods

    async def test_fields_of_class_include_name_and_raw_name(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)
        assert context["fields"], "Expected fixture target class to expose at least one field"

        resp = await http_client.get(
            f"{jadx_base_url}/fields-of-class",
            params={"class_name": context["class_name"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == context["class_name"]
        assert_string_field(data, "raw_class_name")

        fields = data.get("fields")
        assert isinstance(fields, list), "Expected /fields-of-class to return a fields list"
        assert fields, "Expected target class to expose at least one field"

        alias_names = []
        raw_names = []
        for field in fields:
            alias_name, raw_name = assert_alias_raw_pair(field)
            alias_names.append(alias_name)
            raw_names.append(raw_name)

        assert len(alias_names) == len(fields)
        assert len(raw_names) == len(fields)

    async def test_class_info_includes_raw_class_method_and_field_names(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/class-info",
            params={"class_name": context["class_name"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == context["class_name"]
        assert_string_field(data, "raw_class_name")

        method_names = data.get("method_names")
        raw_method_names = data.get("raw_method_names")
        field_names = data.get("field_names")
        raw_field_names = data.get("raw_field_names")

        assert isinstance(method_names, list), "Expected method_names list"
        assert isinstance(raw_method_names, list), "Expected raw_method_names list"
        assert isinstance(field_names, list), "Expected field_names list"
        assert isinstance(raw_field_names, list), "Expected raw_field_names list"

        assert context["method_name"] in method_names
        assert context["raw_method_name"] in raw_method_names
        assert field_names, "Expected class-info to include at least one field name"
        assert raw_field_names, "Expected class-info to include at least one raw field name"

    async def test_main_application_classes_names_include_name_and_raw_name_when_available(
        self, jadx_base_url, http_client
    ):
        file_info = await get_file_info(jadx_base_url, http_client)

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
        context = await resolve_fixture_context(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/search-native-methods",
            params={"package": context["package_name"], "count": 50},
        )
        assert resp.status_code == 200

        data = resp.json()
        native_methods = data.get("native_methods")
        assert isinstance(native_methods, list), "Expected native_methods list"
        assert data.get("count") == len(native_methods)
        assert data.get("total_found", 0) >= len(native_methods)

        for native_method in native_methods:
            assert_string_field(native_method, "class_name")
            assert_string_field(native_method, "raw_class_name")
            assert_string_field(native_method, "method_name")
            assert_string_field(native_method, "raw_method_name")

    async def test_xrefs_to_class_expose_raw_class_and_raw_method(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-class",
            params={"class_name": context["class_name"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        references = data.get("references")
        assert isinstance(references, list), "Expected references list from /xrefs-to-class"

        for reference in references:
            assert_string_field(reference, "class")
            assert_string_field(reference, "raw_class")

            assert "raw_method" in reference, f"Missing 'raw_method' in {reference}"
            raw_method_name = reference["raw_method"]
            assert isinstance(raw_method_name, str), "Expected raw_method to be a string"

            method_name = reference.get("method", "")
            if method_name:
                assert isinstance(method_name, str), "Expected method to be a string"

    async def test_method_by_name_includes_raw_class_and_method_name(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/method-by-name",
            params={"class_name": context["class_name"], "method_name": context["method_name"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == context["class_name"]
        assert_string_field(data, "raw_class_name")
        assert data.get("method_name") == context["method_name"]
        assert_string_field(data, "raw_method_name")
        code = data.get("code")
        assert isinstance(code, str) and code, "Expected /method-by-name to return method source code"
        assert context["method_name"] in code or len(code) > 40

    async def test_method_signature_includes_raw_class_and_method_name(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/method-signature",
            params={"class_name": context["class_name"], "method_name": context["method_name"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == context["class_name"]
        assert_string_field(data, "raw_class_name")
        assert data.get("method_name") == context["method_name"]
        assert_string_field(data, "raw_method_name")

        signatures = data.get("signatures")
        assert isinstance(signatures, list), "Expected signatures list from /method-signature"
        assert signatures, "Expected at least one signature for selected method"

        for signature in signatures:
            assert signature.get("method_name") == context["method_name"]
            assert_string_field(signature, "raw_method_name")


@pytest.mark.asyncio
class TestRenameMappings:
    async def test_export_rename_mappings_returns_empty_array_for_unmodified_fixture(
        self, jadx_base_url, http_client
    ):
        await detect_fixture_type(jadx_base_url, http_client)

        resp = await http_client.get(f"{jadx_base_url}/export-rename-mappings")
        assert resp.status_code == 200

        data = resp.json()
        mappings = data.get("mappings")
        assert isinstance(mappings, list), "Expected mappings to be a list"
        assert data.get("total") == 0, "Unmodified test fixture should export no rename mappings"
        assert mappings == [], "Unmodified test fixture should have an empty rename mapping array"

        for mapping in mappings:
            assert_string_field(mapping, "type")
            assert_string_field(mapping, "original_name")
            assert_string_field(mapping, "new_name")

    async def test_import_rename_mappings_accepts_empty_mapping_array(self, jadx_base_url, http_client):
        await detect_fixture_type(jadx_base_url, http_client)

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
