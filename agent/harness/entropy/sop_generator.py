"""Auto-SOP generation from novel resolutions.

Stub -- Phase 6 implementation.
"""

from __future__ import annotations


async def generate_sop_candidate(symptom: str, resolution: str, device: str) -> dict:
    """Generate an SOP draft from a novel resolution.

    Phase 6: use LLM to convert (symptom, resolution) pair into
    structured SOP document, then insert into sop_drafts review queue.

    Returns:
        SOP candidate dict with title, steps, confidence.
    """
    return {
        "title": "",
        "steps": [],
        "confidence": 0.0,
        "status": "pending_review",
    }
