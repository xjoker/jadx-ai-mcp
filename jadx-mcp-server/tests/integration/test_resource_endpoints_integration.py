"""
Layer 3 Integration Tests - Resource, JAR-only, and Cache Endpoint Coverage

Exercises plugin HTTP endpoints that were not covered by the existing
integration suite while remaining compatible with either the APK or JAR
fixture loaded into the local JADX integration container.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from .helpers import detect_fixture_type


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


KNOWN_PACKAGE_BY_TYPE = {
    "apk": "com.jadxtest.app",
    "jar": "com.jadxtest.library",
}

KNOWN_CLASS_BY_TYPE = {
    "apk": "com.jadxtest.app.MainActivity",
    "jar": "com.jadxtest.library.Calculator",
}

RESOURCE_HINTS_BY_TYPE = {
    "apk": ("AndroidManifest.xml",),
    "jar": ("META-INF/MANIFEST.MF", "MANIFEST.MF", "META-INF/"),
}

MISSING_PACKAGE = "com.jadxtest.missing.package"
MISSING_RESOURCE = "__missing__/does-not-exist.txt"


async def get_with_retry(
    http_client,
    url: str,
    *,
    params: dict | None = None,
    retryable_statuses: tuple[int, ...] = (202, 503),
    max_wait_seconds: float = 35.0,
):
    deadline = time.monotonic() + max_wait_seconds

    while True:
        resp = await http_client.get(url, params=params)
        if resp.status_code not in retryable_statuses:
            return resp

        now = time.monotonic()
        if now >= deadline:
            return resp

        try:
            data = resp.json()
        except ValueError:
            data = {}

        retry_after = data.get("retry_after", 1)
        try:
            sleep_for = float(retry_after)
        except (TypeError, ValueError):
            sleep_for = 1.0

        sleep_for = max(0.5, min(sleep_for, deadline - now))
        await asyncio.sleep(sleep_for)


async def get_resource_file_names(jadx_base_url, http_client, *, count: int = 50) -> list[str]:
    resp = await get_with_retry(
        http_client,
        f"{jadx_base_url}/list-all-resource-files-names",
        params={"count": count},
    )
    assert resp.status_code == 200, f"Expected 200 from /list-all-resource-files-names, got {resp.status_code}"

    data = resp.json()
    files = data.get("files")
    assert isinstance(files, list), f"Expected files list, got: {data}"
    assert files, "Expected at least one resource file name"
    return files


async def get_known_resource_name(jadx_base_url, http_client, file_type: str) -> str:
    files = await get_resource_file_names(jadx_base_url, http_client)

    for hint in RESOURCE_HINTS_BY_TYPE[file_type]:
        for file_name in files:
            if hint in file_name:
                return file_name

    pytest.fail(f"Unable to find a known resource for fixture type {file_type}: {files}")


async def clear_cache_until_success(jadx_base_url, http_client, *, max_wait_seconds: float = 35.0) -> dict:
    deadline = time.monotonic() + max_wait_seconds
    last_data = None

    while True:
        resp = await http_client.post(f"{jadx_base_url}/cache/clear")
        assert resp.status_code == 200, f"Expected 200 from /cache/clear, got {resp.status_code}"

        data = resp.json()
        last_data = data
        if data.get("success") is True:
            return data

        remaining = data.get("cooldown_remaining_seconds")
        if remaining is None:
            pytest.fail(f"Expected cache clear success or cooldown metadata, got: {data}")

        now = time.monotonic()
        if now >= deadline:
            break

        try:
            sleep_for = float(remaining)
        except (TypeError, ValueError):
            sleep_for = 1.0

        sleep_for = max(0.5, min(sleep_for, deadline - now))
        await asyncio.sleep(sleep_for)

    pytest.fail(f"Cache clear stayed debounced until timeout: {last_data}")


class TestMainApplicationClassesCodeEndpoint:
    async def test_main_application_classes_code_returns_source_entries_for_apk_or_rejects_for_jar(
        self, jadx_base_url, http_client
    ):
        file_type = await detect_fixture_type(jadx_base_url, http_client)

        resp = await get_with_retry(
            http_client,
            f"{jadx_base_url}/main-application-classes-code",
            params={"count": 2},
        )
        data = resp.json()

        if file_type == "apk":
            assert resp.status_code == 200
            classes = data.get("classes")
            assert isinstance(classes, list), f"Expected classes list, got: {data}"
            assert classes, "Expected at least one main application class"

            for class_info in classes:
                assert isinstance(class_info, dict), f"Expected class object, got: {class_info!r}"
                assert isinstance(class_info.get("name"), str) and class_info["name"]
                assert isinstance(class_info.get("raw_name"), str) and class_info["raw_name"]
                assert isinstance(class_info.get("content"), str) and class_info["content"].strip()

            pagination = data.get("pagination")
            assert isinstance(pagination, dict), f"Expected pagination metadata, got: {data}"
            assert pagination.get("count") == len(classes)
        else:
            assert resp.status_code == 404, f"Expected Android-only endpoint to reject JAR, got: {data}"
            assert "AndroidManifest.xml" in data.get("error", "")

    async def test_main_application_classes_code_supports_offset_and_count_for_apk(self, jadx_base_url, http_client):
        file_type = await detect_fixture_type(jadx_base_url, http_client)
        if file_type != "apk":
            pytest.skip("main-application-classes-code pagination only applies to APK fixtures")

        first_resp = await get_with_retry(
            http_client,
            f"{jadx_base_url}/main-application-classes-code",
            params={"offset": 0, "count": 1},
        )
        assert first_resp.status_code == 200
        first_page = first_resp.json()

        second_resp = await get_with_retry(
            http_client,
            f"{jadx_base_url}/main-application-classes-code",
            params={"offset": 1, "count": 1},
        )
        assert second_resp.status_code == 200
        second_page = second_resp.json()

        first_classes = first_page.get("classes")
        second_classes = second_page.get("classes")
        assert isinstance(first_classes, list) and len(first_classes) == 1, f"Unexpected first page: {first_page}"
        assert isinstance(second_classes, list) and len(second_classes) == 1, f"Unexpected second page: {second_page}"

        assert first_page["pagination"]["offset"] == 0
        assert first_page["pagination"]["count"] == 1
        assert second_page["pagination"]["offset"] == 1
        assert second_page["pagination"]["count"] == 1
        assert first_classes[0]["name"] != second_classes[0]["name"], "Pagination should advance to a new class"


class TestPackageClassesEndpoint:
    async def test_package_classes_returns_known_package_classes(self, jadx_base_url, http_client):
        file_type = await detect_fixture_type(jadx_base_url, http_client)
        package_name = KNOWN_PACKAGE_BY_TYPE[file_type]

        resp = await http_client.get(
            f"{jadx_base_url}/package-classes",
            params={"package": package_name, "count": 20},
        )
        assert resp.status_code == 200

        data = resp.json()
        classes = data.get("classes")
        assert data.get("status") == "success", f"Expected success response, got: {data}"
        assert data.get("package") == package_name
        assert isinstance(classes, list), f"Expected classes list, got: {data}"
        assert classes, f"Expected package {package_name} to return classes"

        for class_info in classes:
            assert isinstance(class_info, dict), f"Expected class object, got: {class_info!r}"
            assert isinstance(class_info.get("name"), str) and class_info["name"].startswith(package_name)
            assert isinstance(class_info.get("is_inner"), bool)

    async def test_package_classes_missing_package_returns_empty_or_404(self, jadx_base_url, http_client):
        resp = await http_client.get(
            f"{jadx_base_url}/package-classes",
            params={"package": MISSING_PACKAGE, "count": 20},
        )
        assert resp.status_code in {200, 404}, f"Unexpected status from missing package: {resp.status_code}"

        data = resp.json()
        if resp.status_code == 200:
            classes = data.get("classes")
            assert isinstance(classes, list), f"Expected classes list, got: {data}"
            assert classes == [], f"Expected empty result for missing package, got: {classes}"
            assert data.get("total_matched") == 0
        else:
            assert "error" in data


class TestResourceEndpoints:
    async def test_list_all_resource_files_names_returns_fixture_specific_entries(
        self, jadx_base_url, http_client
    ):
        file_type = await detect_fixture_type(jadx_base_url, http_client)
        files = await get_resource_file_names(jadx_base_url, http_client)

        if file_type == "apk":
            assert any("AndroidManifest.xml" in file_name for file_name in files), (
                f"Expected AndroidManifest.xml in APK resources, got: {files}"
            )
        else:
            assert any("META-INF" in file_name or "MANIFEST.MF" in file_name for file_name in files), (
                f"Expected META-INF resource in JAR resources, got: {files}"
            )

    async def test_get_resource_file_returns_content_for_known_resource(self, jadx_base_url, http_client):
        file_type = await detect_fixture_type(jadx_base_url, http_client)
        resource_name = await get_known_resource_name(jadx_base_url, http_client, file_type)

        resp = await get_with_retry(
            http_client,
            f"{jadx_base_url}/get-resource-file",
            params={"file_name": resource_name},
        )
        assert resp.status_code == 200

        data = resp.json()
        content = data.get("content")
        assert data.get("status") == "success", f"Expected success response, got: {data}"
        assert isinstance(content, str) and content.strip(), f"Expected non-empty content, got: {data}"
        assert data.get("file_name") == resource_name

    async def test_get_resource_file_missing_resource_returns_404_or_error(self, jadx_base_url, http_client):
        resp = await http_client.get(
            f"{jadx_base_url}/get-resource-file",
            params={"file_name": MISSING_RESOURCE},
        )
        assert resp.status_code in {200, 404}, f"Unexpected status for missing resource: {resp.status_code}"

        data = resp.json()
        if resp.status_code == 200:
            assert data.get("status") != "success", f"Expected error-like response, got: {data}"
            assert "error" in data
        else:
            assert "error" in data

    async def test_config_strings_returns_successful_fixture_specific_shape(self, jadx_base_url, http_client):
        file_type = await detect_fixture_type(jadx_base_url, http_client)

        resp = await http_client.get(f"{jadx_base_url}/config-strings")
        assert resp.status_code == 200

        data = resp.json()
        assert data.get("status") == "success", f"Expected success response, got: {data}"
        assert data.get("type") == "config-strings"

        if file_type == "apk":
            assert data.get("source_type") == "android_strings"
            assert isinstance(data.get("available"), bool), f"Expected availability flag, got: {data}"
            if data.get("available"):
                assert data.get("recommended_tool") == "get_strings"
        else:
            assert data.get("source_type") == "java_properties"
            assert isinstance(data.get("files"), list), f"Expected files list, got: {data}"
            assert isinstance(data.get("total_files"), int), f"Expected total_files int, got: {data}"


class TestJarOnlyEndpoints:
    async def test_jar_dependencies_returns_success_for_jar_or_not_applicable_for_apk(
        self, jadx_base_url, http_client
    ):
        file_type = await detect_fixture_type(jadx_base_url, http_client)

        resp = await http_client.get(f"{jadx_base_url}/jar-dependencies")
        assert resp.status_code in {200, 404}, f"Unexpected status from /jar-dependencies: {resp.status_code}"

        data = resp.json()
        if file_type == "jar":
            assert resp.status_code == 200
            assert data.get("status") == "success", f"Expected success response, got: {data}"
            assert isinstance(data.get("dependencies"), list), f"Expected dependencies list, got: {data}"
            assert isinstance(data.get("total_dependencies"), int), f"Expected total_dependencies int, got: {data}"
            assert str(data.get("file_name", "")).endswith(".jar")
        else:
            if resp.status_code == 200:
                assert data.get("status") == "NOT_APPLICABLE" or "only for JAR files" in str(data)
            else:
                assert "error" in data

    async def test_jar_bytecode_returns_structured_bytecode_for_jar(self, jadx_base_url, http_client):
        file_type = await detect_fixture_type(jadx_base_url, http_client)
        if file_type != "jar":
            pytest.skip("jar-bytecode coverage is JAR-only for the integration fixture matrix")

        class_name = KNOWN_CLASS_BY_TYPE["jar"]
        resp = await http_client.get(
            f"{jadx_base_url}/jar-bytecode",
            params={"class_name": class_name},
        )
        assert resp.status_code == 200

        data = resp.json()
        bytecode = data.get("bytecode")
        assert data.get("status") == "success", f"Expected success response, got: {data}"
        assert data.get("class_name") == class_name
        assert isinstance(data.get("raw_class_name"), str) and data["raw_class_name"]
        assert data.get("file_type") == "jar"
        assert isinstance(bytecode, str) and bytecode.strip(), f"Expected non-empty bytecode, got: {data}"
        assert "// Class: com.jadxtest.library.Calculator" in bytecode


class TestCacheClearEndpoint:
    async def test_cache_clear_returns_success_and_subsequent_queries_still_work(self, jadx_base_url, http_client):
        file_type = await detect_fixture_type(jadx_base_url, http_client)
        clear_data = await clear_cache_until_success(jadx_base_url, http_client)

        assert clear_data.get("success") is True, f"Expected cache clear success, got: {clear_data}"
        assert "cleared" in clear_data.get("message", "").lower()

        class_name = KNOWN_CLASS_BY_TYPE[file_type]
        resp = await get_with_retry(
            http_client,
            f"{jadx_base_url}/class-source",
            params={"class_name": class_name},
            retryable_statuses=(503,),
        )
        assert resp.status_code == 200

        data = resp.json()
        source = data.get("response", data.get("content", ""))
        assert isinstance(source, str) and source.strip(), f"Expected non-empty source, got: {data}"
        assert class_name.rsplit(".", 1)[-1] in source
