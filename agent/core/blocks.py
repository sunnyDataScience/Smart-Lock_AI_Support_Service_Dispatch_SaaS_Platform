"""Unified content block schema for LangGraph / LangChain messages.

LangGraph message ``content`` can be either:
- ``str`` (plain text)
- ``list[dict]`` (multimodal blocks like ``{"type": "image_url", ...}``)

Historically the harness layer (``debounce.py``) carried half a dozen helpers
that re-implemented ``isinstance(content, str | list)`` branching on every
boundary (audit text, checkpoint cleanup, multimodal stripping, agent input
build...). See audit 2026-05-06 §B5.

This module introduces a single canonical :class:`Block` dataclass and a small
set of conversion helpers so middleware can normalize once at the edge and
consume a typed list everywhere else. The dataclass is ``frozen`` to enforce
the project-wide immutability rule (CLAUDE.md «不可變性 (CRITICAL)»):
helpers always return *new* lists rather than mutating their inputs.

Relation to ``core.content_utils.extract_text``: that helper consumes raw
LangGraph content (``str`` or ``list[dict]``) and renders text. ``blocks.py``
operates one layer above it — once content is normalized to ``list[Block]``,
``to_text`` / ``has_media`` / ``filter_text`` are the typed entry points.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field, replace
from typing import Any, Literal

# Buffer-level item types live alongside the LangGraph content types because
# ``add_message_to_buffer`` deals with *both*: text strings the user typed,
# media metadata dicts injected by ``harness/multimodal.py``, and short-lived
# ``media_pending`` placeholders that the timer coroutine waits on.
BlockType = Literal[
    "text",
    "image",
    "audio",
    "video",
    # Internal: a media item the multimodal layer has finished downloading.
    # Carries enough metadata for ``to_langchain_content`` to build a base64
    # data-URI for the ReAct agent.
    "media",
    # Internal: a placeholder added when LINE notifies the bot of a media
    # message but the binary download has not finished yet. The debounce
    # timer extends its wait window until all placeholders disappear.
    "media_pending",
]


@dataclass(frozen=True)
class Block:
    """One unit of message content.

    Notes:
        - ``text``: ``type == "text"`` — ``text`` field carries the string.
        - ``media`` / ``image`` / ``audio`` / ``video``: ``mime_type`` plus one
          of (``media_bytes``, ``file_path``) is required. ``label`` is the
          Chinese display label (圖片 / 音檔 / 影片 / 媒體) used when
          rendering placeholders in audit / checkpoint cleanup.
        - ``media_pending``: only ``label`` matters; the timer uses
          ``has_pending_media`` to decide whether to keep waiting.
        - ``metadata``: free-form dict for future extension; never mutated in
          place. ``None`` is the default "no metadata" sentinel.
    """

    type: BlockType
    text: str | None = None
    mime_type: str | None = None
    file_path: str | None = None
    media_bytes: bytes | None = None
    label: str | None = None
    metadata: dict[str, Any] | None = None


# ─────────────────────────────────────────────
# Construction helpers
# ─────────────────────────────────────────────


def text_block(text: str) -> Block:
    """Build a ``text`` block."""
    return Block(type="text", text=text)


def media_block(
    *,
    mime_type: str,
    file_path: str | None = None,
    media_bytes: bytes | None = None,
    label: str | None = None,
) -> Block:
    """Build a ``media`` block (unified image/audio/video)."""
    if not label:
        label = (
            "圖片" if "image" in mime_type
            else "音檔" if "audio" in mime_type
            else "影片" if "video" in mime_type
            else "媒體"
        )
    return Block(
        type="media",
        mime_type=mime_type,
        file_path=file_path,
        media_bytes=media_bytes,
        label=label,
    )


def media_pending_block(label: str = "媒體") -> Block:
    """Build a placeholder that the timer waits on."""
    return Block(type="media_pending", label=label)


# ─────────────────────────────────────────────
# Normalization (legacy buffer items / dicts → list[Block])
# ─────────────────────────────────────────────


def from_buffer_item(item: Any) -> Block:
    """Coerce one legacy buffer item to a :class:`Block`.

    Legacy ``add_message_to_buffer`` accepted either:
        - ``str`` — user-typed text
        - ``dict`` with ``type == "media"`` (downloaded media metadata)
        - ``dict`` with ``type == "media_pending"`` (placeholder)

    This function preserves that contract while the codebase is gradually
    migrated; new code should construct :class:`Block` directly via the
    factory helpers above.
    """
    if isinstance(item, Block):
        return item
    if isinstance(item, str):
        return text_block(item)
    if isinstance(item, dict):
        btype = item.get("type")
        if btype == "media":
            return media_block(
                mime_type=item.get("mime_type", ""),
                file_path=item.get("file_path"),
                media_bytes=item.get("media_bytes"),
                label=item.get("label"),
            )
        if btype == "media_pending":
            return media_pending_block(label=item.get("label", "媒體"))
        # Unknown dict shape — preserve as text repr so we never silently drop
        # data in the buffer pipeline.
        return text_block(str(item))
    return text_block(str(item))


def normalize(items: list[Any]) -> list[Block]:
    """Convert a legacy mixed list into a ``list[Block]``.

    Returns a new list; never mutates the input.
    """
    return [from_buffer_item(it) for it in items]


# ─────────────────────────────────────────────
# Predicates / filters
# ─────────────────────────────────────────────


def has_media(blocks: list[Block]) -> bool:
    """Return True if at least one resolved (non-pending) media block exists."""
    return any(b.type == "media" for b in blocks)


def has_pending_media(blocks: list[Block]) -> bool:
    """Return True if at least one ``media_pending`` placeholder exists.

    Used by the debounce timer to decide whether to keep waiting for a media
    download to finish before invoking the agent.
    """
    return any(b.type == "media_pending" for b in blocks)


def filter_text(blocks: list[Block]) -> list[Block]:
    """Return only ``text`` blocks (new list)."""
    return [b for b in blocks if b.type == "text"]


def drop_pending(blocks: list[Block]) -> list[Block]:
    """Return blocks with all ``media_pending`` placeholders removed."""
    return [b for b in blocks if b.type != "media_pending"]


# ─────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────


def to_text(blocks: list[Block], *, with_media_refs: bool = True, join: str = "\n") -> str:
    """Render blocks as plain text.

    Args:
        blocks: input list (not mutated).
        with_media_refs: when True, media blocks render as
            ``[使用者傳送了圖片: <file_path>]`` so the audit log / safety gate
            still sees they happened. When False they are silently dropped
            (use this for keyword-style matching where placeholders would be
            noise).
        join: separator between rendered parts.
    """
    parts: list[str] = []
    for b in blocks:
        if b.type == "text" and b.text is not None:
            parts.append(b.text)
        elif b.type == "media" and with_media_refs:
            label = b.label or "媒體"
            if b.file_path:
                parts.append(f"[使用者傳送了{label}: {b.file_path}]")
            else:
                parts.append(f"[使用者傳送了{label}]")
        elif b.type == "media_pending" and with_media_refs:
            parts.append(f"[使用者正在傳送{b.label or '媒體'}]")
    return join.join(parts)


def to_langchain_content(blocks: list[Block]) -> str | list[dict[str, Any]]:
    """Convert to the shape LangChain ``HumanMessage(content=...)`` expects.

    - All text → return a plain ``str`` (back-compat with text-only flow).
    - Mixed → return a list of LangChain content blocks: ``{"type": "text", ...}``
      for text and ``{"type": "image_url", "image_url": {"url": "data:...;base64,..."}}``
      for media. Falls back to a text reference if the file cannot be read.
    """
    if not has_media(blocks):
        return "\n".join(b.text or "" for b in blocks if b.type == "text")

    lc_blocks: list[dict[str, Any]] = []
    for b in blocks:
        if b.type == "text" and b.text is not None:
            lc_blocks.append({"type": "text", "text": b.text})
        elif b.type == "media":
            data_uri = _media_data_uri(b)
            if data_uri is None:
                # File missing — degrade to a text reference instead of
                # crashing the entire turn (the legacy code did the same).
                label = b.label or "媒體"
                lc_blocks.append({
                    "type": "text",
                    "text": f"[使用者傳送了{label}，但檔案讀取失敗]",
                })
            else:
                lc_blocks.append({
                    "type": "image_url",
                    "image_url": {"url": data_uri},
                })
        # media_pending intentionally dropped here — caller is expected to
        # have stripped them via ``drop_pending`` before invoking the agent.
    return lc_blocks


def _media_data_uri(b: Block) -> str | None:
    """Build a ``data:...;base64,...`` URI from a media Block.

    Prefers in-memory bytes; falls back to reading from ``file_path``.
    Returns ``None`` if neither is usable so the caller can render a
    placeholder instead.
    """
    media_bytes = b.media_bytes
    if not media_bytes and b.file_path:
        try:
            with open(b.file_path, "rb") as f:
                media_bytes = f.read()
        except FileNotFoundError:
            return None
    if not media_bytes:
        return None
    encoded = base64.b64encode(media_bytes).decode("utf-8")
    return f"data:{b.mime_type or 'application/octet-stream'};base64,{encoded}"


# ─────────────────────────────────────────────
# Checkpoint cleanup helpers
# ─────────────────────────────────────────────


def media_text_reference(blocks: list[Block]) -> str:
    """Render a media-rich content list as the text reference stored in the
    checkpoint after the agent has finished (replaces base64 bytes).

    Mirrors the behavior of the legacy ``_content_to_text_reference`` helper
    in ``debounce.py`` but typed via :class:`Block`.
    """
    return to_text(blocks, with_media_refs=True)


# Default empty list helper for dataclass fields — exposed so callers can
# use ``field(default_factory=empty_blocks)`` without re-importing ``field``.
def empty_blocks() -> list[Block]:
    """Return a fresh empty ``list[Block]`` (use as ``default_factory``)."""
    return []


__all__ = [
    "Block",
    "BlockType",
    "drop_pending",
    "empty_blocks",
    "field",
    "filter_text",
    "from_buffer_item",
    "has_media",
    "has_pending_media",
    "media_block",
    "media_pending_block",
    "media_text_reference",
    "normalize",
    "replace",
    "text_block",
    "to_langchain_content",
    "to_text",
]
