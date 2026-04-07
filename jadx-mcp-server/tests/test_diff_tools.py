"""Tests for diff_tools module — cross-version comparison logic."""

import pytest

from server.tools import diff_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_jadx(
    old_classes: list[str],
    new_classes: list[str],
    old_methods: dict[str, list[str]] | None = None,
    new_methods: dict[str, list[str]] | None = None,
    old_file_info: dict | None = None,
    new_file_info: dict | None = None,
):
    """Build a fake get_from_jadx that dispatches by instance_id and endpoint."""
    old_methods = old_methods or {}
    new_methods = new_methods or {}
    old_file_info = old_file_info or {"file_name": "old.apk", "file_type": "apk"}
    new_file_info = new_file_info or {"file_name": "new.apk", "file_type": "apk"}

    async def fake(endpoint, params=None, instance_id=None, **kwargs):
        is_old = instance_id == "old"

        if endpoint == "file-info":
            return old_file_info if is_old else new_file_info

        if endpoint == "all-classes":
            classes = old_classes if is_old else new_classes
            pkg = (params or {}).get("package", "")
            if pkg:
                classes = [c for c in classes if c.startswith(pkg)]
            return {"classes": classes, "total": len(classes)}

        if endpoint == "methods-of-class":
            cls = (params or {}).get("class_name", "")
            methods_map = old_methods if is_old else new_methods
            return {"methods": methods_map.get(cls, []), "count": len(methods_map.get(cls, []))}

        if endpoint == "batch-method-by-name":
            return {"code": "// stub"}

        return {}

    return fake


# ---------------------------------------------------------------------------
# Class-level diff tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_added_and_removed_classes(monkeypatch):
    """Classes only in new should be 'added'; only in old should be 'removed'."""
    fake = _make_fake_jadx(
        old_classes=["com.A", "com.B", "com.C"],
        new_classes=["com.B", "com.C", "com.D"],
    )
    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new")

    assert result["summary"]["classes_added"] == 1
    assert result["summary"]["classes_removed"] == 1
    assert "com.D" in result["added_classes"]
    assert "com.A" in result["removed_classes"]


@pytest.mark.asyncio
async def test_all_classes_same(monkeypatch):
    """When both versions have identical classes and methods, nothing is modified."""
    fake = _make_fake_jadx(
        old_classes=["com.X"],
        new_classes=["com.X"],
        old_methods={"com.X": ["foo", "bar"]},
        new_methods={"com.X": ["foo", "bar"]},
    )
    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new")

    assert result["summary"]["classes_added"] == 0
    assert result["summary"]["classes_removed"] == 0
    assert result["summary"]["classes_modified"] == 0
    assert result["summary"]["classes_unchanged"] == 1


@pytest.mark.asyncio
async def test_no_common_classes(monkeypatch):
    """Disjoint class sets: everything is added or removed, nothing modified."""
    fake = _make_fake_jadx(
        old_classes=["com.Old1", "com.Old2"],
        new_classes=["com.New1"],
    )
    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new")

    assert result["summary"]["classes_added"] == 1
    assert result["summary"]["classes_removed"] == 2
    assert result["summary"]["classes_modified"] == 0
    assert result["modified_classes"] == []


# ---------------------------------------------------------------------------
# Method-level diff tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_method_added_and_removed(monkeypatch):
    """Detect added/removed methods in a common class."""
    fake = _make_fake_jadx(
        old_classes=["com.Foo"],
        new_classes=["com.Foo"],
        old_methods={"com.Foo": ["alpha", "beta"]},
        new_methods={"com.Foo": ["beta", "gamma"]},
    )
    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new")

    assert result["summary"]["classes_modified"] == 1
    assert result["summary"]["methods_added"] == 1
    assert result["summary"]["methods_removed"] == 1
    mod = result["modified_classes"][0]
    assert mod["class_name"] == "com.Foo"
    assert "gamma" in mod["added_methods"]
    assert "alpha" in mod["removed_methods"]


@pytest.mark.asyncio
async def test_multiple_modified_classes(monkeypatch):
    """Multiple common classes each with method changes."""
    fake = _make_fake_jadx(
        old_classes=["com.A", "com.B"],
        new_classes=["com.A", "com.B"],
        old_methods={"com.A": ["m1"], "com.B": ["m2"]},
        new_methods={"com.A": ["m1", "m3"], "com.B": ["m4"]},
    )
    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new")

    # com.A: m3 added; com.B: m2 removed, m4 added
    assert result["summary"]["classes_modified"] == 2
    assert result["summary"]["methods_added"] == 2   # m3 + m4
    assert result["summary"]["methods_removed"] == 1  # m2


# ---------------------------------------------------------------------------
# Package filter test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_package_filter(monkeypatch):
    """Package filter should restrict comparison to matching classes."""
    fake = _make_fake_jadx(
        old_classes=["com.app.A", "com.lib.X"],
        new_classes=["com.app.A", "com.app.B", "com.lib.X"],
    )
    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new", package="com.app")

    # Only com.app.* should appear
    assert result["summary"]["classes_added"] == 1
    assert "com.app.B" in result["added_classes"]
    assert result["summary"]["classes_removed"] == 0
    assert result["package_filter"] == "com.app"


# ---------------------------------------------------------------------------
# Instance unreachable tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_old_instance_unreachable(monkeypatch):
    """Error when old instance is unreachable."""
    async def fake(endpoint, params=None, instance_id=None, **kwargs):
        if instance_id == "old" and endpoint == "file-info":
            raise ConnectionError("refused")
        return {"file_name": "new.apk"}

    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new")
    assert result["error"] == "OLD_INSTANCE_UNREACHABLE"


@pytest.mark.asyncio
async def test_new_instance_unreachable(monkeypatch):
    """Error when new instance is unreachable."""
    async def fake(endpoint, params=None, instance_id=None, **kwargs):
        if instance_id == "new" and endpoint == "file-info":
            raise ConnectionError("refused")
        return {"file_name": "old.apk"}

    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new")
    assert result["error"] == "NEW_INSTANCE_UNREACHABLE"


# ---------------------------------------------------------------------------
# Truncation warning test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_truncation_tip_when_classes_exceed_limit(monkeypatch):
    """Analysis tips should warn when class count exceeds fetch limit."""
    async def fake(endpoint, params=None, instance_id=None, **kwargs):
        if endpoint == "file-info":
            return {"file_name": "app.apk"}
        if endpoint == "all-classes":
            # Return fewer classes but claim total exceeds limit
            return {"classes": ["com.A"], "total": 9999}
        return {"methods": [], "count": 0}

    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new")

    tips = result.get("analysis_tips", [])
    assert any("package" in t.lower() for t in tips)


# ---------------------------------------------------------------------------
# No-package-filter tip test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_package_filter_tip(monkeypatch):
    """When no package filter is set, tips should suggest using one."""
    fake = _make_fake_jadx(old_classes=[], new_classes=[])
    monkeypatch.setattr(diff_tools, "get_from_jadx", fake)

    result = await diff_tools.compare_versions("old", "new", package="")
    tips = result.get("analysis_tips", [])
    assert any("package" in t.lower() and "filter" in t.lower() for t in tips)
