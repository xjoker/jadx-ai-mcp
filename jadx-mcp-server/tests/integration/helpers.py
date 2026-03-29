from __future__ import annotations

import httpx
import pytest


SUPPORTED_FIXTURE_TYPES = {"jar", "apk"}
PREFERRED_CLASSES = {
    "jar": [
        "com.jadxtest.library.Calculator",
        "com.jadxtest.library.StringUtils",
        "com.jadxtest.library.FileProcessor",
        "com.jadxtest.library.network.HttpClient",
        "com.jadxtest.library.model.User",
    ],
    "apk": [
        "com.jadxtest.app.MainActivity",
        "com.jadxtest.app.ApiManager",
        "com.jadxtest.app.DatabaseHelper",
        "com.jadxtest.app.JadxTestApplication",
    ],
}
PREFERRED_METHODS = {
    "jar": ["add", "subtract"],
    "apk": ["onCreate", "onResume", "onStart", "updateStatus"],
}
FALLBACK_PREFIXES = {
    "jar": ("com.jadxtest.library",),
    "apk": ("com.jadxtest.app",),
}


def normalize_class_entry(entry: dict | str) -> dict[str, str]:
    if isinstance(entry, str):
        return {"name": entry, "raw_name": entry}

    if isinstance(entry, dict):
        name = entry.get("name") or entry.get("class_name") or entry.get("raw_name")
        raw_name = entry.get("raw_name") or name
        if isinstance(name, str) and name and isinstance(raw_name, str) and raw_name:
            return {"name": name, "raw_name": raw_name}

    raise AssertionError(f"Unsupported class entry shape: {entry!r}")


async def get_file_info(jadx_base_url: str, http_client: httpx.AsyncClient) -> dict:
    resp = await http_client.get(f"{jadx_base_url}/file-info")
    assert resp.status_code == 200, f"Expected 200 from /file-info, got {resp.status_code}"

    data = resp.json()
    assert data.get("loaded") is True, f"Fixture should be loaded: {data}"
    return data


async def detect_fixture_type(jadx_base_url: str, http_client: httpx.AsyncClient) -> str:
    data = await get_file_info(jadx_base_url, http_client)
    file_type = data.get("file_type")
    assert file_type in SUPPORTED_FIXTURE_TYPES, f"Unsupported integration fixture type: {file_type}"
    return file_type


async def get_all_class_entries(jadx_base_url: str, http_client: httpx.AsyncClient) -> list[dict[str, str]]:
    resp = await http_client.get(f"{jadx_base_url}/all-classes", params={"count": 200})
    assert resp.status_code == 200, f"Expected 200 from /all-classes, got {resp.status_code}"

    data = resp.json()
    classes = data.get("classes")
    assert isinstance(classes, list), "Expected /all-classes to return a classes list"
    assert classes, "Expected at least one class in loaded fixture"
    return [normalize_class_entry(entry) for entry in classes]


def _preferred_candidates(file_type: str, class_entries: list[dict[str, str]]) -> list[str]:
    available = [entry["name"] for entry in class_entries]
    preferred = [name for name in PREFERRED_CLASSES[file_type] if name in available]

    fallbacks = [
        name
        for name in available
        if name not in preferred and name.startswith(FALLBACK_PREFIXES[file_type])
    ]
    remaining = [name for name in available if name not in preferred and name not in fallbacks]
    return preferred + fallbacks + remaining


def _select_method(methods: list[dict], file_type: str) -> dict:
    non_constructors = [
        method
        for method in methods
        if isinstance(method, dict) and isinstance(method.get("name"), str) and not method.get("is_constructor")
    ]
    assert non_constructors, "Expected target class to expose at least one non-constructor method"

    for preferred_name in PREFERRED_METHODS[file_type]:
        for method in non_constructors:
            if method.get("name") == preferred_name:
                return method
    return non_constructors[0]


async def resolve_fixture_context(jadx_base_url: str, http_client: httpx.AsyncClient) -> dict:
    file_info = await get_file_info(jadx_base_url, http_client)
    file_type = file_info["file_type"]
    assert file_type in SUPPORTED_FIXTURE_TYPES, f"Unsupported integration fixture type: {file_type}"
    class_entries = await get_all_class_entries(jadx_base_url, http_client)
    candidates = _preferred_candidates(file_type, class_entries)

    fallback_context = None
    for class_name in candidates:
        methods_resp = await http_client.get(
            f"{jadx_base_url}/methods-of-class",
            params={"class_name": class_name},
        )
        if methods_resp.status_code != 200:
            continue

        methods_data = methods_resp.json()
        methods = methods_data.get("methods")
        if not isinstance(methods, list):
            continue

        try:
            selected_method = _select_method(methods, file_type)
        except AssertionError:
            continue

        fields_resp = await http_client.get(
            f"{jadx_base_url}/fields-of-class",
            params={"class_name": class_name},
        )
        fields = []
        if fields_resp.status_code == 200:
            fields_data = fields_resp.json()
            raw_fields = fields_data.get("fields")
            if isinstance(raw_fields, list):
                fields = raw_fields

        context = {
            "file_info": file_info,
            "file_type": file_type,
            "class_entries": class_entries,
            "class_names": [entry["name"] for entry in class_entries],
            "raw_class_names": [entry["raw_name"] for entry in class_entries],
            "class_name": class_name,
            "package_name": class_name.rsplit(".", 1)[0] if "." in class_name else "",
            "methods": methods,
            "method_name": selected_method["name"],
            "raw_method_name": selected_method.get("raw_name") or selected_method["name"],
            "fields": fields,
        }

        if fields:
            fallback_context = context
            break
        if fallback_context is None:
            fallback_context = context

    if fallback_context is None:
        pytest.fail(f"Unable to resolve a usable target class for fixture type {file_type}")

    batch_class_names = [fallback_context["class_name"]]
    for class_name in candidates:
        if class_name != fallback_context["class_name"]:
            batch_class_names.append(class_name)
        if len(batch_class_names) == 2:
            break

    fallback_context["batch_class_names"] = batch_class_names
    fallback_context["secondary_class_name"] = (
        batch_class_names[1] if len(batch_class_names) > 1 else batch_class_names[0]
    )
    return fallback_context
