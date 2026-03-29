"""
Layer 3 Integration Tests - 6.1.7-dev New Feature Coverage

Covers:
- Analysis planning tool behavior via direct Python tool calls
- Search endpoint improvements on the Java plugin HTTP API
- Unified file-info output for the loaded integration fixture
- POST semantics for refactor endpoints
- Python-side response_size_bytes metadata injection on batch tools
"""

from urllib.parse import urlparse

import pytest
import pytest_asyncio

from src.server.config import HttpClientManager, set_jadx_config
from src.server.tools.analysis_tools import suggest_analysis_plan
from src.server.tools.class_tools import batch_get_class_source
from .helpers import resolve_fixture_context


pytestmark = pytest.mark.integration


EXPECTED_PLAN_IDS = {
    "quick_analysis",
    "security_audit",
    "network_analysis",
    "entry_points",
}


@pytest_asyncio.fixture
async def configured_python_tool_calls(jadx_base_url, mcp_base_url):
    """
    Point direct Python tool calls at the configured integration target.

    The analysis-plan tests themselves do not need the MCP HTTP transport, but
    they should still honor the integration URL fixtures used by this suite.
    """
    assert jadx_base_url.startswith("http")
    assert mcp_base_url.startswith("http")

    parsed = urlparse(jadx_base_url)
    assert parsed.hostname, f"Invalid JADX base URL: {jadx_base_url}"
    assert parsed.port is not None, f"JADX base URL must include an explicit port: {jadx_base_url}"

    set_jadx_config(parsed.hostname, parsed.port)
    yield
    await HttpClientManager.close()


def _plan_ids(result: dict) -> set[str]:
    return {plan["plan_id"] for plan in result.get("recommended_plans", [])}


def _step_tools(result: dict, plan_id: str) -> list[str]:
    for plan in result.get("recommended_plans", []):
        if plan.get("plan_id") == plan_id:
            return [step["tool"] for step in plan.get("steps", [])]
    return []


def _search_params(search_term: str, search_in: str, package_name: str) -> dict[str, str | int]:
    # Keep the request compatible with the current route while also reflecting
    # the feature-request wording that uses "keyword".
    return {
        "keyword": search_term,
        "search_term": search_term,
        "search_in": search_in,
        "package": package_name,
        "count": 20,
    }


@pytest.mark.asyncio
class TestAnalysisPlanIntegration:
    async def test_quick_overview_goal_returns_quick_analysis_plan(
        self, configured_python_tool_calls
    ):
        result = await suggest_analysis_plan("quick overview")

        assert "error" not in result
        assert result["analysis_goal"] == "quick overview"
        assert result["plan_count"] == 1
        assert _plan_ids(result) == {"quick_analysis"}
        assert result["recommended_plans"][0]["steps"], "Quick analysis plan should include steps"
        assert _step_tools(result, "quick_analysis")[:2] == ["get_file_info", "get_apk_info"]

    async def test_security_audit_goal_returns_security_plan(
        self, configured_python_tool_calls
    ):
        result = await suggest_analysis_plan("security audit")

        assert "error" not in result
        assert result["plan_count"] == 1
        assert _plan_ids(result) == {"security_audit"}

        step_tools = _step_tools(result, "security_audit")
        assert "get_android_manifest" in step_tools
        assert "search_native_methods" in step_tools
        assert step_tools.count("search_classes_by_keyword") >= 2

    async def test_network_goal_returns_network_analysis_plan(
        self, configured_python_tool_calls
    ):
        result = await suggest_analysis_plan("network")

        assert "error" not in result
        assert result["plan_count"] == 1
        assert _plan_ids(result) == {"network_analysis"}

        step_tools = _step_tools(result, "network_analysis")
        assert "search_classes_by_keyword" in step_tools
        assert "CertificatePinner" in str(result["recommended_plans"][0]["steps"])

    async def test_entry_points_goal_returns_entry_points_plan(
        self, configured_python_tool_calls
    ):
        result = await suggest_analysis_plan("entry points")

        assert "error" not in result
        assert result["plan_count"] == 1
        assert _plan_ids(result) == {"entry_points"}

        step_tools = _step_tools(result, "entry_points")
        assert step_tools[0] == "get_android_manifest"
        assert "get_method_by_name" in step_tools
        assert "get_xrefs" in step_tools

    async def test_empty_goal_returns_invalid_input(
        self, configured_python_tool_calls
    ):
        result = await suggest_analysis_plan("")

        assert result["error"] == "INVALID_INPUT"
        assert "cannot be empty" in result["message"]
        assert set(result["available_plans"]) == EXPECTED_PLAN_IDS

    async def test_unknown_goal_returns_fallback_with_all_plans(
        self, configured_python_tool_calls
    ):
        result = await suggest_analysis_plan("random unknown goal")

        assert "error" not in result
        assert result["is_fallback"] is True
        assert result["plan_count"] == len(EXPECTED_PLAN_IDS)
        assert _plan_ids(result) == EXPECTED_PLAN_IDS
        assert set(result["available_plan_ids"]) == EXPECTED_PLAN_IDS
        assert result["fallback_message"]


@pytest.mark.asyncio
class TestSearchImprovementsIntegration:
    async def test_code_search_finds_calculator_class(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)
        search_term = context["class_name"].rsplit(".", 1)[-1]

        resp = await http_client.get(
            f"{jadx_base_url}/search-classes-by-keyword",
            params=_search_params(search_term, "code", context["package_name"]),
            timeout=120.0,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        data = resp.json()
        assert "classes" in data
        assert context["class_name"] in data["classes"], \
            f"Expected {context['class_name']} in code search results"
        assert data["search_info"]["timed_out"] is False

    async def test_comment_search_returns_structured_response(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/search-classes-by-keyword",
            params=_search_params("test", "comment", context["package_name"]),
            timeout=120.0,
        )
        assert resp.status_code == 200, f"Comment search should not fail, got {resp.status_code}"

        data = resp.json()
        assert "classes" in data
        assert isinstance(data["classes"], list)
        assert "search_info" in data
        assert "COMMENT" in data["search_info"]["search_locations"]
        assert data["search_info"]["total_found"] >= len(data["classes"])

    async def test_method_name_search_finds_add_method(self, jadx_base_url, http_client):
        context = await resolve_fixture_context(jadx_base_url, http_client)

        resp = await http_client.get(
            f"{jadx_base_url}/search-classes-by-keyword",
            params=_search_params(context["method_name"], "method_name", context["package_name"]),
            timeout=120.0,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        data = resp.json()
        assert "classes" in data
        assert context["class_name"] in data["classes"], \
            f"Expected {context['class_name']} in method-name search results"
        assert "METHOD_NAME" in data["search_info"]["search_locations"]


@pytest.mark.asyncio
class TestCompositePackageDetectionIntegration:
    async def test_file_info_reports_jar_type_for_fixture(self, jadx_base_url, http_client):
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200

        data = resp.json()
        assert data["loaded"] is True
        assert data["file_type"] in {"jar", "apk"}

        if data["file_type"] == "jar":
            assert data["file_category"] == "java"
            assert data["android_features"] is False
            assert data["smali_available"] is False
        else:
            assert data["file_category"] == "android"
            assert data["android_features"] is True
            assert data["smali_available"] is True

    async def test_file_info_recommends_expected_jar_tools(self, jadx_base_url, http_client):
        resp = await http_client.get(f"{jadx_base_url}/file-info")
        assert resp.status_code == 200

        data = resp.json()
        recommended_tools = set(data.get("recommended_tools", []))

        if data["file_type"] == "jar":
            assert {
                "jar_get_manifest",
                "jar_get_entry_points",
                "jar_get_services",
                "get_class_source",
            } <= recommended_tools
            assert "get_android_manifest" not in recommended_tools
            assert "get_smali_of_class" not in recommended_tools
        else:
            assert {
                "get_android_manifest",
                "get_main_activity_class",
                "get_strings",
                "get_smali_of_class",
            } <= recommended_tools
            assert "jar_get_manifest" not in recommended_tools
            assert "jar_get_entry_points" not in recommended_tools


@pytest.mark.asyncio
class TestRenamePostSemanticsIntegration:
    async def test_get_rename_class_old_route_is_not_allowed(self, jadx_base_url, http_client):
        resp = await http_client.get(f"{jadx_base_url}/rename-class")
        assert resp.status_code in {404, 405}, f"Expected 404/405, got {resp.status_code}"

    async def test_post_rename_class_without_required_params_returns_400(
        self, jadx_base_url, http_client
    ):
        resp = await http_client.post(
            f"{jadx_base_url}/rename-class",
            json={},
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"

        data = resp.json()
        assert "error" in data
        assert "Missing required" in data["error"]


@pytest.mark.asyncio
class TestLargeResponseMetadataIntegration:
    async def test_batch_class_source_includes_response_size_bytes(
        self, configured_python_tool_calls, jadx_base_url, http_client
    ):
        context = await resolve_fixture_context(jadx_base_url, http_client)
        result = await batch_get_class_source(context["batch_class_names"])

        assert "error" not in result, f"Unexpected batch_get_class_source error: {result}"
        # response_size_bytes is injected by the Python MCP layer
        assert "response_size_bytes" in result, f"Missing response_size_bytes in {list(result.keys())}"
        assert isinstance(result["response_size_bytes"], int)
        assert result["response_size_bytes"] > 0
        # Actual class data may be in "classes" directly or nested in "batch_result"
        has_classes = "classes" in result or "batch_result" in result
        assert has_classes, f"Expected classes or batch_result in {list(result.keys())}"
