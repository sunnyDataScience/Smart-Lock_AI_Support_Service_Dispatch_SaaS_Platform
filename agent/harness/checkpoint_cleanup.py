"""LangGraph checkpoint cleanup helpers.

Extracted from ``harness/orchestrator.py`` per RP3 F2.4. The orchestrator
historically owned three checkpoint-cleanup helpers:

- ``strip_stale_multimodal`` — preventive: degrade any multimodal
  HumanMessage left in the checkpoint from a previous failed turn into
  text references, so this turn's LLM call doesn't choke on stale base64.
- ``cleanup_multimodal_checkpoint`` — postmortem: replace this turn's
  multimodal HumanMessage with a text reference (rendered from the
  ``list[Block]`` the debounce buffer produced).
- ``cleanup_tool_checkpoint`` — postmortem: replace ToolMessage payloads
  (full SOP body) with ``[已參考技能: <name>]`` markers.

All three are I/O-heavy (call ``agent.aupdate_state``) but contain no
orchestration logic — moving them out of orchestrator.py is a pure SRP win.

F1 contract preserved (RP3 follow-up F1, not the F1 design doc):
- ``cleanup_multimodal`` accepts ``buffer_items: list[Block] | None`` (not
  the legacy raw LangChain content list).
- ``_blocks_to_text_reference`` works on ``list[Block]`` and uses
  ``core.blocks.to_text(..., with_media_refs=True)`` to render each media
  block as ``[使用者傳送了{label}: {file_path}]``.

Layering: harness module. Imports ``core.blocks`` (lower-tier) and
``langchain_core.messages``. Never agent-root.
"""

from __future__ import annotations

from typing import Any

import psycopg
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from core.blocks import Block, to_text as blocks_to_text
from core.logging_config import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────
# Block → text-reference renderer (F1 contract)
# ─────────────────────────────────────────────


def _blocks_to_text_reference(blocks: list[Block]) -> str:
    """Render this turn's :class:`Block` list as the checkpoint text reference.

    F1 (RP3 follow-up) replaced the legacy ``_content_to_text_reference``
    helper that parsed raw LangChain ``content`` dicts. Now that the
    orchestrator owns the typed :class:`Block` list end-to-end, we render
    straight from it — same ``[使用者傳送了{label}: {file_path}]`` output,
    no shim. Falls back to ``"[使用者曾傳送媒體]"`` when ``blocks`` is
    falsy so the cleanup path always writes something coherent.
    """
    if not blocks:
        return "[使用者曾傳送媒體]"
    return blocks_to_text(blocks, with_media_refs=True) or "[使用者曾傳送媒體]"


# ─────────────────────────────────────────────
# Preventive: strip stale multimodal from prior turns
# ─────────────────────────────────────────────


async def strip_stale_multimodal(agent: Any, config: dict) -> None:
    """Replace any historical multimodal HumanMessage with a text reference.

    Octet-stream payloads from previous failed turns can poison subsequent
    invocations (the LLM provider rejects oversized binary blobs); we
    degrade them to text references. Idempotent: running on a clean
    checkpoint is a no-op.

    This helper still parses the *raw* LangChain ``content`` dict shape
    because we're cleaning checkpoints from older turns — those checkpoints
    were written before the F1 typed-Block migration and can contain any
    legacy block dict. Future turns will write text already (since the
    postmortem ``cleanup_multimodal`` rewrites the same turn's message).
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


# ─────────────────────────────────────────────
# Postmortem: this-turn cleanup (F1 list[Block] interface)
# ─────────────────────────────────────────────


async def cleanup_multimodal(
    agent: Any,
    config: dict,
    messages: list,
    buffer_items: list[Block] | None,
) -> None:
    """Replace this turn's multimodal HumanMessage with a text reference.

    Reads file paths and media labels straight off the :class:`Block` list
    produced by the debounce buffer, no longer the raw LangChain dict shape
    (this is the F1 contract — see module docstring).
    """
    try:
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "human" and isinstance(msg.content, list):
                text_ref = _blocks_to_text_reference(buffer_items or [])
                await agent.aupdate_state(
                    config,
                    {"messages": [HumanMessage(content=text_ref, id=msg.id)]},
                )
                log.debug("checkpoint_multimodal_replaced", msg_id=msg.id)
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.warning("checkpoint_multimodal_replace_failed", error=str(e), exc_info=True)


async def cleanup_tool(agent: Any, config: dict, messages: list) -> None:
    """Replace ToolMessage + intermediate AIMessage(tool_calls) with refs.

    Drops the full SOP body that ``load_skill`` returned and replaces it
    with ``[已參考技能: <name>]`` markers. Always preserves the most recent
    intermediate AIMessage so the next LLM turn has fresh context.
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
                    await agent.aupdate_state(
                        config,
                        {"messages": [AIMessage(content=ref, id=msg.id)]},
                    )
                    replaced += 1

        for msg in messages:
            if (
                hasattr(msg, "type") and msg.type == "tool"
                and hasattr(msg, "tool_call_id") and msg.tool_call_id in cleaned_tool_call_ids
            ):
                await agent.aupdate_state(
                    config,
                    {"messages": [RemoveMessage(id=msg.id)]},
                )
                replaced += 1

        if replaced:
            log.info("checkpoint_tool_calls_cleaned", count=replaced)
    except (psycopg.Error, OSError, RuntimeError, ValueError, TimeoutError, ConnectionError, AttributeError) as e:
        log.warning("checkpoint_tool_cleanup_failed", error=str(e), exc_info=True)


__all__ = [
    "cleanup_multimodal",
    "cleanup_tool",
    "strip_stale_multimodal",
]
