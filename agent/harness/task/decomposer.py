"""L1 Task Decompose — Software 3.0 Diagnostic Reasoning Engine.

Orchestrates the diagnostic state machine:
  Python: load knowledge → assemble prompt → invoke LLM → validate → transition state
  LLM:    all diagnostic reasoning (PDCA in single structured output)

State machine (diagnostic_state_machine.py) enforces valid transitions
and guardrails. decomposer.py is the orchestrator that drives the machine.
"""

import json
from langchain_core.runnables import RunnableConfig

from agents import load_prompt_template
from core.config import SYSTEM_CONFIG, HARNESS_CONFIG
from graph.state import GraphState
from harness import is_layer_enabled
from harness.task.knowledge_loader import KnowledgeLoader
from harness.task.diagnostic_state_machine import (
    DiagnosticContext,
    DiagnosticState,
    resolve_next_state,
)

_task_config = HARNESS_CONFIG.get("task", {})
_knowledge_loader: KnowledgeLoader | None = None


def _get_loader() -> KnowledgeLoader:
    global _knowledge_loader
    if _knowledge_loader is None:
        base_dir = _task_config.get("knowledge_base_dir", "harness/task")
        _knowledge_loader = KnowledgeLoader(base_dir)
    return _knowledge_loader


async def task_decompose(state: GraphState, config: RunnableConfig) -> dict:
    """Software 3.0 diagnostic reasoning node with state machine.

    When disabled → pass-through.
    When enabled → load context → LLM reasoning → state transition → update GraphState.
    """
    if not is_layer_enabled("task"):
        return {"history": ["task_decompose:skip"]}

    loader = _get_loader()
    domain = SYSTEM_CONFIG.get("domain", "電子鎖")
    question = state.get("question", "")
    task_state = state.get("task", {})
    safety_result = state.get("safety", {})

    # ── Restore state machine context ──
    ctx = DiagnosticContext.from_dict(task_state.get("diagnostic_fsm", {}))

    # ── Safety override: check before any LLM call ──
    if safety_result.get("red_code") or safety_result.get("escalation_required"):
        ctx.force_escalation(
            "red_code" if safety_result.get("red_code") else "sentiment_escalation"
        )
        return {
            "history": [f"task_decompose:escalated:{ctx.current_state.value}"],
            "task": {
                **task_state,
                "diagnosis_status": "escalated",
                "diagnostic_fsm": ctx.to_dict(),
            },
        }

    # ── Tier 1: Always injected context ──
    symptom_taxonomy = loader.get_symptom_taxonomy()
    failure_context = loader.get_failure_context()
    component_graph = loader.get_component_graph()

    # ── Tier 2: Filtered by accumulated symptoms ──
    prev_symptoms = ctx.extracted_symptoms or []
    fault_trees = loader.get_relevant_fault_trees(prev_symptoms)

    # ── Conversation history ──
    messages = state.get("messages", [])
    conversation_history = "\n".join(
        f"{m.type}: {m.content}" for m in messages[-10:] if hasattr(m, "content")
    )

    # ── ProblemCard state ──
    problem_card = json.dumps(task_state.get("problem_card", {}), ensure_ascii=False, indent=2)

    # ── Assemble diagnostic reasoning prompt ──
    prompt = load_prompt_template(
        _task_config.get("diagnostic_prompt", "harness/task/prompts/diagnostic_reasoning.md"),
        domain=domain,
        symptom_taxonomy=symptom_taxonomy,
        failure_context=failure_context,
        component_graph=component_graph,
        fault_trees=fault_trees,
        conversation_history=conversation_history,
        problem_card=problem_card,
    )

    # ── LLM call ──
    cfg = config.get("configurable", {})
    llm = cfg.get("diagnostic_llm") or cfg.get("llm")
    if llm is None:
        return {"history": ["task_decompose:no_llm"], "task": task_state}

    response = await llm.ainvoke(prompt)
    raw = response.content if hasattr(response, "content") else str(response)

    # ── Parse structured JSON output ──
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        result = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        ctx.verification_round += 1
        return {
            "history": ["task_decompose:parse_error"],
            "task": {**task_state, "diagnostic_fsm": ctx.to_dict()},
        }

    # ── Validate symptom IDs ──
    extracted = loader.validate_symptom_ids(result.get("extracted_symptoms", []))
    result["extracted_symptoms"] = extracted

    # ── Update accumulated evidence in context ──
    if extracted:
        # Merge new symptoms with existing (deduplicate)
        all_symptoms = list(dict.fromkeys(ctx.extracted_symptoms + extracted))
        ctx.extracted_symptoms = all_symptoms

    ctx.matched_failures = result.get("matched_failures", ctx.matched_failures)
    ctx.hypothesized_fms = result.get("hypothesized_failure_modes", ctx.hypothesized_fms)

    # Check if LLM detected dispatch signal (brand error codes)
    next_action = result.get("next_action", {})
    if next_action.get("type") == "recommend_dispatch":
        ctx.dispatch_signal_detected = True

    # ── State machine transition ──
    llm_status = result.get("diagnosis_status", "need_more_info")
    target_state = resolve_next_state(ctx, llm_status, safety_result)

    if ctx.current_state == DiagnosticState.INTAKE and extracted:
        # First round: intake → symptom_collected → target
        ctx.transition(DiagnosticState.SYMPTOM_COLLECTED, "symptoms extracted")
        if result.get("matched_failures"):
            ctx.transition(DiagnosticState.FAILURE_IDENTIFIED, "failure matched")

    # Transition to target (may skip intermediate states)
    transitioned = ctx.transition(target_state, f"llm:{llm_status}")
    if not transitioned:
        # If direct transition not valid, try intermediate steps
        if target_state == DiagnosticState.CONCLUSION_READY:
            ctx.transition(DiagnosticState.HYPOTHESIS_FORMED, "intermediate")
            ctx.transition(DiagnosticState.CONCLUSION_READY, f"llm:{llm_status}")
        elif target_state == DiagnosticState.DISPATCH_RECOMMENDED:
            ctx.transition(DiagnosticState.DISPATCH_RECOMMENDED, f"llm:{llm_status}")

    # Track verification rounds
    if ctx.current_state == DiagnosticState.VERIFYING:
        ctx.verification_round += 1
        if next_action.get("question"):
            ctx.verification_answers.append({
                "round": ctx.verification_round,
                "question_asked": next_action["question"],
            })

    # ── Build diagnostic context for agent prompt injection ──
    diagnostic_context = json.dumps(
        {
            "state": ctx.current_state.value,
            "verification_round": ctx.verification_round,
            "hypothesized_failure_modes": ctx.hypothesized_fms,
            "next_action": next_action,
            "corrective_action_immediate": result.get("corrective_action_immediate", ""),
            "diagnosis_status": ctx.current_state.value,
            "shared_dependency": result.get("shared_dependency_detected", {}),
            "state_history": ctx.state_history,
        },
        ensure_ascii=False,
        indent=2,
    )

    # ── Update task state ──
    updated_pc = result.get("updated_problem_card", {})
    new_task = {
        **task_state,
        "extracted_symptoms": ctx.extracted_symptoms,
        "matched_failures": ctx.matched_failures,
        "diagnosis_status": ctx.current_state.value,
        "diagnostic_round": ctx.verification_round,
        "diagnostic_context": diagnostic_context,
        "diagnostic_fsm": ctx.to_dict(),
        "problem_card": {**task_state.get("problem_card", {}), **updated_pc},
    }

    state_val = ctx.current_state.value
    return {
        "history": [f"task_decompose:round_{ctx.verification_round}:{state_val}"],
        "task": new_task,
    }
