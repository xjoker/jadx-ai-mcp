"""
Layer 3 Integration Tests - Core Endpoint Coverage

Adds coverage for high-priority plugin endpoints that are expected to work
against either the JAR or APK integration fixture.
"""

from __future__ import annotations

import pytest

from .helpers import detect_fixture_type, resolve_fixture_context


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


MISSING_CLASS = "com.jadxtest.missing.DoesNotExist"
MISSING_METHOD = "__missing_method__"
MISSING_FIELD = "__missing_field__"
PREFERRED_METHOD_TARGETS = {
    "jar": {
        "class_name": "com.jadxtest.library.Calculator",
        "preferred_methods": ("add", "subtract"),
    },
    "apk": {
        "class_name": "com.jadxtest.app.MainActivity",
        "preferred_methods": ("onCreate", "onResume", "onStart"),
    },
}


def assert_string_field(data: dict, field: str) -> str:
    assert field in data, f"Missing '{field}' in {data}"
    value = data[field]
    assert isinstance(value, str), f"Expected '{field}' to be str, got {type(value).__name__}"
    assert value.strip(), f"Expected '{field}' to be non-empty"
    return value


def extract_xrefs(data: dict) -> list[dict]:
    xrefs = data.get("xrefs")
    if xrefs is None:
        xrefs = data.get("references")
    assert isinstance(xrefs, list), f"Expected xrefs/references list, got: {data}"
    return xrefs


def select_non_constructor_method(methods: list[dict], preferred_names: tuple[str, ...]) -> dict:
    candidates = [
        method
        for method in methods
        if isinstance(method, dict) and isinstance(method.get("name"), str) and not method.get("is_constructor")
    ]
    assert candidates, "Expected at least one non-constructor method"

    for preferred_name in preferred_names:
        for method in candidates:
            if method.get("name") == preferred_name:
                return method
    return candidates[0]


async def resolve_dynamic_context(jadx_base_url, http_client) -> dict:
    file_type = await detect_fixture_type(jadx_base_url, http_client)
    context = await resolve_fixture_context(jadx_base_url, http_client)
    assert context["file_type"] == file_type
    return context


async def resolve_method_target(jadx_base_url, http_client) -> dict:
    context = await resolve_dynamic_context(jadx_base_url, http_client)
    preferred = PREFERRED_METHOD_TARGETS[context["file_type"]]

    candidate_classes = [
        preferred["class_name"],
        context["class_name"],
        context["secondary_class_name"],
    ]
    seen = set()

    for class_name in candidate_classes:
        if class_name in seen:
            continue
        seen.add(class_name)

        resp = await http_client.get(
            f"{jadx_base_url}/methods-of-class",
            params={"class_name": class_name},
        )
        if resp.status_code != 200:
            continue

        data = resp.json()
        methods = data.get("methods")
        if not isinstance(methods, list) or not methods:
            continue

        selected_method = select_non_constructor_method(methods, preferred["preferred_methods"])
        return {
            "file_type": context["file_type"],
            "class_name": data.get("class_name", class_name),
            "raw_class_name": data.get("raw_class_name", class_name),
            "method_name": selected_method["name"],
            "raw_method_name": selected_method.get("raw_name") or selected_method["name"],
        }

    pytest.fail(f"Unable to resolve a valid method target for fixture type {context['file_type']}")


async def resolve_field_target(jadx_base_url, http_client) -> dict:
    context = await resolve_dynamic_context(jadx_base_url, http_client)
    preferred = PREFERRED_METHOD_TARGETS[context["file_type"]]["class_name"]

    candidate_classes = [
        context["class_name"],
        context["secondary_class_name"],
        preferred,
    ]
    seen = set()
    fallback_target = None

    for class_name in candidate_classes:
        if class_name in seen:
            continue
        seen.add(class_name)

        fields_resp = await http_client.get(
            f"{jadx_base_url}/fields-of-class",
            params={"class_name": class_name},
        )
        if fields_resp.status_code != 200:
            continue

        fields_data = fields_resp.json()
        fields = fields_data.get("fields")
        if not isinstance(fields, list) or not fields:
            continue

        normalized_class_name = fields_data.get("class_name", class_name)
        for field in fields:
            field_name = field.get("name")
            if not isinstance(field_name, str) or not field_name:
                continue

            candidate = {
                "class_name": normalized_class_name,
                "field_name": field_name,
            }
            if fallback_target is None:
                fallback_target = candidate

            xrefs_resp = await http_client.get(
                f"{jadx_base_url}/xrefs-to-field",
                params=candidate,
            )
            if xrefs_resp.status_code != 200:
                continue

            xrefs = extract_xrefs(xrefs_resp.json())
            if xrefs:
                return candidate

    if fallback_target is not None:
        return fallback_target

    pytest.fail(f"Unable to resolve a valid field target for fixture type {context['file_type']}")


async def fetch_batch_method_result(jadx_base_url, http_client, class_name: str, method_name: str) -> dict:
    resp = await http_client.get(
        f"{jadx_base_url}/batch-method-by-name",
        params={"methods": f"{class_name}:{method_name}"},
    )
    assert resp.status_code == 200

    data = resp.json()
    # Response may be direct {"methods": [...]} or wrapped {"batch_result": "JSON string"}
    if "batch_result" in data and isinstance(data["batch_result"], str):
        import json
        inner = json.loads(data["batch_result"])
        methods = inner.get("methods", [])
    else:
        methods = data.get("methods", [])
    assert isinstance(methods, list), f"Expected methods list, got {data}"
    assert len(methods) == 1, f"Expected single batch method result, got {methods}"
    return methods[0]


async def fetch_batch_xrefs(jadx_base_url, http_client, targets: list[str]) -> dict:
    resp = await http_client.get(
        f"{jadx_base_url}/batch-xrefs",
        params={"targets": ",".join(targets)},
    )
    assert resp.status_code == 200
    return resp.json()


class TestHealthEndpoint:
    async def test_health_returns_200_with_status(self, jadx_base_url, http_client):
        await resolve_dynamic_context(jadx_base_url, http_client)

        resp = await http_client.get(f"{jadx_base_url}/health")
        assert resp.status_code == 200

        data = resp.json()
        assert_string_field(data, "status")

    async def test_health_includes_jadx_classes_total(self, jadx_base_url, http_client):
        await resolve_dynamic_context(jadx_base_url, http_client)

        resp = await http_client.get(f"{jadx_base_url}/health")
        assert resp.status_code == 200

        data = resp.json()
        jadx = data.get("jadx")
        assert isinstance(jadx, dict), f"Expected jadx object, got {data}"
        assert "classes_total" in jadx, f"Expected jadx.classes_total, got {jadx}"
        assert isinstance(jadx["classes_total"], int), "Expected jadx.classes_total to be int"
        assert jadx["classes_total"] > 0, "Expected jadx.classes_total to be positive"


class TestMethodCalleesEndpoint:
    async def test_method_callees_known_method_returns_callees_array(self, jadx_base_url, http_client):
        target = await resolve_method_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/method-callees",
            params={"class_name": target["class_name"], "method_name": target["method_name"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        callees = data.get("callees")
        assert isinstance(callees, list), f"Expected callees list, got {data}"

    async def test_method_callees_include_resolved_and_unresolved_groups(self, jadx_base_url, http_client):
        target = await resolve_method_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/method-callees",
            params={"class_name": target["class_name"], "method_name": target["method_name"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert isinstance(data.get("resolved_callees"), list), "Expected resolved_callees list"
        assert isinstance(data.get("unresolved_callees"), list), "Expected unresolved_callees list"

    async def test_method_callees_include_raw_names(self, jadx_base_url, http_client):
        target = await resolve_method_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/method-callees",
            params={"class_name": target["class_name"], "method_name": target["method_name"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("class_name") == target["class_name"]
        assert data.get("method_name") == target["method_name"]
        assert_string_field(data, "raw_class_name")
        assert_string_field(data, "raw_method_name")

    async def test_method_callees_missing_class_returns_404_or_error(self, jadx_base_url, http_client):
        target = await resolve_method_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/method-callees",
            params={"class_name": MISSING_CLASS, "method_name": target["method_name"]},
        )
        data = resp.json()

        assert resp.status_code == 404 or "error" in data, (
            f"Expected 404 or error response for missing class, got {resp.status_code}: {data}"
        )


class TestBatchMethodByNameEndpoint:
    async def test_batch_method_by_name_known_method_returns_source(self, jadx_base_url, http_client):
        target = await resolve_method_target(jadx_base_url, http_client)

        result = await fetch_batch_method_result(
            jadx_base_url,
            http_client,
            target["class_name"],
            target["method_name"],
        )

        assert result.get("found") is True
        code = result.get("code")
        assert isinstance(code, str) and code, "Expected batch method result to include non-empty code"

    async def test_batch_method_by_name_includes_raw_names(self, jadx_base_url, http_client):
        target = await resolve_method_target(jadx_base_url, http_client)

        result = await fetch_batch_method_result(
            jadx_base_url,
            http_client,
            target["class_name"],
            target["method_name"],
        )

        assert result.get("class_name") == target["class_name"]
        assert result.get("method_name") == target["method_name"]
        assert_string_field(result, "raw_class_name")
        assert_string_field(result, "raw_method_name")

    async def test_batch_method_by_name_missing_method_marks_result_not_found(
        self, jadx_base_url, http_client
    ):
        target = await resolve_method_target(jadx_base_url, http_client)

        result = await fetch_batch_method_result(
            jadx_base_url,
            http_client,
            target["class_name"],
            MISSING_METHOD,
        )

        assert result.get("class_name") == target["class_name"]
        assert result.get("method_name") == MISSING_METHOD
        assert result.get("found") is False


class TestXrefsToFieldEndpoint:
    async def test_xrefs_to_field_known_field_returns_xrefs_array(self, jadx_base_url, http_client):
        target = await resolve_field_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-field",
            params={"class_name": target["class_name"], "field_name": target["field_name"]},
        )
        assert resp.status_code == 200

        xrefs = extract_xrefs(resp.json())
        assert isinstance(xrefs, list)

    async def test_xrefs_to_field_include_raw_class_and_raw_method(self, jadx_base_url, http_client):
        target = await resolve_field_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-field",
            params={"class_name": target["class_name"], "field_name": target["field_name"]},
        )
        assert resp.status_code == 200

        xrefs = extract_xrefs(resp.json())
        assert xrefs, f"Expected at least one xref for {target['class_name']}:{target['field_name']}"

        for xref in xrefs:
            assert "raw_class" in xref, f"Missing raw_class in xref: {xref}"
            assert "raw_method" in xref, f"Missing raw_method in xref: {xref}"
            assert isinstance(xref["raw_class"], str), "Expected raw_class to be a string"
            assert isinstance(xref["raw_method"], str), "Expected raw_method to be a string"

    async def test_xrefs_to_field_missing_field_returns_empty_or_error(self, jadx_base_url, http_client):
        target = await resolve_field_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/xrefs-to-field",
            params={"class_name": target["class_name"], "field_name": MISSING_FIELD},
        )
        data = resp.json()

        if resp.status_code == 200:
            xrefs = extract_xrefs(data)
            assert xrefs == []
        else:
            assert "error" in data


class TestBatchXrefsEndpoint:
    async def test_batch_xrefs_targets_return_results_array(self, jadx_base_url, http_client):
        context = await resolve_dynamic_context(jadx_base_url, http_client)
        targets = [f"class:{class_name}" for class_name in context["batch_class_names"]]

        data = await fetch_batch_xrefs(jadx_base_url, http_client, targets)
        results = data.get("results")

        assert isinstance(results, list), f"Expected results list, got {data}"
        assert len(results) == len(targets), "Expected one batch result per target"

    async def test_batch_xrefs_results_include_found_and_xrefs(self, jadx_base_url, http_client):
        context = await resolve_dynamic_context(jadx_base_url, http_client)
        targets = [f"class:{class_name}" for class_name in context["batch_class_names"]]

        data = await fetch_batch_xrefs(jadx_base_url, http_client, targets)
        results = data.get("results")
        assert isinstance(results, list), f"Expected results list, got {data}"

        for result in results:
            assert "found" in result, f"Missing found flag in batch xrefs result: {result}"
            assert result.get("found") is True, f"Expected known target to be found: {result}"
            assert isinstance(result.get("xrefs"), list), f"Expected xrefs list in batch result: {result}"
