"""Audit log writes for agent results, inbound, and outbound messages.

Extracted from ``harness/orchestrator.py`` per RP3 F2.5. The legacy
``_audit_agent_result`` was a 70-line block dedicated to extracting tool
invocations + LLM usage records from the agent's message list and
scheduling audit writes. Plus the inbound/outbound audit calls scattered
in ``agent_and_reply``. All three are pure DB-write side flows that don't
shape the agent pipeline — they just observe it.

This module owns those three writes as standalone async helpers. Callers
inject the audit storage so the helpers are unit-testable with a fake.

F1 contract preserved: inbound media audit uses
``[b.file_path for b in items if b.type == "media" and b.file_path]``
on typed :class:`Block` instances (not legacy dict shape).

Layering: harness module. Imports ``core.blocks`` (lower-tier) and
``llm_metrics`` (sibling). Never agent-root.
"""
from __future__ import annotations

PHASE: str = "H8"  # per harness/__init__.py PIPELINE inventory (ADR-0024 §3 S2)

import json
from typing import Any

import psycopg

from core.blocks import Block
from core.logging_config import get_logger
from harness.llm_metrics import extract_usage_from_messages, schedule_log

log = get_logger(__name__)


# ─────────────────────────────────────────────
# Agent-result audit (tool invocations + LLM usage)
# ─────────────────────────────────────────────


async def write_agent_result(
    *,
    audit_storage: Any | None,
    user_id: str,
    messages: list,
    latency_ms: float,
    model_name: str,
    turn_id: str | None = None,
    user_question: str | None = None,
) -> None:
    """Persist tool-call audit + LLM usage records for one ainvoke.

    Schedules ``log_tool_invocation`` + ``log_escalation`` for each tool
    call, then walks the AI messages to schedule one ``schedule_log`` per
    react-agent step (so we capture token counts even for intermediate
    steps that only emitted tool calls).
    """
    if not audit_storage:
        return
    try:
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "tool_calls"):
                for tc in (msg.tool_calls or []):
                    tool_name = tc.get("name", "")
                    args_summary = json.dumps(tc.get("args", {}), ensure_ascii=False)[:200]
                    await audit_storage.log_tool_invocation(
                        user_id, "smart_lock_agent", tool_name,
                        # read-only tools 都 risk=read；transfer / update_user_info 才升 escalate
                        risk_level="read" if tool_name in ("load_skill", "load_product_info") else "escalate",
                        args_summary=args_summary,
                    )
                    if tool_name == "transfer_to_human":
                        reason = tc.get("args", {}).get("reason", "")
                        await audit_storage.log_escalation(user_id, reason)

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
                audit_storage,
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
                audit_storage,
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
# Inbound user message (text-only or media-rich)
# ─────────────────────────────────────────────


async def log_inbound_message(
    *,
    audit_storage: Any | None,
    user_id: str,
    text_for_audit: str,
    buffer_items: list[Block] | None,
) -> None:
    """Audit one inbound user turn.

    F1 contract: media file paths come from typed Block attribute access
    (``b.type == "media" and b.file_path``). When at least one media file
    is present we use the rich ``log_event`` payload so the dashboard can
    render the files; otherwise the plain ``log_message`` is enough.
    """
    if not audit_storage:
        return
    try:
        media_paths = [
            b.file_path
            for b in (buffer_items or [])
            if b.type == "media" and b.file_path
        ]
        if media_paths:
            await audit_storage.log_event(
                event_type="conversation",
                actor_id=user_id,
                actor_role="user",
                action="conversation.message",
                payload={"content": text_for_audit, "media_files": media_paths},
            )
        else:
            await audit_storage.log_message(user_id, "user", text_for_audit)
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.warning("audit_user_message_failed", user_id=user_id, error=str(e), exc_info=True)


# ─────────────────────────────────────────────
# Outbound AI reply
# ─────────────────────────────────────────────


async def log_outbound_message(
    *,
    audit_storage: Any | None,
    user_id: str,
    ai_response: str,
) -> None:
    """Audit one outbound AI reply."""
    if not audit_storage:
        return
    try:
        await audit_storage.log_message(user_id, "ai", ai_response)
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.warning("audit_ai_reply_failed", user_id=user_id, error=str(e), exc_info=True)


# ─────────────────────────────────────────────
# Safety-gate hit (H6)
# ─────────────────────────────────────────────


async def log_safety_gate_hit(
    *,
    audit_storage: Any | None,
    user_id: str,
) -> None:
    """Audit one H6 safety-gate block.

    Single-keyword shape preserved from legacy: ``[{"keyword_match": True}]``.
    The orchestrator currently only blocks on keyword hits so we don't
    expose a richer detail object yet.
    """
    if not audit_storage:
        return
    try:
        await audit_storage.log_safety_gate(user_id, "blocked", [{"keyword_match": True}])
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.warning("audit_safety_gate_failed", user_id=user_id, error=str(e), exc_info=True)


__all__ = [
    "log_inbound_message",
    "log_outbound_message",
    "log_safety_gate_hit",
    "write_agent_result",
]
