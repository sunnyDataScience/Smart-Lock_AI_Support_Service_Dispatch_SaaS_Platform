"""Diagnostic State Machine — manages cross-turn diagnostic flow.

Defines the valid state transitions for diagnostic reasoning,
enforces guardrails, and orchestrates the PDCA lifecycle.

States follow the four-layer causal chain:
  Symptom → Failure → Failure Mode → Defect (to-be-confirmed)

Each state has:
  - entry conditions (what must be true to enter)
  - allowed transitions (where you can go next)
  - exit actions (what happens on transition)
  - guardrails (what prevents incorrect transitions)

The state machine is data-driven (no hardcoded if/else trees).
Transitions are triggered by LLM diagnosis_status output + Python safety nets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Diagnostic States ──

class DiagnosticState(str, Enum):
    """States in the diagnostic PDCA lifecycle."""

    # ── PLAN phase ──
    INTAKE = "intake"
    """Initial state. User message received, no analysis yet."""

    SYMPTOM_COLLECTED = "symptom_collected"
    """Symptoms extracted from user message. Mapped to taxonomy IDs."""

    FAILURE_IDENTIFIED = "failure_identified"
    """Failure type identified (e.g., F-LOCK-001). May have multiple candidates."""

    # ── DO phase ──
    HYPOTHESIS_FORMED = "hypothesis_formed"
    """Failure Mode hypothesis generated with ranked candidates.
    Verification chain available for further narrowing."""

    VERIFYING = "verifying"
    """Actively asking verification questions to narrow hypothesis.
    Each round updates hypothesis confidence."""

    # ── CHECK phase ──
    CONCLUSION_READY = "conclusion_ready"
    """Sufficient information to provide diagnosis + corrective action.
    May still recommend on-site confirmation."""

    # ── ACT phase ──
    REMOTE_RESOLVED = "remote_resolved"
    """Issue resolved remotely (user confirmed fix worked)."""

    DISPATCH_RECOMMENDED = "dispatch_recommended"
    """Remote diagnosis inconclusive or confirms need for on-site service."""

    ESCALATED = "escalated"
    """Transferred to human agent (Red_Code, sentiment, or 3-round limit)."""

    # ── Terminal ──
    CLOSED = "closed"
    """Case closed. ProblemCard finalized. Ready for knowledge loop."""


# ── Transition Rules ──

# fmt: off
VALID_TRANSITIONS: dict[DiagnosticState, list[DiagnosticState]] = {
    DiagnosticState.INTAKE: [
        DiagnosticState.SYMPTOM_COLLECTED,   # LLM extracted symptoms
        DiagnosticState.ESCALATED,           # Red_Code / sentiment trigger
    ],
    DiagnosticState.SYMPTOM_COLLECTED: [
        DiagnosticState.FAILURE_IDENTIFIED,  # Mapped symptoms to Failure
        DiagnosticState.VERIFYING,           # Need more info (symptoms too vague)
        DiagnosticState.ESCALATED,           # Red_Code
    ],
    DiagnosticState.FAILURE_IDENTIFIED: [
        DiagnosticState.HYPOTHESIS_FORMED,   # FM hypotheses generated
        DiagnosticState.VERIFYING,           # Need verification to narrow FM
        DiagnosticState.ESCALATED,           # Red_Code
    ],
    DiagnosticState.HYPOTHESIS_FORMED: [
        DiagnosticState.VERIFYING,           # Start verification chain
        DiagnosticState.CONCLUSION_READY,    # High confidence, skip verification
        DiagnosticState.DISPATCH_RECOMMENDED,# Dispatch signal detected (e.g., red LED x4)
        DiagnosticState.ESCALATED,           # Red_Code
    ],
    DiagnosticState.VERIFYING: [
        DiagnosticState.VERIFYING,           # Next verification question (loop)
        DiagnosticState.HYPOTHESIS_FORMED,   # Updated hypothesis after answer
        DiagnosticState.CONCLUSION_READY,    # Enough info after verification
        DiagnosticState.DISPATCH_RECOMMENDED,# 3-round limit or dispatch signal
        DiagnosticState.ESCALATED,           # Red_Code / sentiment
    ],
    DiagnosticState.CONCLUSION_READY: [
        DiagnosticState.REMOTE_RESOLVED,     # User confirms fix worked
        DiagnosticState.DISPATCH_RECOMMENDED,# User requests on-site
        DiagnosticState.VERIFYING,           # User provides new info that changes diagnosis
        DiagnosticState.ESCALATED,           # Sentiment escalation
    ],
    DiagnosticState.REMOTE_RESOLVED: [
        DiagnosticState.CLOSED,              # Finalize
    ],
    DiagnosticState.DISPATCH_RECOMMENDED: [
        DiagnosticState.CLOSED,              # After dispatch arranged
    ],
    DiagnosticState.ESCALATED: [
        DiagnosticState.CLOSED,              # After human handles
    ],
    DiagnosticState.CLOSED: [],              # Terminal
}
# fmt: on


# ── Mapping from LLM diagnosis_status to state ──

LLM_STATUS_TO_STATE: dict[str, DiagnosticState] = {
    "need_more_info": DiagnosticState.VERIFYING,
    "hypothesis_formed": DiagnosticState.HYPOTHESIS_FORMED,
    "ready_to_conclude": DiagnosticState.CONCLUSION_READY,
    "recommend_dispatch": DiagnosticState.DISPATCH_RECOMMENDED,
}


# ── State Context (carried in GraphState["task"]) ──

@dataclass
class DiagnosticContext:
    """Tracks the diagnostic state machine context across turns.

    Serialized to/from GraphState["task"]["diagnostic_fsm"].
    """

    current_state: DiagnosticState = DiagnosticState.INTAKE
    verification_round: int = 0
    max_verification_rounds: int = 3
    state_history: list[str] = field(default_factory=list)

    # Accumulated evidence
    extracted_symptoms: list[str] = field(default_factory=list)
    matched_failures: list[str] = field(default_factory=list)
    hypothesized_fms: list[dict] = field(default_factory=list)
    verification_answers: list[dict] = field(default_factory=list)

    # Confidence accumulation
    confidence_score: float = 0.0
    confidence_threshold: float = 0.75

    # Flags
    red_code: bool = False
    escalation_required: bool = False
    dispatch_signal_detected: bool = False

    def transition(self, new_state: DiagnosticState, reason: str = "") -> bool:
        """Attempt a state transition. Returns True if valid, False if rejected."""
        allowed = VALID_TRANSITIONS.get(self.current_state, [])
        if new_state not in allowed:
            return False

        old = self.current_state.value
        self.current_state = new_state
        entry = f"{old}→{new_state.value}"
        if reason:
            entry += f" ({reason})"
        self.state_history.append(entry)
        return True

    def force_escalation(self, reason: str) -> None:
        """Force transition to ESCALATED regardless of current state (Red_Code / safety)."""
        if self.current_state != DiagnosticState.CLOSED:
            old = self.current_state.value
            self.current_state = DiagnosticState.ESCALATED
            self.state_history.append(f"{old}→escalated (forced: {reason})")

    def to_dict(self) -> dict:
        """Serialize for GraphState["task"]["diagnostic_fsm"]."""
        return {
            "current_state": self.current_state.value,
            "verification_round": self.verification_round,
            "max_verification_rounds": self.max_verification_rounds,
            "state_history": self.state_history,
            "extracted_symptoms": self.extracted_symptoms,
            "matched_failures": self.matched_failures,
            "hypothesized_fms": self.hypothesized_fms,
            "verification_answers": self.verification_answers,
            "confidence_score": self.confidence_score,
            "confidence_threshold": self.confidence_threshold,
            "red_code": self.red_code,
            "escalation_required": self.escalation_required,
            "dispatch_signal_detected": self.dispatch_signal_detected,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DiagnosticContext:
        """Deserialize from GraphState["task"]["diagnostic_fsm"]."""
        if not data:
            return cls()
        ctx = cls()
        ctx.current_state = DiagnosticState(data.get("current_state", "intake"))
        ctx.verification_round = data.get("verification_round", 0)
        ctx.max_verification_rounds = data.get("max_verification_rounds", 3)
        ctx.state_history = data.get("state_history", [])
        ctx.extracted_symptoms = data.get("extracted_symptoms", [])
        ctx.matched_failures = data.get("matched_failures", [])
        ctx.hypothesized_fms = data.get("hypothesized_fms", [])
        ctx.verification_answers = data.get("verification_answers", [])
        ctx.confidence_score = data.get("confidence_score", 0.0)
        ctx.confidence_threshold = data.get("confidence_threshold", 0.75)
        ctx.red_code = data.get("red_code", False)
        ctx.escalation_required = data.get("escalation_required", False)
        ctx.dispatch_signal_detected = data.get("dispatch_signal_detected", False)
        return ctx


def resolve_next_state(
    ctx: DiagnosticContext,
    llm_status: str,
    safety_result: dict | None = None,
) -> DiagnosticState:
    """Determine the next state based on LLM output + safety gate + guardrails.

    Priority order:
    1. Red_Code / escalation (safety gate) → ESCALATED
    2. Dispatch signal (LLM detected brand error code) → DISPATCH_RECOMMENDED
    3. Confidence threshold reached → CONCLUSION_READY
    4. Verification round limit → DISPATCH_RECOMMENDED
    5. LLM diagnosis_status → mapped state
    6. Default → VERIFYING (need more info)
    """
    # 1. Safety override
    if safety_result:
        if safety_result.get("red_code"):
            ctx.red_code = True
            return DiagnosticState.ESCALATED
        if safety_result.get("escalation_required"):
            ctx.escalation_required = True
            return DiagnosticState.ESCALATED

    # 2. Dispatch signal from LLM
    if llm_status == "recommend_dispatch" or ctx.dispatch_signal_detected:
        return DiagnosticState.DISPATCH_RECOMMENDED

    # 3. Confidence threshold reached
    if ctx.confidence_score >= ctx.confidence_threshold and llm_status == "need_more_info":
        return DiagnosticState.CONCLUSION_READY

    # 4. Verification round limit
    if ctx.verification_round >= ctx.max_verification_rounds and llm_status == "need_more_info":
        return DiagnosticState.DISPATCH_RECOMMENDED

    # 4. LLM status mapping
    if llm_status in LLM_STATUS_TO_STATE:
        return LLM_STATUS_TO_STATE[llm_status]

    # 5. Default
    return DiagnosticState.VERIFYING
