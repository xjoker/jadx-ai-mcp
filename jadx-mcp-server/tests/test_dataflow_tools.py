"""Tests for dataflow_tools module — BFS call-chain tracing and pattern detection."""

import pytest

from server.tools import dataflow_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_callee_graph(graph: dict[str, list[dict[str, str]]]):
    """Build a fake get_from_jadx for forward tracing (method-callees).

    Args:
        graph: mapping of "class#method" -> list of callee dicts
               e.g. {"com.A#start": [{"class_name": "com.B", "method_name": "run"}]}
    """
    async def fake(endpoint, params=None, instance_id=None, **kwargs):
        if endpoint == "method-callees":
            cls = (params or {}).get("class_name", "")
            method = (params or {}).get("method_name", "")
            key = f"{cls}#{method}"
            return {"callees": graph.get(key, [])}
        return {}

    return fake


def _make_xref_graph(graph: dict[str, list[dict[str, str]]]):
    """Build a fake get_from_jadx for backward tracing (xrefs-to-method).

    Args:
        graph: mapping of "class#method" -> list of caller reference dicts
    """
    async def fake(endpoint, params=None, instance_id=None, **kwargs):
        if endpoint == "xrefs-to-method":
            cls = (params or {}).get("class_name", "")
            method = (params or {}).get("method_name", "")
            key = f"{cls}#{method}"
            return {"references": graph.get(key, [])}
        return {}

    return fake


# ---------------------------------------------------------------------------
# trace_data_flow — BFS and sink detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trace_simple_chain(monkeypatch):
    """A -> B -> C should produce a tree of depth 2."""
    graph = {
        "com.A#start": [{"class_name": "com.B", "method_name": "process"}],
        "com.B#process": [{"class_name": "com.C", "method_name": "finish"}],
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_callee_graph(graph))

    result = await dataflow_tools.trace_data_flow("com.A", "start", max_depth=3)

    assert result["stats"]["nodes_explored"] == 2
    assert result["stats"]["max_depth_reached"] == 2
    # Root has one child (B.process), which has one child (C.finish)
    root = result["call_tree"]
    assert root["depth"] == 0
    assert len(root["children"]) == 1
    assert root["children"][0]["method"] == "B.process"
    assert len(root["children"][0]["children"]) == 1
    assert root["children"][0]["children"][0]["method"] == "C.finish"


@pytest.mark.asyncio
async def test_trace_detects_sink(monkeypatch):
    """A sink pattern in callees should be flagged."""
    graph = {
        "com.A#send": [{"class_name": "java.net.URLConnection", "method_name": "connect"}],
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_callee_graph(graph))

    result = await dataflow_tools.trace_data_flow("com.A", "send", max_depth=2)

    assert result["stats"]["sinks_count"] == 1
    sink = result["sinks_found"][0]
    assert sink["sink_type"] == "network"
    assert "URLConnection.connect" in sink["method"]


@pytest.mark.asyncio
async def test_trace_detects_multiple_sink_types(monkeypatch):
    """Verify detection of storage and logging sinks."""
    graph = {
        "com.X#run": [
            {"class_name": "android.content.SharedPreferences", "method_name": "edit"},
            {"class_name": "android.util.Log", "method_name": "d"},
        ],
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_callee_graph(graph))

    result = await dataflow_tools.trace_data_flow("com.X", "run", max_depth=1)

    types = {s["sink_type"] for s in result["sinks_found"]}
    assert "storage" in types
    assert "logging" in types


@pytest.mark.asyncio
async def test_trace_depth_limit(monkeypatch):
    """BFS should stop at max_depth even if the graph continues."""
    graph = {
        "com.A#m": [{"class_name": "com.B", "method_name": "m"}],
        "com.B#m": [{"class_name": "com.C", "method_name": "m"}],
        "com.C#m": [{"class_name": "com.D", "method_name": "m"}],
        "com.D#m": [{"class_name": "com.E", "method_name": "m"}],
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_callee_graph(graph))

    result = await dataflow_tools.trace_data_flow("com.A", "m", max_depth=2)

    # Should only reach depth 2 (B and C), not D or E
    assert result["stats"]["max_depth_reached"] == 2
    assert result["stats"]["nodes_explored"] == 2


@pytest.mark.asyncio
async def test_trace_max_depth_clamped(monkeypatch):
    """max_depth > 5 should be clamped to 5."""
    graph = {}
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_callee_graph(graph))

    result = await dataflow_tools.trace_data_flow("com.A", "m", max_depth=99)
    assert result["max_depth"] == 5


@pytest.mark.asyncio
async def test_trace_no_callees(monkeypatch):
    """A method with no callees should produce an empty tree."""
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_callee_graph({}))

    result = await dataflow_tools.trace_data_flow("com.A", "leaf", max_depth=3)

    assert result["stats"]["nodes_explored"] == 0
    assert result["stats"]["sinks_count"] == 0
    assert result["call_tree"]["children"] == []


@pytest.mark.asyncio
async def test_trace_avoids_cycles(monkeypatch):
    """Cycles in the call graph should not cause infinite loops."""
    graph = {
        "com.A#m": [{"class_name": "com.B", "method_name": "m"}],
        "com.B#m": [{"class_name": "com.A", "method_name": "m"}],  # cycle back
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_callee_graph(graph))

    result = await dataflow_tools.trace_data_flow("com.A", "m", max_depth=5)

    # Should terminate despite the cycle
    assert result["stats"]["nodes_explored"] >= 1


@pytest.mark.asyncio
async def test_trace_handles_api_error(monkeypatch):
    """API errors should be silently skipped, not crash."""
    async def failing_fake(endpoint, params=None, instance_id=None, **kwargs):
        raise ConnectionError("server down")

    monkeypatch.setattr(dataflow_tools, "get_from_jadx", failing_fake)

    result = await dataflow_tools.trace_data_flow("com.A", "m", max_depth=2)

    assert result["stats"]["nodes_explored"] == 0
    assert result["call_tree"]["children"] == []


# ---------------------------------------------------------------------------
# find_callers_chain — backward BFS and source detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_callers_simple_chain(monkeypatch):
    """C <- B <- A should produce a caller tree of depth 2."""
    graph = {
        "com.C#target": [{"class_name": "com.B", "method_name": "middle"}],
        "com.B#middle": [{"class_name": "com.A", "method_name": "entry"}],
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_xref_graph(graph))

    result = await dataflow_tools.find_callers_chain("com.C", "target", max_depth=3)

    assert result["stats"]["nodes_explored"] == 2
    root = result["caller_tree"]
    assert len(root["callers"]) == 1
    assert root["callers"][0]["method"] == "B.middle"
    assert len(root["callers"][0]["callers"]) == 1
    assert root["callers"][0]["callers"][0]["method"] == "A.entry"


@pytest.mark.asyncio
async def test_callers_detects_source(monkeypatch):
    """An input-source pattern in callers should be flagged."""
    graph = {
        "com.Proc#handle": [
            {"class_name": "android.widget.EditText", "method_name": "getText"},
        ],
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_xref_graph(graph))

    result = await dataflow_tools.find_callers_chain("com.Proc", "handle", max_depth=2)

    assert result["stats"]["sources_count"] == 1
    src = result["sources_found"][0]
    assert src["source_type"] == "user_input"


@pytest.mark.asyncio
async def test_callers_detects_network_input(monkeypatch):
    """Network input sources should be detected."""
    graph = {
        "com.Parser#parse": [
            {"class_name": "okhttp3.Response", "method_name": "body"},
        ],
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_xref_graph(graph))

    result = await dataflow_tools.find_callers_chain("com.Parser", "parse", max_depth=2)

    assert result["stats"]["sources_count"] == 1
    assert result["sources_found"][0]["source_type"] == "network_input"


@pytest.mark.asyncio
async def test_callers_depth_limit(monkeypatch):
    """BFS should stop at max_depth."""
    graph = {
        "com.D#m": [{"class_name": "com.C", "method_name": "m"}],
        "com.C#m": [{"class_name": "com.B", "method_name": "m"}],
        "com.B#m": [{"class_name": "com.A", "method_name": "m"}],
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_xref_graph(graph))

    result = await dataflow_tools.find_callers_chain("com.D", "m", max_depth=2)

    assert result["stats"]["max_depth_reached"] == 2
    assert result["stats"]["nodes_explored"] == 2


@pytest.mark.asyncio
async def test_callers_no_refs(monkeypatch):
    """A method with no callers should produce an empty tree."""
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_xref_graph({}))

    result = await dataflow_tools.find_callers_chain("com.A", "isolated", max_depth=3)

    assert result["stats"]["nodes_explored"] == 0
    assert result["caller_tree"]["callers"] == []


@pytest.mark.asyncio
async def test_callers_avoids_cycles(monkeypatch):
    """Cycles in the caller graph should not cause infinite loops."""
    graph = {
        "com.A#m": [{"class_name": "com.B", "method_name": "m"}],
        "com.B#m": [{"class_name": "com.A", "method_name": "m"}],
    }
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_xref_graph(graph))

    result = await dataflow_tools.find_callers_chain("com.A", "m", max_depth=5)

    assert result["stats"]["nodes_explored"] >= 1


@pytest.mark.asyncio
async def test_callers_handles_api_error(monkeypatch):
    """API errors should be silently skipped."""
    async def failing_fake(endpoint, params=None, instance_id=None, **kwargs):
        raise ConnectionError("server down")

    monkeypatch.setattr(dataflow_tools, "get_from_jadx", failing_fake)

    result = await dataflow_tools.find_callers_chain("com.A", "m", max_depth=2)

    assert result["stats"]["nodes_explored"] == 0


# ---------------------------------------------------------------------------
# Sink/source pattern unit tests
# ---------------------------------------------------------------------------

def test_sink_pattern_matching():
    """Verify _match_sink detects known patterns."""
    is_sink, stype = dataflow_tools._match_sink("URLConnection.connect")
    assert is_sink and stype == "network"

    is_sink, stype = dataflow_tools._match_sink("SharedPreferences.edit")
    assert is_sink and stype == "storage"

    is_sink, stype = dataflow_tools._match_sink("sendBroadcast")
    assert is_sink and stype == "ipc"

    is_sink, stype = dataflow_tools._match_sink("Cipher.doFinal")
    assert is_sink and stype == "crypto"

    is_sink, stype = dataflow_tools._match_sink("someRandomMethod")
    assert not is_sink and stype is None


def test_source_pattern_matching():
    """Verify _match_source detects known patterns."""
    is_src, stype = dataflow_tools._match_source("EditText.getText")
    assert is_src and stype == "user_input"

    is_src, stype = dataflow_tools._match_source("Response.body")
    assert is_src and stype == "network_input"

    is_src, stype = dataflow_tools._match_source("SharedPreferences.getString")
    assert is_src and stype == "storage_input"

    is_src, stype = dataflow_tools._match_source("randomStuff")
    assert not is_src and stype is None


# ---------------------------------------------------------------------------
# Limitations field test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_limitations_field_present(monkeypatch):
    """Both tools should include a 'limitations' field."""
    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_callee_graph({}))
    result1 = await dataflow_tools.trace_data_flow("com.A", "m")
    assert "limitations" in result1 and "pattern-based" in result1["limitations"]

    monkeypatch.setattr(dataflow_tools, "get_from_jadx", _make_xref_graph({}))
    result2 = await dataflow_tools.find_callers_chain("com.A", "m")
    assert "limitations" in result2 and "pattern-based" in result2["limitations"]
