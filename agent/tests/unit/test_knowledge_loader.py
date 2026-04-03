"""Unit tests for WBS 2.0 — KnowledgeLoader (L1 foundation)."""

import pytest

from harness.task.knowledge_loader import KnowledgeLoader


@pytest.fixture
def loader(knowledge_base_dir):
    return KnowledgeLoader(knowledge_base_dir)


class TestKnowledgeLoaderInit:
    def test_loads_symptoms(self, loader):
        assert loader.symptom_count > 0

    def test_loads_failure_modes(self, loader):
        assert loader.failure_mode_count > 0

    def test_loads_fault_trees(self, loader):
        assert loader.fault_tree_count >= 1


class TestTier1Context:
    def test_symptom_taxonomy_not_empty(self, loader):
        text = loader.get_symptom_taxonomy()
        assert len(text) > 100
        assert "aliases:" in text

    def test_failure_context_has_failures_and_modes(self, loader):
        text = loader.get_failure_context()
        assert "failures" in text
        assert "failure_modes" in text
        assert "F-LOCK-" in text

    def test_component_graph_has_topology(self, loader):
        text = loader.get_component_graph()
        assert len(text) > 50


class TestTier2Filtering:
    def test_relevant_fault_trees_with_matching_symptoms(self, loader):
        """Should return fault trees when symptoms overlap."""
        result = loader.get_relevant_fault_trees(["false_alarm", "beeping_no_operation"])
        assert result != "[]"
        assert "FT-HW-003" in result

    def test_relevant_fault_trees_no_match(self, loader):
        result = loader.get_relevant_fault_trees(["nonexistent_symptom"])
        assert result == "[]"

    def test_relevant_fault_trees_empty_input(self, loader):
        result = loader.get_relevant_fault_trees([])
        assert result == "[]"


class TestSOPLookup:
    def test_get_sop_hardware_fault(self, loader):
        result = loader.get_sop("hardware_fault")
        assert "SOP-HW-001" in result

    def test_get_sop_nonexistent(self, loader):
        result = loader.get_sop("nonexistent_category")
        assert result == "{}"


class TestValidation:
    def test_validate_valid_ids(self, loader):
        """Valid symptom IDs should pass through."""
        # Use IDs from the actual taxonomy
        all_ids = list(loader._valid_symptom_ids)[:3]
        result = loader.validate_symptom_ids(all_ids)
        assert result == all_ids

    def test_validate_filters_invalid(self, loader):
        valid_id = list(loader._valid_symptom_ids)[0] if loader._valid_symptom_ids else "test"
        result = loader.validate_symptom_ids([valid_id, "fake_symptom", "another_fake"])
        assert "fake_symptom" not in result
        assert "another_fake" not in result

    def test_validate_empty_input(self, loader):
        result = loader.validate_symptom_ids([])
        assert result == []
