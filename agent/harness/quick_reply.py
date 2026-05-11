"""H_QR Quick Reply state machine — brand/model collection middleware.

Extracted from ``harness/debounce.py:686-843`` (the legacy
``_quick_reply_intercept``) per audit 2026-05-06 §C3 + §B6.

Responsibilities:
1. When the bot does not yet know the user's lock brand or model, hold the
   user's original message in a :class:`PendingStore` and reply with a LINE
   Quick Reply asking for the missing fact.
2. When the user answers with the missing fact, persist it via
   ``ProfileManager`` and release the original message back into the agent
   pipeline.
3. When the user types something that doesn't match any known brand/model,
   degrade gracefully — combine their reply with the held message and let
   the agent figure it out (with the now-known partial facts injected as
   context).

Why split out:
- audit §C3: ``debounce.py`` was a 1100+ line god class; H_QR was one of
  the eight responsibilities tangled inside it.
- audit §B6: the legacy implementation was an 11-elif state machine that
  violated CLAUDE.md "no special cases". This module replaces it with an
  explicit :class:`BrandModelState` enum + dispatch table — every transition
  has a named handler and a docstring instead of being a nested ``if`` arm.

Layering: this is a harness module. It is allowed to import other harness
modules (``buffer``, ``line_ui_factory``) and ``core``, but must not import
``agent`` (top-level orchestration) — that direction would re-introduce
the cycle that ADR ``agent-layering-rules.md`` v1.0 just removed.
"""
from __future__ import annotations

PHASE: str = "H_QR"  # per harness/__init__.py PIPELINE inventory (ADR-0024 §3 S2)

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Awaitable, Callable

import core.line_bot as line_bot
from core.brand_match import (
    get_brand_models,
    infer_brand_from_text,
    match_brand,
    match_model,
)
from core.logging_config import get_logger

from harness.buffer import PendingState, PendingStore
from harness.line_ui_factory import build_line_messages, is_quick_reply_enabled

log = get_logger(__name__)


# ─────────────────────────────────────────────
# State machine model
# ─────────────────────────────────────────────


class BrandModelState(Enum):
    """Coarse-grained classification of the user's known facts.

    The legacy intercept inferred this implicitly via 11 nested ``elif``
    branches. Naming the state lets each handler be a small, testable
    function instead of an arm in a giant conditional.
    """

    BOTH_KNOWN = auto()
    """Brand + model already on file → bypass quick reply entirely."""

    BRAND_KNOWN_NO_MODELS = auto()
    """Brand on file but the brand has no per-model skills (e.g. registered
    brands with empty model lists). Nothing to ask — bypass."""

    BRAND_KNOWN_NEEDS_MODEL = auto()
    """Brand on file, model missing, brand has known models → ask model."""

    BRAND_UNKNOWN = auto()
    """Brand missing → ask brand."""


def determine_state(brand: str | None, model: str | None) -> BrandModelState:
    """Classify the user's current known facts.

    Pure function: deterministic, side-effect-free. Tests can call it with
    arbitrary (brand, model) without touching DB or LINE.
    """
    if not brand:
        return BrandModelState.BRAND_UNKNOWN
    if model:
        return BrandModelState.BOTH_KNOWN
    if get_brand_models(brand):
        return BrandModelState.BRAND_KNOWN_NEEDS_MODEL
    return BrandModelState.BRAND_KNOWN_NO_MODELS


# ─────────────────────────────────────────────
# Dependencies (injected by orchestrator/app.py)
# ─────────────────────────────────────────────


# AgentResume is the callable the orchestrator hands us so we can release a
# held message back into the agent pipeline once facts are collected.
# Signature:
#   await resume(user_id, reply_token, content, items, *, skip_quick_reply=True)
AgentResume = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class QuickReplyContext:
    """Per-call context bundle.

    Bundling the dependencies in a frozen object means each handler takes one
    parameter instead of seven, and the orchestrator can construct the
    context once per request rather than threading the same args through
    every helper.
    """

    user_id: str
    reply_token: str
    content: Any  # str | list[dict]
    items: tuple | None  # original Block tuple, for resume path
    profile_mgr: Any
    pending: PendingStore
    resume: AgentResume
    set_current_brand: Callable[[str | None, str | None], None]


# Result of an intercept attempt — communicates back to caller whether the
# agent run should be skipped.
@dataclass(frozen=True)
class InterceptResult:
    intercepted: bool
    """True ⇒ caller must NOT invoke the agent (we already replied or
    re-dispatched the original message via ``resume``)."""


_NOT_INTERCEPTED = InterceptResult(intercepted=False)
_INTERCEPTED = InterceptResult(intercepted=True)


# ─────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────


async def intercept(ctx: QuickReplyContext, *, text: str) -> InterceptResult:
    """Decide whether the current message should be held / collected / passed.

    The function is split into two top-level paths:

    1. **Resume path** — there is a pending state for this user, so the
       current message is treated as their answer to the previous question.
       We try to match it against the missing fact, persist if successful,
       and either ask for the next missing fact or release the original
       message back into the agent pipeline.

    2. **Initial path** — no pending state. Check whether brand/model are
       known; if not, attempt to infer them from the user's text first
       (covers «首訊就含品牌型號» — see commit message of legacy 21bf21b).
       If facts are still missing, hold the message and ask via Quick Reply.

    The two paths are dispatched on :class:`BrandModelState` so adding a new
    branch in the future is a matter of adding an enum variant + handler —
    not adding another ``elif``.
    """
    if not is_quick_reply_enabled() or not ctx.profile_mgr or not ctx.profile_mgr.facts_enabled:
        return _NOT_INTERCEPTED

    # Re-read facts inside intercept rather than trusting whatever
    # determine_state(brand, model) the orchestrator computed pre-call —
    # the user may have updated their profile between debounce flush and
    # intercept (e.g. update_user_info tool ran in the previous turn).
    _, facts = await ctx.profile_mgr.load_full_profile_with_facts(ctx.user_id)
    brand = facts.get("device_brand")
    model = facts.get("device_model")
    ctx.set_current_brand(brand, model)

    pending_state = await ctx.pending.get(ctx.user_id)

    if pending_state is not None:
        # Resume path: user is answering a previous prompt.
        return await _resume_path(ctx, pending_state, text=text, brand=brand, model=model)

    # Initial path: try inferring facts from the user's first message before
    # falling back to asking via Quick Reply.
    brand, model = await _maybe_infer_from_text(ctx, text=text, brand=brand, model=model)
    state = determine_state(brand, model)
    return await _INITIAL_HANDLERS[state](ctx, brand=brand, model=model)


# ─────────────────────────────────────────────
# Initial-path handlers (no pending state)
# ─────────────────────────────────────────────


async def _initial_both_known(
    ctx: QuickReplyContext, *, brand: str | None, model: str | None
) -> InterceptResult:
    """All facts known → no intercept; agent runs normally."""
    return _NOT_INTERCEPTED


async def _initial_brand_known_no_models(
    ctx: QuickReplyContext, *, brand: str | None, model: str | None
) -> InterceptResult:
    """Brand known but registry has no model list → no intercept."""
    return _NOT_INTERCEPTED


async def _initial_brand_known_needs_model(
    ctx: QuickReplyContext, *, brand: str | None, model: str | None
) -> InterceptResult:
    """Brand known, model missing → hold message, ask model via Quick Reply."""
    await _hold_and_ask(
        ctx,
        prompt=f"請問您的 {brand} 電子鎖是什麼型號呢？",
        brand=brand,
        model=None,
    )
    log.info("quick_reply_model_prompt_pending", user_id=ctx.user_id, brand=brand or "")
    return _INTERCEPTED


async def _initial_brand_unknown(
    ctx: QuickReplyContext, *, brand: str | None, model: str | None
) -> InterceptResult:
    """Brand missing → hold message, ask brand via Quick Reply."""
    await _hold_and_ask(
        ctx,
        prompt="請問您的電子鎖是什麼品牌呢？",
        brand=None,
        model=None,
    )
    log.info("quick_reply_brand_prompt_pending", user_id=ctx.user_id)
    return _INTERCEPTED


_INITIAL_HANDLERS: dict[
    BrandModelState,
    Callable[..., Awaitable[InterceptResult]],
] = {
    BrandModelState.BOTH_KNOWN: _initial_both_known,
    BrandModelState.BRAND_KNOWN_NO_MODELS: _initial_brand_known_no_models,
    BrandModelState.BRAND_KNOWN_NEEDS_MODEL: _initial_brand_known_needs_model,
    BrandModelState.BRAND_UNKNOWN: _initial_brand_unknown,
}


# ─────────────────────────────────────────────
# Resume-path handlers (pending state exists)
# ─────────────────────────────────────────────


async def _resume_path(
    ctx: QuickReplyContext,
    pending_state: PendingState,
    *,
    text: str,
    brand: str | None,
    model: str | None,
) -> InterceptResult:
    """User has a pending message — interpret current text as their answer.

    The legacy code was a single ``if not brand: ... elif brand and not model: ...``
    fork. Splitting it makes the brand-collect vs model-collect paths readable
    and aligns each branch with the same dispatch-table style as the initial
    path.
    """
    text_stripped = text.strip()
    if not brand:
        return await _resume_collect_brand(ctx, pending_state, text=text_stripped, model=model)
    if not model:
        return await _resume_collect_model(ctx, pending_state, text=text_stripped, brand=brand)
    # Both known but pending state survived (race / TTL not yet hit) — treat
    # as «release» so we don't strand the user.
    await ctx.pending.pop(ctx.user_id)
    log.info("quick_reply_release_both_known", user_id=ctx.user_id, brand=brand or "", model=model or "")
    await _resume_agent(ctx, pending_state, override_content=None)
    return _INTERCEPTED


async def _resume_collect_brand(
    ctx: QuickReplyContext,
    pending_state: PendingState,
    *,
    text: str,
    model: str | None,
) -> InterceptResult:
    """User is answering «what brand». Try Quick-Reply match → infer → release."""
    matched = match_brand(text)
    if matched:
        await ctx.profile_mgr.update_fact(ctx.user_id, "device_brand", matched)
        ctx.set_current_brand(matched, model)
        log.info("quick_reply_brand_selected", user_id=ctx.user_id, brand=matched)

        if get_brand_models(matched):
            # Brand has models → ask the next question (don't release yet).
            await _send_reply(
                ctx,
                f"收到，{matched}！請問您的電子鎖是什麼型號呢？",
                brand=matched,
                model=None,
            )
            return _INTERCEPTED

        # Brand has no per-model skills → release.
        await ctx.pending.pop(ctx.user_id)
        log.info("quick_reply_brand_done_no_model", user_id=ctx.user_id, brand=matched)
        await _resume_agent(ctx, pending_state, override_content=None)
        return _INTERCEPTED

    # No exact brand match — try fuzzy inference (the user typed something
    # like "我的鎖是 Dormakaba 的 DP-850").
    inferred_brand, inferred_model = infer_brand_from_text(text)
    if inferred_brand:
        await ctx.profile_mgr.update_fact(ctx.user_id, "device_brand", inferred_brand)
        new_model: str | None = None
        if inferred_model:
            await ctx.profile_mgr.update_fact(ctx.user_id, "device_model", inferred_model)
            new_model = inferred_model
        ctx.set_current_brand(inferred_brand, new_model)
        log.info(
            "quick_reply_brand_inferred",
            user_id=ctx.user_id,
            brand=inferred_brand,
            model=new_model or "",
        )

        if not new_model and get_brand_models(inferred_brand):
            # Still need model.
            await _send_reply(
                ctx,
                f"收到，{inferred_brand}！請問您的電子鎖是什麼型號呢？",
                brand=inferred_brand,
                model=None,
            )
            return _INTERCEPTED

        await ctx.pending.pop(ctx.user_id)
        log.info(
            "quick_reply_inference_done",
            user_id=ctx.user_id,
            brand=inferred_brand,
            model=new_model or "",
        )
        await _resume_agent(ctx, pending_state, override_content=None)
        return _INTERCEPTED

    # Total mismatch — fold the user's text into the held content and
    # release. The agent will see «<user reply>\n<original question>» and
    # can typically still respond, just without brand-specific gating.
    await ctx.pending.pop(ctx.user_id)
    log.info("quick_reply_brand_unknown_release", user_id=ctx.user_id)
    combined = _combine_content(text, pending_state.content)
    await _resume_agent(ctx, pending_state, override_content=combined)
    return _INTERCEPTED


async def _resume_collect_model(
    ctx: QuickReplyContext,
    pending_state: PendingState,
    *,
    text: str,
    brand: str,
) -> InterceptResult:
    """User is answering «what model». Match → "其他" sentinel → free-form."""
    matched = match_model(brand, text)
    if matched:
        new_model: str = matched
        log.info(
            "quick_reply_model_selected",
            user_id=ctx.user_id,
            brand=brand,
            model=matched,
        )
    elif text in ("其他型號，請直接回覆",):
        # User picked the «其他型號» Quick Reply button — record sentinel so
        # we don't ask again, but the agent still routes via _common skills.
        new_model = "其他"
        log.info("quick_reply_model_other", user_id=ctx.user_id, brand=brand)
    else:
        # User typed a free-form model — store verbatim.
        new_model = text
        log.info(
            "quick_reply_model_typed",
            user_id=ctx.user_id,
            brand=brand,
            model=text,
        )

    await ctx.profile_mgr.update_fact(ctx.user_id, "device_model", new_model)
    ctx.set_current_brand(brand, new_model)
    await ctx.pending.pop(ctx.user_id)
    log.info(
        "quick_reply_collection_done",
        user_id=ctx.user_id,
        brand=brand,
        model=new_model,
    )
    await _resume_agent(ctx, pending_state, override_content=None)
    return _INTERCEPTED


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


async def _maybe_infer_from_text(
    ctx: QuickReplyContext, *, text: str, brand: str | None, model: str | None
) -> tuple[str | None, str | None]:
    """Best-effort fact extraction from the user's first message.

    Mirrors the legacy «B0» preprocessing: covers the case where the user's
    very first message contains both brand + model and we'd otherwise
    annoy them by asking for what they already volunteered.

    Updates the DB if anything new is found; returns the (possibly enriched)
    pair so the caller can dispatch on it.
    """
    if brand and model:
        return brand, model
    inferred_brand, inferred_model = infer_brand_from_text(text.strip())
    new_brand = brand
    new_model = model
    if inferred_brand and not brand:
        await ctx.profile_mgr.update_fact(ctx.user_id, "device_brand", inferred_brand)
        new_brand = inferred_brand
        log.info(
            "quick_reply_first_message_brand_inferred",
            user_id=ctx.user_id,
            brand=new_brand,
        )
    if inferred_model and not model:
        await ctx.profile_mgr.update_fact(ctx.user_id, "device_model", inferred_model)
        new_model = inferred_model
        log.info(
            "quick_reply_first_message_model_inferred",
            user_id=ctx.user_id,
            model=new_model,
        )
    if new_brand != brand or new_model != model:
        ctx.set_current_brand(new_brand, new_model)
    return new_brand, new_model


async def _hold_and_ask(
    ctx: QuickReplyContext,
    *,
    prompt: str,
    brand: str | None,
    model: str | None,
) -> None:
    """Stash the original message + reply with the LINE Quick Reply prompt.

    The held content is whatever ``ctx.content`` is — we do NOT re-render
    via blocks here because the resume path needs to hand the verbatim
    LangChain content back to the agent (preserves multimodal blocks).
    """
    items_tuple = tuple(ctx.items or ())
    await ctx.pending.set(
        ctx.user_id,
        PendingState(content=ctx.content, items=items_tuple, ts=time.time()),
    )
    await _send_reply(ctx, prompt, brand=brand, model=model)


async def _send_reply(
    ctx: QuickReplyContext,
    text: str,
    *,
    brand: str | None,
    model: str | None,
) -> None:
    """Send a LINE reply with the appropriate Quick Reply buttons."""
    messages = build_line_messages(text, brand=brand, model=model)
    await line_bot.send_response(
        ctx.user_id,
        ctx.reply_token,
        text,
        message_objects=messages,
    )


async def _resume_agent(
    ctx: QuickReplyContext,
    pending_state: PendingState,
    *,
    override_content: Any,
) -> None:
    """Hand the held content back to the agent pipeline.

    ``override_content`` lets the brand-unknown-release branch substitute a
    combined string («<user_reply>\n<original_question>»). When ``None``,
    the original content from the pending state is used verbatim.
    """
    content = override_content if override_content is not None else pending_state.content
    items_list: list = list(pending_state.items) if pending_state.items else []
    await ctx.resume(
        ctx.user_id,
        ctx.reply_token,
        content,
        items_list,
        skip_quick_reply=True,
    )


def _combine_content(text: str, original: Any) -> Any:
    """Combine the user's free-form text with the originally held content.

    For text-only originals: prepend "<text>\n" so the agent sees the new
    user input as additional context.

    For multimodal originals (list of LangChain blocks): leave the original
    intact — combining base64 image blocks with a free-form fallback string
    is more likely to confuse the LLM than help. The agent will still see
    the original multimodal message; the user's mismatched reply is
    effectively ignored except for the fact that we logged it.
    """
    if isinstance(original, str):
        return f"{text}\n{original}"
    return original


__all__ = [
    "BrandModelState",
    "InterceptResult",
    "QuickReplyContext",
    "determine_state",
    "intercept",
]
