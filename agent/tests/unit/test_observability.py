"""Unit tests for WBS 1.0 — L7 Observability (tracer + metrics)."""

import pytest

from harness.observability.tracer import traced, get_session_traces, clear_session_traces
from harness.observability.metrics import aggregate_session_metrics, SessionMetrics


# ── Mock harness enabled ──

@pytest.fixture(autouse=True)
def enable_observability(monkeypatch):
    """Enable observability layer for all tests in this module."""
    monkeypatch.setattr("harness.observability.tracer.is_layer_enabled", lambda layer: True)
    clear_session_traces()


# ── Tracer tests ──

@pytest.mark.asyncio
async def test_traced_records_ok():
    """@traced should record node_name, status=ok, duration_ms."""

    @traced("test_node")
    async def dummy_node(state, config=None):
        return {"history": ["test_node:ok"]}

    result = await dummy_node({})
    assert result == {"history": ["test_node:ok"]}

    traces = get_session_traces()
    assert len(traces) == 1
    assert traces[0]["node_name"] == "test_node"
    assert traces[0]["status"] == "ok"
    assert traces[0]["duration_ms"] >= 0
    assert "timestamp" in traces[0]


@pytest.mark.asyncio
async def test_traced_records_error():
    """@traced should record status=error when node raises."""

    @traced("failing_node")
    async def failing_node(state, config=None):
        raise ValueError("test error")

    with pytest.raises(ValueError, match="test error"):
        await failing_node({})

    traces = get_session_traces()
    assert len(traces) == 1
    assert traces[0]["status"] == "error"
    assert "test error" in traces[0]["error"]


@pytest.mark.asyncio
async def test_traced_extracts_diagnostic_metadata():
    """@traced should extract diagnosis_status and symptoms from task state."""

    @traced("task_decompose")
    async def decompose(state, config=None):
        return {
            "history": ["task_decompose:round_1:need_more_info"],
            "task": {
                "diagnosis_status": "need_more_info",
                "extracted_symptoms": ["fingerprint_fail", "bluetooth_disconnected"],
            },
        }

    await decompose({})
    traces = get_session_traces()
    assert traces[0]["diagnosis_status"] == "need_more_info"
    assert traces[0]["symptoms"] == ["fingerprint_fail", "bluetooth_disconnected"]


@pytest.mark.asyncio
async def test_traced_skips_when_disabled(monkeypatch):
    """@traced should be a no-op when observability is disabled."""
    monkeypatch.setattr("harness.observability.tracer.is_layer_enabled", lambda layer: False)
    clear_session_traces()

    @traced("skipped_node")
    async def node(state, config=None):
        return {"history": ["ok"]}

    await node({})
    assert get_session_traces() == []


@pytest.mark.asyncio
async def test_clear_session_traces():
    """clear_session_traces should reset the buffer."""

    @traced("node_a")
    async def node_a(state, config=None):
        return {}

    await node_a({})
    assert len(get_session_traces()) == 1

    clear_session_traces()
    assert len(get_session_traces()) == 0


# ── Metrics tests ──

@pytest.mark.asyncio
async def test_aggregate_session_metrics():
    """aggregate_session_metrics should summarize trace events."""

    @traced("pre_process")
    async def pre_process(state, config=None):
        return {"history": ["pre_process:ok"]}

    @traced("task_decompose")
    async def task_decompose(state, config=None):
        return {
            "history": ["task_decompose:round_1:hypothesis_formed"],
            "task": {
                "diagnosis_status": "hypothesis_formed",
                "extracted_symptoms": ["lock_tongue_stuck"],
            },
        }

    @traced("router")
    async def router(state, config=None):
        return {"history": ["router:hardware_tech"]}

    await pre_process({})
    await task_decompose({})
    await router({})

    metrics = aggregate_session_metrics(session_id="test-session-001")
    assert metrics.session_id == "test-session-001"
    assert metrics.node_path == ["pre_process", "task_decompose", "router"]
    assert metrics.total_latency_ms >= 0
    assert metrics.diagnosis_status == "hypothesis_formed"
    assert metrics.symptoms_extracted == ["lock_tongue_stuck"]
    assert metrics.transferred is False
    assert metrics.resolution_level == "L1"


def test_aggregate_empty_session():
    """Should return empty metrics when no traces exist."""
    clear_session_traces()
    metrics = aggregate_session_metrics(session_id="empty")
    assert metrics.node_path == []
    assert metrics.total_latency_ms == 0
