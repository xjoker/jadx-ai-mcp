"""
Headless Mode Contract Tests

Verifies behavioral equivalence between GUI-mode and headless-mode JADX instances.
All tests are skipped until headless support is implemented.

To activate: remove @pytest.mark.skip decorators and set environment variables:
    GUI_BASE_URL=http://gui-host:8650
    HEADLESS_BASE_URL=http://headless-host:8650
    JADX_AUTH_TOKEN=jadx-plugin-secret-token

Contract definition:
    - get_class_source: decompiled Java code must be character-for-character identical
      (or within 5% diff ratio for version-dependent formatting)
    - get_xrefs: reference lists must be set-equal (same class+method pairs, order ignored)
    - search_classes_by_keyword: returned class sets must be identical for metadata search
    - get_decompile_status: all required fields must be present (values may differ)
    - search_string_literals: returned literal sets must be identical
"""

import pytest
import httpx
import json
import os
from typing import Optional

pytestmark = [pytest.mark.integration, pytest.mark.headless_contract]

# ============================================================================
# Configuration
# ============================================================================

GUI_BASE_URL = os.getenv("GUI_BASE_URL", "http://localhost:8650")
HEADLESS_BASE_URL = os.getenv("HEADLESS_BASE_URL", "http://localhost:8660")  # different port
AUTH_TOKEN = os.getenv("JADX_AUTH_TOKEN", "jadx-plugin-secret-token")
AUTH_HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}"}

# Test APK class for contract checks (must exist in both instances)
CONTRACT_CLASS = os.getenv("CONTRACT_CLASS", "")  # set at runtime

# ============================================================================
# Helpers
# ============================================================================


def diff_ratio(a: str, b: str) -> float:
    """Compute character-level diff ratio between two strings.

    Returns:
        float: 0.0 = identical, 1.0 = completely different
    """
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0
    total = max(len(a), len(b))
    matching = sum(c1 == c2 for c1, c2 in zip(a, b))
    return 1.0 - (matching / total)


def extract_class_set(data: dict) -> set:
    """Extract class names from search response."""
    classes = data.get("classes", data.get("results", []))
    if isinstance(classes, list):
        return set(str(c) for c in classes)
    return set()


# ============================================================================
# Test Classes
# ============================================================================


class TestDecompileEquivalence:
    """Contract: decompiled output must be equivalent across GUI and headless modes."""

    @pytest.mark.skip(reason="headless not implemented yet")
    async def test_class_source_identical(self):
        """get_class_source must produce identical Java output on GUI and headless."""
        # Fetch from both
        async with httpx.AsyncClient() as client:
            gui_resp = await client.post(
                f"{GUI_BASE_URL}/api/class/source",
                json={"class_name": CONTRACT_CLASS},
                headers=AUTH_HEADERS,
            )
            headless_resp = await client.post(
                f"{HEADLESS_BASE_URL}/api/class/source",
                json={"class_name": CONTRACT_CLASS},
                headers=AUTH_HEADERS,
            )

        gui_source = gui_resp.json().get("source", "")
        headless_source = headless_resp.json().get("source", "")

        # Assert diff_ratio < 0.05 (allow <5% diff for minor formatting)
        ratio = diff_ratio(gui_source, headless_source)
        assert ratio < 0.05, (
            f"Class source diff ratio {ratio:.3f} exceeds 5% threshold. "
            f"GUI length={len(gui_source)}, headless length={len(headless_source)}"
        )
        pass

    @pytest.mark.skip(reason="headless not implemented yet")
    async def test_smali_identical(self):
        """get_smali_of_class must produce identical Smali."""
        async with httpx.AsyncClient() as client:
            gui_resp = await client.post(
                f"{GUI_BASE_URL}/api/class/smali",
                json={"class_name": CONTRACT_CLASS},
                headers=AUTH_HEADERS,
            )
            headless_resp = await client.post(
                f"{HEADLESS_BASE_URL}/api/class/smali",
                json={"class_name": CONTRACT_CLASS},
                headers=AUTH_HEADERS,
            )

        gui_smali = gui_resp.json().get("smali", "")
        headless_smali = headless_resp.json().get("smali", "")

        ratio = diff_ratio(gui_smali, headless_smali)
        assert ratio < 0.05, (
            f"Smali diff ratio {ratio:.3f} exceeds 5% threshold. "
            f"GUI length={len(gui_smali)}, headless length={len(headless_smali)}"
        )
        pass


class TestSearchEquivalence:
    """Contract: search results must be identical between GUI and headless modes."""

    @pytest.mark.skip(reason="headless not implemented yet")
    async def test_metadata_search_same_results(self):
        """search_classes_by_keyword with search_in=class must return identical class sets."""
        keyword = os.getenv("CONTRACT_SEARCH_KEYWORD", "Activity")

        async with httpx.AsyncClient() as client:
            gui_resp = await client.post(
                f"{GUI_BASE_URL}/api/search/classes",
                json={"keyword": keyword, "search_in": "class"},
                headers=AUTH_HEADERS,
            )
            headless_resp = await client.post(
                f"{HEADLESS_BASE_URL}/api/search/classes",
                json={"keyword": keyword, "search_in": "class"},
                headers=AUTH_HEADERS,
            )

        gui_classes = extract_class_set(gui_resp.json())
        headless_classes = extract_class_set(headless_resp.json())

        assert gui_classes == headless_classes, (
            f"Metadata search results differ. "
            f"GUI-only: {gui_classes - headless_classes}, "
            f"headless-only: {headless_classes - gui_classes}"
        )
        pass

    @pytest.mark.skip(reason="headless not implemented yet")
    async def test_string_literal_search_same_results(self):
        """search_string_literals must return identical literal sets."""
        pattern = os.getenv("CONTRACT_STRING_PATTERN", "https://")

        async with httpx.AsyncClient() as client:
            gui_resp = await client.post(
                f"{GUI_BASE_URL}/api/search/strings",
                json={"pattern": pattern},
                headers=AUTH_HEADERS,
            )
            headless_resp = await client.post(
                f"{HEADLESS_BASE_URL}/api/search/strings",
                json={"pattern": pattern},
                headers=AUTH_HEADERS,
            )

        gui_literals = set(str(s) for s in gui_resp.json().get("strings", []))
        headless_literals = set(str(s) for s in headless_resp.json().get("strings", []))

        assert gui_literals == headless_literals, (
            f"String literal search results differ. "
            f"GUI-only: {gui_literals - headless_literals}, "
            f"headless-only: {headless_literals - gui_literals}"
        )
        pass


class TestXrefsEquivalence:
    """Contract: cross-reference results must be set-equal between GUI and headless."""

    @pytest.mark.skip(reason="headless not implemented yet")
    async def test_xrefs_to_class_same_references(self):
        """xrefs-to-class must return set-equal references (order-independent)."""
        async with httpx.AsyncClient() as client:
            gui_resp = await client.post(
                f"{GUI_BASE_URL}/api/xrefs",
                json={"class_name": CONTRACT_CLASS, "direction": "to"},
                headers=AUTH_HEADERS,
            )
            headless_resp = await client.post(
                f"{HEADLESS_BASE_URL}/api/xrefs",
                json={"class_name": CONTRACT_CLASS, "direction": "to"},
                headers=AUTH_HEADERS,
            )

        def extract_ref_set(data: dict) -> set:
            refs = data.get("xrefs", data.get("references", []))
            result = set()
            for ref in refs:
                if isinstance(ref, dict):
                    key = f"{ref.get('class', '')}::{ref.get('method', '')}"
                else:
                    key = str(ref)
                result.add(key)
            return result

        gui_refs = extract_ref_set(gui_resp.json())
        headless_refs = extract_ref_set(headless_resp.json())

        assert gui_refs == headless_refs, (
            f"Xref sets differ. "
            f"GUI-only: {gui_refs - headless_refs}, "
            f"headless-only: {headless_refs - gui_refs}"
        )
        pass


class TestStatusEquivalence:
    """Contract: status endpoints must return all required fields in both modes."""

    @pytest.mark.skip(reason="headless not implemented yet")
    async def test_decompile_status_fields_present(self):
        """decompile-status must return all required fields (values may differ)."""
        # Required fields: total_classes, cached_percentage, memory, search_lock
        required_fields = {"total_classes", "cached_percentage", "memory", "search_lock"}

        async with httpx.AsyncClient() as client:
            gui_resp = await client.get(
                f"{GUI_BASE_URL}/api/status/decompile",
                headers=AUTH_HEADERS,
            )
            headless_resp = await client.get(
                f"{HEADLESS_BASE_URL}/api/status/decompile",
                headers=AUTH_HEADERS,
            )

        gui_data = gui_resp.json()
        headless_data = headless_resp.json()

        gui_missing = required_fields - set(gui_data.keys())
        headless_missing = required_fields - set(headless_data.keys())

        assert not gui_missing, f"GUI decompile-status missing fields: {gui_missing}"
        assert not headless_missing, (
            f"Headless decompile-status missing fields: {headless_missing}"
        )
        pass

    @pytest.mark.skip(reason="headless not implemented yet")
    async def test_file_info_equivalent(self):
        """file-info must report same file_type and android_features."""
        async with httpx.AsyncClient() as client:
            gui_resp = await client.get(
                f"{GUI_BASE_URL}/api/file/info",
                headers=AUTH_HEADERS,
            )
            headless_resp = await client.get(
                f"{HEADLESS_BASE_URL}/api/file/info",
                headers=AUTH_HEADERS,
            )

        gui_data = gui_resp.json()
        headless_data = headless_resp.json()

        assert gui_data.get("file_type") == headless_data.get("file_type"), (
            f"file_type mismatch: GUI={gui_data.get('file_type')}, "
            f"headless={headless_data.get('file_type')}"
        )
        assert gui_data.get("android_features") == headless_data.get("android_features"), (
            f"android_features mismatch: GUI={gui_data.get('android_features')}, "
            f"headless={headless_data.get('android_features')}"
        )
        pass


class TestPerformanceContractBounds:
    """Performance contract: headless mode must not be significantly slower than GUI."""

    @pytest.mark.skip(reason="headless not implemented yet")
    async def test_class_source_headless_not_slower_than_2x_gui(self):
        """headless class-source must be within 2x the GUI latency."""
        import time

        fixtures_path = os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "baseline_gui_results.json",
        )

        # Load baseline from fixtures/baseline_gui_results.json
        if os.path.exists(fixtures_path):
            with open(fixtures_path) as f:
                baseline = json.load(f)
            gui_p50 = baseline.get("class_source_p50_ms")
        else:
            # No baseline: measure GUI live
            samples = []
            async with httpx.AsyncClient() as client:
                for _ in range(5):
                    t0 = time.monotonic()
                    await client.post(
                        f"{GUI_BASE_URL}/api/class/source",
                        json={"class_name": CONTRACT_CLASS},
                        headers=AUTH_HEADERS,
                    )
                    samples.append((time.monotonic() - t0) * 1000)
            samples.sort()
            gui_p50 = samples[len(samples) // 2]

        assert gui_p50 is not None, "Could not determine GUI P50 baseline"

        # Run headless
        headless_samples = []
        async with httpx.AsyncClient() as client:
            for _ in range(5):
                t0 = time.monotonic()
                await client.post(
                    f"{HEADLESS_BASE_URL}/api/class/source",
                    json={"class_name": CONTRACT_CLASS},
                    headers=AUTH_HEADERS,
                )
                headless_samples.append((time.monotonic() - t0) * 1000)

        headless_samples.sort()
        headless_p50 = headless_samples[len(headless_samples) // 2]

        # Assert headless_p50 < gui_p50 * 2.0
        assert headless_p50 < gui_p50 * 2.0, (
            f"Headless P50 {headless_p50:.1f}ms exceeds 2x GUI baseline "
            f"{gui_p50:.1f}ms (limit={gui_p50 * 2.0:.1f}ms)"
        )
        pass


# ============================================================================
# Contract Registry
# ============================================================================
# This dict documents all contracts so they can be checked programmatically.
# When implementing headless support, verify each contract is satisfied.

CONTRACTS = {
    "class_source": {
        "description": "Decompiled Java source must be character-for-character identical (<=5% diff)",
        "test": "TestDecompileEquivalence::test_class_source_identical",
        "tolerance": "diff_ratio < 0.05",
    },
    "xrefs": {
        "description": "Cross-reference sets must be set-equal (order-independent)",
        "test": "TestXrefsEquivalence::test_xrefs_to_class_same_references",
        "tolerance": "set equality",
    },
    "metadata_search": {
        "description": "Class search results must be identical for search_in=class",
        "test": "TestSearchEquivalence::test_metadata_search_same_results",
        "tolerance": "exact set equality",
    },
    "performance": {
        "description": "Headless P50 latency must not exceed 2x GUI baseline",
        "test": "TestPerformanceContractBounds::test_class_source_headless_not_slower_than_2x_gui",
        "tolerance": "headless_p50 < gui_p50 * 2.0",
    },
}
