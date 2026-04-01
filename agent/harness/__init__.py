"""Agent Harness Framework -- 8-layer runtime architecture for agent systems.

Layers:
    L1 Task Representation   (harness.task)
    L2 Context Assembly      (harness.context)
    L3 Tool Governance       (harness.governance)
    L4 State & Memory        (existing memory/ + profiles/)
    L5 Feedback & Verify     (harness.feedback)
    L6 Safety & Control      (harness.safety)
    L7 Observability         (harness.observability)
    L8 Entropy Management    (harness.entropy)
"""

from core.config import HARNESS_CONFIG


def is_harness_enabled() -> bool:
    """Check if the harness framework master switch is on."""
    return HARNESS_CONFIG.get("enabled", False)


def is_layer_enabled(layer: str) -> bool:
    """Check if a specific harness layer is enabled.

    Args:
        layer: one of 'task', 'context', 'governance', 'feedback',
               'safety', 'observability', 'entropy'
    """
    if not is_harness_enabled():
        return False
    layer_cfg = HARNESS_CONFIG.get(layer, {})
    # Each layer has its own enabled key (e.g. decompose_enabled, verify_enabled)
    # or falls back to the master switch
    for key in layer_cfg:
        if key.endswith("_enabled"):
            return layer_cfg[key]
    return True
