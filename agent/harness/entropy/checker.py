"""L8 Entropy Check node -- detects novel resolutions and queues SOP generation.

This is a pass-through skeleton. Actual implementation in Phase 6.
"""

from graph.state import GraphState
from harness import is_layer_enabled


async def entropy_check(state: GraphState) -> dict:
    """Check for novel resolutions and trigger SOP candidate generation.

    When disabled, acts as pass-through (zero impact on existing flow).
    """
    if not is_layer_enabled("entropy"):
        return {"history": ["entropy_check:skip"]}

    # Phase 6 implementation:
    # 1. Load resolved ProblemCard
    # 2. Vector-search for similar past cards
    # 3. If similarity < threshold, mark is_novel = True
    # 4. Queue SOP generation candidate

    return {
        "entropy": {"novel_resolution": False, "sop_candidates": []},
        "history": ["entropy_check:skip"],
    }
