"""Extended tests for refactor_tools — covers rename_method, rename_field,
rename_variable, rename_package, export_rename_mappings, import_rename_mappings,
and apply_proguard_mapping."""

import pytest

from server.tools import refactor_tools


def _make_fake(captured: dict, response: dict = None):
    """Create a fake get_from_jadx that records the last call."""
    async def fake(endpoint, params=None, instance_id=None, timeout=None, method="GET", json_body=None):
        captured.update(
            endpoint=endpoint,
            params=params,
            instance_id=instance_id,
            timeout=timeout,
            method=method,
            json_body=json_body,
        )
        return response if response is not None else {"success": True}
    return fake


# ---------------------------------------------------------------------------
# rename_method
# ---------------------------------------------------------------------------

class TestRenameMethod:

    @pytest.mark.asyncio
    async def test_uses_post_with_required_fields(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        result = await refactor_tools.rename_method(
            "com.example.Parser", "parse", "parseDocument", instance_id="demo"
        )

        assert result == {"success": True}
        assert captured["endpoint"] == "rename-method"
        assert captured["method"] == "POST"
        assert captured["json_body"]["class_name"] == "com.example.Parser"
        assert captured["json_body"]["method_name"] == "parse"
        assert captured["json_body"]["new_name"] == "parseDocument"
        assert captured["instance_id"] == "demo"

    @pytest.mark.asyncio
    async def test_optional_method_signature_included_when_provided(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        await refactor_tools.rename_method(
            "com.example.Parser", "parse", "parseDocument",
            method_signature="parse(Ljava/lang/String;)V",
        )

        assert captured["json_body"]["method_signature"] == "parse(Ljava/lang/String;)V"

    @pytest.mark.asyncio
    async def test_method_signature_omitted_when_not_provided(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        await refactor_tools.rename_method("com.example.A", "foo", "bar")

        assert "method_signature" not in captured["json_body"]


# ---------------------------------------------------------------------------
# rename_field
# ---------------------------------------------------------------------------

class TestRenameField:

    @pytest.mark.asyncio
    async def test_uses_post_and_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        result = await refactor_tools.rename_field(
            "com.example.Config", "mTag", "tag", instance_id="inst1"
        )

        assert result == {"success": True}
        assert captured["endpoint"] == "rename-field"
        assert captured["method"] == "POST"
        assert captured["instance_id"] == "inst1"

    @pytest.mark.asyncio
    async def test_json_body_uses_new_field_name_key(self, monkeypatch):
        """Server expects 'new_field_name', not 'new_name'."""
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        await refactor_tools.rename_field("com.example.Config", "mTag", "tag")

        assert captured["json_body"] == {
            "class_name": "com.example.Config",
            "field_name": "mTag",
            "new_field_name": "tag",
        }


# ---------------------------------------------------------------------------
# rename_variable
# ---------------------------------------------------------------------------

class TestRenameVariable:

    @pytest.mark.asyncio
    async def test_uses_post_with_required_fields(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        result = await refactor_tools.rename_variable(
            "com.example.Auth", "verify", "p0", "inputToken", instance_id="inst2"
        )

        assert result == {"success": True}
        assert captured["endpoint"] == "rename-variable"
        assert captured["method"] == "POST"
        assert captured["json_body"]["class_name"] == "com.example.Auth"
        assert captured["json_body"]["method_name"] == "verify"
        assert captured["json_body"]["variable_name"] == "p0"
        assert captured["json_body"]["new_name"] == "inputToken"

    @pytest.mark.asyncio
    async def test_optional_reg_and_ssa_included_when_provided(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        await refactor_tools.rename_variable(
            "com.example.Auth", "verify", "p0", "inputToken", reg="3", ssa="1"
        )

        assert captured["json_body"]["reg"] == "3"
        assert captured["json_body"]["ssa"] == "1"

    @pytest.mark.asyncio
    async def test_optional_fields_absent_when_not_provided(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        await refactor_tools.rename_variable("com.example.A", "m", "v", "value")

        assert "reg" not in captured["json_body"]
        assert "ssa" not in captured["json_body"]


# ---------------------------------------------------------------------------
# rename_package
# ---------------------------------------------------------------------------

class TestRenamePackage:

    @pytest.mark.asyncio
    async def test_uses_post_and_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        result = await refactor_tools.rename_package(
            "com.example.old", "com.example.new", instance_id="inst3"
        )

        assert result == {"success": True}
        assert captured["endpoint"] == "rename-package"
        assert captured["method"] == "POST"
        assert captured["instance_id"] == "inst3"

    @pytest.mark.asyncio
    async def test_json_body_contains_package_names(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        await refactor_tools.rename_package("com.old.pkg", "com.new.pkg")

        assert captured["json_body"] == {
            "old_package_name": "com.old.pkg",
            "new_package_name": "com.new.pkg",
        }


# ---------------------------------------------------------------------------
# export_rename_mappings
# ---------------------------------------------------------------------------

class TestExportRenameMappings:

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint_with_get(self, monkeypatch):
        captured = {}
        fake_response = {"mappings": [], "total": 0}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured, fake_response))

        result = await refactor_tools.export_rename_mappings(instance_id="inst4")

        assert result == fake_response
        assert captured["endpoint"] == "export-rename-mappings"
        assert captured["method"] == "GET"
        assert captured["instance_id"] == "inst4"

    @pytest.mark.asyncio
    async def test_no_body_sent(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        await refactor_tools.export_rename_mappings()

        assert captured["json_body"] is None
        assert captured["params"] is None


# ---------------------------------------------------------------------------
# import_rename_mappings
# ---------------------------------------------------------------------------

class TestImportRenameMappings:

    @pytest.mark.asyncio
    async def test_uses_post_with_mappings_list(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        mappings = [
            {"type": "class", "original_name": "a.b.c", "new_name": "com.real.Name", "class_context": ""}
        ]
        result = await refactor_tools.import_rename_mappings(mappings, instance_id="inst5")

        assert result == {"success": True}
        assert captured["endpoint"] == "import-rename-mappings"
        assert captured["method"] == "POST"
        assert captured["json_body"] == {"mappings": mappings}
        assert captured["instance_id"] == "inst5"

    @pytest.mark.asyncio
    async def test_empty_mappings_list_allowed(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        await refactor_tools.import_rename_mappings([])

        assert captured["json_body"] == {"mappings": []}


# ---------------------------------------------------------------------------
# apply_proguard_mapping (module-level function, not the MCP tool wrapper)
# ---------------------------------------------------------------------------

class TestApplyProguardMapping:

    @pytest.mark.asyncio
    async def test_uses_post_and_correct_endpoint(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        mapping_txt = "com.real.Name -> a.b.c:\n    void realMethod() -> d"
        result = await refactor_tools.apply_proguard_mapping(mapping_txt, instance_id="inst6")

        assert result == {"success": True}
        assert captured["endpoint"] == "apply-proguard-mapping"
        assert captured["method"] == "POST"
        assert captured["json_body"] == {"mapping_content": mapping_txt}
        assert captured["instance_id"] == "inst6"

    @pytest.mark.asyncio
    async def test_mapping_content_sent_verbatim(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(refactor_tools, "get_from_jadx", _make_fake(captured))

        content = "com.example.Real -> a:\n    int field -> b\n    void method() -> c"
        await refactor_tools.apply_proguard_mapping(content)

        assert captured["json_body"]["mapping_content"] == content
