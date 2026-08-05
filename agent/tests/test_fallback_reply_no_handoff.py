"""系統兜底話術不可觸發 CR-0097 的轉真人兜底（2026-08-02 資安/正確性掃描）。

**原問題**：`_FALLBACK_REPLY`（LLM 呼叫失敗時給客人的話）原本是

    「不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏」

其中「**專員與您**」正好命中 CR-0097 的 `_SOFT_HANDOFF_MARKERS`。連鎖反應：

1. LLM 逾時／API 錯誤 → `except` → `reply = _FALLBACK_REPLY`
2. CR-0097 兜底看到「AI 承諾轉接 + 本輪沒呼叫 transfer_to_human」
3. → 補一筆 escalation → 建問題卡 → 對話翻成 `escalated`
4. → **該客人的 AI 從此永久靜音**（見 gateway vs loop 分層：任何 escalation 都會靜音 AI）

也就是**一次暫時性的 LLM 失敗，就讓那個客人再也收不到 AI 回覆**，
而客人看到的訊息還承諾「專員與您聯繫」——但那個專員只是被兜底建出來的卡。

**修法**：改措辭，讓系統故障就只是系統故障。監控由上游的 `logger.exception` 負責；
客人的訊息仍會持久化，客服在對話管理看得到。

CR-0097 兜底本身**不動**——它的設計取捨（寧可多建卡也不讓真報修蒸發）是對的，
問題只在於系統自己的故障訊息不該被算成「AI 的承諾」。
"""

from __future__ import annotations

import pytest

from lockcore.channels.line_gateway import (
    _DEFINITIVE_HANDOFF_MARKERS,
    _FALLBACK_REPLY,
    _SOFT_HANDOFF_MARKERS,
    _promised_handoff,
)


def test_fallback_reply_does_not_promise_handoff():
    """核心：兜底話術不可被判定為「承諾轉接」。"""
    assert _promised_handoff(_FALLBACK_REPLY) is False, (
        f"兜底話術 {_FALLBACK_REPLY!r} 會觸發 CR-0097 轉真人兜底——"
        "一次 LLM 失敗就會讓該客人的 AI 永久靜音"
    )


def test_fallback_reply_contains_no_handoff_marker_at_all():
    """比行為測試更嚴：連字面上都不該出現任何 marker。

    `_promised_handoff` 有 hedge（條件語氣）豁免邏輯，措辭一改可能剛好
    靠 hedge 躲過判定——那是脆弱的。直接禁掉字面出現，改措辭時才不會踩線。
    """
    hits = [
        m for m in (*_DEFINITIVE_HANDOFF_MARKERS, *_SOFT_HANDOFF_MARKERS)
        if m in _FALLBACK_REPLY
    ]
    assert not hits, f"兜底話術含轉接承諾字樣 {hits}：{_FALLBACK_REPLY!r}"


def test_the_original_wording_would_have_failed_this_test():
    """釘住這個 bug 本身——證明測試真的抓得到，不是恆真。"""
    original = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"
    assert _promised_handoff(original) is True, (
        "原措辭現在不觸發了——可能是 marker 清單改了，"
        "請確認本測試是否仍在守住原本要守的東西"
    )


@pytest.mark.parametrize(
    "reply",
    [
        "已幫您轉接專員,稍後與您聯繫",
        "我已為您安排師傅到府",
        "已登記您的報修",
    ],
)
def test_real_handoff_promises_still_detected(reply: str):
    """反向：真正的轉接承諾必須仍被偵測到，不可因為改措辭而放鬆判定。"""
    assert _promised_handoff(reply) is True, f"真承諾沒被偵測到：{reply!r}"


# ── 2026-08-05 補強：只驗常數是不夠的 ──────────────────────────────────
#
# 上面那批測試在 2026-08-02 就存在，卻沒擋下同一個 bug 的第二現場：
# `line_gateway.py` 的 turn 失敗 except 分支裡**另外硬寫了一句**
#
#     reply = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"
#
# 那正是被修掉的原措辭。常數改了、字面量沒改，於是 LLM 一失敗仍然
# 走完整條「escalation → 建卡 → 對話 escalated → 該客人 AI 永久靜音」。
# 教訓：守線要守**行為的所有入口**，不是守那一個常數。


def _reply_string_literals(module_path) -> list[tuple[int, str]]:
    """AST 掃出所有 `reply = "字面量"` 形式的指派（含 walrus 與多重指派）。

    只認字面量：`reply = _FALLBACK_REPLY` 這種引用常數的寫法本來就受
    上面的常數測試保護，不重複檢查。
    """
    import ast

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []

    def _record(targets, value):
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            return
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "reply":
                found.append((value.lineno, value.value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            _record(node.targets, node.value)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            _record([node.target], node.value)
        elif isinstance(node, ast.NamedExpr):
            _record([node.target], node.value)
    return found


def test_no_hardcoded_reply_literal_promises_handoff():
    """`line_gateway.py` 內任何直接指派給 reply 的字面量都不得承諾轉接。

    這是 2026-08-02 那次修復漏掉的那一層：常數安全不代表所有出口安全。
    """
    import pathlib

    from lockcore.channels import line_gateway

    module_path = pathlib.Path(line_gateway.__file__)
    offenders = [
        f"{module_path.name}:{lineno} → {text!r}"
        for lineno, text in _reply_string_literals(module_path)
        if _promised_handoff(text)
    ]

    assert not offenders, (
        "偵測到會觸發 CR-0097 轉真人兜底的硬寫兜底話術——"
        "一次暫時性 LLM 失敗就會讓該客人的 AI 永久靜音。"
        "請改用 _FALLBACK_REPLY 常數：\n  " + "\n  ".join(offenders)
    )
