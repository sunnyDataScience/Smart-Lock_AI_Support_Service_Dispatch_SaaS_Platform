"""Unit tests for ``core.content_utils.extract_text``.

Covers the three call-site contracts that the helper consolidates:
- ``harness/debounce.py`` (default behavior, fallback to repr on un-extractable list)
- ``harness/memory_manager.py`` (multimodal placeholder, no fallback)
- ``quality/quality_check.py`` (default behavior, identical to debounce)
"""

from __future__ import annotations

import pytest

from core.content_utils import extract_text

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────
# Plain string passthrough
# ─────────────────────────────────────────────


def test_str_passthrough():
    assert extract_text("hello") == "hello"


def test_empty_str_passthrough():
    assert extract_text("") == ""


# ─────────────────────────────────────────────
# List of text blocks (default join is "\n" to match historical behavior)
# ─────────────────────────────────────────────


def test_list_of_text_blocks_joins_with_newline():
    blocks = [
        {"type": "text", "text": "hello"},
        {"type": "text", "text": "world"},
    ]
    assert extract_text(blocks) == "hello\nworld"


def test_list_of_text_blocks_with_custom_join():
    blocks = [
        {"type": "text", "text": "hello"},
        {"type": "text", "text": "world"},
    ]
    assert extract_text(blocks, join="") == "helloworld"


def test_skips_non_text_blocks_by_default():
    blocks = [
        {"type": "text", "text": "before"},
        {"type": "image_url", "image_url": {"url": "..."}},
        {"type": "text", "text": "after"},
    ]
    assert extract_text(blocks) == "before\nafter"


def test_str_block_in_list():
    assert extract_text(["a", "b"]) == "a\nb"


def test_empty_list_returns_empty_string():
    assert extract_text([]) == ""


# ─────────────────────────────────────────────
# Multimodal placeholder mode (memory_manager use-case)
# ─────────────────────────────────────────────


def test_image_block_placeholder_when_enabled():
    blocks = [
        {"type": "text", "text": "看一下"},
        {"type": "image_url", "mime_type": "image/jpeg", "image_url": {"url": "..."}},
    ]
    out = extract_text(blocks, include_media_placeholder=True)
    assert "看一下" in out
    assert "[傳送了圖片]" in out


def test_audio_block_placeholder_when_enabled():
    blocks = [
        {"type": "media", "mime_type": "audio/mp3"},
    ]
    out = extract_text(blocks, include_media_placeholder=True)
    assert out == "[傳送了音檔]"


def test_video_block_placeholder_when_enabled():
    blocks = [
        {"type": "media", "mime_type": "video/mp4"},
    ]
    out = extract_text(blocks, include_media_placeholder=True)
    assert out == "[傳送了影片]"


def test_media_placeholder_disabled_skips_blocks():
    blocks = [
        {"type": "image_url", "mime_type": "image/jpeg", "image_url": {"url": "..."}},
    ]
    # default: media blocks are skipped
    assert extract_text(blocks) == str(blocks)  # falls back to repr (no extractable text)


# ─────────────────────────────────────────────
# Fallback semantics
# ─────────────────────────────────────────────


def test_unextractable_list_falls_back_to_repr_by_default():
    """Mirrors debounce/quality_check behavior: list with only unknown blocks → str(content)."""
    blocks = [{"type": "tool_use", "name": "x"}]
    assert extract_text(blocks) == str(blocks)


def test_unextractable_list_returns_empty_when_fallback_disabled():
    """Mirrors memory_manager behavior: empty extraction → ""."""
    blocks = [{"type": "tool_use", "name": "x"}]
    assert extract_text(blocks, fallback_to_repr=False) == ""


def test_fallback_for_unexpected_top_level_type():
    assert extract_text(123) == "123"
    assert extract_text(None) == "None"


# ─────────────────────────────────────────────
# Behavioral parity with the three previous implementations
# ─────────────────────────────────────────────


def test_parity_with_debounce_and_quality_default_behavior():
    """The pre-refactor _extract_text in debounce.py / quality_check.py used
    "\\n".join and ``str(content)`` fallback. Verify defaults match that."""
    # str: same
    assert extract_text("foo") == "foo"

    # list of text blocks: same
    blocks = [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
    expected_old = "\n".join(["a", "b"])
    assert extract_text(blocks) == expected_old

    # mixed text + str: same
    mixed = [{"type": "text", "text": "x"}, "y"]
    assert extract_text(mixed) == "x\ny"

    # non-list, non-str: str(content)
    assert extract_text(42) == "42"


def test_parity_with_memory_manager_multimodal_behavior():
    """memory_manager._extract_text_from_content rendered image/audio/video
    blocks as ``[傳送了X]`` and returned ``""`` when nothing extractable."""
    # image rendering
    blocks = [{"type": "image_url", "mime_type": "image/jpeg"}]
    out = extract_text(blocks, include_media_placeholder=True, fallback_to_repr=False)
    assert out == "[傳送了圖片]"

    # empty extraction → ""
    out = extract_text([{"type": "tool_use"}], include_media_placeholder=True, fallback_to_repr=False)
    assert out == ""
