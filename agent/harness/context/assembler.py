"""L2 Context Assembly node -- curates optimal context for downstream agents.

This is a pass-through skeleton. Actual implementation in Phase 4.
"""

from graph.state import GraphState
from langchain_core.runnables import RunnableConfig
from harness import is_layer_enabled


async def context_assemble(state: GraphState, config: RunnableConfig) -> dict:
    """Assemble context with freshness scoring and token budget.

    When disabled, acts as pass-through (zero impact on existing flow).
    """
    if not is_layer_enabled("context"):
        return {"history": ["context_assemble:skip"]}

    # Phase 4 implementation:
    # 1. Score source freshness from pgvector metadata
    # 2. Compute relevance weights based on task goal
    # 3. Apply token budget ceiling
    # 4. On retry, read feedback.retry_context_adjustments

    return {"history": ["context_assemble:skip"]}
