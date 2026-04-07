"""Auto-SOP generation from novel resolutions.

Uses LLM to convert (symptom, resolution) pair into a structured SOP document,
then saves to data/storage/knowledge_drafts/sop/ for human review pipeline.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from langchain_core.messages import HumanMessage


# Draft output directory (under data/ project root)
_DRAFTS_DIR = Path(__file__).resolve().parents[3] / "data" / "storage" / "knowledge_drafts" / "sop"


async def generate_sop_candidate(symptom: str, resolution: str, device: str) -> dict:
    """Generate an SOP draft from a novel resolution via LLM.

    Returns:
        SOP candidate dict with title, steps, confidence.
        On failure, returns default empty dict (non-blocking).
    """
    if not symptom or not resolution:
        return _default_result()

    try:
        from agents import load_prompt_template
        from core.config import LLM_CONFIG
        from llms import get_llm

        # Load prompt template
        prompt_path = "harness/entropy/prompts/generate_sop.md"
        prompt = load_prompt_template(
            prompt_path,
            symptom=symptom,
            resolution=resolution,
            device=device or "unknown",
        )

        # Call LLM
        llm = get_llm(LLM_CONFIG)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content if hasattr(response, "content") else str(response)

        # Parse JSON (strip markdown code fences)
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        result = json.loads(text)

        # Validate required keys
        if not result.get("title") or not result.get("steps"):
            print(f"  [SOP Generator] LLM 輸出缺少 title 或 steps")
            return _default_result()

        result["status"] = "pending_review"

        # Save draft to filesystem
        _save_draft(result, device)

        print(f"  [SOP Generator] 已生成 SOP: {result['title']}")
        return result

    except Exception as e:
        print(f"  [SOP Generator] 生成失敗（非致命）: {e}")
        return _default_result()


def _default_result() -> dict:
    return {
        "title": "",
        "steps": [],
        "confidence": 0.0,
        "status": "pending_review",
    }


def _save_draft(sop: dict, device: str) -> None:
    """Save SOP draft to knowledge_drafts/sop/ for review pipeline."""
    try:
        _DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_device = re.sub(r"[^\w\-]", "_", device or "unknown")
        out_path = _DRAFTS_DIR / f"sop_{timestamp}_{safe_device}.json"
        out_path.write_text(
            json.dumps(sop, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  [SOP Generator] 草稿已存儲: {out_path}")
    except Exception as e:
        print(f"  [SOP Generator] 草稿存儲失敗: {e}")
