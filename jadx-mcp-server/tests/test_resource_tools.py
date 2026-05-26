"""
Tests for resource_tools.py HTTP request behavior.

Verifies that each resource tool calls the correct JADX endpoint,
passes the expected query parameters, and propagates instance_id.
Tools that use PaginationUtils are tested by monkeypatching get_from_jadx
(the lambda-captured reference inside the module).

All HTTP calls are replaced by an in-process fake; no running JADX
server is required.
"""

import pytest

from server.tools import resource_tools


def _make_fake(captured: dict, response: dict = None):
    """Return a fake get_from_jadx that records the last call."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            method=method,
        )
        return response if response is not None else {}
    return fake


# ---------------------------------------------------------------------------
# get_strings
# ---------------------------------------------------------------------------

class TestGetStrings:

    @pytest.mark.asyncio
    async def test_calls_strings_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_strings()
        assert captured["endpoint"] == "strings"

    @pytest.mark.asyncio
    async def test_mode_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_strings(mode="list")
        assert captured["params"]["mode"] == "list"

    @pytest.mark.asyncio
    async def test_optional_query_added_when_provided(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_strings(mode="search", query="auth")
        assert captured["params"]["query"] == "auth"

    @pytest.mark.asyncio
    async def test_query_absent_when_not_provided(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_strings(mode="summary")
        assert "query" not in captured["params"]

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_strings(instance_id="inst-r1")
        assert captured["instance_id"] == "inst-r1"


# ---------------------------------------------------------------------------
# get_config_strings
# ---------------------------------------------------------------------------

class TestGetConfigStrings:

    @pytest.mark.asyncio
    async def test_calls_config_strings_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_config_strings()
        assert captured["endpoint"] == "config-strings"

    @pytest.mark.asyncio
    async def test_mode_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_config_strings(mode="search", query="db.url")
        assert captured["params"]["mode"] == "search"
        assert captured["params"]["query"] == "db.url"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_config_strings(instance_id="inst-r2")
        assert captured["instance_id"] == "inst-r2"


# ---------------------------------------------------------------------------
# get_all_resource_file_names  (uses PaginationUtils)
# ---------------------------------------------------------------------------

class TestGetAllResourceFileNames:

    @pytest.mark.asyncio
    async def test_calls_list_resource_files_endpoint(self, monkeypatch):
        captured = {}

        async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
            captured.update(endpoint=endpoint, params=params, instance_id=instance_id)
            return {"files": [], "pagination": {}}

        monkeypatch.setattr(resource_tools, "get_from_jadx", fake)
        await resource_tools.get_all_resource_file_names()
        assert captured["endpoint"] == "list-all-resource-files-names"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}

        async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
            captured.update(instance_id=instance_id)
            return {"files": [], "pagination": {}}

        monkeypatch.setattr(resource_tools, "get_from_jadx", fake)
        await resource_tools.get_all_resource_file_names(instance_id="inst-r3")
        assert captured["instance_id"] == "inst-r3"


# ---------------------------------------------------------------------------
# get_resource_file
# ---------------------------------------------------------------------------

class TestGetResourceFile:

    @pytest.mark.asyncio
    async def test_calls_get_resource_file_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_resource_file("res/layout/activity_main.xml")
        assert captured["endpoint"] == "get-resource-file"

    @pytest.mark.asyncio
    async def test_file_name_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_resource_file("res/raw/config.json")
        assert captured["params"]["file_name"] == "res/raw/config.json"

    @pytest.mark.asyncio
    async def test_chunk_zero_not_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_resource_file("res/layout/activity_main.xml", chunk=0)
        assert "chunk" not in captured["params"]

    @pytest.mark.asyncio
    async def test_nonzero_chunk_included(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_resource_file("res/raw/big.xml", chunk=2)
        assert captured["params"]["chunk"] == "2"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_resource_file("res/layout/main.xml", instance_id="inst-r4")
        assert captured["instance_id"] == "inst-r4"


# ---------------------------------------------------------------------------
# get_file_info
# ---------------------------------------------------------------------------

class TestGetFileInfo:

    @pytest.mark.asyncio
    async def test_calls_file_info_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_file_info()
        assert captured["endpoint"] == "file-info"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_file_info(instance_id="inst-r5")
        assert captured["instance_id"] == "inst-r5"


# ---------------------------------------------------------------------------
# get_package_classes  (uses get_from_jadx via conditional params)
# ---------------------------------------------------------------------------

class TestGetPackageClasses:

    @pytest.mark.asyncio
    async def test_calls_package_classes_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_package_classes(package="com.example")
        assert captured["endpoint"] == "package-classes"

    @pytest.mark.asyncio
    async def test_package_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_package_classes(package="com.example.app")
        assert captured["params"]["package"] == "com.example.app"

    @pytest.mark.asyncio
    async def test_auto_flag_in_params(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_package_classes(auto=True)
        assert captured["params"]["auto"] == "true"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.get_package_classes(package="com.example", instance_id="inst-r6")
        assert captured["instance_id"] == "inst-r6"


# ---------------------------------------------------------------------------
# jar_get_manifest
# ---------------------------------------------------------------------------

class TestJarGetManifest:

    @pytest.mark.asyncio
    async def test_calls_jar_manifest_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.jar_get_manifest()
        assert captured["endpoint"] == "jar-manifest"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.jar_get_manifest(instance_id="jar-inst")
        assert captured["instance_id"] == "jar-inst"


# ---------------------------------------------------------------------------
# jar_get_dependencies
# ---------------------------------------------------------------------------

class TestJarGetDependencies:

    @pytest.mark.asyncio
    async def test_calls_jar_dependencies_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.jar_get_dependencies()
        assert captured["endpoint"] == "jar-dependencies"

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(resource_tools, "get_from_jadx", _make_fake(captured))
        await resource_tools.jar_get_dependencies(instance_id="jar-dep-inst")
        assert captured["instance_id"] == "jar-dep-inst"
