"""L1 Task Decompose — Software 3.0 Diagnostic Reasoning Engine.

Loads structured knowledge assets, assembles diagnostic prompt context,
invokes LLM for PDCA reasoning, validates output, updates GraphState.

Python does: load + filter + serialize + validate + orchestrate.
LLM does:    all diagnostic reasoning (symptom matching, hypothesis
             generation, verification question selection, confidence assessment).
"""

import json
from langchain_core.runnables import RunnableConfig

from agents import load_prompt_template
from core.config import SYSTEM_CONFIG, HARNESS_CONFIG
from graph.state import GraphState
from harness import is_layer_enabled
from harness.task.knowledge_loader import KnowledgeLoader
from harness.task.problem_card import get_domain_schema

# Module-level knowledge loader (loaded once at import time)
_task_config = HARNESS_CONFIG.get("task", {})
_knowledge_loader: KnowledgeLoader | None = None

MAX_DIAGNOSTIC_ROUNDS = 3


def _get_loader() -> KnowledgeLoader:
    """Lazy-init knowledge loader."""
    global _knowledge_loader
    if _knowledge_loader is None:
        base_dir = _task_config.get("knowledge_base_dir", "harness/task")
        _knowledge_loader = KnowledgeLoader(base_dir)
    return _knowledge_loader


def _is_diagnostic_intent(intents: list[str]) -> bool:
    """Check if any intent is eligible for diagnostic reasoning."""
    diagnostic = set(_task_config.get("diagnostic_intents", ["hardware_tech"]))
    return bool(set(intents) & diagnostic)


async def task_decompose(state: GraphState, config: RunnableConfig) -> dict:
    """Software 3.0 diagnostic reasoning node.

    When disabled, acts as pass-through (zero impact on existing flow).
    When enabled, loads knowledge → assembles prompt → LLM reasons → updates state.
    """
    if not is_layer_enabled("task"):
        return {"history": ["task_decompose:skip"]}

    loader = _get_loader()
    domain = SYSTEM_CONFIG.get("domain", "電子鎖")
    question = state.get("question", "")
    task_state = state.get("task", {})
    diagnostic_round = task_state.get("diagnostic_round", 0)

    # ─�� Tier 1: Always injected context ──
    symptom_taxonomy = loader.get_symptom_taxonomy()
    failure_context = loader.get_failure_context()
    component_graph = loader.get_component_graph()

    # ── Tier 2: Filtered by previous round's symptoms ──
    prev_symptoms = task_state.get("extracted_symptoms", [])
    fault_trees = loader.get_relevant_fault_trees(prev_symptoms)

    # ── Conversation history (last N messages for context) ──
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

    # ── LLM call: single structured output ──
    cfg = config.get("configurable", {})
    llm = cfg.get("diagnostic_llm") or cfg.get("llm")
    if llm is None:
        # Fallback: skip diagnostic if no LLM available
        return {"history": ["task_decompose:no_llm"], "task": task_state}

    response = await llm.ainvoke(prompt)
    raw = response.content if hasattr(response, "content") else str(response)

    # ── Parse structured JSON output ──
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        result = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return {
            "history": ["task_decompose:parse_error"],
            "task": {**task_state, "diagnostic_round": diagnostic_round + 1},
        }

    # ── Validate symptom IDs ──
    extracted = loader.validate_symptom_ids(result.get("extracted_symptoms", []))
    result["extracted_symptoms"] = extracted

    # ── Safety net: max diagnostic rounds ──
    diagnostic_round += 1
    status = result.get("diagnosis_status", "need_more_info")
    if diagnostic_round >= MAX_DIAGNOSTIC_ROUNDS and status == "need_more_info":
        status = "recommend_dispatch"
        result["diagnosis_status"] = status
        result["next_action"] = {
            "type": "recommend_dispatch",
            "question": "",
            "reasoning": f"Exceeded {MAX_DIAGNOSTIC_ROUNDS} diagnostic rounds without convergence",
        }

    # ── Build diagnostic context for agent prompt injection ──
    diagnostic_context = json.dumps(
        {
            "hypothesized_failure_modes": result.get("hypothesized_failure_modes", []),
            "next_action": result.get("next_action", {}),
            "corrective_action_immediate": result.get("corrective_action_immediate", ""),
            "diagnosis_status": status,
            "shared_dependency": result.get("shared_dependency_detected", {}),
        },
        ensure_ascii=False,
        indent=2,
    )

    # ── Determine intents from diagnosis ──
    intents = task_state.get("intents", [])
    # If diagnosis concludes dispatch needed, add dispatch intent
    if status == "recommend_dispatch" and "dispatch" not in intents:
        # Keep existing intent for now; dispatch is V2.0
        pass

    # ── Update task state ──
    updated_pc = result.get("updated_problem_card", {})
    new_task = {
        **task_state,
        "extracted_symptoms": extracted,
        "matched_failures": result.get("matched_failures", []),
        "diagnosis_status": status,
        "diagnostic_round": diagnostic_round,
        "diagnostic_context": diagnostic_context,
        "problem_card": {**task_state.get("problem_card", {}), **updated_pc},
    }

    return {
        "history": [f"task_decompose:round_{diagnostic_round}:{status}"],
        "task": new_task,
    }
