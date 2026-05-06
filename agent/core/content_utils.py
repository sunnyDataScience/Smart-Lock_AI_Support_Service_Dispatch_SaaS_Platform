"""Shared utilities for normalizing langchain message content blocks.

LangChain message ``content`` can be:
- ``str`` (simple text)
- ``list`` of blocks, e.g. ``[{"type": "text", "text": "..."}, {"type": "image_url", ...}]``

This module provides a single canonical helper for converting either shape into
a plain ``str`` so that downstream consumers (audit logging, memory
compression, quality checks, debug printing) do not each re-implement the same
logic.

The previous codebase had three near-duplicate copies of this routine in
``harness/debounce.py``, ``harness/memory_manager.py`` and
``quality/quality_check.py`` — see refactor RP1.C.3.
"""

from __future__ import annotations

from typing import Any

# Mapping of multimodal block ``type`` values to a Chinese label used when the
# caller asks us to render a placeholder for non-text blocks.  Mirrors the
# previous behavior that lived in ``memory_manager._extract_text_from_content``.
# Block ``type`` values that should be rendered as a placeholder when
# ``include_media_placeholder=True``.  ``"media"`` is an internal generic
# wrapper; the concrete kind (image/audio/video) is determined from the
# ``mime_type`` field via :func:`_label_for_media_block`.
_MEDIA_BLOCK_TYPES: frozenset[str] = frozenset(
    {
        "image_url",
        "image",
        "audio",
        "audio_url",
        "video",
        "video_url",
        "media",
    }
)


def _label_for_media_block(block: dict[str, Any]) -> str:
    """Return a human-readable label for a multimodal content block.

    Inspects both the block ``type`` and ``mime_type`` field; mirrors the
    legacy heuristic from ``memory_manager._extract_text_from_content``.
    """
    btype = str(block.get("type", ""))
    mime = str(block.get("mime_type", ""))
    if "image" in mime or "image" in btype:
        return "圖片"
    if "audio" in mime or "audio" in btype:
        return "音檔"
    if "video" in mime or "video" in btype:
        return "影片"
    return "媒體"


def extract_text(
    content: Any,
    *,
    join: str = "\n",
    include_media_placeholder: bool = False,
    fallback_to_repr: bool = True,
) -> str:
    """Convert a langchain message ``content`` into plain text.

    Args:
        content: Either ``str``, ``list`` of content blocks, or any other
            object.
        join: Separator used when joining multiple text blocks.  Defaults to
            ``"\\n"`` to match the historical behavior shared by debounce /
            memory_manager / quality_check.
        include_media_placeholder: When ``True``, non-text multimodal blocks
            (``image_url``, ``audio``, ``video``...) are rendered as
            ``[傳送了圖片]`` / ``[傳送了音檔]`` / ``[傳送了影片]`` — useful
            when summarizing a conversation for an LLM that should know media
            was exchanged but does not need the raw bytes.  When ``False``
            (default), non-text blocks are silently skipped.
        fallback_to_repr: When ``True`` (default), a non-empty ``list`` that
            yielded no extractable text falls back to ``str(content)``; when
            ``False`` an empty string is returned.  Note: an empty list always
            returns ``""`` regardless of this flag.

    Returns:
        Plain string representation suitable for logging, summarization or
        keyword matching.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type")
                if btype == "text":
                    parts.append(block.get("text", ""))
                elif include_media_placeholder and btype in _MEDIA_BLOCK_TYPES:
                    parts.append(f"[傳送了{_label_for_media_block(block)}]")
            elif isinstance(block, str):
                parts.append(block)

        if parts:
            return join.join(parts)
        if not content:
            return ""
        return str(content) if fallback_to_repr else ""

    return str(content)
