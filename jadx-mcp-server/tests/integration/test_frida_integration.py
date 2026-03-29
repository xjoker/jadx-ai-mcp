"""
Layer 3 Integration Tests - Frida Script Generation

Tests real JADX container Frida endpoints against the loaded fixture.
This file is designed to run in either JAR or APK mode:

- JAR fixture: tests/fixtures/jadx-test-library-1.0.0.jar
- APK fixture: tests/fixtures/jadx-test-app-1.0.0.apk

The loaded file type is detected via /file-info, then the test switches to
known stable classes/methods for that fixture:

- JAR: com.jadxtest.library.Calculator
- APK: com.jadxtest.app.MainActivity / com.jadxtest.app.ApiManager
"""

import pytest


pytestmark = pytest.mark.integration


JAR_TARGET = {
    "file_type": "jar",
    "hook_class": "com.jadxtest.library.Calculator",
    "hook_method": "add",
    "extra_method": "subtract",
    "constructor_class": "com.jadxtest.library.model.User",
}

APK_TARGET = {
    "file_type": "apk",
    "hook_class": "com.jadxtest.app.MainActivity",
    "hook_method": "onCreate",
    "extra_method": "onResume",
    "constructor_class": "com.jadxtest.app.ApiManager",
}

MISSING_CLASS = "com.jadxtest.missing.DoesNotExist"


async def get_loaded_target(jadx_base_url, http_client):
    """Return the stable test target for the currently loaded fixture."""
    resp = await http_client.get(f"{jadx_base_url}/file-info")
    assert resp.status_code == 200

    data = resp.json()
    file_type = data.get("file_type")
    if file_type == "jar":
        return JAR_TARGET
    if file_type == "apk":
        return APK_TARGET

    pytest.fail(f"Unsupported file_type for Frida integration tests: {file_type}")


def assert_success_response_has_names(data):
    assert "class_name" in data, "Response should include class_name"
    assert "raw_class_name" in data, "Response should include raw_class_name"
    assert data["class_name"], "class_name should not be empty"
    assert data["raw_class_name"], "raw_class_name should not be empty"


def assert_script_uses_raw_class_name(data):
    script = data.get("script", "")
    raw_class_name = data["raw_class_name"]

    assert script, "Response should include a non-empty script"
    assert f"Java.use('{raw_class_name}')" in script, \
        "Generated Frida script should use raw_class_name in Java.use()"

    class_name = data["class_name"]
    if class_name != raw_class_name:
        assert f"Java.use('{class_name}')" not in script, \
            "Generated Frida script should not use alias class_name in Java.use()"


@pytest.mark.asyncio
class TestFridaHookGeneration:
    async def test_generate_single_method_hook_both(self, jadx_base_url, http_client):
        target = await get_loaded_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/generate-frida-hook",
            params={
                "class_name": target["hook_class"],
                "method_name": target["hook_method"],
                "hook_type": "both",
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert_success_response_has_names(data)
        assert data.get("hook_type") == "both"
        assert data.get("method_name") == target["hook_method"]

        script = data.get("script", "")
        assert "Java.perform" in script
        assert "Java.use" in script
        assert f"clazz.{target['hook_method']}" in script
        assert_script_uses_raw_class_name(data)

    async def test_generate_all_methods_hook_contains_multiple_hooks(self, jadx_base_url, http_client):
        target = await get_loaded_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/generate-frida-hook",
            params={
                "class_name": target["hook_class"],
                "hook_type": "all_methods",
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert_success_response_has_names(data)
        assert data.get("hook_type") == "all_methods"
        assert data.get("method_name") == "(all)"

        script = data.get("script", "")
        assert f"clazz.{target['hook_method']}" in script
        assert f"clazz.{target['extra_method']}" in script
        assert script.count(".implementation = function(") >= 2, \
            "all_methods hook should generate multiple method implementations"

    async def test_generate_constructor_hook_contains_init(self, jadx_base_url, http_client):
        target = await get_loaded_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/generate-frida-hook",
            params={
                "class_name": target["constructor_class"],
                "hook_type": "constructor",
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert_success_response_has_names(data)
        assert data.get("hook_type") == "constructor"

        script = data.get("script", "")
        assert "$init" in script, "Constructor hook should target Frida $init"
        assert ".implementation = function(" in script
        assert_script_uses_raw_class_name(data)

    async def test_generate_hook_returns_raw_class_name_and_uses_it_in_script(
        self, jadx_base_url, http_client
    ):
        target = await get_loaded_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/generate-frida-hook",
            params={
                "class_name": target["hook_class"],
                "method_name": target["extra_method"],
                "hook_type": "both",
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert_success_response_has_names(data)
        assert_script_uses_raw_class_name(data)

    async def test_generate_hook_missing_class_name_returns_400(self, jadx_base_url, http_client):
        resp = await http_client.get(
            f"{jadx_base_url}/generate-frida-hook",
            params={"method_name": "add", "hook_type": "both"},
        )
        assert resp.status_code == 400

        data = resp.json()
        assert "error" in data
        assert "class_name" in data["error"]

    async def test_generate_hook_nonexistent_class_returns_404(self, jadx_base_url, http_client):
        resp = await http_client.get(
            f"{jadx_base_url}/generate-frida-hook",
            params={
                "class_name": MISSING_CLASS,
                "method_name": "add",
                "hook_type": "both",
            },
        )
        assert resp.status_code == 404

        data = resp.json()
        assert "error" in data
        assert "Class not found" in data["error"]


@pytest.mark.asyncio
class TestFridaTraceGeneration:
    async def test_generate_trace_script(self, jadx_base_url, http_client):
        target = await get_loaded_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/generate-frida-trace",
            params={"class_name": target["hook_class"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert_success_response_has_names(data)

        script = data.get("script", "")
        assert "Java.perform" in script
        assert "console.log" in script
        assert_script_uses_raw_class_name(data)

    async def test_generate_trace_script_with_include_subclasses(self, jadx_base_url, http_client):
        target = await get_loaded_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/generate-frida-trace",
            params={
                "class_name": target["hook_class"],
                "include_subclasses": "true",
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert_success_response_has_names(data)
        assert data.get("include_subclasses") is True

        script = data.get("script", "")
        assert script.startswith("'use strict';")
        assert "Java.perform" in script
        assert "try {" in script
        assert_script_uses_raw_class_name(data)

    async def test_generate_trace_missing_class_name_returns_400(self, jadx_base_url, http_client):
        resp = await http_client.get(f"{jadx_base_url}/generate-frida-trace")
        assert resp.status_code == 400

        data = resp.json()
        assert "error" in data
        assert "class_name" in data["error"]


@pytest.mark.asyncio
class TestFridaEnumGeneration:
    async def test_generate_enum_script(self, jadx_base_url, http_client):
        target = await get_loaded_target(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/generate-frida-enum",
            params={"class_name": target["hook_class"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert_success_response_has_names(data)

        script = data.get("script", "")
        assert "Java.perform" in script
        assert "Java.choose" in script or ".value" in script
        assert_script_uses_raw_class_name(data)

    async def test_generate_enum_missing_class_name_returns_400(self, jadx_base_url, http_client):
        resp = await http_client.get(f"{jadx_base_url}/generate-frida-enum")
        assert resp.status_code == 400

        data = resp.json()
        assert "error" in data
        assert "class_name" in data["error"]


@pytest.mark.asyncio
class TestFridaRawNameConsistency:
    async def test_all_frida_responses_include_class_name_and_raw_class_name(
        self, jadx_base_url, http_client
    ):
        target = await get_loaded_target(jadx_base_url, http_client)

        requests = [
            (
                "generate-frida-hook",
                {
                    "class_name": target["hook_class"],
                    "method_name": target["hook_method"],
                    "hook_type": "both",
                },
            ),
            (
                "generate-frida-trace",
                {"class_name": target["hook_class"]},
            ),
            (
                "generate-frida-enum",
                {"class_name": target["hook_class"]},
            ),
        ]

        for endpoint, params in requests:
            resp = await http_client.get(f"{jadx_base_url}/{endpoint}", params=params)
            assert resp.status_code == 200, f"{endpoint} should return 200"

            data = resp.json()
            assert_success_response_has_names(data)
