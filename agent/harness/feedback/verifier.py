"""L5 Feedback Verification node -- evaluates answer quality.

This is a pass-through skeleton. Actual implementation in Phase 5.
"""

from graph.state import GraphState
from langchain_core.runnables import RunnableConfig
from harness import is_layer_enabled


async def verify_answer(state: GraphState, config: RunnableConfig) -> dict:
    """Evaluate answer quality and decide pass/retry.

    When disabled, acts as pass-through (zero impact on existing flow).
    """
    if not is_layer_enabled("feedback"):
        return {"history": ["verify_answer:skip"]}

    # Phase 5 implementation:
    # 1. Use evaluator LLM to score answer against ProblemCard goal
    # 2. Check: addresses fault_description? actionable steps? no system leakage?
    # 3. If score < threshold and retry_count < max_retry: set status "failed"
    # 4. Append ResolutionAttempt to ProblemCard

    return {
        "feedback": {"verification_status": "passed", "quality_scores": {}},
        "history": ["verify_answer:skip"],
    }
