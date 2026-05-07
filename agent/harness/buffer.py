"""Encapsulated stores for debounce timer + Quick Reply pending state.

audit 2026-05-06 §A2 flagged the legacy module-level dicts in
``harness/debounce.py`` as a CRITICAL concurrency hazard:

- ``user_buffers[user_id]["items"].append(content)`` was a nested mutation on
  a shared dict with no locking. A single user firing two messages within the
  1.5s debounce window could race the placeholder-replacement path against
  the timer-flush path.
- ``_pending_messages[user_id] = {...}`` (the Quick Reply hold queue) had a
  symmetric problem: pop in one task vs set in another.

This module provides two typed, lock-protected stores that replace those
dicts. Both expose only async getters/setters so callers cannot reach into
the underlying dict and mutate it. Internal records are ``frozen`` dataclasses
— anything that would have been a field mutation is implemented as a
copy-on-write via :func:`dataclasses.replace`, which both satisfies the
CLAUDE.md immutability rule and lets the locks stay narrow.

Per-user :class:`asyncio.Lock` is provided so callers can compose multi-step
read-modify-write sequences (the timer path needs this when it pops items,
inspects them, and may re-issue work). The lock objects are created lazily
and never removed — this is bounded by the active LINE user count, which is
well within the few-thousand range the harness is sized for.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field, replace
from typing import Any

# Use the short project-relative form (``core.blocks`` not
# ``agent.core.blocks``): the agent runtime sets ``WORKDIR=/app/agent`` in
# the Dockerfile and tests/scripts add ``agent/`` to ``sys.path``. The
# ``reverse-import-lint.yml`` CI guard also forbids ``from agent ...`` inside
# harness/, so the short path is the only one that satisfies both.
from core.blocks import (
    Block,
    drop_pending,
    has_pending_media,
)


# ─────────────────────────────────────────────
# Debounce buffer (replaces module-level user_buffers dict)
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class BufferEntry:
    """One user's pending debounce window.

    Attributes:
        items: tuple (immutable!) of buffered :class:`Block` instances. Use
            ``replace(entry, items=entry.items + (new_block,))`` to append.
        task: the timer coroutine that will flush this entry. ``None`` while
            the entry is being constructed before the timer is scheduled.
        reply_token: LINE reply token associated with the most recent message
            in the buffer (LINE only allows replying to the *latest* token).
        created_at: monotonic timestamp used by ``cleanup_stale`` to evict
            buffers whose owner went silent before the timer fired.
    """

    items: tuple[Block, ...] = ()
    task: asyncio.Task | None = None
    reply_token: str = ""
    created_at: float = 0.0


class BufferStore:
    """Lock-protected store of per-user :class:`BufferEntry`.

    All public methods are async — even simple gets — because callers commonly
    chain a get+set inside a single ``async with store.lock(uid)`` block to
    avoid TOCTOU bugs the legacy code used to suffer from.
    """

    def __init__(self) -> None:
        self._data: dict[str, BufferEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ── Per-user locking ──

    def lock(self, user_id: str) -> asyncio.Lock:
        """Return (creating if needed) the per-user lock.

        Synchronous because creating an :class:`asyncio.Lock` does not
        require a running loop. Callers ``async with`` the result.
        """
        lock = self._locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[user_id] = lock
        return lock

    # ── Atomic primitives (caller usually wraps with ``lock``) ──

    async def get(self, user_id: str) -> BufferEntry | None:
        """Return the current entry or ``None`` if no buffer exists."""
        return self._data.get(user_id)

    async def set(self, user_id: str, entry: BufferEntry) -> None:
        """Replace the entry wholesale (creates a new mapping)."""
        self._data[user_id] = entry

    async def pop(self, user_id: str) -> BufferEntry | None:
        """Remove and return the entry."""
        return self._data.pop(user_id, None)

    async def all_user_ids(self) -> list[str]:
        """Snapshot of currently buffered user IDs (for cleanup sweeps)."""
        return list(self._data.keys())

    # ── Higher-level helpers used by the timer/orchestrator ──

    async def append_block(
        self,
        user_id: str,
        block: Block,
        *,
        reply_token: str | None,
        replace_pending: bool,
    ) -> BufferEntry:
        """Append ``block`` to the user's buffer (creating it if absent).

        Args:
            block: the new content block to append.
            reply_token: the LINE reply token. ``None`` keeps the previous
                value (used when a background media download finishes after
                the user has typed something else — we don't want to replace
                the live token with stale media).
            replace_pending: when ``True``, drop any existing
                ``media_pending`` placeholders before appending. The
                multimodal layer uses this to swap a placeholder for the
                actual downloaded payload.

        Returns:
            The new (frozen) entry — convenient for callers that want to
            inspect ``items`` without re-fetching.
        """
        async with self.lock(user_id):
            cur = self._data.get(user_id)
            now = time.monotonic()
            if cur is None:
                items: tuple[Block, ...] = (block,)
                entry = BufferEntry(
                    items=items,
                    task=None,
                    reply_token=reply_token or "",
                    created_at=now,
                )
            else:
                base_items = cur.items
                if replace_pending:
                    base_items = tuple(b for b in base_items if b.type != "media_pending")
                entry = replace(
                    cur,
                    items=base_items + (block,),
                    reply_token=reply_token if reply_token is not None else cur.reply_token,
                    created_at=now,
                )
            self._data[user_id] = entry
            return entry

    async def cancel_pending_task(self, user_id: str) -> None:
        """Cancel and clear the existing flush task (if any).

        Used by the debounce timer when a new message arrives mid-window:
        the previous coroutine must be cancelled so the new one waits the
        full ``buffer_wait`` from the latest message.
        """
        async with self.lock(user_id):
            cur = self._data.get(user_id)
            if cur and cur.task and not cur.task.done():
                cur.task.cancel()

    async def attach_task(self, user_id: str, task: asyncio.Task) -> None:
        """Attach a freshly-created flush task to the entry.

        Replaces the ``.task`` field via copy-on-write so the dataclass stays
        immutable.
        """
        async with self.lock(user_id):
            cur = self._data.get(user_id)
            if cur is not None:
                self._data[user_id] = replace(cur, task=task)

    async def take_for_flush(self, user_id: str) -> tuple[Block, ...]:
        """Snapshot the items that should be flushed now.

        Returns the items minus any lingering ``media_pending`` placeholders
        (the timer is supposed to wait for those before calling this; this is
        a defensive filter that mirrors the legacy semantics of
        ``process_and_reply``).
        """
        async with self.lock(user_id):
            cur = self._data.get(user_id)
            if cur is None:
                return ()
            return tuple(drop_pending(list(cur.items)))

    async def has_pending(self, user_id: str) -> bool:
        """Whether the user's buffer still contains a media_pending placeholder."""
        async with self.lock(user_id):
            cur = self._data.get(user_id)
            if cur is None:
                return False
            return has_pending_media(list(cur.items))

    async def discard_if_owned(self, user_id: str, task: asyncio.Task) -> None:
        """Remove the entry only if the given task still owns it.

        The timer coroutine calls this in its ``finally`` clause. If a *new*
        message has since taken over the buffer (creating a new task), the
        outgoing task must not delete the new entry.
        """
        async with self.lock(user_id):
            cur = self._data.get(user_id)
            if cur is not None and cur.task is task:
                self._data.pop(user_id, None)

    async def evict_stale(self, ttl_seconds: float, *, now: float | None = None) -> list[str]:
        """Remove entries older than ``ttl_seconds`` and cancel their tasks.

        Returns the list of evicted user IDs (for logging by the caller).
        """
        cutoff = (now if now is not None else time.monotonic()) - ttl_seconds
        evicted: list[str] = []
        # Take a snapshot first so we don't iterate while mutating.
        for uid in list(self._data.keys()):
            async with self.lock(uid):
                cur = self._data.get(uid)
                if cur is None:
                    continue
                if cur.created_at <= cutoff:
                    if cur.task and not cur.task.done():
                        cur.task.cancel()
                    self._data.pop(uid, None)
                    evicted.append(uid)
        return evicted


# ─────────────────────────────────────────────
# Quick Reply pending state (replaces _pending_messages dict)
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class PendingState:
    """The original message a user sent before being asked for brand/model.

    Stashed while the Quick Reply state machine collects the missing facts;
    flushed back through the agent once the user provides them.

    Attributes:
        content: the original LangChain content (``str`` for text, ``list``
            for multimodal). Kept in its native shape so the resume path
            can hand it back to the agent verbatim.
        items: the buffer items that produced ``content`` (used by
            ``_cleanup_multimodal_checkpoint`` to look up file paths when
            stripping base64 from the checkpoint).
        ts: epoch seconds, for TTL eviction.
    """

    content: Any  # str | list[dict] — LangChain content shape
    items: tuple[Block, ...] = field(default_factory=tuple)
    ts: float = 0.0


class PendingStore:
    """Lock-protected store of Quick Reply pending messages.

    Same locking discipline as :class:`BufferStore`.
    """

    def __init__(self) -> None:
        self._data: dict[str, PendingState] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def lock(self, user_id: str) -> asyncio.Lock:
        lock = self._locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[user_id] = lock
        return lock

    async def get(self, user_id: str) -> PendingState | None:
        return self._data.get(user_id)

    async def has(self, user_id: str) -> bool:
        return user_id in self._data

    async def set(self, user_id: str, state: PendingState) -> None:
        async with self.lock(user_id):
            self._data[user_id] = state

    async def pop(self, user_id: str) -> PendingState | None:
        async with self.lock(user_id):
            return self._data.pop(user_id, None)

    async def evict_stale(self, ttl_seconds: float, *, now: float | None = None) -> list[str]:
        """Remove entries whose ``ts`` is older than ``ttl_seconds``."""
        cutoff = (now if now is not None else time.time()) - ttl_seconds
        evicted: list[str] = []
        for uid in list(self._data.keys()):
            async with self.lock(uid):
                cur = self._data.get(uid)
                if cur is not None and cur.ts <= cutoff:
                    self._data.pop(uid, None)
                    evicted.append(uid)
        return evicted


# ─────────────────────────────────────────────
# Module-level singletons
# ─────────────────────────────────────────────
#
# The legacy code used module-level dicts (``user_buffers`` / ``_pending_messages``)
# and the FastAPI startup hook implicitly relied on them being shared across
# requests. Mirror that lifecycle with two singletons so callers (debounce
# timer, quick_reply state machine, orchestrator pipeline) all see the same
# state without each carrying a reference around. Tests can still construct
# fresh ``BufferStore`` / ``PendingStore`` instances if they want isolation.

buffers = BufferStore()
pending = PendingStore()


__all__ = [
    "BufferEntry",
    "BufferStore",
    "PendingState",
    "PendingStore",
    "buffers",
    "pending",
]
