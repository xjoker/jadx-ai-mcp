"""Tests for analysis report export tools."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from server.tools.export_tools import export_analysis_report


# ==================== Shared Fixtures ====================


@pytest.fixture()
def mock_file_info():
    return {
        "file_name": "sample.apk",
        "file_type": "apk",
        "package_name": "com.example.sample",
        "name": "sample.apk",
    }


@pytest.fixture()
def mock_analysis_data():
    return {
        "annotations": [
            {
                "id": 1,
                "target_type": "class",
                "target_name": "com.example.Crypto",
                "content": "Uses weak encryption",
                "author": "analyst",
            },
        ],
        "bookmarks": [
            {
                "id": 1,
                "target_type": "method",
                "target_name": "com.example.Main#onCreate()",
                "label": "entry point",
                "note": "App startup",
                "author": "analyst",
            },
        ],
        "tags": [
            {
                "id": 1,
                "target_type": "class",
                "target_name": "com.example.Network",
                "tag": "network",
                "author": "analyst",
            },
        ],
    }


@pytest.fixture()
def mock_empty_analysis_data():
    return {
        "annotations": [],
        "bookmarks": [],
        "tags": [],
    }


@pytest.fixture()
def mock_jadx(mock_file_info, mock_analysis_data):
    """Mock get_from_jadx to return file-info and analysis-notes."""
    async def side_effect(endpoint, **kwargs):
        if endpoint == "file-info":
            return mock_file_info
        if endpoint == "analysis-notes":
            return mock_analysis_data
        return {}

    with patch(
        "server.tools.export_tools.get_from_jadx",
        new_callable=AsyncMock,
        side_effect=side_effect,
    ) as mock:
        yield mock


@pytest.fixture()
def mock_jadx_empty(mock_file_info, mock_empty_analysis_data):
    """Mock get_from_jadx with empty analysis data."""
    async def side_effect(endpoint, **kwargs):
        if endpoint == "file-info":
            return mock_file_info
        if endpoint == "analysis-notes":
            return mock_empty_analysis_data
        return {}

    with patch(
        "server.tools.export_tools.get_from_jadx",
        new_callable=AsyncMock,
        side_effect=side_effect,
    ) as mock:
        yield mock


# ==================== Markdown Format Tests ====================


class TestMarkdownExport:
    """Test Markdown format output."""

    @pytest.mark.asyncio
    async def test_contains_report_header(self, mock_jadx):
        result = await export_analysis_report(format="markdown")
        assert "# Analysis Report:" in result["report"]
        assert "com.example.sample" in result["report"]

    @pytest.mark.asyncio
    async def test_contains_annotations_section(self, mock_jadx):
        result = await export_analysis_report(format="markdown")
        report = result["report"]
        assert "## Annotations (1)" in report
        assert "com.example.Crypto" in report
        assert "Uses weak encryption" in report

    @pytest.mark.asyncio
    async def test_contains_bookmarks_section(self, mock_jadx):
        result = await export_analysis_report(format="markdown")
        report = result["report"]
        assert "## Bookmarks (1)" in report
        assert "entry point" in report

    @pytest.mark.asyncio
    async def test_contains_tags_section(self, mock_jadx):
        result = await export_analysis_report(format="markdown")
        report = result["report"]
        assert "## Tags (1)" in report
        assert "network" in report

    @pytest.mark.asyncio
    async def test_stats_correct(self, mock_jadx):
        result = await export_analysis_report(format="markdown")
        assert result["stats"] == {"annotations": 1, "bookmarks": 1, "tags": 1}
        assert result["format"] == "markdown"
        assert "generated_at" in result

    @pytest.mark.asyncio
    async def test_empty_data_shows_placeholder(self, mock_jadx_empty):
        result = await export_analysis_report(format="markdown")
        report = result["report"]
        assert "_No annotations found._" in report
        assert "_No bookmarks found._" in report
        assert "_No tags found._" in report
        assert result["stats"] == {"annotations": 0, "bookmarks": 0, "tags": 0}


# ==================== JSON Format Tests ====================


class TestJsonExport:
    """Test JSON format output."""

    @pytest.mark.asyncio
    async def test_parseable_json(self, mock_jadx):
        result = await export_analysis_report(format="json")
        parsed = json.loads(result["report"])
        assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_contains_all_sections(self, mock_jadx):
        result = await export_analysis_report(format="json")
        parsed = json.loads(result["report"])
        assert "annotations" in parsed
        assert "bookmarks" in parsed
        assert "tags" in parsed
        assert "file_info" in parsed
        assert len(parsed["annotations"]) == 1

    @pytest.mark.asyncio
    async def test_empty_data(self, mock_jadx_empty):
        result = await export_analysis_report(format="json")
        parsed = json.loads(result["report"])
        assert parsed["annotations"] == []
        assert parsed["bookmarks"] == []
        assert parsed["tags"] == []


# ==================== SARIF Format Tests ====================


class TestSarifExport:
    """Test SARIF 2.1.0 format output."""

    @pytest.mark.asyncio
    async def test_valid_sarif_structure(self, mock_jadx):
        result = await export_analysis_report(format="sarif")
        sarif = json.loads(result["report"])

        assert sarif["version"] == "2.1.0"
        assert "$schema" in sarif
        assert "runs" in sarif
        assert len(sarif["runs"]) == 1

    @pytest.mark.asyncio
    async def test_sarif_tool_info(self, mock_jadx):
        result = await export_analysis_report(format="sarif")
        sarif = json.loads(result["report"])
        driver = sarif["runs"][0]["tool"]["driver"]
        assert driver["name"] == "jadx-ai-mcp"

    @pytest.mark.asyncio
    async def test_sarif_results_from_annotations_and_bookmarks(self, mock_jadx):
        result = await export_analysis_report(format="sarif")
        sarif = json.loads(result["report"])
        results = sarif["runs"][0]["results"]
        # 1 annotation + 1 bookmark = 2 results (tags are not converted to SARIF results)
        assert len(results) == 2
        rule_ids = [r["ruleId"] for r in results]
        assert "annotation" in rule_ids
        assert "bookmark" in rule_ids

    @pytest.mark.asyncio
    async def test_sarif_empty(self, mock_jadx_empty):
        result = await export_analysis_report(format="sarif")
        sarif = json.loads(result["report"])
        assert sarif["runs"][0]["results"] == []


# ==================== Error Handling Tests ====================


class TestExportErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_invalid_format(self):
        # No mock needed -- validation happens before any JADX call
        result = await export_analysis_report(format="pdf")
        assert result["error"] == "INVALID_FORMAT"
        assert "pdf" in result["message"]

    @pytest.mark.asyncio
    async def test_include_flags_filter_data(self, mock_jadx):
        result = await export_analysis_report(
            format="json",
            include_annotations=False,
            include_bookmarks=False,
            include_tags=True,
        )
        parsed = json.loads(result["report"])
        assert parsed["annotations"] == []
        assert parsed["bookmarks"] == []
        assert len(parsed["tags"]) == 1
        assert result["stats"] == {"annotations": 0, "bookmarks": 0, "tags": 1}
