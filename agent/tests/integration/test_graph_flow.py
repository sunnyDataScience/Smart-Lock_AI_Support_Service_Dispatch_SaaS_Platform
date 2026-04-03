"""Integration tests — harness node logic without langchain/langgraph dependencies.

Tests harness modules directly (decomposer, safety gate, knowledge loader)
without importing graph.nodes (which requires langchain_core).

Full graph flow tests require `pip install langchain-core langgraph` and
should be run in the project's virtual environment.
"""

import pytest


# ── Fixtures ──

@pytest.fixture(autouse=True)
def mock_harness_disabled(monkeypatch):
    """Disable all harness layers by default."""
    monkeypatch.setattr("harness.is_layer_enabled", lambda layer: False)
    monkeypatch.setattr("harness.is_harness_enabled", lambda: False)


@pytest.fixture
def base_state():
    return {
        "messages": [],
        "question": "我的鎖按指紋沒反應",
        "user_profile": "",
        "answer": "",
        "history": [],
        "summary": "",
        "next_agents": [],
        "ui_hints": [],
        "response_ui": [],
        "task": {},
        "context_meta": {},
        "feedback": {},
        "safety": {},
        "entropy": {},
    }


@pytest.fixture
def mock_config():
    return {"configurable": {"thread_id": "test-thread-001"}}


# ── Task Decompose (L1) via harness.task.decomposer directly ──

_has_langchain = True
try:
    import langchain_core  # noqa: F401
except ImportError:
    _has_langchain = False


@pytest.mark.skipif(not _has_langchain, reason="langchain_core not installed")
class TestTaskDecomposePassthrough:

    @pytest.mark.asyncio
    async def test_skip_when_disabled(self, base_state, mock_config):
        from harness.task.decomposer import task_decompose
        result = await task_decompose(base_state, mock_config)
        assert "task_decompose:skip" in result.get("history", [])

    @pytest.mark.asyncio
    async def test_state_unchanged_when_disabled(self, base_state, mock_config):
        from harness.task.decomposer import task_decompose
        result = await task_decompose(base_state, mock_config)
        assert result.get("task", {}).get("intents") is None


# ── Safety Gate (L6) via harness.safety.gate directly ──

class TestSafetyGatePassthrough:

    @pytest.mark.asyncio
    async def test_skip_when_disabled(self, base_state):
        from harness.safety.gate import safety_gate
        result = await safety_gate(base_state)
        assert "safety_gate:skip" in result.get("history", [])


class TestSafetyGateEnabled:

    @pytest.mark.asyncio
    async def test_detects_dangerous_keyword(self, base_state, monkeypatch):
        monkeypatch.setattr("harness.safety.gate.is_layer_enabled", lambda layer: True)
        monkeypatch.setattr(
            "harness.safety.gate.HARNESS_CONFIG",
            {"safety": {"dangerous_instruction_keywords": ["拆開電路板"]}},
        )
        base_state["question"] = "我想拆開電路板看看裡面"

        from harness.safety.gate import safety_gate
        result = await safety_gate(base_state)

        safety = result["safety"]
        assert safety["requires_approval"] is True
        assert any(r["keyword"] == "拆開電路板" for r in safety["flagged_risks"])

    @pytest.mark.asyncio
    async def test_detects_red_code(self, base_state, monkeypatch):
        monkeypatch.setattr("harness.safety.gate.is_layer_enabled", lambda layer: True)
        monkeypatch.setattr(
            "harness.safety.gate.HARNESS_CONFIG",
            {"safety": {"dangerous_instruction_keywords": []}},
        )
        base_state["question"] = "我被鎖在外面，小孩在裡面"

        from harness.safety.gate import safety_gate
        result = await safety_gate(base_state)
        assert result["safety"]["red_code"] is True
        assert "safety_gate:red_code" in result["history"]

    @pytest.mark.asyncio
    async def test_detects_high_risk_sentiment(self, base_state, monkeypatch):
        monkeypatch.setattr("harness.safety.gate.is_layer_enabled", lambda layer: True)
        monkeypatch.setattr(
            "harness.safety.gate.HARNESS_CONFIG",
            {"safety": {"dangerous_instruction_keywords": []}},
        )
        base_state["question"] = "太離譜了，我要投訴你們"

        from harness.safety.gate import safety_gate
        result = await safety_gate(base_state)
        assert result["safety"]["escalation_required"] is True
        assert "safety_gate:escalation" in result["history"]

    @pytest.mark.asyncio
    async def test_normal_passes(self, base_state, monkeypatch):
        monkeypatch.setattr("harness.safety.gate.is_layer_enabled", lambda layer: True)
        monkeypatch.setattr(
            "harness.safety.gate.HARNESS_CONFIG",
            {"safety": {"dangerous_instruction_keywords": []}},
        )
        base_state["question"] = "我的指紋按了沒反應"

        from harness.safety.gate import safety_gate
        result = await safety_gate(base_state)
        assert result["safety"]["requires_approval"] is False
        assert result["safety"]["red_code"] is False


# ── Knowledge Loader full integration ──

class TestKnowledgeLoaderIntegration:

    def test_full_tier1_context_size(self, knowledge_base_dir):
        from harness.task.knowledge_loader import KnowledgeLoader
        loader = KnowledgeLoader(knowledge_base_dir)

        symptoms = loader.get_symptom_taxonomy()
        failures = loader.get_failure_context()
        components = loader.get_component_graph()

        total_chars = len(symptoms) + len(failures) + len(components)
        est_tokens = total_chars // 4
        print(f"\nTier 1 context: {total_chars:,} chars, ~{est_tokens:,} tokens")
        assert est_tokens < 15000  # Budget

    def test_tier2_fault_tree_match(self, knowledge_base_dir):
        from harness.task.knowledge_loader import KnowledgeLoader
        loader = KnowledgeLoader(knowledge_base_dir)
        ft = loader.get_relevant_fault_trees(["false_alarm", "beeping_no_operation"])
        assert "FT-HW-003" in ft

    def test_cold_start_graceful(self, knowledge_base_dir):
        """No fault tree match → empty, but Tier 1 still works."""
        from harness.task.knowledge_loader import KnowledgeLoader
        loader = KnowledgeLoader(knowledge_base_dir)
        ft = loader.get_relevant_fault_trees(["nonexistent_xyz"])
        assert ft == "[]"
        assert len(loader.get_symptom_taxonomy()) > 0

    def test_cross_reference_integrity(self, knowledge_base_dir):
        """Flag symptom IDs in fault trees that are missing from taxonomy."""
        from harness.task.knowledge_loader import KnowledgeLoader
        loader = KnowledgeLoader(knowledge_base_dir)

        valid_ids = loader._valid_symptom_ids
        missing = []
        for ft in loader._fault_trees:
            for s in ft.get("required_symptoms", []) + ft.get("optional_symptoms", []):
                if s not in valid_ids:
                    missing.append(f"{ft['id']}:{s}")

        if missing:
            import warnings
            warnings.warn(
                f"Cross-reference gaps (need expert review): {missing}",
                UserWarning,
            )
        # Should have at least some valid references
        total_refs = sum(
            len(ft.get("required_symptoms", []) + ft.get("optional_symptoms", []))
            for ft in loader._fault_trees
        )
        assert total_refs > 0, "No fault tree symptom references found at all"
