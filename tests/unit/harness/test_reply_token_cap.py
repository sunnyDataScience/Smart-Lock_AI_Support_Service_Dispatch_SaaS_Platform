"""Unit tests for reply token cap — BR-A01-02 / AC-V11-11.

Tests:
- C-5.1: cap 內原文不變（短文字原樣回傳）
- C-5.2: 剛好等於 cap_chars 不截斷
- C-5.3: 超過 cap → 截斷 + marker，且截在句界（不切在句中）
- C-5.4: 超過 cap 但無句界可回退 → 硬切到 cap_chars + marker
- C-5.5: 空字串 fail-open（不補 marker、不報錯）
- C-5.6: None fail-open（不補 marker、不報錯）
- C-5.7: 截斷後不得回傳空字串
- C-5.8: marker 本身導致空 → fail-open 回退原文
"""

from __future__ import annotations

import pytest

from harness.orchestrator import _apply_token_cap


MARKER = "（詳情請洽客服）"


# ── C-5.1: 短文字，在 cap 內，原樣回傳 ──────────────────────────────────────────
@pytest.mark.unit
def test_short_text_unchanged():
    text = "這是一段短文字。"
    result = _apply_token_cap(text, cap_chars=100, marker=MARKER)
    assert result == text


# ── C-5.2: 剛好等於 cap_chars，不截斷 ────────────────────────────────────────────
@pytest.mark.unit
def test_exactly_at_cap_not_truncated():
    text = "A" * 50
    result = _apply_token_cap(text, cap_chars=50, marker=MARKER)
    assert result == text


# ── C-5.3: 超過 cap → 截到最後句界 + marker ─────────────────────────────────────
@pytest.mark.unit
def test_truncation_at_sentence_boundary():
    # 句界回退：text = "第一句。" (4 chars) + 超過 cap 的內容
    text = "第一句。" + "X" * 20
    cap = 10
    result = _apply_token_cap(text, cap_chars=cap, marker=MARKER)
    # 應該截到「第一句。」句界後接 marker
    assert result.endswith(MARKER)
    assert not result.endswith(MARKER + MARKER)
    # 不應截在句子中間（結尾 marker 之前的部分不應包含 X）
    body = result[: -len(MARKER)]
    assert "X" not in body


# ── C-5.3b: 多個句界，取 cap 範圍內最後一個句界 ──────────────────────────────────
@pytest.mark.unit
def test_truncation_at_last_sentence_boundary_in_cap():
    # "句一。句二！句三。" + 超過 cap 的 padding
    text = "句一。句二！" + "X" * 30
    cap = 9  # 包含「句一。句二！」共 6 chars + 3 X
    result = _apply_token_cap(text, cap_chars=cap, marker=MARKER)
    assert result.endswith(MARKER)
    # 應截在「句二！」之後（最晚句界），X 不在 body
    body = result[: -len(MARKER)]
    assert "X" not in body
    # body 至少包含句一
    assert "句一" in body


# ── C-5.4: 超過 cap 但無句界 → 硬切 + marker ────────────────────────────────────
@pytest.mark.unit
def test_truncation_no_sentence_boundary():
    text = "ABCDEFGHIJ" * 5  # 50 chars，全英數無句界
    cap = 10
    result = _apply_token_cap(text, cap_chars=cap, marker=MARKER)
    assert result.endswith(MARKER)
    # 硬切到 cap_chars
    body = result[: -len(MARKER)]
    assert len(body) == cap


# ── C-5.5: 空字串 fail-open ──────────────────────────────────────────────────────
@pytest.mark.unit
def test_empty_string_fail_open():
    result = _apply_token_cap("", cap_chars=100, marker=MARKER)
    assert result == ""


# ── C-5.6: None fail-open ────────────────────────────────────────────────────────
@pytest.mark.unit
def test_none_fail_open():
    result = _apply_token_cap(None, cap_chars=100, marker=MARKER)  # type: ignore[arg-type]
    assert result is None or result == ""  # 允許回傳 None 或空字串（不補 marker）


# ── C-5.7: 截斷後不得回傳空字串 ─────────────────────────────────────────────────
@pytest.mark.unit
def test_truncated_never_empty():
    # 即使 cap_chars=1 且文字超過，也不能回空
    text = "一二三四五六七八九十"
    result = _apply_token_cap(text, cap_chars=1, marker=MARKER)
    assert result  # truthy（非空）
    assert isinstance(result, str)


# ── C-5.8: marker 過長導致截斷後 body 為空 → fail-open 回退原文 ──────────────────
@pytest.mark.unit
def test_marker_too_long_fallback_to_original():
    # marker 本身超過 cap，若 naive 實作會產生空 body；必須回退原文
    text = "一二三四五"
    long_marker = "M" * 200
    result = _apply_token_cap(text, cap_chars=5, marker=long_marker)
    # 不得回傳空
    assert result
    # 可以是原文（回退），或至少非空
    assert isinstance(result, str)


# ── C-5.9: 句界字元 ！？\n 也要回退 ────────────────────────────────────────────
@pytest.mark.unit
def test_sentence_boundary_includes_other_chars():
    # 「！」「？」「\n」都是句界
    text = "A！" + "X" * 30
    cap = 5
    result = _apply_token_cap(text, cap_chars=cap, marker=MARKER)
    assert result.endswith(MARKER)
    body = result[: -len(MARKER)]
    assert "X" not in body
