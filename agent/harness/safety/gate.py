"""L6 Safety Gate node -- pre-routing safety check.

This is a pass-through skeleton. Actual implementation in Phase 3.
"""

from graph.state import GraphState
from harness import is_layer_enabled


async def safety_gate(state: GraphState) -> dict:
    """Pre-routing safety check for dangerous instructions.

    When disabled, acts as pass-through (zero impact on existing flow).
    """
    if not is_layer_enabled("safety"):
        return {"history": ["safety_gate:skip"]}

    # Phase 3 implementation:
    # 1. Scan question for dangerous instruction keywords
    # 2. Check PII exposure risk
    # 3. Set requires_approval flag if critical
    # 4. Record audit trail entry

    return {
        "safety": {
            "permission_level": "read",
            "requires_approval": False,
            "flagged_risks": [],
            "audit_trail": [],
        },
        "history": ["safety_gate:skip"],
    }
