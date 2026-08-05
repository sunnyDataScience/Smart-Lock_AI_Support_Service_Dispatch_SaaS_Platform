"""canary 自動推進要尊重 SLO halt 判斷（CR-0210 D4(b)）。

WHY：現況是**一邊自動推、一邊不自動停**——canary cron 純依 ETA 推進、不讀任何 SLO，
而 `check_slo_halt` 只回建議不真實 halt（`config_m18_service.py:985-986` 明文，
那是「避免自動 trigger 風險」的刻意設計）。

淨效果：admin 已經看到指標破線、跑過檢查、系統也把 `should_halt=true` 寫進 audit 了，
**cron 下一輪照樣把壞版本推到 50% / 100%**。

本檢查不自動 halt、不改 rollout 狀態（維持人工 rollback 的設計），
只是「破線就不要再往前推」——壞版本停在原 stage 等人處理，而不是自己爬到全量。
cron 沒有 metrics 來源可以自己算 SLO（那是 CR-0209 A 群的缺口、綁 SigNoz），
但它讀得到人已經做過的判斷。
"""
from __future__ import annotations

import pytest

import realtime.config_canary_advance_cron as cron

pytestmark = pytest.mark.component


class _FakeCur:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row=None, boom=False):
        self._row, self._boom = row, boom

    async def execute(self, *_a, **_k):
        if self._boom:
            raise RuntimeError("db exploded")
        return _FakeCur(self._row)


@pytest.mark.asyncio
async def test_halt_decision_blocks_advance(monkeypatch):
    """最近一次檢查說 should_halt → 回 True（cron 會跳過推進）。"""
    monkeypatch.setattr(cron.db_module, "_conn",
                        _FakeConn(({"slo_check": True, "should_halt": True},)))
    assert await cron._latest_slo_says_halt("r1") is True


@pytest.mark.asyncio
async def test_healthy_decision_allows_advance(monkeypatch):
    monkeypatch.setattr(cron.db_module, "_conn",
                        _FakeConn(({"slo_check": True, "should_halt": False},)))
    assert await cron._latest_slo_says_halt("r1") is False


@pytest.mark.asyncio
async def test_no_check_recorded_allows_advance(monkeypatch):
    """從未跑過 SLO 檢查 → 維持既有推進行為（不因為「沒資料」就卡住）。"""
    monkeypatch.setattr(cron.db_module, "_conn", _FakeConn(None))
    assert await cron._latest_slo_says_halt("r1") is False


@pytest.mark.asyncio
async def test_query_failure_is_fail_open(monkeypatch):
    """查詢自己爆炸時 fail-open —— 這道保護不該因為它壞掉就讓所有 rollout 卡死。"""
    monkeypatch.setattr(cron.db_module, "_conn", _FakeConn(boom=True))
    assert await cron._latest_slo_says_halt("r1") is False
