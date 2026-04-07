"""Tests for analysis planning tools."""

import pytest

from server.tools.analysis_tools import suggest_analysis_plan, _match_plan, _PLANS


class TestMatchPlan:
    """Test keyword-to-plan matching logic."""

    def test_security_keywords(self):
        assert "security_audit" in _match_plan("security audit")
        assert "security_audit" in _match_plan("check 安全 vulnerabilities")
        assert "security_audit" in _match_plan("find hardcoded passwords")

    def test_network_keywords(self):
        assert "network_analysis" in _match_plan("network communication")
        assert "network_analysis" in _match_plan("find retrofit API endpoints")
        assert "network_analysis" in _match_plan("okhttp interceptor")

    def test_entry_points_keywords(self):
        assert "entry_points" in _match_plan("entry points analysis")
        assert "entry_points" in _match_plan("find all activities")
        assert "entry_points" in _match_plan("分析组件生命周期")

    def test_quick_analysis_keywords(self):
        assert "quick_analysis" in _match_plan("quick overview")
        assert "quick_analysis" in _match_plan("快速概览")

    def test_multiple_matches(self):
        result = _match_plan("security network audit")
        assert "security_audit" in result
        assert "network_analysis" in result

    def test_no_match_returns_all(self):
        result = _match_plan("xyzzy gibberish")
        assert set(result) == set(_PLANS.keys())

    def test_case_insensitive(self):
        assert "security_audit" in _match_plan("SECURITY AUDIT")
        assert "network_analysis" in _match_plan("RETROFIT")


class TestSuggestAnalysisPlan:
    """Test the suggest_analysis_plan async function."""

    @pytest.mark.asyncio
    async def test_empty_goal_returns_error(self):
        result = await suggest_analysis_plan("")
        assert result["error"] == "INVALID_INPUT"
        assert "available_plans" in result

    @pytest.mark.asyncio
    async def test_whitespace_goal_returns_error(self):
        result = await suggest_analysis_plan("   ")
        assert result["error"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_specific_goal_returns_matched_plans(self):
        result = await suggest_analysis_plan("security audit")
        assert result["analysis_goal"] == "security audit"
        assert result["plan_count"] >= 1
        assert not result["is_fallback"]
        plan_ids = [p["plan_id"] for p in result["recommended_plans"]]
        assert "security_audit" in plan_ids

    @pytest.mark.asyncio
    async def test_fallback_when_no_match(self):
        result = await suggest_analysis_plan("xyzzy unknown goal")
        assert result["is_fallback"] is True
        assert result["plan_count"] == len(_PLANS)
        assert result["fallback_message"] is not None

    @pytest.mark.asyncio
    async def test_plan_structure(self):
        result = await suggest_analysis_plan("quick overview")
        plan = result["recommended_plans"][0]
        assert "plan_id" in plan
        assert "name" in plan
        assert "description" in plan
        assert "steps" in plan
        assert "tips" in plan
        assert len(plan["steps"]) > 0
        step = plan["steps"][0]
        assert "step" in step
        assert "tool" in step
        assert "reason" in step

    @pytest.mark.asyncio
    async def test_response_has_usage_hint(self):
        result = await suggest_analysis_plan("security")
        assert "usage_hint" in result
        assert "available_plan_ids" in result


class TestPlanDefinitions:
    """Validate plan definitions are well-formed."""

    @pytest.mark.parametrize("plan_id", list(_PLANS.keys()))
    def test_plan_has_required_fields(self, plan_id):
        plan = _PLANS[plan_id]
        assert "name" in plan
        assert "description" in plan
        assert "steps" in plan
        assert "tips" in plan
        assert len(plan["steps"]) > 0
        assert len(plan["tips"]) > 0

    @pytest.mark.parametrize("plan_id", list(_PLANS.keys()))
    def test_steps_are_sequential(self, plan_id):
        steps = _PLANS[plan_id]["steps"]
        for i, step in enumerate(steps):
            assert step["step"] == i + 1
            assert "tool" in step
            assert "reason" in step
