"""Brand auto-inference + SCD2 fact update scheduling.

Extracted from ``harness/orchestrator.py`` per RP3 F2.2 — the legacy
``_resolve_brand_model`` mixed three concerns:

1. Read user facts from the profile manager.
2. Run brand/model inference on the user's text.
3. Schedule background DB updates when the inferred values differ from the
   stored ones.

This module owns concerns 2 + 3 as pure-ish helpers (concern 1 stays at the
caller because it needs the orchestrator's ``_profile_mgr`` instance).

Layering: harness module. Imports ``core.brand_match`` (no cycle).
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.brand_match import infer_brand_from_text as _infer
from core.logging_config import get_logger

log = get_logger(__name__)


def infer_brand_from_text(text: str) -> tuple[str | None, str | None]:
    """Public re-export of :func:`core.brand_match.infer_brand_from_text`.

    Why re-export: callers traditionally imported via
    ``harness.line_ui_factory.infer_brand_from_text``; this module is the
    new canonical home for «brand inference from free-form user text», so
    the function is mirrored here for discoverability.
    """
    return _infer(text)


def _input_to_text(user_input: str | list) -> str:
    """Best-effort flatten of LangChain content into a single string.

    Mirrors the legacy inline behaviour in ``_resolve_brand_model``: text-only
    inputs pass through; multimodal lists collapse to the concatenation of
    their ``{"type": "text", ...}`` blocks.
    """
    if isinstance(user_input, str):
        return user_input
    return " ".join(
        b.get("text", "") for b in user_input if isinstance(b, dict)
    )


async def resolve_brand_and_model(
    *,
    user_id: str,
    user_input: str | list,
    profile_mgr: Any,
) -> tuple[str | None, str | None, str | None, str | None, str]:
    """Resolve brand/model for the current turn, scheduling SCD2 updates.

    Returns:
        ``(brand, model, mentioned_brand, mentioned_model, profile_text)``

        - ``brand`` / ``model``: post-inference values (what the agent should
          use this turn).
        - ``mentioned_brand`` / ``mentioned_model``: what was inferred from
          this turn's text (None if nothing inferred). Used by the skill
          prefix builder to surface "brand switch" warnings.
        - ``profile_text``: the formatted profile block for the [用戶資料]
          prefix (empty string when facts disabled).

    Side effect: schedules ``profile_mgr.update_fact`` / ``clear_fact`` as
    background tasks when inference disagrees with the stored facts. Errors
    in those background tasks are surfaced via the profile manager's own
    logging — we don't await them so the LLM call can start immediately.
    """
    if not (profile_mgr and profile_mgr.facts_enabled):
        return None, None, None, None, ""

    profile_text, facts = await profile_mgr.load_full_profile_with_facts(user_id)
    brand: str | None = facts.get("device_brand")
    model: str | None = facts.get("device_model")

    input_text = _input_to_text(user_input)
    mentioned_brand, mentioned_model = _infer(input_text)

    if mentioned_brand and mentioned_brand != brand:
        old_brand, old_model = brand, model
        brand = mentioned_brand
        model = mentioned_model
        asyncio.create_task(profile_mgr.update_fact(user_id, "device_brand", brand))
        if model:
            asyncio.create_task(profile_mgr.update_fact(user_id, "device_model", model))
        elif old_model and old_brand and old_brand != brand:
            # Brand changed but no new model inferred — wipe the stale model
            # so we don't carry e.g. "AI-99" over from the old brand.
            asyncio.create_task(profile_mgr.clear_fact(user_id, "device_model"))
        log.info(
            "brand_switched", user_id=user_id,
            from_brand=old_brand or "", from_model=old_model or "",
            to_brand=brand, to_model=model or "",
        )
    elif mentioned_brand == brand and mentioned_model and mentioned_model != model:
        old_model = model
        model = mentioned_model
        asyncio.create_task(profile_mgr.update_fact(user_id, "device_model", model))
        log.info(
            "model_switched", user_id=user_id, brand=brand,
            from_model=old_model or "", to_model=model,
        )

    return brand, model, mentioned_brand, mentioned_model, profile_text


__all__ = ["infer_brand_from_text", "resolve_brand_and_model"]
