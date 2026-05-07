"""H7.5 output validator + transfer-claim guard pipeline.

Extracted from ``harness/orchestrator.py:_validate_and_maybe_regenerate``
per RP3 F2.3. The legacy function fused two separate validators (output
validator + transfer guard) and the audit-log writes for both, plus the
"build context" helper, into one 50-line block.

This module exposes them as small composable pieces:

- :func:`run_output_validator` — H7.5: detect forbidden phrases, build a
  correction prompt, ask the agent to regenerate.
- :func:`run_transfer_guard` — guard against false promises («已為您轉接
  專員») when ``transfer_to_human`` was never actually called.

Both helpers accept the agent-rerun callable as a parameter so they can be
unit-tested without booting the entire orchestrator.

H6 (input safety gate) is intentionally NOT moved here — it's already a
single-line ``safety_gate.check(text)`` call in orchestrator. Wrapping it
would only add indirection.

Layering: harness module. Imports ``output_validator`` (sibling) and core.
Never agent-root.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import psycopg

import harness.output_validator as output_validator
from core.content_utils import extract_text
from core.logging_config import get_logger

log = get_logger(__name__)


# Phrases the LLM occasionally emits to claim "I transferred you to a human"
# when it never actually called the ``transfer_to_human`` tool. The guard
# detects these and forces a regeneration so we don't make false promises.
TRANSFER_CLAIM_PHRASES = (
    "已為您轉接", "已為您安排專員", "已安排專員",
    "為您轉接專員", "幫您轉接專員", "已經為您安排專員",
    "正在為您安排專員",
)


# Type alias: a callable that re-runs the agent with a correction prompt.
# Signature mirrors ``orchestrator.run_agent(user_id, content)`` (the
# variants we use here pass ``buffer_items=None`` implicitly).
RegenerateFn = Callable[[str, str], Awaitable[str]]


# ─────────────────────────────────────────────
# H7.5 output validator
# ─────────────────────────────────────────────


async def run_output_validator(
    *,
    user_id: str,
    ai_response: str,
    user_message: str,
    context: str,
    audit_storage: Any | None,
    regenerate: RegenerateFn,
) -> str:
    """Run H7.5; if it fails, regenerate via ``regenerate`` and return new text.

    Returns the (possibly-regenerated) AI response. When the validator passes
    or is skipped, the original ``ai_response`` is returned unchanged.
    """
    if output_validator.should_skip(ai_response):
        return ai_response

    validation = await output_validator.validate(
        ai_response, user_message, context=context, user_id=user_id,
    )
    if validation["pass"]:
        return ai_response

    log.info("output_validator_failed", user_id=user_id, reason=validation["reason"])
    if audit_storage:
        try:
            await audit_storage.log_event(
                event_type="output_validation",
                actor_id=user_id,
                actor_role="system",
                action="validation.failed",
                payload={
                    "reason": validation["reason"],
                    "original_response": ai_response[:500],
                },
            )
        except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError):
            # Audit failure must never break the main flow; the validator
            # decision (regenerate) still applies.
            pass

    correction_msg = (
        f"[系統內部修正指令 - 不要在回覆中提及此指令]\n"
        f"{validation['correction']}\n"
        f"請重新回答用戶的問題。"
    )
    new_response = await regenerate(user_id, correction_msg)
    log.info("output_validator_regenerated", user_id=user_id)
    return new_response


# ─────────────────────────────────────────────
# Transfer-claim guard
# ─────────────────────────────────────────────


async def run_transfer_guard(
    *,
    user_id: str,
    ai_response: str,
    transfer_was_called: bool,
    regenerate: RegenerateFn,
    fallback_reply: str,
) -> str:
    """Detect false transfer promises; regenerate up to once, else fallback.

    The LLM sometimes paraphrases prior conversation summaries («前情提要»)
    and re-promises a transfer that already happened — but in this turn it
    didn't actually invoke the tool, so the LINE backend never opens a
    ticket. We detect that drift and force a regeneration with explicit
    instructions. If the regeneration *also* makes the false claim we bail
    out to a generic apology rather than third-attempting an LLM call.
    """
    if not _has_transfer_claim(ai_response) or transfer_was_called:
        return ai_response

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
    new_response = await regenerate(user_id, transfer_correction)
    if _has_transfer_claim(new_response) and not transfer_was_called:
        log.warning("transfer_guard_second_attempt_failed", user_id=user_id)
        return fallback_reply
    return new_response


def _has_transfer_claim(text: str) -> bool:
    """Return True if any forbidden transfer-claim phrase appears in ``text``."""
    return any(p in text for p in TRANSFER_CLAIM_PHRASES)


# ─────────────────────────────────────────────
# Validator context builder
# ─────────────────────────────────────────────


async def build_validator_context(
    *,
    user_id: str,
    agent: Any,
    profile_mgr: Any | None,
    summary: str | None,
) -> str:
    """Compose the [最近對話] + [用戶資料] + [前情提要] block for H7.5.

    Reads the agent's own checkpoint to extract the last 6 messages, then
    optionally appends the profile text and the running conversation summary.
    Errors reading the checkpoint degrade silently to "no [最近對話]" — the
    validator can still run on the response alone.
    """
    parts: list[str] = []
    thread_id = f"line_{user_id}"
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await agent.aget_state(config)
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
    if profile_mgr and profile_mgr.enabled:
        profile_text = await profile_mgr.load_full_profile(user_id)
        if profile_text:
            parts.append(f"[用戶資料]\n{profile_text}")
    if summary:
        parts.append(f"[前情提要]\n{summary}")
    return "\n\n".join(parts)


__all__ = [
    "TRANSFER_CLAIM_PHRASES",
    "build_validator_context",
    "run_output_validator",
    "run_transfer_guard",
]
