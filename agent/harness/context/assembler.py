"""L2 Context Assembly node -- curates optimal context for downstream agents.

Responsibilities:
  1. Score source freshness from pgvector metadata
  2. Compute relevance weights based on task goal / extracted symptoms
  3. Apply token budget ceiling
  4. On retry (from L5 feedback), adjust context strategy
"""

from graph.state import GraphState
from langchain_core.runnables import RunnableConfig
from core.config import HARNESS_CONFIG
from harness import is_layer_enabled
from harness.context.budget import estimate_tokens, calculate_context_budget
from harness.context.freshness import score_freshness


_context_config = HARNESS_CONFIG.get("context", {})


async def context_assemble(state: GraphState, config: RunnableConfig) -> dict:
    """Assemble context with freshness scoring and token budget.

    When disabled, acts as pass-through (zero impact on existing flow).
    """
    if not is_layer_enabled("context"):
        return {"history": ["context_assemble:skip"]}

    task = state.get("task", {})
    feedback = state.get("feedback", {})
    max_budget = _context_config.get("token_budget", 4096)
    freshness_days = _context_config.get("freshness_threshold_days", 90)

    # Extracted symptoms inform relevance weighting
    symptoms = task.get("extracted_symptoms", [])
    diagnosis_status = task.get("diagnosis_status", "")

    # Score freshness for active knowledge sources
    source_names = ["kb_video", "kb_line_chat", "kb_website", "kb_youtube", "kb_gdrive"]
    freshness_scores = {}
    for src in source_names:
        freshness_scores[src] = await score_freshness(src, freshness_days)

    # Compute relevance weights based on symptoms
    relevance_weights = {}
    if symptoms:
        # Hardware symptoms → boost kb_video and kb_line_chat
        relevance_weights["kb_video"] = 1.0
        relevance_weights["kb_line_chat"] = 0.8
        relevance_weights["kb_website"] = 0.3
        relevance_weights["kb_youtube"] = 0.5
        relevance_weights["kb_gdrive"] = 0.6
    else:
        # Non-diagnostic → equal weights
        for src in source_names:
            relevance_weights[src] = 1.0

    # Token budget tracking
    diagnostic_context = task.get("diagnostic_context", "")
    conversation = "\n".join(
        m.content for m in state.get("messages", [])[-6:]
        if hasattr(m, "content") and isinstance(m.content, str)
    )
    budget_info = calculate_context_budget(
        system_prompt=diagnostic_context,
        conversation_history=conversation,
        max_budget=max_budget,
    )

    # On retry: check if feedback has adjustment hints
    retry_adjustments = feedback.get("retry_adjustments", {})
    if retry_adjustments:
        print(f"  [context_assemble] retry with adjustments: {retry_adjustments}")

    budget_used = budget_info["total_used"]
    print(f"  [context_assemble] budget: {budget_used}/{max_budget} tokens "
          f"({budget_info['utilization']:.0%}), symptoms={len(symptoms)}")

    return {
        "context_meta": {
            "freshness_scores": freshness_scores,
            "relevance_weights": relevance_weights,
            "budget_used": budget_used,
            "budget_remaining": budget_info["remaining"],
            "retry_adjustments": retry_adjustments,
        },
        "history": ["context_assemble"],
    }
