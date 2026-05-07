"""H3 orchestrator — agent invocation pipeline.

Extracted from ``harness/debounce.py`` per audit 2026-05-06 §A1. The legacy
file mixed timer-based message merging (the actual debounce concern) with
the entire middleware orchestration pipeline (safety gate, data correction,
quick reply, brand inference, skill prefix building, agent.ainvoke, output
validator, transfer guard, audit, profile updater, memory compression).
That god-class layout meant every cross-cutting tweak required surgery in
the middle of a 1100-line file.

This module owns the orchestration. It exposes two top-level entry points:

- :func:`run_agent` — pure agent invocation: build prefixes, ainvoke, clean
  up checkpoint. Used by both the LINE flow and the ``GET /chat`` test
  endpoint.
- :func:`agent_and_reply` — full LINE-bound pipeline: audit → safety gate →
  data correction → quick reply → run_agent → output validator → transfer
  guard → audit reply → URL rendering → send → memory compression.

Both depend on a small set of injected components (the agent itself, the
profile manager, the audit storage, the opik tracer, etc.) that
``app.py`` startup wires via :func:`init`. Dependencies are passed via
module-level state that mirrors the legacy debounce.init() shape — this
keeps the migration small. The longer-term goal (out of scope for this
PR) is dataclass-based dependency injection so individual functions can
be tested in isolation.

Layering: orchestrator is harness-tier. It imports core, harness, and
skills; never agent-root (forbidden by reverse-import-lint.yml).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from typing import Any

import psycopg
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

import core.line_bot as line_bot
from core.content_utils import extract_text
from core.logging_config import get_logger

import harness.data_correction as data_correction
import harness.memory_manager as memory_manager
import harness.output_validator as output_validator
import harness.profile_updater as profile_updater
import harness.safety_gate as safety_gate
from harness import quick_reply as quick_reply_mod
from harness.buffer import PendingStore, pending as _default_pending_store
from harness.line_ui_factory import build_line_messages
from harness.llm_metrics import extract_usage_from_messages, schedule_log

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
    """Inject runtime dependencies. Called once at app startup.

    Args:
        agent: compiled LangGraph agent.
        config: merged debounce + system config dict.
        templates: reply templates (error_timeout / error_no_reply / ...).
        profile_mgr: ProfileManager (optional — None disables fact features).
        audit_storage: AuditStorage backend (optional — None disables H8).
        opik_tracer: OpikTracer for LLM observability (optional).
        system_prompt_getter: callable returning the current system prompt
            string. Avoids the legacy harness→agent reverse import.
        pending_store: override the module-level Quick Reply pending store
            (tests use this for isolation).
    """
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
# Debug printing helpers
# ─────────────────────────────────────────────


async def _print_context(user_id: str, ai_response: str) -> None:
    """Pretty-print the full conversation state after a turn (debug only)."""
    thread_id = f"line_{user_id}"
    config = {"configurable": {"thread_id": thread_id}}
    sys_prompt = _get_system_prompt()

    messages: list = []
    try:
        state = await _agent.aget_state(config)
        if state and state.values:
            messages = state.values.get("messages", [])
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        print(f"[Debug] 無法讀取 checkpoint: {e}")

    print(f"\n{'═' * 60}")
    print(f"[對話上下文] user={user_id}, thread={thread_id}, 共 {len(messages)} 則訊息")
    print(f"{'═' * 60}")
    if sys_prompt:
        print(f"  [📋 System Prompt]\n{sys_prompt}")
        print(f"{'─' * 60}")
    for i, msg in enumerate(messages):
        role = getattr(msg, "type", "unknown")
        if role == "human":
            content = msg.content if isinstance(msg.content, str) else "[多模態內容]"
            print(f"  [{i}] 👤 Human: {content[:100]}{'...' if isinstance(msg.content, str) and len(msg.content) > 100 else ''}")
        elif role == "ai":
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    print(f"  [{i}] 🤖 AI → tool_call: {tc.get('name', '?')}({json.dumps(tc.get('args', {}), ensure_ascii=False)[:100]})")
            if msg.content:
                text = extract_text(msg.content)
                print(f"  [{i}] 🤖 AI: {text[:100]}{'...' if len(text) > 100 else ''}")
        elif role == "tool":
            name = getattr(msg, "name", "?")
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            print(f"  [{i}] 🔧 Tool({name}): {content[:100]}{'...' if len(content) > 100 else ''}")
        else:
            print(f"  [{i}] ❓ {role}: {str(getattr(msg, 'content', ''))[:100]}")
        print(f"{'─' * 60}")


# ─────────────────────────────────────────────
# Checkpoint cleanup helpers (also re-exported via debounce for back-compat
# with quality_check.py which imports them by their legacy names)
# ─────────────────────────────────────────────


def _content_to_text_reference(content: list, items: list | None = None) -> str:
    """Render multimodal blocks as a text reference (for checkpoint cleanup).

    Mirrors legacy debounce._content_to_text_reference. Kept here because
    it operates on raw LangChain content blocks (dict shape), not the new
    typed ``core.blocks.Block`` form — the checkpoint stores the raw shape
    and we don't want to round-trip through Block just to render placeholders.
    """
    parts: list[str] = []
    media_idx = 0
    media_items = [i for i in (items or []) if isinstance(i, dict) and i.get("type") == "media"]

    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block["text"])
            elif block.get("type") in ("media", "image_url"):
                file_path = (
                    media_items[media_idx]["file_path"]
                    if media_idx < len(media_items)
                    else "unknown"
                )
                mime = block.get("mime_type", "")
                if not mime and block.get("image_url", {}).get("url", "").startswith("data:"):
                    mime = block["image_url"]["url"].split(";")[0].replace("data:", "")
                label = (
                    "圖片" if "image" in mime
                    else "音檔" if "audio" in mime
                    else "影片" if "video" in mime
                    else "媒體"
                )
                parts.append(f"[使用者傳送了{label}: {file_path}]")
                media_idx += 1
        elif isinstance(block, str):
            parts.append(block)

    return "\n".join(parts)


async def strip_stale_multimodal(agent: Any, config: dict) -> None:
    """Replace any historical multimodal HumanMessage in the checkpoint with text.

    Octet-stream payloads from previous failed turns can poison subsequent
    invocations; we degrade them to text references. Idempotent.
    """
    try:
        state = await agent.aget_state(config)
        if not state.values:
            return
        messages = state.values.get("messages", [])
        replaced = 0
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "human" and isinstance(msg.content, list):
                text_parts: list[str] = []
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
                        elif block.get("type") in ("media", "image_url"):
                            mime = block.get("mime_type", "")
                            label = (
                                "圖片" if "image" in str(mime)
                                else "音檔" if "audio" in str(mime)
                                else "影片" if "video" in str(mime)
                                else "媒體"
                            )
                            text_parts.append(f"[使用者曾傳送{label}]")
                    elif isinstance(block, str):
                        text_parts.append(block)
                text_ref = "\n".join(text_parts) if text_parts else "[使用者曾傳送媒體]"
                await agent.aupdate_state(
                    config,
                    {"messages": [HumanMessage(content=text_ref, id=msg.id)]},
                )
                replaced += 1
        if replaced:
            log.info("checkpoint_multimodal_cleaned", count=replaced)
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.warning("checkpoint_multimodal_cleanup_failed", error=str(e), exc_info=True)


async def cleanup_multimodal_checkpoint(
    config: dict, messages: list, buffer_items: list | None,
) -> None:
    """Replace this turn's multimodal HumanMessage with a text reference."""
    try:
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "human" and isinstance(msg.content, list):
                text_ref = _content_to_text_reference(msg.content, buffer_items)
                await _agent.aupdate_state(
                    config,
                    {"messages": [HumanMessage(content=text_ref, id=msg.id)]},
                )
                log.debug("checkpoint_multimodal_replaced", msg_id=msg.id)
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.warning("checkpoint_multimodal_replace_failed", error=str(e), exc_info=True)


async def cleanup_tool_checkpoint(config: dict, messages: list) -> None:
    """Replace ToolMessage + intermediate AIMessage(tool_calls) with refs.

    Drops the full SOP body that ``load_skill`` returned and replaces it
    with ``[已參考技能: <name>]`` markers. Always preserves the most recent
    intermediate AIMessage so the next LLM turn has fresh context.

    Public name (no leading underscore) so callers like ``quality_check``
    can import it directly. ``debounce.py`` re-exports the legacy
    underscore-prefixed name for back-compat.
    """
    try:
        replaced = 0
        cleaned_tool_call_ids: set[str] = set()

        latest_intermediate_ai_id: str | None = None
        for msg in reversed(messages):
            if (
                hasattr(msg, "type") and msg.type == "ai"
                and hasattr(msg, "tool_calls") and msg.tool_calls
                and (not msg.content or not str(msg.content).strip())
            ):
                latest_intermediate_ai_id = msg.id
                break

        for msg in messages:
            if msg.id == latest_intermediate_ai_id:
                continue
            if (
                hasattr(msg, "type") and msg.type == "ai"
                and hasattr(msg, "tool_calls") and msg.tool_calls
                and (not msg.content or not str(msg.content).strip())
            ):
                skill_names: list[str] = []
                for tc in msg.tool_calls:
                    if tc.get("name") == "load_skill":
                        skill_names.append(tc.get("args", {}).get("name", "unknown"))
                if skill_names:
                    for tc in msg.tool_calls:
                        if tc.get("id"):
                            cleaned_tool_call_ids.add(tc["id"])
                    ref = ", ".join(f"[已參考技能: {n}]" for n in skill_names)
                    await _agent.aupdate_state(
                        config,
                        {"messages": [AIMessage(content=ref, id=msg.id)]},
                    )
                    replaced += 1

        for msg in messages:
            if (
                hasattr(msg, "type") and msg.type == "tool"
                and hasattr(msg, "tool_call_id") and msg.tool_call_id in cleaned_tool_call_ids
            ):
                await _agent.aupdate_state(
                    config,
                    {"messages": [RemoveMessage(id=msg.id)]},
                )
                replaced += 1

        if replaced:
            log.info("checkpoint_tool_calls_cleaned", count=replaced)
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.warning("checkpoint_tool_cleanup_failed", error=str(e), exc_info=True)


# ─────────────────────────────────────────────
# Audit helpers
# ─────────────────────────────────────────────


async def _audit_agent_result(
    user_id: str,
    messages: list,
    latency_ms: float,
    turn_id: str | None = None,
    user_question: str | None = None,
) -> None:
    """Persist tool-call audit + LLM usage records for one ainvoke."""
    if not _audit_storage:
        return
    try:
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "tool_calls"):
                for tc in (msg.tool_calls or []):
                    tool_name = tc.get("name", "")
                    args_summary = json.dumps(tc.get("args", {}), ensure_ascii=False)[:200]
                    await _audit_storage.log_tool_invocation(
                        user_id, "smart_lock_agent", tool_name,
                        risk_level="read" if tool_name == "load_skill" else "escalate",
                        args_summary=args_summary,
                    )
                    if tool_name == "transfer_to_human":
                        reason = tc.get("args", {}).get("reason", "")
                        await _audit_storage.log_escalation(user_id, reason)

        model_name = _config.get("model_name", "gemini-2.5-flash")
        ai_steps = extract_usage_from_messages(messages)
        last_index = len(ai_steps) - 1
        for step in ai_steps:
            usage = step["usage"] or {}
            ai_msg = step["message"]
            is_last = step["step_index"] == last_index
            tool_names = [tc.get("name") for tc in (getattr(ai_msg, "tool_calls", None) or [])]
            ai_content = getattr(ai_msg, "content", None)
            if isinstance(ai_content, list):
                ai_content = "".join(
                    b.get("text", "") for b in ai_content if isinstance(b, dict) and b.get("type") == "text"
                )
            schedule_log(
                _audit_storage,
                user_id=user_id,
                call_site="react_agent_step",
                model=model_name,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                total_tokens=usage.get("total_tokens"),
                latency_ms=int(latency_ms) if is_last else None,
                success=True,
                turn_id=turn_id,
                user_question=user_question,
                ai_reply=ai_content if isinstance(ai_content, str) else None,
                metadata={
                    "step_index": step["step_index"],
                    "is_final": is_last,
                    "tool_calls": tool_names or None,
                },
            )
        if not ai_steps:
            schedule_log(
                _audit_storage,
                user_id=user_id,
                call_site="react_agent_step",
                model=model_name,
                latency_ms=int(latency_ms),
                success=False,
                error_type="no_ai_message",
                turn_id=turn_id,
                user_question=user_question,
            )
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.warning("audit_agent_result_failed", error=str(e), exc_info=True)


# ─────────────────────────────────────────────
# Skill / brand prefix construction
# ─────────────────────────────────────────────


def _extract_text_from_items(items: list) -> str:
    """Best-effort textification of buffer items (audit / log path)."""
    parts: list[str] = []
    for item in items:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and item.get("type") == "media":
            label = item.get("label", "媒體")
            file_path = item.get("file_path", "")
            parts.append(f"[使用者傳送了{label}: {file_path}]")
    return "\n".join(parts)


async def _resolve_brand_model(
    user_id: str, user_input: str | list,
) -> tuple[str | None, str | None, str | None, str | None, str]:
    """Load profile, infer brand/model from user text, possibly switch facts.

    Returns:
        (brand, model, mentioned_brand, mentioned_model, profile_text)
    """
    brand: str | None = None
    model: str | None = None
    profile_text: str = ""

    if not (_profile_mgr and _profile_mgr.facts_enabled):
        return brand, model, None, None, profile_text

    profile_text, facts = await _profile_mgr.load_full_profile_with_facts(user_id)
    brand = facts.get("device_brand")
    model = facts.get("device_model")

    input_text = user_input if isinstance(user_input, str) else " ".join(
        b.get("text", "") for b in user_input if isinstance(b, dict)
    )
    from harness.line_ui_factory import infer_brand_from_text
    mentioned_brand, mentioned_model = infer_brand_from_text(input_text)

    if mentioned_brand and mentioned_brand != brand:
        old_brand, old_model = brand, model
        brand = mentioned_brand
        model = mentioned_model
        asyncio.create_task(_profile_mgr.update_fact(user_id, "device_brand", brand))
        if model:
            asyncio.create_task(_profile_mgr.update_fact(user_id, "device_model", model))
        elif old_model and old_brand and old_brand != brand:
            asyncio.create_task(_profile_mgr.clear_fact(user_id, "device_model"))
        log.info(
            "brand_switched", user_id=user_id,
            from_brand=old_brand or "", from_model=old_model or "",
            to_brand=brand, to_model=model or "",
        )
    elif mentioned_brand == brand and mentioned_model and mentioned_model != model:
        old_model = model
        model = mentioned_model
        asyncio.create_task(_profile_mgr.update_fact(user_id, "device_model", model))
        log.info(
            "model_switched", user_id=user_id, brand=brand,
            from_model=old_model or "", to_model=model,
        )

    return brand, model, mentioned_brand, mentioned_model, profile_text


def _build_skills_prefix(
    brand: str | None, model: str | None,
    mentioned_brand: str | None, mentioned_model: str | None,
) -> str:
    """Build the [可用技能] prefix for the user message."""
    from skills import filter_skills
    from skills.tools import get_skills

    registered = get_skills()

    def _brand_has_skills(b: str) -> bool:
        return any(s.brands and b in s.brands for s in registered)

    _SUB_PFX = ("ts-", "app-", "ss-")
    _SUB_EXC = {"app-guide", "ss-dormakaba"}

    if brand and _brand_has_skills(brand) and model:
        skill_list = filter_skills(registered, brand, model)
        header = f"[可用技能]\n（用戶為 {brand} {model}，使用 load_skill 載入）\n"
    elif brand and _brand_has_skills(brand):
        skill_list = filter_skills(registered, brand, None)
        header = (
            f"[可用技能]\n"
            f"⚠️ {brand} 型號未確認，僅能載入 _common/* 與品牌通用技能。回覆時請聲明：\n"
            f"「以下為通用建議，您的型號實際操作可能略有差異，建議補充型號取得精準步驟。」\n"
        )
    elif brand:
        skill_list = filter_skills(registered, None, None)
        header = (
            f"[可用技能]\n"
            f"⚠️ 目前無 {brand} 詳細技能資料，僅能提供 _common/* 通用建議。\n"
            f"禁止說「我這邊沒有 {brand} 的詳細資料」「建議您查看說明書」這類話術；\n"
            f"優先載入 _common/* 給通用建議，若客戶問題需要型號專屬步驟就呼叫 transfer_to_human 安排專員協助。\n"
        )
    else:
        skill_list = filter_skills(registered, None, None)
        header = (
            "[可用技能]\n"
            "⚠️ 品牌或型號未確認，僅能載入 _common/* 通用資訊。回覆時請聲明：\n"
            "「以下為通用建議，您的型號實際操作可能略有差異。」\n"
            "**請呼叫 update_user_info 確認用戶品牌。**\n"
        )

    if mentioned_brand and brand and mentioned_brand != brand:
        switch_lines = [
            "",
            f"⚠️ 切換產品上下文：客戶在本輪訊息中提到「{mentioned_brand}",
        ]
        if mentioned_model:
            switch_lines[-1] += f" {mentioned_model}"
        switch_lines[-1] += f"」，與紀錄中的 {brand}"
        if model:
            switch_lines[-1] += f" {model}"
        switch_lines[-1] += " 不同。"
        switch_lines.append(
            f"請先呼叫 update_user_info(brand=\"{mentioned_brand}\""
            + (f", model=\"{mentioned_model}\"" if mentioned_model else "")
            + ") 切換產品上下文，"
            "再 load_skill 載入對應技能回答客戶原問題。"
        )
        switch_lines.append(
            "禁止用「客戶設備型號跟紀錄不符」當拒答理由，也禁止叫客戶查說明書。"
        )
        header += "\n".join(switch_lines) + "\n"

    top_level = [
        s for s in skill_list
        if s.name in _SUB_EXC or not s.name.startswith(_SUB_PFX)
    ]
    doc_lines = "\n".join(f"- {s.name}: {s.description}" for s in top_level)
    return f"{header}{doc_lines}\n\n"


# ─────────────────────────────────────────────
# Public entry: run_agent
# ─────────────────────────────────────────────


# Internal regex shared by run_agent — strips internal-reference markers the
# LLM occasionally echoes back from cleaned ToolMessage stubs.
_REF_MARKER_RE = re.compile(r"\s*\[已參考(?:技能)?:[^\]]*\][\s,，]*")


async def run_agent(
    user_id: str,
    user_input: str | list,
    buffer_items: list | None = None,
) -> str:
    """Send the user's input through the ReAct agent and return the AI text.

    Args:
        user_input: plain text or LangChain multimodal content blocks list.
        buffer_items: legacy buffer items (used by checkpoint cleanup to look
            up file paths). May be None when called from /chat.
    """
    from skills.tools import (
        set_current_user_id, set_current_brand, reset_run_state, set_current_user_input,
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

    t_phase_start = time.monotonic()
    try:
        thread_id = f"line_{user_id}"

        brand, model, mentioned_brand, mentioned_model, profile_text = await _resolve_brand_model(
            user_id, user_input
        )

        profile_prefix = ""
        if _profile_mgr and _profile_mgr.enabled and profile_text:
            profile_prefix = f"[用戶資料]\n{profile_text}\n\n"

        set_current_brand(brand, model)
        skills_prefix = _build_skills_prefix(brand, model, mentioned_brand, mentioned_model)

        config = {"configurable": {"thread_id": thread_id}}

        t_pre_strip = time.monotonic()
        await strip_stale_multimodal(_agent, config)

        summary_prefix = ""
        summary = memory_manager.get_summary(thread_id)
        if summary:
            log.debug("summary_injected", user_id=user_id, length=len(summary))
            summary_prefix = memory_manager.build_summary_prefix(summary)

        if is_multimodal:
            prefix = skills_prefix
            if profile_prefix:
                prefix += profile_prefix
            if summary_prefix:
                prefix += summary_prefix
            prefix += "[用戶訊息]\n"
            message_content: str | list = [{"type": "text", "text": prefix}] + user_input
        else:
            message = f"{skills_prefix}{profile_prefix}[用戶訊息]\n{user_input}"
            if summary_prefix:
                message = summary_prefix + message
            message_content = message

        display = _extract_text_from_items(buffer_items) if buffer_items else (
            extract_text(message_content) if isinstance(message_content, str) else "[多模態訊息]"
        )
        log.info("agent_invoke_start", user_id=user_id, input_preview=display[:200])
        print(f"[Agent] 送入內容:\n{'─' * 40}\n{display[:500]}{'...(截斷)' if len(display) > 500 else ''}\n{'─' * 40}")

        run_config = config.copy()
        if _opik_tracer:
            run_config["callbacks"] = [_opik_tracer]
        run_config.setdefault("metadata", {})["user_id"] = user_id

        t0 = time.monotonic()
        pre_setup_s = t_pre_strip - t_phase_start
        strip_s = t0 - t_pre_strip
        try:
            result = await asyncio.wait_for(
                _agent.ainvoke(
                    {"messages": [{"role": "user", "content": message_content}]},
                    run_config,
                ),
                timeout=request_timeout,
            )
        except asyncio.TimeoutError:
            ainvoke_s = time.monotonic() - t0
            log.error(
                "agent_timeout", user_id=user_id, timeout_s=request_timeout,
                pre_s=round(pre_setup_s, 2), strip_s=round(strip_s, 2), ainvoke_s=round(ainvoke_s, 2),
            )
            return _templates.get("error_timeout", "不好意思，系統處理時間過長，請稍後再試一次。")
        t_invoke_done = time.monotonic()
        latency_ms = (t_invoke_done - t0) * 1000

        messages = result.get("messages", [])

        if is_multimodal:
            await cleanup_multimodal_checkpoint(config, messages, buffer_items)

        turn_id = uuid.uuid4().hex[:16]
        asyncio.create_task(_audit_agent_result(user_id, messages, latency_ms, turn_id, display))

        ai_response = _templates.get("error_no_reply", "抱歉，系統沒有產生回覆。")
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                ai_response = extract_text(msg.content)
                break

        ai_response = _REF_MARKER_RE.sub("", ai_response).strip()

        # Background tool-checkpoint cleanup so the user reply isn't blocked.
        asyncio.create_task(cleanup_tool_checkpoint(config, messages))
        total_s = time.monotonic() - t_phase_start
        ainvoke_s = (t_invoke_done - t0)
        log.info(
            "agent_invoke_done", user_id=user_id,
            pre_s=round(pre_setup_s, 2), strip_s=round(strip_s, 2),
            ainvoke_s=round(ainvoke_s, 2), total_s=round(total_s, 2),
        )

        return ai_response

    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.error("agent_run_failed", user_id=user_id, error=str(e), exc_info=True)
        return _templates.get("error_system", "不好意思，系統大腦剛剛稍微當機了一下，請稍後再試一次！")


# ─────────────────────────────────────────────
# Public entry: agent_and_reply (LINE pipeline)
# ─────────────────────────────────────────────


_TRANSFER_CLAIM_PHRASES = (
    "已為您轉接", "已為您安排專員", "已安排專員",
    "為您轉接專員", "幫您轉接專員", "已經為您安排專員",
    "正在為您安排專員",
)


async def agent_and_reply(
    user_id: str,
    reply_token: str,
    content: str | list,
    buffer_items: list | None = None,
    *,
    skip_quick_reply: bool = False,
) -> None:
    """Full LINE-bound pipeline for one merged debounce window.

    Pipeline stages:
        1. log inbound user message (H8 audit)
        2. H6 safety gate
        3. H_DC data correction intercept
        4. H_QR quick reply intercept (unless caller already passed brand/model)
        5. run_agent — actual LLM call
        6. H7.5 output validator + transfer guard
        7. H4 background profile updater
        8. H8 audit reply
        9. H7 URL→FlexMessage rendering + send
        10. H5 background memory compression
    """
    log.info("agent_dispatch_start", user_id=user_id)

    text_for_audit = (
        content if isinstance(content, str) else _extract_text_from_items(buffer_items or [])
    )

    # 1. inbound audit
    if _audit_storage:
        try:
            media_paths = [
                item["file_path"]
                for item in (buffer_items or [])
                if isinstance(item, dict) and item.get("type") == "media" and item.get("file_path")
            ]
            if media_paths:
                await _audit_storage.log_event(
                    event_type="conversation",
                    actor_id=user_id,
                    actor_role="user",
                    action="conversation.message",
                    payload={"content": text_for_audit, "media_files": media_paths},
                )
            else:
                await _audit_storage.log_message(user_id, "user", text_for_audit)
        except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
            log.warning("audit_user_message_failed", user_id=user_id, error=str(e), exc_info=True)

    # 2. safety gate
    blocked = safety_gate.check(text_for_audit)
    if blocked:
        if _audit_storage:
            try:
                await _audit_storage.log_safety_gate(user_id, "blocked", [{"keyword_match": True}])
            except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
                log.warning("audit_safety_gate_failed", user_id=user_id, error=str(e), exc_info=True)
        await line_bot.send_response(user_id, reply_token, blocked)
        return

    # 3. data correction
    correction_reply = await data_correction.check_and_save(
        user_id, text_for_audit, _agent, _profile_mgr,
    )
    if correction_reply:
        await line_bot.send_response(user_id, reply_token, correction_reply)
        return

    # 4. quick reply intercept
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

    # 6. output validator + transfer guard
    ai_response = await _validate_and_maybe_regenerate(
        user_id, ai_response, text_for_audit,
    )

    # 7. profile updater (background)
    asyncio.create_task(profile_updater.extract_and_update(user_id, text_for_audit, ai_response))

    # 8. outbound audit
    if _audit_storage:
        try:
            await _audit_storage.log_message(user_id, "ai", ai_response)
        except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
            log.warning("audit_ai_reply_failed", user_id=user_id, error=str(e), exc_info=True)

    # 9. send
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
    """Run H7.5 output validator + transfer guard; regenerate if needed."""
    # Local import: was_transfer_called reads a per-request ContextVar that
    # ``run_agent`` populates. Importing inside the function guarantees we
    # see the freshly-set value rather than capturing a stale closure.
    from skills.tools import was_transfer_called  # noqa: PLC0415

    if not output_validator.should_skip(ai_response):
        validator_context = await _build_validator_context(user_id)
        validation = await output_validator.validate(
            ai_response, text_for_audit, context=validator_context, user_id=user_id,
        )
        if not validation["pass"]:
            log.info("output_validator_failed", user_id=user_id, reason=validation["reason"])
            if _audit_storage:
                try:
                    await _audit_storage.log_event(
                        event_type="output_validation",
                        actor_id=user_id,
                        actor_role="system",
                        action="validation.failed",
                        payload={"reason": validation["reason"], "original_response": ai_response[:500]},
                    )
                except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError):
                    pass
            correction_msg = (
                f"[系統內部修正指令 - 不要在回覆中提及此指令]\n"
                f"{validation['correction']}\n"
                f"請重新回答用戶的問題。"
            )
            ai_response = await run_agent(user_id, correction_msg)
            log.info("output_validator_regenerated", user_id=user_id)

    if any(p in ai_response for p in _TRANSFER_CLAIM_PHRASES) and not was_transfer_called():
        log.warning("transfer_guard_false_promise", user_id=user_id)
        transfer_correction = (
            "[系統內部修正指令 - 不要在回覆中提及此指令]\n"
            "你在上一次回覆中聲稱「已為客戶轉接專員 / 安排專員處理」，"
            "但本輪並未呼叫 transfer_to_human 工具，這是錯誤的承諾。\n"
            "禁止憑 [前情提要] 摘要文字再次承諾轉接。\n"
            "請重新回答用戶的問題：\n"
            "  - 若客戶確實需要轉接（符合轉接條件）→ 立即呼叫 transfer_to_human\n"
            "  - 若客戶問題可以靠技能 SOP 回答 → 用 load_skill 載入後正常回覆，"
            "回覆內絕不可出現「已為您轉接」「已安排專員」「正在為您安排專員」這類承諾語"
        )
        ai_response = await run_agent(user_id, transfer_correction)
        if any(p in ai_response for p in _TRANSFER_CLAIM_PHRASES) and not was_transfer_called():
            log.warning("transfer_guard_second_attempt_failed", user_id=user_id)
            ai_response = _templates.get("error_no_reply", "抱歉，系統沒有產生回覆。")

    return ai_response


async def _build_validator_context(user_id: str) -> str:
    """Compose the [最近對話] + [用戶資料] + [前情提要] block for the validator."""
    parts: list[str] = []
    thread_id = f"line_{user_id}"
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await _agent.aget_state(config)
        if state and state.values:
            recent_msgs = state.values.get("messages", [])[-6:]
            history_lines: list[str] = []
            for msg in recent_msgs:
                role = getattr(msg, "type", "")
                if role == "human":
                    text = msg.content if isinstance(msg.content, str) else "[多模態]"
                    history_lines.append(f"用戶: {text[:100]}")
                elif role == "ai" and msg.content:
                    text = extract_text(msg.content)
                    if text:
                        history_lines.append(f"客服: {text[:100]}")
            if history_lines:
                parts.append("[最近對話]\n" + "\n".join(history_lines))
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError):
        pass
    if _profile_mgr and _profile_mgr.enabled:
        profile_text = await _profile_mgr.load_full_profile(user_id)
        if profile_text:
            parts.append(f"[用戶資料]\n{profile_text}")
    summary = memory_manager.get_summary(thread_id)
    if summary:
        parts.append(f"[前情提要]\n{summary}")
    return "\n\n".join(parts)


__all__ = [
    "agent_and_reply",
    "cleanup_multimodal_checkpoint",
    "cleanup_tool_checkpoint",
    "init",
    "run_agent",
    "strip_stale_multimodal",
]
