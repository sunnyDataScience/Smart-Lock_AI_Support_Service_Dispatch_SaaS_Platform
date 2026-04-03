"""Unit tests for diagnostic state machine."""

import pytest

from harness.task.diagnostic_state_machine import (
    DiagnosticContext,
    DiagnosticState,
    resolve_next_state,
    VALID_TRANSITIONS,
)


# ── State transition tests ──

class TestDiagnosticContext:

    def test_initial_state(self):
        ctx = DiagnosticContext()
        assert ctx.current_state == DiagnosticState.INTAKE
        assert ctx.verification_round == 0
        assert ctx.state_history == []

    def test_valid_transition(self):
        ctx = DiagnosticContext()
        ok = ctx.transition(DiagnosticState.SYMPTOM_COLLECTED, "test")
        assert ok is True
        assert ctx.current_state == DiagnosticState.SYMPTOM_COLLECTED
        assert "intake→symptom_collected" in ctx.state_history[0]

    def test_invalid_transition_rejected(self):
        ctx = DiagnosticContext()
        # Can't go directly from INTAKE to CONCLUSION_READY
        ok = ctx.transition(DiagnosticState.CONCLUSION_READY, "skip")
        assert ok is False
        assert ctx.current_state == DiagnosticState.INTAKE

    def test_force_escalation(self):
        ctx = DiagnosticContext()
        ctx.transition(DiagnosticState.SYMPTOM_COLLECTED)
        ctx.transition(DiagnosticState.FAILURE_IDENTIFIED)
        ctx.force_escalation("red_code")
        assert ctx.current_state == DiagnosticState.ESCALATED
        assert "forced: red_code" in ctx.state_history[-1]

    def test_closed_is_terminal(self):
        ctx = DiagnosticContext()
        ctx.current_state = DiagnosticState.CLOSED
        ok = ctx.transition(DiagnosticState.INTAKE, "reopen")
        assert ok is False
        assert ctx.current_state == DiagnosticState.CLOSED


class TestVerificationLoop:

    def test_verifying_can_loop(self):
        """VERIFYING → VERIFYING is a valid self-transition."""
        ctx = DiagnosticContext()
        ctx.current_state = DiagnosticState.VERIFYING
        ok = ctx.transition(DiagnosticState.VERIFYING, "next question")
        assert ok is True
        assert ctx.current_state == DiagnosticState.VERIFYING

    def test_verifying_to_conclusion(self):
        ctx = DiagnosticContext()
        ctx.current_state = DiagnosticState.VERIFYING
        ok = ctx.transition(DiagnosticState.CONCLUSION_READY, "enough info")
        assert ok is True

    def test_verifying_to_dispatch(self):
        ctx = DiagnosticContext()
        ctx.current_state = DiagnosticState.VERIFYING
        ok = ctx.transition(DiagnosticState.DISPATCH_RECOMMENDED, "3-round limit")
        assert ok is True


class TestFullDiagnosticFlow:

    def test_happy_path_remote_resolved(self):
        """INTAKE → SYMPTOM → FAILURE → HYPOTHESIS → VERIFY → CONCLUSION → RESOLVED → CLOSED"""
        ctx = DiagnosticContext()
        assert ctx.transition(DiagnosticState.SYMPTOM_COLLECTED, "symptoms extracted")
        assert ctx.transition(DiagnosticState.FAILURE_IDENTIFIED, "failure matched")
        assert ctx.transition(DiagnosticState.HYPOTHESIS_FORMED, "FM hypotheses")
        assert ctx.transition(DiagnosticState.VERIFYING, "ask question")
        assert ctx.transition(DiagnosticState.CONCLUSION_READY, "enough info")
        assert ctx.transition(DiagnosticState.REMOTE_RESOLVED, "user confirmed")
        assert ctx.transition(DiagnosticState.CLOSED, "finalized")
        assert len(ctx.state_history) == 7

    def test_dispatch_path(self):
        """INTAKE → SYMPTOM → FAILURE → HYPOTHESIS → DISPATCH → CLOSED"""
        ctx = DiagnosticContext()
        ctx.transition(DiagnosticState.SYMPTOM_COLLECTED)
        ctx.transition(DiagnosticState.FAILURE_IDENTIFIED)
        ctx.transition(DiagnosticState.HYPOTHESIS_FORMED)
        assert ctx.transition(DiagnosticState.DISPATCH_RECOMMENDED, "brand error code")
        assert ctx.transition(DiagnosticState.CLOSED)

    def test_escalation_from_any_state(self):
        """force_escalation works from any non-CLOSED state."""
        for state in DiagnosticState:
            if state == DiagnosticState.CLOSED:
                continue
            ctx = DiagnosticContext()
            ctx.current_state = state
            ctx.force_escalation("test")
            assert ctx.current_state == DiagnosticState.ESCALATED


# ── Serialization tests ──

class TestSerialization:

    def test_round_trip(self):
        ctx = DiagnosticContext()
        ctx.transition(DiagnosticState.SYMPTOM_COLLECTED)
        ctx.extracted_symptoms = ["fingerprint_fail", "low_battery_alarm"]
        ctx.verification_round = 2
        ctx.red_code = True

        data = ctx.to_dict()
        restored = DiagnosticContext.from_dict(data)

        assert restored.current_state == DiagnosticState.SYMPTOM_COLLECTED
        assert restored.extracted_symptoms == ["fingerprint_fail", "low_battery_alarm"]
        assert restored.verification_round == 2
        assert restored.red_code is True
        assert len(restored.state_history) == 1

    def test_from_empty_dict(self):
        ctx = DiagnosticContext.from_dict({})
        assert ctx.current_state == DiagnosticState.INTAKE

    def test_from_none(self):
        ctx = DiagnosticContext.from_dict(None)
        assert ctx.current_state == DiagnosticState.INTAKE


# ── resolve_next_state tests ──

class TestResolveNextState:

    def test_red_code_overrides_everything(self):
        ctx = DiagnosticContext()
        state = resolve_next_state(ctx, "ready_to_conclude", {"red_code": True})
        assert state == DiagnosticState.ESCALATED

    def test_escalation_overrides(self):
        ctx = DiagnosticContext()
        state = resolve_next_state(ctx, "need_more_info", {"escalation_required": True})
        assert state == DiagnosticState.ESCALATED

    def test_dispatch_signal(self):
        ctx = DiagnosticContext()
        ctx.dispatch_signal_detected = True
        state = resolve_next_state(ctx, "hypothesis_formed")
        assert state == DiagnosticState.DISPATCH_RECOMMENDED

    def test_round_limit_forces_dispatch(self):
        ctx = DiagnosticContext()
        ctx.verification_round = 3
        ctx.max_verification_rounds = 3
        state = resolve_next_state(ctx, "need_more_info")
        assert state == DiagnosticState.DISPATCH_RECOMMENDED

    def test_llm_status_mapping(self):
        ctx = DiagnosticContext()
        assert resolve_next_state(ctx, "need_more_info") == DiagnosticState.VERIFYING
        assert resolve_next_state(ctx, "hypothesis_formed") == DiagnosticState.HYPOTHESIS_FORMED
        assert resolve_next_state(ctx, "ready_to_conclude") == DiagnosticState.CONCLUSION_READY
        assert resolve_next_state(ctx, "recommend_dispatch") == DiagnosticState.DISPATCH_RECOMMENDED

    def test_unknown_status_defaults_verifying(self):
        ctx = DiagnosticContext()
        state = resolve_next_state(ctx, "some_unknown_status")
        assert state == DiagnosticState.VERIFYING


# ── Transition graph completeness ──

class TestTransitionGraph:

    def test_all_states_have_transitions_defined(self):
        """Every state should appear as a key in VALID_TRANSITIONS."""
        for state in DiagnosticState:
            assert state in VALID_TRANSITIONS, f"{state} missing from VALID_TRANSITIONS"

    def test_closed_has_no_transitions(self):
        assert VALID_TRANSITIONS[DiagnosticState.CLOSED] == []

    def test_no_transition_to_intake(self):
        """INTAKE should never be a transition target (it's the initial state only)."""
        for source, targets in VALID_TRANSITIONS.items():
            assert DiagnosticState.INTAKE not in targets, \
                f"{source} → INTAKE should not be allowed"
