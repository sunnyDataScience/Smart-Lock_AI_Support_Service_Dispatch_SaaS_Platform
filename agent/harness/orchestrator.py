"""H3 orchestrator — agent invocation pipeline (thin coordinator).

Responsibilities (post-RP3 F2):

1. Hold the runtime dependencies (agent, audit_storage, profile_mgr, ...)
   as module-level state so ``app.py`` startup can wire them once via
   :func:`init` and so ``quality_check`` can monkey-patch ``_agent`` for
   eval runs (legacy contract).
2. Provide :func:`run_agent` — pure agent invocation: build prefixes,
   ainvoke, run checkpoint cleanup. Used by both the LINE flow and the
   ``GET /chat`` test endpoint.
3. Provide :func:`agent_and_reply` — full LINE-bound pipeline that strings
   together the dedicated harness modules (safety_gate, data_correction,
   quick_reply, validator_pipeline, profile_updater, agent_audit,
   memory_manager, line_ui_factory).

Everything *content-level* — building skill prefixes, inferring brand,
running validators, checkpoint cleanup, audit writes — now lives in
sibling modules:

- ``harness.skills_prefix``       (RP3 F2.1)
- ``harness.brand_resolver``      (RP3 F2.2)
- ``harness.validator_pipeline``  (RP3 F2.3)
- ``harness.checkpoint_cleanup``  (RP3 F2.4)
- ``harness.agent_audit``         (RP3 F2.4)

Layering: harness-tier. Imports core, harness, skills; never agent-root
(forbidden by reverse-import-lint.yml).
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import Any

import psycopg

import core.line_bot as line_bot
from core.blocks import Block, to_text as blocks_to_text
from core.content_utils import extract_text
from core.logging_config import get_logger

import harness.agent_audit as agent_audit
import harness.checkpoint_cleanup as checkpoint_cleanup
import harness.data_correction as data_correction
import harness.memory_manager as memory_manager
import harness.profile_updater as profile_updater
import harness.safety_gate as safety_gate
import harness.skills_prefix as skills_prefix
import harness.validator_pipeline as validator_pipeline
from harness import quick_reply as quick_reply_mod
from harness.brand_resolver import resolve_brand_and_model
from harness.buffer import PendingStore, pending as _default_pending_store
from harness.line_ui_factory import build_line_messages

log = get_logger(__name__)

# ─────────────────────────────────────────────
# Module-level wiring (set by init() from app.py startup)
# ─────────────────────────────────────────────

_agent: Any = None
_config: dict = {}
_templates: dict = {}
_profile_mgr: Any = None
_audit_storage: Any = None
_opik_tracer: Any = None
_pending_store: PendingStore = _default_pending_store

# RP2.3 — getter callable injected by app.py to avoid harness→agent reverse
# import. Returns the current system prompt string for debug rendering.
_get_system_prompt = lambda: ""  # noqa: E731 — sentinel that init() may overwrite


def init(
    agent: Any,
    config: dict,
    templates: dict,
    *,
    profile_mgr: Any = None,
    audit_storage: Any = None,
    opik_tracer: Any = None,
    system_prompt_getter: Any = None,
    pending_store: PendingStore | None = None,
) -> None:
    """Inject runtime dependencies. Called once at app startup."""
    global _agent, _config, _templates, _profile_mgr, _audit_storage
    global _opik_tracer, _get_system_prompt, _pending_store
    _agent = agent
    _config = config
    _templates = templates
    _profile_mgr = profile_mgr
    _audit_storage = audit_storage
    _opik_tracer = opik_tracer
    if system_prompt_getter is not None:
        _get_system_prompt = system_prompt_getter
    if pending_store is not None:
        _pending_store = pending_store


# ─────────────────────────────────────────────
# Back-compat thin wrappers (delegate to checkpoint_cleanup module)
# ─────────────────────────────────────────────


async def strip_stale_multimodal(agent: Any, config: dict) -> None:
    """Back-compat wrapper — see :func:`checkpoint_cleanup.strip_stale_multimodal`."""
    await checkpoint_cleanup.strip_stale_multimodal(agent, config)


async def cleanup_multimodal_checkpoint(
    config: dict, messages: list, buffer_items: list[Block] | None,
) -> None:
    """Back-compat wrapper — see :func:`checkpoint_cleanup.cleanup_multimodal`.

    Uses the module-level ``_agent`` so callers (debounce, quality_check
    patch path) keep their existing call shape.
    """
    await checkpoint_cleanup.cleanup_multimodal(_agent, config, messages, buffer_items)


async def cleanup_tool_checkpoint(config: dict, messages: list) -> None:
    """Back-compat wrapper — see :func:`checkpoint_cleanup.cleanup_tool`."""
    await checkpoint_cleanup.cleanup_tool(_agent, config, messages)


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────


def _extract_text_from_items(items: list[Block]) -> str:
    """Best-effort textification of buffer :class:`Block` items (audit/log)."""
    return blocks_to_text(items, with_media_refs=True)


# Strip internal-reference markers the LLM occasionally echoes back from
# cleaned ToolMessage stubs.
_REF_MARKER_RE = re.compile(r"\s*\[已參考(?:技能)?:[^\]]*\][\s,，]*")


# ─────────────────────────────────────────────
# Public entry: run_agent
# ─────────────────────────────────────────────


async def _build_message_content(
    user_id: str, user_input: str | list, thread_id: str,
) -> tuple[str | list, str | None, str | None, str | None, str | None]:
    """Build the LangChain ``content`` for one ainvoke + return inferred facts.

    Returns:
        ``(message_content, brand, model, mentioned_brand, mentioned_model)``
    """
    from skills import filter_skills
    from skills.tools import get_skills, set_current_brand

    brand, model, mentioned_brand, mentioned_model, profile_text = await resolve_brand_and_model(
        user_id=user_id, user_input=user_input, profile_mgr=_profile_mgr,
    )
    set_current_brand(brand, model)

    skills_block = skills_prefix.build_skills_block(
        brand=brand, model=model,
        mentioned_brand=mentioned_brand, mentioned_model=mentioned_model,
        registered_skills=get_skills(),
        filter_skills=filter_skills,
    )

    profile_to_inject = (
        profile_text if (_profile_mgr and _profile_mgr.enabled and profile_text) else None
    )
    summary = memory_manager.get_summary(thread_id)
    summary_prefix = memory_manager.build_summary_prefix(summary) if summary else None
    if summary:
        log.debug("summary_injected", user_id=user_id, length=len(summary))

    prefix = skills_prefix.build_user_prefix(
        skills_block=skills_block,
        profile_text=profile_to_inject,
        summary_prefix=summary_prefix,
    )
    if isinstance(user_input, list):
        message_content: str | list = [{"type": "text", "text": prefix}] + user_input
    else:
        message_content = f"{prefix}{user_input}"
    return message_content, brand, model, mentioned_brand, mentioned_model


def _extract_final_ai_text(messages: list) -> str:
    """Walk the result messages to find the final AI response text."""
    fallback = _templates.get("error_no_reply", "抱歉，系統沒有產生回覆。")
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            return _REF_MARKER_RE.sub("", extract_text(msg.content)).strip()
    return fallback


async def run_agent(
    user_id: str,
    user_input: str | list,
    buffer_items: list[Block] | None = None,
) -> str:
    """Send the user's input through the ReAct agent and return the AI text."""
    from skills.tools import (
        set_current_user_id, reset_run_state, set_current_user_input,
    )
    set_current_user_id(user_id)
    reset_run_state()

    if isinstance(user_input, str):
        set_current_user_input(user_input)
    else:
        text_parts = [b["text"] for b in user_input if isinstance(b, dict) and b.get("type") == "text"]
        set_current_user_input(" ".join(text_parts))

    request_timeout = _config.get("request_timeout", 60)
    is_multimodal = isinstance(user_input, list)
    thread_id = f"line_{user_id}"
    t_phase_start = time.monotonic()

    try:
        message_content, *_facts = await _build_message_content(user_id, user_input, thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        t_pre_strip = time.monotonic()
        await checkpoint_cleanup.strip_stale_multimodal(_agent, config)

        display = _extract_text_from_items(buffer_items) if buffer_items else (
            extract_text(message_content) if isinstance(message_content, str) else "[多模態訊息]"
        )
        log.info("agent_invoke_start", user_id=user_id, input_preview=display[:200])
        print(f"[Agent] 送入內容:\n{'─' * 40}\n{display[:500]}{'...(截斷)' if len(display) > 500 else ''}\n{'─' * 40}")

        run_config: dict = {"configurable": {"thread_id": thread_id}}
        if _opik_tracer:
            run_config["callbacks"] = [_opik_tracer]
        run_config.setdefault("metadata", {})["user_id"] = user_id

        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(
                _agent.ainvoke(
                    {"messages": [{"role": "user", "content": message_content}]},
                    run_config,
                ),
                timeout=request_timeout,
            )
        except asyncio.TimeoutError:
            log.error(
                "agent_timeout", user_id=user_id, timeout_s=request_timeout,
                pre_s=round(t_pre_strip - t_phase_start, 2),
                strip_s=round(t0 - t_pre_strip, 2),
                ainvoke_s=round(time.monotonic() - t0, 2),
            )
            return _templates.get("error_timeout", "不好意思，系統處理時間過長，請稍後再試一次。")

        t_invoke_done = time.monotonic()
        messages = result.get("messages", [])

        if is_multimodal:
            await checkpoint_cleanup.cleanup_multimodal(_agent, config, messages, buffer_items)

        asyncio.create_task(agent_audit.write_agent_result(
            audit_storage=_audit_storage,
            user_id=user_id,
            messages=messages,
            latency_ms=(t_invoke_done - t0) * 1000,
            model_name=_config.get("model_name", "gemini-2.5-flash"),
            turn_id=uuid.uuid4().hex[:16],
            user_question=display,
        ))

        ai_response = _extract_final_ai_text(messages)

        # Background tool-checkpoint cleanup so the user reply isn't blocked.
        asyncio.create_task(checkpoint_cleanup.cleanup_tool(_agent, config, messages))
        log.info(
            "agent_invoke_done", user_id=user_id,
            pre_s=round(t_pre_strip - t_phase_start, 2),
            strip_s=round(t0 - t_pre_strip, 2),
            ainvoke_s=round(t_invoke_done - t0, 2),
            total_s=round(time.monotonic() - t_phase_start, 2),
        )
        return ai_response

    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.error("agent_run_failed", user_id=user_id, error=str(e), exc_info=True)
        return _templates.get("error_system", "不好意思，系統大腦剛剛稍微當機了一下，請稍後再試一次！")


# ─────────────────────────────────────────────
# Public entry: agent_and_reply (LINE pipeline)
# ─────────────────────────────────────────────


async def agent_and_reply(
    user_id: str,
    reply_token: str,
    content: str | list,
    buffer_items: list[Block] | None = None,
    *,
    skip_quick_reply: bool = False,
) -> None:
    """Full LINE-bound pipeline for one merged debounce window.

    Stages: inbound audit → H6 safety gate → H_DC data correction →
    H_QR quick reply → run_agent → H7.5 output validator + transfer guard
    → H4 profile updater (background) → outbound audit → URL render +
    send → H5 memory compression (background).
    """
    log.info("agent_dispatch_start", user_id=user_id)

    text_for_audit = (
        content if isinstance(content, str) else _extract_text_from_items(buffer_items or [])
    )

    # 1. inbound audit
    await agent_audit.log_inbound_message(
        audit_storage=_audit_storage,
        user_id=user_id,
        text_for_audit=text_for_audit,
        buffer_items=buffer_items,
    )

    # 2. H6 safety gate
    blocked = safety_gate.check(text_for_audit)
    if blocked:
        await agent_audit.log_safety_gate_hit(audit_storage=_audit_storage, user_id=user_id)
        await line_bot.send_response(user_id, reply_token, blocked)
        return

    # 3. H_DC data correction
    correction_reply = await data_correction.check_and_save(
        user_id, text_for_audit, _agent, _profile_mgr,
    )
    if correction_reply:
        await line_bot.send_response(user_id, reply_token, correction_reply)
        return

    # 4. H_QR quick reply intercept
    if not skip_quick_reply:
        from skills.tools import set_current_brand
        ctx = quick_reply_mod.QuickReplyContext(
            user_id=user_id,
            reply_token=reply_token,
            content=content,
            items=tuple(buffer_items or ()),
            profile_mgr=_profile_mgr,
            pending=_pending_store,
            resume=agent_and_reply,
            set_current_brand=set_current_brand,
        )
        result = await quick_reply_mod.intercept(ctx, text=text_for_audit)
        if result.intercepted:
            return

    # 5. agent invocation
    ai_response = await run_agent(user_id, content, buffer_items=buffer_items)
    print(
        f"[Agent] 思考完畢！回覆內容:\n{'─' * 40}\n"
        f"{ai_response[:500]}{'...(截斷)' if len(ai_response) > 500 else ''}\n{'─' * 40}"
    )

    # 6. H7.5 output validator + transfer guard
    ai_response = await _validate_and_maybe_regenerate(
        user_id, ai_response, text_for_audit,
    )

    # 7. profile updater (background)
    asyncio.create_task(profile_updater.extract_and_update(user_id, text_for_audit, ai_response))

    # 8. outbound audit
    await agent_audit.log_outbound_message(
        audit_storage=_audit_storage, user_id=user_id, ai_response=ai_response,
    )

    # 9. send
    # TODO(V1.5): migrate to NotificationRouter once non-LINE channels exist.
    #   Current direct call keeps Phase 0 behaviour identical; abstraction
    #   layer (agent/notifications/) is registered at startup but not wired
    #   here yet — see docs/02-design/specs/notification-channel-strategy.md
    max_len = _config.get("max_reply_length", 5000)
    message_objects = build_line_messages(ai_response[:max_len], skip_quick_reply=True)
    await line_bot.send_response(
        user_id, reply_token, ai_response,
        max_len=max_len, message_objects=message_objects,
    )

    # 10. memory compression (background)
    thread_id = f"line_{user_id}"
    asyncio.create_task(memory_manager.maybe_compress(_agent, thread_id, user_id=user_id))


async def _validate_and_maybe_regenerate(
    user_id: str, ai_response: str, text_for_audit: str,
) -> str:
    """Run H7.5 output validator + transfer guard via validator_pipeline."""
    # Local import: was_transfer_called reads a per-request ContextVar that
    # ``run_agent`` populates. Importing inside the function guarantees we
    # see the freshly-set value rather than capturing a stale closure.
    from skills.tools import was_transfer_called  # noqa: PLC0415

    thread_id = f"line_{user_id}"
    summary = memory_manager.get_summary(thread_id)
    context = await validator_pipeline.build_validator_context(
        user_id=user_id,
        agent=_agent,
        profile_mgr=_profile_mgr,
        summary=summary,
    )

    async def _regen(uid: str, prompt: str) -> str:
        return await run_agent(uid, prompt)

    ai_response = await validator_pipeline.run_output_validator(
        user_id=user_id,
        ai_response=ai_response,
        user_message=text_for_audit,
        context=context,
        audit_storage=_audit_storage,
        regenerate=_regen,
    )

    ai_response = await validator_pipeline.run_transfer_guard(
        user_id=user_id,
        ai_response=ai_response,
        transfer_was_called=was_transfer_called(),
        regenerate=_regen,
        fallback_reply=_templates.get("error_no_reply", "抱歉，系統沒有產生回覆。"),
    )

    return ai_response


__all__ = [
    "agent_and_reply",
    "cleanup_multimodal_checkpoint",
    "cleanup_tool_checkpoint",
    "init",
    "run_agent",
    "strip_stale_multimodal",
]
