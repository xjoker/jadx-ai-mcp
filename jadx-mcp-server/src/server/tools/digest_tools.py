"""
JADX MCP Server - APK/JAR Digest Tools

This module provides MCP tools for generating structured pre-analysis digests
of loaded APK/JAR files, serving as an AI-friendly starting point for reverse
engineering workflows.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

import re
from typing import Optional
from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("digest_tools")

# ---------------------------------------------------------------------------
# Third-party SDK detection prefixes
# ---------------------------------------------------------------------------

SDK_PREFIXES: list[dict[str, str]] = [
    {"name": "Google SDK", "package_prefix": "com.google."},
    {"name": "Google Play Services", "package_prefix": "com.google.android.gms."},
    {"name": "Firebase", "package_prefix": "com.google.firebase."},
    {"name": "Facebook SDK", "package_prefix": "com.facebook."},
    {"name": "OkHttp", "package_prefix": "com.squareup.okhttp"},
    {"name": "Retrofit", "package_prefix": "com.squareup.retrofit"},
    {"name": "Moshi", "package_prefix": "com.squareup.moshi."},
    {"name": "RxJava", "package_prefix": "io.reactivex."},
    {"name": "RxJava3", "package_prefix": "io.reactivex.rxjava3."},
    {"name": "Apache Commons", "package_prefix": "org.apache."},
    {"name": "Alibaba SDK", "package_prefix": "com.alibaba."},
    {"name": "Tencent SDK", "package_prefix": "com.tencent."},
    {"name": "ByteDance SDK", "package_prefix": "com.bytedance."},
    {"name": "Kotlin Stdlib", "package_prefix": "kotlin."},
    {"name": "Kotlinx Coroutines", "package_prefix": "kotlinx.coroutines."},
    {"name": "AndroidX", "package_prefix": "androidx."},
    {"name": "Glide", "package_prefix": "com.bumptech.glide."},
    {"name": "Gson", "package_prefix": "com.google.gson."},
    {"name": "Dagger/Hilt", "package_prefix": "dagger."},
    {"name": "Butterknife", "package_prefix": "butterknife."},
    {"name": "EventBus", "package_prefix": "org.greenrobot.eventbus."},
    {"name": "Lottie", "package_prefix": "com.airbnb.lottie."},
    {"name": "Picasso", "package_prefix": "com.squareup.picasso."},
    {"name": "Timber", "package_prefix": "timber.log."},
    {"name": "Baidu SDK", "package_prefix": "com.baidu."},
    {"name": "Huawei SDK", "package_prefix": "com.huawei."},
    {"name": "WeChat SDK", "package_prefix": "com.tencent.mm."},
    {"name": "Alipay SDK", "package_prefix": "com.alipay."},
    {"name": "Umeng Analytics", "package_prefix": "com.umeng."},
    {"name": "JetBrains Annotations", "package_prefix": "org.jetbrains.annotations."},
]


def detect_sdks(class_names: list[str]) -> list[dict[str, str | int]]:
    """Detect third-party SDKs from a list of fully-qualified class names."""
    sdk_counts: dict[str, int] = {}
    sdk_lookup: dict[str, str] = {}

    for sdk in SDK_PREFIXES:
        prefix = sdk["package_prefix"]
        sdk_counts[prefix] = 0
        sdk_lookup[prefix] = sdk["name"]

    # Sort by prefix length descending so more specific prefixes match first
    # (e.g., "com.google.firebase." before "com.google.")
    sorted_sdks = sorted(SDK_PREFIXES, key=lambda s: len(s["package_prefix"]), reverse=True)

    for cls in class_names:
        for sdk in sorted_sdks:
            if cls.startswith(sdk["package_prefix"]):
                sdk_counts[sdk["package_prefix"]] += 1
                break  # count each class only under the first matching prefix

    results = []
    for prefix, count in sdk_counts.items():
        if count > 0:
            results.append({
                "name": sdk_lookup[prefix],
                "package_prefix": prefix,
                "class_count": count,
            })
    # Sort by class count descending for readability
    results.sort(key=lambda x: x["class_count"], reverse=True)
    return results


def assess_obfuscation(class_names: list[str]) -> tuple[str, dict]:
    """
    Assess obfuscation level based on class name characteristics.

    Returns (level, details) where level is one of: none, low, medium, high.
    """
    if not class_names:
        return "none", {"short_name_ratio": 0.0, "single_char_packages": 0}

    short_name_count = 0
    single_char_packages = set()

    for cls in class_names:
        # Extract simple class name (after last dot)
        parts = cls.rsplit(".", 1)
        simple_name = parts[-1] if parts else cls
        if len(simple_name) <= 2:
            short_name_count += 1

        # Check for single-character package segments
        if "." in cls:
            package_parts = cls.rsplit(".", 1)[0].split(".")
            for part in package_parts:
                if len(part) == 1:
                    single_char_packages.add(part)

    ratio = short_name_count / len(class_names) if class_names else 0.0
    single_char_count = len(single_char_packages)

    if ratio >= 0.5:
        level = "high"
    elif ratio >= 0.2:
        level = "medium"
    elif ratio > 0.05:
        level = "low"
    else:
        level = "none"

    return level, {
        "short_name_ratio": round(ratio, 3),
        "single_char_packages": single_char_count,
    }


def parse_manifest_components(manifest_xml: str) -> dict:
    """
    Parse AndroidManifest.xml to extract components, permissions, SDK info,
    and entry points.  Uses simple regex matching (no XML parser dependency).
    """
    result: dict = {
        "package_name": "",
        "version": "",
        "sdk_info": {"min_sdk": 0, "target_sdk": 0},
        "permissions": [],
        "components": {
            "activities": [],
            "services": [],
            "receivers": [],
            "providers": [],
            "exported_components": [],
        },
        "entry_points": {
            "main_activity": "",
            "launcher_activities": [],
        },
    }

    # Package name
    m = re.search(r'package="([^"]+)"', manifest_xml)
    if m:
        result["package_name"] = m.group(1)

    # Version
    m = re.search(r'android:versionName="([^"]+)"', manifest_xml)
    if m:
        result["version"] = m.group(1)

    # SDK versions
    m = re.search(r'android:minSdkVersion="(\d+)"', manifest_xml)
    if m:
        result["sdk_info"]["min_sdk"] = int(m.group(1))
    m = re.search(r'android:targetSdkVersion="(\d+)"', manifest_xml)
    if m:
        result["sdk_info"]["target_sdk"] = int(m.group(1))

    # Permissions
    result["permissions"] = re.findall(
        r'<uses-permission\s+android:name="([^"]+)"', manifest_xml
    )

    # Components - extract with their blocks to check exported and intent-filter
    component_tags = {
        "activity": "activities",
        "service": "services",
        "receiver": "receivers",
        "provider": "providers",
    }

    for tag, key in component_tags.items():
        # Match both self-closing and block tags
        pattern = rf'<{tag}\s[^>]*android:name="([^"]+)"[^>]*(?:/>|>.*?</{tag}>)'
        for match in re.finditer(pattern, manifest_xml, re.DOTALL):
            name = match.group(1)
            result["components"][key].append(name)

            full_block = match.group(0)
            # Check exported attribute
            if 'android:exported="true"' in full_block:
                result["components"]["exported_components"].append(name)
            # Also count components with intent-filter as implicitly exported
            elif "<intent-filter" in full_block and 'android:exported="false"' not in full_block:
                result["components"]["exported_components"].append(name)

            # Detect launcher activities
            if tag == "activity" and "android.intent.action.MAIN" in full_block:
                result["entry_points"]["main_activity"] = name
                if "android.intent.category.LAUNCHER" in full_block:
                    result["entry_points"]["launcher_activities"].append(name)

    return result


def generate_analysis_tips(
    file_type: str,
    total_classes: int,
    obfuscation_level: str,
    detected_sdks: list[dict],
    sampled_count: int,
) -> list[str]:
    """Generate context-aware analysis tips based on file characteristics."""
    tips: list[str] = []

    if total_classes > 200 and sampled_count < total_classes:
        tips.append(
            f"Only {sampled_count} of {total_classes} classes were sampled for SDK detection. "
            "Call generate_apk_digest again or use all-classes with a larger count for more accurate results."
        )

    if obfuscation_level in ("medium", "high"):
        tips.append(
            "High obfuscation detected. Consider using string search (search_classes_by_keyword) "
            "rather than class name browsing for analysis."
        )

    if total_classes > 50000:
        tips.append(
            "Very large APK (>50k classes). Use package filtering in search tools "
            "and focus on app-owned packages to avoid third-party noise."
        )

    sdk_names = {s["name"] for s in detected_sdks}
    if "OkHttp" in sdk_names or "Retrofit" in sdk_names:
        tips.append(
            "Network libraries detected (OkHttp/Retrofit). Use suggest_analysis_plan('network') "
            "for structured network layer analysis."
        )

    if file_type == "jar":
        tips.append(
            "JAR file loaded. APK-specific tools (get_apk_info, get_android_manifest) are not available."
        )

    if not tips:
        tips.append(
            "Use suggest_analysis_plan to get a structured analysis workflow tailored to your goal."
        )

    return tips


# ---------------------------------------------------------------------------
# Main digest function
# ---------------------------------------------------------------------------

async def _generate_apk_digest(instance_id: Optional[str] = None) -> dict:
    """
    Generate a structured pre-analysis digest of the loaded APK/JAR file.

    Aggregates file info, manifest data, class statistics, SDK detection,
    and obfuscation assessment into a single response suitable as an AI
    analysis starting point.
    """
    logger.info("generate_apk_digest: starting digest generation")

    # Step 1: file info
    file_info = await get_from_jadx("file-info", instance_id=instance_id)
    if "error" in file_info:
        return {
            "error": "DIGEST_FAILED",
            "message": f"Cannot retrieve file info: {file_info.get('error')}",
            "recovery_hint": "Ensure a file is loaded in JADX before calling generate_apk_digest.",
        }

    file_type = file_info.get("file_type", "unknown").lower()
    file_size_bytes = file_info.get("file_size", 0)
    file_size_mb = round(file_size_bytes / (1024 * 1024), 2) if file_size_bytes else 0.0

    # Step 1b: enhanced APK metadata (signing certs, native libs, dex count)
    # Available only for APK/AAR/DEX file types; ignore errors gracefully.
    apk_meta: dict = {}
    if file_type in ("apk", "aar", "dex"):
        try:
            apk_info_result = await get_from_jadx("apk-info", instance_id=instance_id)
            if isinstance(apk_info_result, dict) and "error" not in apk_info_result:
                apk_meta = apk_info_result
        except Exception as exc:
            logger.warning(f"generate_apk_digest: could not fetch apk-info: {exc}")

    # Step 2: manifest (type-dependent)
    manifest_data: dict = {}
    if file_type in ("apk", "aar", "dex"):
        manifest_result = await get_from_jadx("manifest", instance_id=instance_id)
        if isinstance(manifest_result, str):
            manifest_data = parse_manifest_components(manifest_result)
        elif isinstance(manifest_result, dict) and "content" in manifest_result:
            manifest_data = parse_manifest_components(manifest_result["content"])
        elif isinstance(manifest_result, dict) and "error" not in manifest_result:
            manifest_data = parse_manifest_components(str(manifest_result))
    elif file_type == "jar":
        jar_manifest = await get_from_jadx("jar-manifest", instance_id=instance_id)
        if isinstance(jar_manifest, dict):
            manifest_data = {
                "jar_manifest": jar_manifest,
            }

    # Step 3: class count
    class_count_result = await get_from_jadx(
        "all-classes", {"offset": 0, "count": 1}, instance_id=instance_id
    )
    total_classes = 0
    if isinstance(class_count_result, dict):
        total_classes = class_count_result.get("total", 0)

    # Step 4: decompile status
    decompile_status = await get_from_jadx("decompile-status", instance_id=instance_id)
    cached_percentage = 0.0
    decompile_total = 0
    if isinstance(decompile_status, dict):
        cached_percentage = decompile_status.get("cached_percentage", 0.0)
        decompile_total = decompile_status.get("total_classes", total_classes)

    # Step 5: fetch class names for SDK detection and obfuscation assessment
    sample_count = min(total_classes, 200)
    class_list_result = await get_from_jadx(
        "all-classes", {"offset": 0, "count": sample_count}, instance_id=instance_id
    )
    class_names: list[str] = []
    if isinstance(class_list_result, dict):
        classes = class_list_result.get("classes", [])
        for c in classes:
            if isinstance(c, str):
                class_names.append(c)
            elif isinstance(c, dict):
                class_names.append(c.get("name", c.get("class_name", "")))

    detected_sdks = detect_sdks(class_names)
    obfuscation_level, obfuscation_details = assess_obfuscation(class_names)

    # Estimate app vs third-party classes
    third_party_count = sum(s["class_count"] for s in detected_sdks)
    app_classes_estimate = max(0, total_classes - third_party_count)

    # Build analysis tips
    tips = generate_analysis_tips(
        file_type, total_classes, obfuscation_level, detected_sdks, len(class_names)
    )

    # Assemble result
    result: dict = {
        "file_type": file_type,
        "file_size_mb": file_size_mb,
    }

    # APK-specific fields
    if file_type in ("apk", "aar", "dex") and manifest_data:
        result["package_name"] = manifest_data.get("package_name", "")
        result["version"] = manifest_data.get("version", "")
        result["sdk_info"] = manifest_data.get("sdk_info", {"min_sdk": 0, "target_sdk": 0})
        result["permissions"] = manifest_data.get("permissions", [])
        result["components"] = manifest_data.get("components", {})
        result["entry_points"] = manifest_data.get("entry_points", {})
    elif file_type == "jar" and manifest_data:
        result["jar_manifest"] = manifest_data.get("jar_manifest", {})

    result["class_stats"] = {
        "total_classes": total_classes,
        "app_classes_estimate": app_classes_estimate,
        "third_party_sdk_classes": third_party_count,
    }
    result["detected_sdks"] = detected_sdks
    result["obfuscation_level"] = obfuscation_level
    result["obfuscation_details"] = obfuscation_details
    result["decompile_status"] = {
        "cached_percentage": cached_percentage,
        "total_classes": decompile_total,
    }
    result["analysis_tips"] = tips

    # Inject enhanced APK metadata fields when available (APK/AAR/DEX only).
    # signing_certificates: list of {subject, sha256, algorithm, valid_from, valid_until}
    # native_libraries: list of {path, abi, name} for .so files bundled in the APK
    # dex_count: number of DEX files (multi-dex APKs have dex_count > 1)
    # total_classes: canonical class count from apk-info (may refine the estimate above)
    if apk_meta:
        if "signing_certificates" in apk_meta:
            result["signing_certificates"] = apk_meta["signing_certificates"]
        if "native_libraries" in apk_meta:
            result["native_libraries"] = apk_meta["native_libraries"]
        if "dex_count" in apk_meta:
            result["dex_count"] = apk_meta["dex_count"]
        if "total_classes" in apk_meta:
            # Prefer the authoritative count from apk-info over the sampled estimate
            result["class_stats"]["total_classes_apk_info"] = apk_meta["total_classes"]

    logger.info(
        f"generate_apk_digest: completed — type={file_type}, classes={total_classes}, "
        f"sdks={len(detected_sdks)}, obfuscation={obfuscation_level}"
    )
    return result


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

def register_digest_tools(mcp, with_busy_check):
    """Register digest tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def generate_apk_digest(instance_id: Optional[str] = None) -> dict:
        """Generate a pre-analysis digest: file info, manifest, SDK detection, obfuscation assessment, entry points.

        For APK/AAR/DEX files, also includes enhanced metadata when available from the JADX instance:
        - signing_certificates: [{subject, sha256, algorithm, valid_from, valid_until}]
            Signing certificate chain details — useful for verifying APK authenticity and
            comparing against known publisher fingerprints.
        - native_libraries: [{path, abi, name}]
            Native .so files bundled in the APK (lib/arm64-v8a/, lib/x86_64/, etc.).
            Presence of native code typically requires additional analysis with Ghidra/IDA.
        - dex_count: int
            Number of DEX files. Values > 1 indicate MultiDex; very large APKs may have
            3-5+ DEX files.

        Args:
            instance_id: Target JADX instance name.
        Returns:
            dict: {file_type, package_name, class_stats, detected_sdks, obfuscation_level,
                   analysis_tips, signing_certificates (APK only), native_libraries (APK only),
                   dex_count (APK only)}
        """
        return await _generate_apk_digest(instance_id=instance_id)

    logger.info("Digest tools registered: generate_apk_digest")
