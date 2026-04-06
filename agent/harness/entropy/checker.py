"""L8 Entropy Check node -- detects novel resolutions and queues SOP generation.

Responsibilities:
  1. Check if the resolution is novel (not matching existing fault trees/SOPs)
  2. If novel, mark for SOP generation
  3. Track entropy signals in GraphState
"""

from graph.state import GraphState
from core.config import HARNESS_CONFIG
from harness import is_layer_enabled


_entropy_config = HARNESS_CONFIG.get("entropy", {})


async def entropy_check(state: GraphState) -> dict:
    """Check for novel resolutions and trigger SOP candidate generation.

    When disabled, acts as pass-through (zero impact on existing flow).
    """
    if not is_layer_enabled("entropy"):
        return {"history": ["entropy_check:skip"]}

    task = state.get("task", {})
    diagnosis_status = task.get("diagnosis_status", "")
    answer = state.get("answer", "")

    # Only check entropy for resolved diagnostic cases
    if diagnosis_status not in ("conclusion_ready", "remote_resolved", "dispatch_recommended"):
        return {
            "entropy": {"novel_resolution": False, "sop_candidates": []},
            "history": ["entropy_check:no_resolution"],
        }

    # Check if the resolution matches existing fault trees
    matched_failures = task.get("matched_failures", [])
    hypothesized_fms = task.get("hypothesized_failure_modes", [])

    # Heuristic: if no fault tree matched or hypothesized FMs have low confidence,
    # the resolution is likely novel
    novel_threshold = _entropy_config.get("novel_resolution_threshold", 0.3)
    is_novel = False
    sop_candidates = []

    if not matched_failures and not hypothesized_fms:
        # No fault tree applied — completely novel case
        is_novel = True
    elif hypothesized_fms:
        # Check confidence of top hypothesis
        top_fm = hypothesized_fms[0] if isinstance(hypothesized_fms[0], dict) else {}
        confidence = top_fm.get("confidence", "low")
        if confidence == "low":
            is_novel = True

    if is_novel:
        problem_card = task.get("problem_card", {})
        sop_candidates.append({
            "symptom_summary": problem_card.get("symptom_summary", ""),
            "resolution_summary": answer[:200] if answer else "",
            "category": problem_card.get("category", "unknown"),
            "status": "pending_review",
        })
        print(f"  [entropy_check] 偵測到新案例，已加入 SOP 候選佇列")
    else:
        print(f"  [entropy_check] 非新案例，跳過 SOP 生成")

    return {
        "entropy": {
            "novel_resolution": is_novel,
            "sop_candidates": sop_candidates,
        },
        "history": [f"entropy_check:{'novel' if is_novel else 'known'}"],
    }
