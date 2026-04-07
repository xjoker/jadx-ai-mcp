"""Tests for digest_tools module."""

import pytest

from server.tools import digest_tools
from server.tools.digest_tools import (
    assess_obfuscation,
    detect_sdks,
    generate_analysis_tips,
    parse_manifest_components,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_get_from_jadx(responses: dict):
    """Create a fake get_from_jadx that returns canned responses by endpoint."""
    async def fake(endpoint, params=None, instance_id=None, **kwargs):
        if endpoint in responses:
            val = responses[endpoint]
            return val(params) if callable(val) else val
        return {"error": "NOT_FOUND"}
    return fake


SAMPLE_MANIFEST = """\
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.myapp"
    android:versionName="1.2.3">
    <uses-sdk android:minSdkVersion="21" android:targetSdkVersion="33"/>
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <application>
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        <activity android:name=".SettingsActivity" android:exported="false"/>
        <service android:name=".SyncService"/>
        <receiver android:name=".BootReceiver" android:exported="true"/>
        <provider android:name=".DataProvider" android:exported="false"/>
    </application>
</manifest>
"""


# ---------------------------------------------------------------------------
# SDK detection tests
# ---------------------------------------------------------------------------

class TestDetectSdks:

    def test_detects_multiple_sdks(self):
        class_names = [
            "com.google.firebase.FirebaseApp",
            "com.google.firebase.auth.Auth",
            "com.squareup.okhttp.OkHttpClient",
            "com.example.app.MainActivity",
        ]
        result = detect_sdks(class_names)
        sdk_names = {s["name"] for s in result}
        assert "Firebase" in sdk_names
        assert "OkHttp" in sdk_names

    def test_counts_classes_correctly(self):
        class_names = [
            "com.facebook.sdk.Module1",
            "com.facebook.sdk.Module2",
            "com.facebook.sdk.Module3",
        ]
        result = detect_sdks(class_names)
        fb = next(s for s in result if s["name"] == "Facebook SDK")
        assert fb["class_count"] == 3

    def test_no_sdks_returns_empty(self):
        class_names = ["com.example.app.Main", "com.example.app.Utils"]
        result = detect_sdks(class_names)
        assert result == []

    def test_empty_input_returns_empty(self):
        assert detect_sdks([]) == []

    def test_sorted_by_count_descending(self):
        class_names = [
            "com.facebook.A",
            "com.google.X",
            "com.google.Y",
            "com.google.Z",
        ]
        result = detect_sdks(class_names)
        assert result[0]["name"] == "Google SDK"
        assert result[0]["class_count"] == 3

    def test_class_counted_only_once(self):
        # com.google.firebase matches both "Google SDK" and "Firebase" prefixes
        # but should only be counted under the first matching prefix
        class_names = ["com.google.firebase.App"]
        result = detect_sdks(class_names)
        total = sum(s["class_count"] for s in result)
        assert total == 1


# ---------------------------------------------------------------------------
# Obfuscation assessment tests
# ---------------------------------------------------------------------------

class TestAssessObfuscation:

    def test_high_obfuscation(self):
        # >50% short names
        class_names = ["a.b.c", "a.b.d", "a.b.e", "com.example.RealClass"]
        level, details = assess_obfuscation(class_names)
        assert level == "high"
        assert details["short_name_ratio"] >= 0.5

    def test_medium_obfuscation(self):
        # 20-50% short names
        class_names = [
            "a.b.A",
            "com.example.ClassOne",
            "com.example.ClassTwo",
            "com.example.ClassThree",
            "com.example.ClassFour",
        ]
        level, _ = assess_obfuscation(class_names)
        assert level == "medium" or level == "low"

    def test_no_obfuscation(self):
        class_names = [
            "com.example.MainActivity",
            "com.example.SettingsActivity",
            "com.example.Utils",
        ]
        level, details = assess_obfuscation(class_names)
        assert level == "none"
        assert details["short_name_ratio"] == 0.0

    def test_empty_input(self):
        level, details = assess_obfuscation([])
        assert level == "none"
        assert details["short_name_ratio"] == 0.0

    def test_single_char_packages_counted(self):
        class_names = ["a.b.ClassName", "c.d.OtherClass"]
        _, details = assess_obfuscation(class_names)
        assert details["single_char_packages"] >= 2


# ---------------------------------------------------------------------------
# Manifest parsing tests
# ---------------------------------------------------------------------------

class TestParseManifestComponents:

    def test_parses_package_name(self):
        result = parse_manifest_components(SAMPLE_MANIFEST)
        assert result["package_name"] == "com.example.myapp"

    def test_parses_version(self):
        result = parse_manifest_components(SAMPLE_MANIFEST)
        assert result["version"] == "1.2.3"

    def test_parses_sdk_versions(self):
        result = parse_manifest_components(SAMPLE_MANIFEST)
        assert result["sdk_info"]["min_sdk"] == 21
        assert result["sdk_info"]["target_sdk"] == 33

    def test_parses_permissions(self):
        result = parse_manifest_components(SAMPLE_MANIFEST)
        assert "android.permission.INTERNET" in result["permissions"]
        assert "android.permission.CAMERA" in result["permissions"]

    def test_parses_activities(self):
        result = parse_manifest_components(SAMPLE_MANIFEST)
        assert ".MainActivity" in result["components"]["activities"]
        assert ".SettingsActivity" in result["components"]["activities"]

    def test_parses_services(self):
        result = parse_manifest_components(SAMPLE_MANIFEST)
        assert ".SyncService" in result["components"]["services"]

    def test_parses_exported_components(self):
        result = parse_manifest_components(SAMPLE_MANIFEST)
        exported = result["components"]["exported_components"]
        assert ".MainActivity" in exported
        assert ".BootReceiver" in exported

    def test_detects_launcher_activity(self):
        result = parse_manifest_components(SAMPLE_MANIFEST)
        assert result["entry_points"]["main_activity"] == ".MainActivity"
        assert ".MainActivity" in result["entry_points"]["launcher_activities"]

    def test_empty_manifest(self):
        result = parse_manifest_components("")
        assert result["package_name"] == ""
        assert result["permissions"] == []


# ---------------------------------------------------------------------------
# Analysis tips tests
# ---------------------------------------------------------------------------

class TestGenerateAnalysisTips:

    def test_tip_when_sampling_limited(self):
        tips = generate_analysis_tips("apk", 500, "none", [], 200)
        assert any("sampled" in t.lower() or "200" in t for t in tips)

    def test_tip_for_obfuscated(self):
        tips = generate_analysis_tips("apk", 100, "high", [], 100)
        assert any("obfuscation" in t.lower() for t in tips)

    def test_tip_for_large_apk(self):
        tips = generate_analysis_tips("apk", 60000, "none", [], 200)
        assert any("large" in t.lower() or "50k" in t.lower() for t in tips)

    def test_tip_for_network_sdks(self):
        sdks = [{"name": "OkHttp", "package_prefix": "com.squareup.okhttp", "class_count": 5}]
        tips = generate_analysis_tips("apk", 100, "none", sdks, 100)
        assert any("network" in t.lower() for t in tips)

    def test_tip_for_jar(self):
        tips = generate_analysis_tips("jar", 50, "none", [], 50)
        assert any("jar" in t.lower() for t in tips)

    def test_fallback_tip(self):
        tips = generate_analysis_tips("apk", 50, "none", [], 50)
        assert len(tips) >= 1


# ---------------------------------------------------------------------------
# Full digest integration (with mocked JADX)
# ---------------------------------------------------------------------------

class TestGenerateApkDigest:

    @pytest.mark.asyncio
    async def test_apk_digest_success(self, monkeypatch):
        responses = {
            "file-info": {"file_type": "apk", "file_size": 10_485_760},
            "manifest": SAMPLE_MANIFEST,
            "all-classes": lambda params: {
                "total": 300,
                "classes": [
                    {"name": "com.google.firebase.App"},
                    {"name": "com.example.myapp.Main"},
                    {"name": "a.b.C"},
                ],
            },
            "decompile-status": {"cached_percentage": 45.0, "total_classes": 300},
        }
        monkeypatch.setattr(digest_tools, "get_from_jadx", _make_fake_get_from_jadx(responses))

        result = await digest_tools._generate_apk_digest()

        assert result["file_type"] == "apk"
        assert result["file_size_mb"] == 10.0
        assert result["package_name"] == "com.example.myapp"
        assert "detected_sdks" in result
        assert "obfuscation_level" in result
        assert "analysis_tips" in result
        assert result["decompile_status"]["cached_percentage"] == 45.0

    @pytest.mark.asyncio
    async def test_jar_digest_skips_apk_fields(self, monkeypatch):
        responses = {
            "file-info": {"file_type": "jar", "file_size": 1_048_576},
            "jar-manifest": {"Main-Class": "com.example.Main"},
            "all-classes": lambda params: {
                "total": 50,
                "classes": [{"name": "com.example.Main"}],
            },
            "decompile-status": {"cached_percentage": 100.0, "total_classes": 50},
        }
        monkeypatch.setattr(digest_tools, "get_from_jadx", _make_fake_get_from_jadx(responses))

        result = await digest_tools._generate_apk_digest()

        assert result["file_type"] == "jar"
        assert "package_name" not in result
        assert "permissions" not in result
        assert "jar_manifest" in result

    @pytest.mark.asyncio
    async def test_file_info_error_returns_error(self, monkeypatch):
        responses = {
            "file-info": {"error": "NO_FILE_LOADED"},
        }
        monkeypatch.setattr(digest_tools, "get_from_jadx", _make_fake_get_from_jadx(responses))

        result = await digest_tools._generate_apk_digest()

        assert result["error"] == "DIGEST_FAILED"
        assert "recovery_hint" in result

    @pytest.mark.asyncio
    async def test_passes_instance_id(self, monkeypatch):
        captured_ids = []

        async def tracking_fake(endpoint, params=None, instance_id=None, **kwargs):
            captured_ids.append(instance_id)
            if endpoint == "file-info":
                return {"error": "NO_FILE"}
            return {}

        monkeypatch.setattr(digest_tools, "get_from_jadx", tracking_fake)
        await digest_tools._generate_apk_digest(instance_id="my-instance")
        assert all(i == "my-instance" for i in captured_ids)
