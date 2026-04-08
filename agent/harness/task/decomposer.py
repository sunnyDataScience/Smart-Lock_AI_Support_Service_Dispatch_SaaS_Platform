"""L1 Task Decompose — Software 3.0 Diagnostic Reasoning Engine.

Orchestrates the diagnostic state machine:
  Python: load knowledge → assemble prompt → invoke LLM → validate → transition state
  LLM:    all diagnostic reasoning (PDCA in single structured output)

State machine (diagnostic_state_machine.py) enforces valid transitions
and guardrails. decomposer.py is the orchestrator that drives the machine.
"""

import json
from uuid import uuid4
from langchain_core.runnables import RunnableConfig

from agents import load_prompt_template
from core.config import SYSTEM_CONFIG, HARNESS_CONFIG, LLM_CONFIG
from graph.state import GraphState
from llms import get_llm
from harness import is_layer_enabled
from harness.task.knowledge_loader import KnowledgeLoader
from domain.problem_card import (
    ProblemCard, CardStatus, calculate_completeness,
)
from domain.diagnostic_state_machine import (
    DiagnosticContext,
    DiagnosticState,
    resolve_next_state,
)

_task_config = HARNESS_CONFIG.get("task", {})
_knowledge_loader: KnowledgeLoader | None = None
_llm = get_llm(LLM_CONFIG)


def _get_loader() -> KnowledgeLoader:
    global _knowledge_loader
    if _knowledge_loader is None:
        base_dir = _task_config.get("knowledge_base_dir", "harness/task")
        _knowledge_loader = KnowledgeLoader(base_dir)
    return _knowledge_loader


def _dict_to_problem_card(d: dict) -> ProblemCard:
    """Reconstruct ProblemCard from dict stored in GraphState."""
    card = ProblemCard(
        card_id=d.get("card_id", ""),
        user_id=d.get("user_id", ""),
        symptom_summary=d.get("symptom_summary", ""),
        category=d.get("category", ""),
        completeness_score=d.get("completeness_score", 0.0),
        domain_attributes=d.get("domain_attributes", {}),
    )
    if d.get("status"):
        try:
            card.status = CardStatus(d["status"])
        except ValueError:
            pass
    card.attempts = d.get("attempts", [])
    card.resolution_summary = d.get("resolution_summary", "")
    card.resolution_level = d.get("resolution_level", "")
    card.diagnosis_status = d.get("diagnosis_status", "")
    card.diagnostic_round = d.get("diagnostic_round", 0)
    card.confidence_score = d.get("confidence_score", 0.0)
    card.is_novel = d.get("is_novel", False)
    card.sop_generated = d.get("sop_generated", False)
    return card


def _problem_card_to_dict(card: ProblemCard) -> dict:
    """Serialize ProblemCard to dict for GraphState storage."""
    return {
        "card_id": card.card_id,
        "user_id": card.user_id,
        "created_at": card.created_at.isoformat() if hasattr(card.created_at, "isoformat") else str(card.created_at),
        "status": card.status.value if isinstance(card.status, CardStatus) else card.status,
        "symptom_summary": card.symptom_summary,
        "category": card.category,
        "completeness_score": card.completeness_score,
        "domain_attributes": card.domain_attributes,
        "attempts": card.attempts,
        "resolution_summary": card.resolution_summary,
        "resolution_level": card.resolution_level,
        "diagnosis_status": card.diagnosis_status,
        "diagnostic_round": card.diagnostic_round,
        "confidence_score": card.confidence_score,
        "is_novel": card.is_novel,
        "sop_generated": card.sop_generated,
    }


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

    # ── Restore or create ProblemCard ──
    pc_dict = task_state.get("problem_card", {})
    if pc_dict.get("card_id"):
        pc = _dict_to_problem_card(pc_dict)
    else:
        cfg = config.get("configurable", {})
        user_id = cfg.get("user_id") or cfg.get("thread_id", "anonymous")
        pc = ProblemCard(
            card_id=f"pc_{uuid4().hex[:8]}",
            user_id=user_id,
            status=CardStatus.DIAGNOSING,
        )
        print(f"  [task_decompose] 建立 ProblemCard: {pc.card_id}")

    # ── Safety override: check before any LLM call ──
    if safety_result.get("red_code") or safety_result.get("escalation_required"):
        ctx.force_escalation(
            "red_code" if safety_result.get("red_code") else "sentiment_escalation"
        )
        pc.status = CardStatus.ESCALATED
        return {
            "history": [f"task_decompose:escalated:{ctx.current_state.value}"],
            "task": {
                **task_state,
                "diagnosis_status": "escalated",
                "diagnostic_fsm": ctx.to_dict(),
                "problem_card": _problem_card_to_dict(pc),
            },
        }

    # ── Tier 1: Always injected context (with brand-specific overrides) ──
    symptom_taxonomy = loader.get_symptom_taxonomy()
    failure_context = loader.get_failure_context()
    brand = pc.domain_attributes.get("device_brand", "")
    component_graph = loader.get_component_graph(brand=brand)

    # ── Tier 2: Filtered by accumulated symptoms ──
    prev_symptoms = ctx.extracted_symptoms or []
    fault_trees = loader.get_relevant_fault_trees(prev_symptoms)

    # ── Conversation history ──
    messages = state.get("messages", [])
    conversation_history = "\n".join(
        f"{m.type}: {m.content}" for m in messages[-10:] if hasattr(m, "content")
    )

    # ── Assemble diagnostic reasoning prompt ──
    prompt = load_prompt_template(
        _task_config.get("diagnostic_prompt", "harness/task/prompts/diagnostic_reasoning.md"),
        domain=domain,
        symptom_taxonomy=symptom_taxonomy,
        failure_context=failure_context,
        component_graph=component_graph,
        fault_trees=fault_trees,
        conversation_history=conversation_history,
        problem_card=json.dumps(_problem_card_to_dict(pc), ensure_ascii=False, indent=2),
    )

    # ── LLM call ──
    response = await _llm.ainvoke(prompt)
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
            "task": {
                **task_state,
                "diagnostic_fsm": ctx.to_dict(),
                "problem_card": _problem_card_to_dict(pc),
            },
        }

    # ── Non-hardware early exit: let router handle via RAG ──
    if result.get("is_hardware_fault") is False:
        intent_classification = result.get("intent_classification", [])
        print(f"  [task_decompose] 非硬體故障，意圖={intent_classification}")
        return {
            "history": ["task_decompose:not_hardware"],
            "task": {
                **task_state,
                "diagnosis_status": "",
                "intents": intent_classification,
                "problem_card": _problem_card_to_dict(pc),
            },
        }

    # ── Merge LLM output into ProblemCard ──
    updated_pc = result.get("updated_problem_card", {})
    if updated_pc.get("symptom_summary"):
        pc.symptom_summary = updated_pc["symptom_summary"]
    if updated_pc.get("category"):
        pc.category = updated_pc["category"]
    for key, val in updated_pc.get("domain_attributes", {}).items():
        if val and str(val).strip() and val not in ("unknown", "empty", ""):
            pc.domain_attributes[key] = val
    pc.completeness_score = calculate_completeness(pc)
    print(f"  [task_decompose] ProblemCard completeness: {pc.completeness_score}")

    # ── Validate symptom IDs ──
    extracted = loader.validate_symptom_ids(result.get("extracted_symptoms", []))
    result["extracted_symptoms"] = extracted

    # ── Update accumulated evidence in context ──
    if extracted:
        all_symptoms = list(dict.fromkeys(ctx.extracted_symptoms + extracted))
        ctx.extracted_symptoms = all_symptoms

    ctx.matched_failures = result.get("matched_failures", ctx.matched_failures)
    ctx.hypothesized_fms = result.get("hypothesized_failure_modes", ctx.hypothesized_fms)

    # Accumulate confidence score
    conf_update = result.get("confidence_update", {})
    if conf_update.get("confidence_gain"):
        ctx.confidence_score += conf_update["confidence_gain"]
        print(f"  [task_decompose] confidence: +{conf_update['confidence_gain']:.2f} "
              f"→ {ctx.confidence_score:.2f}/{ctx.confidence_threshold}")

    # Check if LLM detected dispatch signal (brand error codes)
    next_action = result.get("next_action", {})
    if next_action.get("type") == "recommend_dispatch":
        ctx.dispatch_signal_detected = True

    # ── State machine transition ──
    llm_status = result.get("diagnosis_status", "need_more_info")
    target_state = resolve_next_state(ctx, llm_status, safety_result)

    if ctx.current_state == DiagnosticState.INTAKE and extracted:
        ctx.transition(DiagnosticState.SYMPTOM_COLLECTED, "symptoms extracted")
        if result.get("matched_failures"):
            ctx.transition(DiagnosticState.FAILURE_IDENTIFIED, "failure matched")

    transitioned = ctx.transition(target_state, f"llm:{llm_status}")
    if not transitioned:
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
            "corrective_action_steps": result.get("corrective_action_steps", []),
            "dispatch_required": result.get("dispatch_required", False),
            "dispatch_reason": result.get("dispatch_reason", ""),
            "diagnosis_status": ctx.current_state.value,
            "shared_dependency": result.get("shared_dependency_detected", {}),
            "state_history": ctx.state_history,
        },
        ensure_ascii=False,
        indent=2,
    )

    # ── Update task state ──
    intent_classification = result.get("intent_classification", ["hardware_tech"])
    new_task = {
        **task_state,
        "extracted_symptoms": ctx.extracted_symptoms,
        "matched_failures": ctx.matched_failures,
        "hypothesized_failure_modes": ctx.hypothesized_fms,
        "diagnosis_status": ctx.current_state.value,
        "diagnostic_round": ctx.verification_round,
        "diagnostic_context": diagnostic_context,
        "diagnostic_fsm": ctx.to_dict(),
        "problem_card": _problem_card_to_dict(pc),
        "intents": intent_classification,
    }

    # Populate diagnostic progress before persisting
    pc.diagnosis_status = ctx.current_state.value
    pc.diagnostic_round = ctx.verification_round
    pc.confidence_score = ctx.confidence_score

    # Fire-and-forget: persist ProblemCard to PostgreSQL
    import asyncio
    asyncio.create_task(_save_pc_background(pc))

    state_val = ctx.current_state.value
    return {
        "history": [f"task_decompose:round_{ctx.verification_round}:{state_val}"],
        "task": new_task,
    }


async def _save_pc_background(pc: ProblemCard) -> None:
    """Non-blocking ProblemCard persistence."""
    try:
        from domain.problem_card import save_problem_card
        await save_problem_card(pc)
    except Exception as e:
        print(f"  [task_decompose] ProblemCard 持久化失敗（非致命）: {e}")
