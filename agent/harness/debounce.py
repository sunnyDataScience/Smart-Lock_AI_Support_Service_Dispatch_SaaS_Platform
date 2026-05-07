"""H3 debounce — timer-based message merging.

Single responsibility (post-RP3): coalesce rapid-fire LINE messages from the
same user into one logical turn before invoking the agent. Everything that
used to live here — orchestration, safety gate, quick reply, audit log,
output validator — now lives in dedicated modules:

- ``harness/orchestrator.py`` — agent_and_reply / run_agent pipeline
- ``harness/quick_reply.py`` — H_QR brand/model collection state machine
- ``harness/buffer.py`` — typed BufferStore + PendingStore (locked)
- ``core/blocks.py`` — content block schema

This file is the *only* place the debounce timer lives. Public API:

- :func:`init` — wire dependencies (delegates to orchestrator.init).
- :func:`add_message_to_buffer` — webhook entry point: append a content
  block to the user's buffer and (re)start the flush timer.
- :func:`process_and_reply` — the timer coroutine: wait for the debounce
  window, then hand the merged buffer to the orchestrator.
- :func:`cleanup_stale_buffers` — periodic eviction of timed-out buffers.
- :func:`run_agent` — re-export of orchestrator.run_agent (used by
  ``GET /chat`` test endpoint and quality_check).

Back-compat re-exports for callers that pre-date the split:
- ``_cleanup_tool_checkpoint`` / ``_cleanup_multimodal_checkpoint`` /
  ``_strip_stale_multimodal`` — same names as the legacy private helpers,
  now thin pass-throughs to ``orchestrator``.
"""

from __future__ import annotations

import asyncio

from core.blocks import Block, from_buffer_item, to_langchain_content
from core.logging_config import get_logger

import harness.orchestrator as orchestrator
from harness.buffer import buffers

# Re-exports (back-compat) — see module docstring.
from harness.orchestrator import (  # noqa: F401  re-export for legacy callers
    agent_and_reply,
    cleanup_multimodal_checkpoint as _cleanup_multimodal_checkpoint,
    cleanup_tool_checkpoint as _cleanup_tool_checkpoint,
    run_agent,
    strip_stale_multimodal as _strip_stale_multimodal,
)

log = get_logger(__name__)

# Module-level config copy for the timer. Orchestrator owns the canonical
# config; we only need a few keys here (buffer_wait, media_extra_wait,
# buffer_ttl, cleanup_interval, enabled).
_config: dict = {}


def init(
    agent,
    config: dict,
    templates: dict,
    profile_mgr=None,
    audit_storage=None,
    opik_tracer=None,
    system_prompt_getter=None,
):
    """Inject runtime dependencies. Called once at app startup.

    Forwards everything to :func:`orchestrator.init` and keeps a reference
    to ``config`` for the timer's own use.
    """
    global _config
    _config = config
    orchestrator.init(
        agent, config, templates,
        profile_mgr=profile_mgr,
        audit_storage=audit_storage,
        opik_tracer=opik_tracer,
        system_prompt_getter=system_prompt_getter,
    )


# ─────────────────────────────────────────────
# Buffer entry point (webhook)
# ─────────────────────────────────────────────


def add_message_to_buffer(
    user_id: str,
    reply_token: str | None,
    content,
    *,
    replace_media_pending: bool = False,
) -> None:
    """Append ``content`` to the user's debounce buffer; (re)start the timer.

    Called from three webhook paths:
      - text message → ``content`` is ``str``
      - new media event → ``content`` is ``{"type": "media_pending", ...}``
      - background media download finished → ``content`` is the resolved
        media metadata dict (``{"type": "media", ...}``); pass
        ``replace_media_pending=True`` so the placeholder is swapped out.

    When debounce is disabled we shortcut straight to the orchestrator —
    helpful for low-volume / single-user dev mode.
    """
    block = from_buffer_item(content)

    if not _config.get("enabled", True):
        items = [block]
        message_content = to_langchain_content(items)
        asyncio.create_task(
            orchestrator.agent_and_reply(
                user_id, reply_token or "", message_content, buffer_items=items,
            )
        )
        return

    asyncio.create_task(
        _enqueue_and_arm_timer(
            user_id, reply_token, block, replace_media_pending=replace_media_pending,
        )
    )


async def _enqueue_and_arm_timer(
    user_id: str,
    reply_token: str | None,
    block: Block,
    *,
    replace_media_pending: bool,
) -> None:
    """Append the block, cancel any pending flush, and schedule a new one.

    Why two-step: appending and timer-arming both touch the same
    BufferStore entry, so we order them deterministically:
      1. cancel an in-flight flush (if any) — under the per-user lock
      2. append the new block — under the per-user lock; returns the
         updated entry with reply_token / created_at refreshed
      3. create the new flush task and attach it — under the per-user lock

    The legacy code did all three under one synchronous block by mutating
    the dict directly. With async locks we must release between cancel and
    create_task to avoid deadlocking the cancelled task on the same lock.
    """
    await buffers.cancel_pending_task(user_id)

    entry = await buffers.append_block(
        user_id, block,
        reply_token=reply_token,
        replace_pending=replace_media_pending,
    )

    new_task = asyncio.create_task(process_and_reply(user_id, entry.reply_token))
    await buffers.attach_task(user_id, new_task)


# ─────────────────────────────────────────────
# Timer flush
# ─────────────────────────────────────────────


async def process_and_reply(user_id: str, reply_token: str) -> None:
    """Wait for the debounce window, then dispatch the merged buffer.

    The window has two parts:
      1. ``buffer_wait`` (default 1.5s) — the regular debounce delay.
      2. up to ``media_extra_wait`` (default 10s) — extra wait while any
         ``media_pending`` placeholder is still present in the buffer
         (user just sent an image, the binary is still downloading in the
         background).

    Both delays are read from config at call time so live-reload works.
    """
    try:
        await asyncio.sleep(_config.get("buffer_wait", 1.5))

        media_wait = _config.get("media_extra_wait", 10)
        waited = 0.0
        while waited < media_wait:
            if not await buffers.has_pending(user_id):
                break
            await asyncio.sleep(0.5)
            waited += 0.5

        items = await buffers.take_for_flush(user_id)
        if not items:
            # Either the buffer was already drained or every block was a
            # media_pending placeholder that never resolved. Inject a
            # graceful fallback so the user gets *some* reply.
            items = (Block(type="text", text="[使用者傳送了媒體檔案，但系統處理超時，請盡量協助]"),)

        items_list = list(items)
        message_content = to_langchain_content(items_list)
        await orchestrator.agent_and_reply(
            user_id, reply_token, message_content,
            buffer_items=items_list,
        )

    except asyncio.CancelledError:
        log.debug("debounce_timer_reset", user_id=user_id)
        raise

    finally:
        # Only remove the entry if *we* still own the timer task — a newer
        # message may have taken over and we mustn't drop its work.
        await buffers.discard_if_owned(user_id, asyncio.current_task())


# ─────────────────────────────────────────────
# Periodic cleanup
# ─────────────────────────────────────────────


async def cleanup_stale_buffers() -> None:
    """Background loop: evict buffers + Quick Reply pending state on TTL."""
    from harness.buffer import pending  # local import: avoid hard coupling at module load

    buffer_ttl = _config.get("buffer_ttl", 300)
    pending_ttl = _config.get("pending_ttl", 300)
    cleanup_interval = _config.get("cleanup_interval", 60)

    while True:
        await asyncio.sleep(cleanup_interval)
        evicted_buffers = await buffers.evict_stale(buffer_ttl)
        for uid in evicted_buffers:
            log.debug("buffer_expired_removed", user_id=uid)

        evicted_pending = await pending.evict_stale(pending_ttl)
        for uid in evicted_pending:
            log.debug("quick_reply_expired_removed", user_id=uid)


__all__ = [
    "add_message_to_buffer",
    "agent_and_reply",
    "cleanup_stale_buffers",
    "init",
    "process_and_reply",
    "run_agent",
]
