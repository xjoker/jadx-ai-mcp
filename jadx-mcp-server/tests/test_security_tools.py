"""Tests for security_tools module."""

import pytest

from server.tools import security_tools
from server.tools.security_tools import (
    SECURITY_RULES,
    filter_rules,
    _extract_matches,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_get_from_jadx(responses: dict):
    """Create a fake get_from_jadx that returns canned responses."""
    async def fake(endpoint, params=None, instance_id=None, **kwargs):
        if endpoint in responses:
            val = responses[endpoint]
            return val(params) if callable(val) else val
        return {"error": "NOT_FOUND"}
    return fake


# ---------------------------------------------------------------------------
# filter_rules tests
# ---------------------------------------------------------------------------

class TestFilterRules:

    def test_full_returns_all_rules(self):
        result = filter_rules("full")
        assert result == SECURITY_RULES

    def test_secrets_filter(self):
        result = filter_rules("secrets")
        for rule in result.values():
            assert rule["category"] == "secrets"
        # Should include hardcoded_secrets and data_leakage
        assert "hardcoded_secrets" in result
        assert "data_leakage" in result

    def test_crypto_filter(self):
        result = filter_rules("crypto")
        for rule in result.values():
            assert rule["category"] == "crypto"
        assert "insecure_crypto" in result

    def test_network_filter(self):
        result = filter_rules("network")
        for rule in result.values():
            assert rule["category"] == "network"
        assert "insecure_network" in result

    def test_permissions_filter(self):
        result = filter_rules("permissions")
        for rule in result.values():
            assert rule["category"] == "permissions"
        assert "dangerous_apis" in result

    def test_unknown_type_returns_all(self):
        # Unknown types fall through to returning all rules
        result = filter_rules("nonexistent")
        assert result == SECURITY_RULES


# ---------------------------------------------------------------------------
# _extract_matches tests
# ---------------------------------------------------------------------------

class TestExtractMatches:

    def test_extracts_from_classes_key(self):
        data = {
            "classes": [
                {"class_name": "com.Foo", "snippet": "password = 'abc'"},
                {"class_name": "com.Bar", "snippet": "secret = 'xyz'"},
            ]
        }
        matches = _extract_matches(data)
        assert len(matches) == 2
        assert matches[0]["class_name"] == "com.Foo"

    def test_extracts_from_results_key(self):
        data = {
            "results": [
                {"name": "com.Baz", "match": "some match"},
            ]
        }
        matches = _extract_matches(data)
        assert len(matches) == 1
        assert matches[0]["class_name"] == "com.Baz"

    def test_handles_string_items(self):
        data = {"classes": ["com.Foo", "com.Bar"]}
        matches = _extract_matches(data)
        assert len(matches) == 2
        assert matches[0]["class_name"] == "com.Foo"

    def test_empty_response(self):
        assert _extract_matches({}) == []
        assert _extract_matches({"classes": []}) == []


# ---------------------------------------------------------------------------
# Code search skip logic tests
# ---------------------------------------------------------------------------

class TestCodeSearchSkipLogic:

    @pytest.mark.asyncio
    async def test_skips_code_search_when_cache_low(self, monkeypatch):
        """When cached_percentage < 20%, code searches should be skipped."""
        search_calls = []

        async def tracking_fake(endpoint, params=None, instance_id=None, **kwargs):
            if endpoint == "decompile-status":
                return {"cached_percentage": 5.0, "total_classes": 100}
            if endpoint == "search-classes-by-keyword":
                search_calls.append(params)
                return {"classes": []}
            return {}

        monkeypatch.setattr(security_tools, "get_from_jadx", tracking_fake)
        result = await security_tools._run_security_scan(scan_type="full")

        # All code searches should have been skipped
        for call in search_calls:
            assert call["search_in"] != "code", "Code search should have been skipped"

        # There should be skipped_rules entries
        assert len(result["skipped_rules"]) > 0
        assert result["scan_coverage"]["code_search_available"] is False

    @pytest.mark.asyncio
    async def test_runs_code_search_when_cache_sufficient(self, monkeypatch):
        """When cached_percentage >= 20%, code searches should run."""
        search_calls = []

        async def tracking_fake(endpoint, params=None, instance_id=None, **kwargs):
            if endpoint == "decompile-status":
                return {"cached_percentage": 50.0, "total_classes": 100}
            if endpoint == "search-classes-by-keyword":
                search_calls.append(params)
                return {"classes": []}
            return {}

        monkeypatch.setattr(security_tools, "get_from_jadx", tracking_fake)
        result = await security_tools._run_security_scan(scan_type="full")

        code_searches = [c for c in search_calls if c["search_in"] == "code"]
        assert len(code_searches) > 0, "Code searches should have run"
        assert result["scan_coverage"]["code_search_available"] is True


# ---------------------------------------------------------------------------
# Result structure tests
# ---------------------------------------------------------------------------

class TestResultStructure:

    @pytest.mark.asyncio
    async def test_result_has_required_keys(self, monkeypatch):
        responses = {
            "decompile-status": {"cached_percentage": 50.0, "total_classes": 100},
            "search-classes-by-keyword": {"classes": []},
        }
        monkeypatch.setattr(security_tools, "get_from_jadx", _make_fake_get_from_jadx(responses))

        result = await security_tools._run_security_scan()

        assert "scan_type" in result
        assert "scan_time_seconds" in result
        assert "summary" in result
        assert "findings" in result
        assert "skipped_rules" in result
        assert "scan_coverage" in result

    @pytest.mark.asyncio
    async def test_summary_counts_correct(self, monkeypatch):
        """Findings with matches should be counted by severity."""
        call_count = 0

        async def fake(endpoint, params=None, instance_id=None, **kwargs):
            nonlocal call_count
            if endpoint == "decompile-status":
                return {"cached_percentage": 80.0}
            if endpoint == "search-classes-by-keyword":
                call_count += 1
                # Return matches only for "password" term
                if params and params.get("search_term") == "password":
                    return {"classes": [{"class_name": "com.Foo", "snippet": "pw='123'"}]}
                return {"classes": []}
            return {}

        monkeypatch.setattr(security_tools, "get_from_jadx", fake)
        result = await security_tools._run_security_scan(scan_type="secrets")

        summary = result["summary"]
        assert summary["total_findings"] >= 1
        # Verify findings contain recommendation
        for finding in result["findings"]:
            assert "recommendation" in finding
            assert "severity" in finding

    @pytest.mark.asyncio
    async def test_invalid_scan_type_returns_error(self, monkeypatch):
        result = await security_tools._run_security_scan(scan_type="invalid_type")
        assert result["error"] == "INVALID_SCAN_TYPE"

    @pytest.mark.asyncio
    async def test_package_filter_passed_to_search(self, monkeypatch):
        captured_params = []

        async def tracking_fake(endpoint, params=None, instance_id=None, **kwargs):
            if endpoint == "decompile-status":
                return {"cached_percentage": 0.0}
            if endpoint == "search-classes-by-keyword":
                captured_params.append(params)
                return {"classes": []}
            return {}

        monkeypatch.setattr(security_tools, "get_from_jadx", tracking_fake)
        await security_tools._run_security_scan(package="com.example")

        for params in captured_params:
            assert params["package"] == "com.example"

    @pytest.mark.asyncio
    async def test_instance_id_forwarded(self, monkeypatch):
        captured_ids = []

        async def tracking_fake(endpoint, params=None, instance_id=None, **kwargs):
            captured_ids.append(instance_id)
            if endpoint == "decompile-status":
                return {"cached_percentage": 0.0}
            if endpoint == "search-classes-by-keyword":
                return {"classes": []}
            return {}

        monkeypatch.setattr(security_tools, "get_from_jadx", tracking_fake)
        await security_tools._run_security_scan(instance_id="inst-1")

        assert all(i == "inst-1" for i in captured_ids)

    @pytest.mark.asyncio
    async def test_finding_structure(self, monkeypatch):
        """Each finding should have all required fields."""
        async def fake(endpoint, params=None, instance_id=None, **kwargs):
            if endpoint == "decompile-status":
                return {"cached_percentage": 80.0}
            if endpoint == "search-classes-by-keyword":
                return {"classes": [{"class_name": "com.Test", "snippet": "match"}]}
            return {}

        monkeypatch.setattr(security_tools, "get_from_jadx", fake)
        result = await security_tools._run_security_scan(scan_type="crypto")

        assert len(result["findings"]) > 0
        finding = result["findings"][0]
        required_keys = {
            "rule_id", "category", "severity", "description",
            "matches", "match_count", "recommendation",
        }
        assert required_keys.issubset(finding.keys())
        assert finding["match_count"] > 0
        assert isinstance(finding["matches"], list)
