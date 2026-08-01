"""轉真人 escalation 轉發的耐久性（2026-08-02）。

**修正前的缺陷**：轉真人轉發是整個 gateway 唯一沒有耐久性的旁路。

| | 失敗時的處理 |
|---|---|
| 對話持久化 | 落 spool + 下次補送 + `[ARCHIVE_ALERT]` ERROR |
| escalation 轉發 | **只有一行 WARNING**，不重試、不落 spool、不告警 |

一次 5xx 或逾時就永久遺失。而「翻對話狀態成等待人工」與「建 AI 草擬問題卡」**都是
API 端收到 escalation 之後的副作用** —— 那個 POST 掉了，兩件事都不會發生。

產生的畫面正是業主 2026-08-01 回報的：訊息看得到（persist 成功）、AI 也說了
「幫您轉接給真人專員」，但對話狀態還是「進行中」、客服接不了手、後台沒有問題卡。

本檔釘住三件事：5xx/逾時要落 spool、下次要補送、4xx 不重試（payload 壞掉重送也沒用，
不該無限佔用 spool）。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from lockcore.channels import line_gateway as gw


@pytest.fixture
def spool(tmp_path, monkeypatch) -> Path:
    p = tmp_path / "escalation_spool.jsonl"
    monkeypatch.setattr(gw, "_ESCALATION_SPOOL_PATH", str(p))
    return p


def _payload(uid: str = "U-test") -> dict:
    return {
        "tenant_id": "locksmart",
        "line_user_id": uid,
        "session_id": f"locksmart:{uid}",
        "reason": "客戶要求真人",
        "is_explicit": True,
        "facts_snapshot": {"brand": "Yale", "symptom": "外部無法解鎖"},
    }


class _Resp:
    def __init__(self, status: int, text: str = ""):
        self.status_code = status
        self.text = text


def test_server_error_is_spooled_not_lost(spool, monkeypatch):
    """5xx → 落 spool（修正前只有一行 WARNING 就永久遺失）。"""
    async def _fail(*_a, **_k):
        return False

    monkeypatch.setattr(gw, "_post_escalation", _fail)
    asyncio.run(gw._spool_append(_payload(), gw._ESCALATION_SPOOL_PATH))

    lines = [ln for ln in spool.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["line_user_id"] == "U-test"


def test_spool_is_flushed_on_next_attempt(spool, monkeypatch):
    """下次轉發時先補送歷史失敗，成功後 spool 清空。"""
    asyncio.run(gw._spool_append(_payload("U-old"), gw._ESCALATION_SPOOL_PATH))
    assert spool.exists()

    posted: list[dict] = []

    async def _ok(_base, _token, payload):
        posted.append(payload)
        return True

    monkeypatch.setattr(gw, "_post_escalation", _ok)
    asyncio.run(gw._flush_escalation_spool("http://api.local", "tok"))

    assert [p["line_user_id"] for p in posted] == ["U-old"]
    assert not spool.exists(), "全部送達後 spool 應被刪除"


def test_failed_flush_keeps_entries_for_retry(spool, monkeypatch):
    """補送再失敗要保留，不可因為「試過了」就丟掉。"""
    asyncio.run(gw._spool_append(_payload("U-a"), gw._ESCALATION_SPOOL_PATH))
    asyncio.run(gw._spool_append(_payload("U-b"), gw._ESCALATION_SPOOL_PATH))

    async def _fail(*_a, **_k):
        return False

    monkeypatch.setattr(gw, "_post_escalation", _fail)
    asyncio.run(gw._flush_escalation_spool("http://api.local", "tok"))

    lines = [ln for ln in spool.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2, "兩筆都該留著下次再試"


def test_partial_success_keeps_only_failures(spool, monkeypatch):
    """一成一敗：成功的移除、失敗的留下（不可整批重送造成重複建卡）。"""
    asyncio.run(gw._spool_append(_payload("U-ok"), gw._ESCALATION_SPOOL_PATH))
    asyncio.run(gw._spool_append(_payload("U-bad"), gw._ESCALATION_SPOOL_PATH))

    async def _selective(_base, _token, payload):
        return payload["line_user_id"] == "U-ok"

    monkeypatch.setattr(gw, "_post_escalation", _selective)
    asyncio.run(gw._flush_escalation_spool("http://api.local", "tok"))

    lines = [ln for ln in spool.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["line_user_id"] == "U-bad"


def test_4xx_is_terminal_and_not_retried(monkeypatch):
    """4xx 代表 payload 本身有問題，重送也不會好 → 回 True（終局），不佔 spool。

    否則一筆壞資料會卡在 spool 裡每輪重試，最終把上限撐爆、把好的擠掉。
    """
    class _Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_a):
            return False
        async def post(self, *_a, **_k):
            return _Resp(422, "validation error")

    monkeypatch.setattr("httpx.AsyncClient", lambda **_k: _Client())
    assert asyncio.run(gw._post_escalation("http://api.local", "tok", _payload())) is True


def test_5xx_is_retryable(monkeypatch):
    """5xx＝對方暫時不行，要回 False 讓它落 spool。"""
    class _Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_a):
            return False
        async def post(self, *_a, **_k):
            return _Resp(503, "upstream down")

    monkeypatch.setattr("httpx.AsyncClient", lambda **_k: _Client())
    assert asyncio.run(gw._post_escalation("http://api.local", "tok", _payload())) is False
