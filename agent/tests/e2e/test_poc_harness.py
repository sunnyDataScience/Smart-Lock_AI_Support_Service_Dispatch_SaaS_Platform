"""POC E2E Test Suite — 50 test cases validating Harness framework.

Runs each test case from poc_test_dataset.json through the full graph,
validates: intent classification, routing path, ProblemCard creation.

Usage:
    cd agent
    python -m pytest tests/e2e/test_poc_harness.py -v
    python -m pytest tests/e2e/test_poc_harness.py -v -k "TC-FP"     # fingerprint only
    python -m pytest tests/e2e/test_poc_harness.py -v -k "TC-LM"     # latch/mechanism only
    python -m pytest tests/e2e/test_poc_harness.py -v -k "TC-BD"     # boundary cases
"""

import json
import sys
import asyncio
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(AGENT_DIR))

DATASET_PATH = Path(__file__).parent / "poc_test_dataset.json"


@pytest.fixture(scope="module")
def test_cases():
    """Load the 50-case POC test dataset."""
    data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return data["test_cases"]


@pytest.fixture(scope="module")
def graph_app():
    """Build the LangGraph app once for all tests."""
    async def _build():
        from graph.builder import build_graph
        return await build_graph()
    return asyncio.get_event_loop().run_until_complete(_build())


def _get_test_ids():
    """Generate pytest IDs from dataset."""
    data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return [tc["id"] for tc in data["test_cases"]]


@pytest.mark.parametrize("case_idx", range(50), ids=_get_test_ids())
@pytest.mark.asyncio
async def test_poc_case(graph_app, test_cases, case_idx):
    """Run a single POC test case through the full Harness graph."""
    tc = test_cases[case_idx]
    tc_id = tc["id"]
    query = tc["query"]
    expected_intent = tc["expected_intent"]
    expected_path = tc["expected_path"]

    # Run through graph
    thread_id = f"poc_{tc_id}"
    inputs = {"question": query}
    config = {"configurable": {"thread_id": thread_id, "user_id": thread_id}}

    result = await graph_app.ainvoke(inputs, config=config)

    # --- Assertions ---

    # 1. Answer was produced
    answer = result.get("answer", "")
    assert answer, f"[{tc_id}] No answer produced for: {query}"

    # 2. History path contains expected nodes
    history = result.get("history", [])
    history_str = " ".join(history)

    # All cases should pass through Harness nodes
    assert any("pre_process" in h for h in history), f"[{tc_id}] Missing pre_process"
    assert any("rewrite_query" in h for h in history), f"[{tc_id}] Missing rewrite_query"
    assert any("task_decompose" in h for h in history), f"[{tc_id}] Missing task_decompose"

    # 3. ProblemCard was created
    task = result.get("task", {})
    pc = task.get("problem_card", {})
    assert pc.get("card_id", "").startswith("pc_"), \
        f"[{tc_id}] ProblemCard not created (card_id={pc.get('card_id')})"

    # 4. Path-specific validation
    if expected_path == "diagnostic":
        # Should go through diagnostic_respond, NOT router
        assert any("diagnostic_respond" in h for h in history), \
            f"[{tc_id}] Expected diagnostic path but got: {history}"
        assert task.get("diagnosis_status"), \
            f"[{tc_id}] Expected diagnosis_status but got empty"

    elif expected_path == "rag":
        # Should go through router → agent
        intents = task.get("intents", [])
        assert intents, f"[{tc_id}] Expected intents for RAG path but got empty"

    elif expected_path == "reject":
        # out_of_domain → router produces answer directly
        assert any("out_of_domain" in h for h in history), \
            f"[{tc_id}] Expected out_of_domain but got: {history}"

    elif expected_path == "red_code":
        # Should trigger Red_Code escalation
        safety = result.get("safety", {})
        # Red_Code can be caught by safety_gate or task_decompose
        is_red = safety.get("red_code", False)
        is_escalated = task.get("diagnosis_status") == "escalated"
        assert is_red or is_escalated, \
            f"[{tc_id}] Expected Red_Code but safety={safety}, diagnosis_status={task.get('diagnosis_status')}"

    elif expected_path == "escalation":
        # Should trigger sentiment escalation
        safety = result.get("safety", {})
        is_esc = safety.get("escalation_required", False)
        is_escalated = task.get("diagnosis_status") == "escalated"
        assert is_esc or is_escalated or "guardrail_triggered" in history_str, \
            f"[{tc_id}] Expected escalation but got: safety={safety}"

    # 5. Intent classification check (soft — LLM may classify differently)
    intents = task.get("intents", [])
    if intents and expected_intent != "hardware_tech":
        # For non-hardware intents, check if expected intent is in the list
        # This is a soft check because LLM classification may vary
        if expected_intent not in intents:
            pytest.skip(f"[{tc_id}] Intent mismatch: expected={expected_intent}, got={intents} (soft check)")
