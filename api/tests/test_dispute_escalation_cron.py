"""Dispute 60d auto-escalation cron unit tests (DB mocked)。

驗證：
- DEFAULT_INTERVAL = 86400 (HD-2 daily) sanity
- run_once db_unavailable → 0
- run_once 寫對 SQL（status filter + sla_deadline + 可選 tenant_id）
- run_once 回 rowcount
- start/stop 冪等
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from realtime.dispute_escalation_cron import (
    DEFAULT_INTERVAL_S,
    DisputeEscalationCron,
)


def test_default_interval_is_daily():
    assert DEFAULT_INTERVAL_S == 86400


@pytest.mark.asyncio
async def test_run_once_db_unavailable_returns_zero(monkeypatch):
    import realtime.dispute_escalation_cron as cron_mod

    async def fake_ensure():
        return False

    monkeypatch.setattr(cron_mod, "_ensure_conn", fake_ensure)
    w = DisputeEscalationCron()
    assert await w.run_once() == 0


@pytest.mark.asyncio
async def test_run_once_executes_update_with_filter(monkeypatch):
    """SQL 必含 status IN + sla_deadline < NOW + tenant_id 條件。"""
    import realtime.dispute_escalation_cron as cron_mod
    import core.db as db_module

    captured_sql = {}

    class FakeCur:
        rowcount = 5

    class FakeConn:
        async def execute(self, sql, args):
            captured_sql["sql"] = sql
            captured_sql["args"] = args
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(cron_mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    w = DisputeEscalationCron()
    count = await w.run_once(tenant_id="tenant-1")
    assert count == 5
    assert "status IN ('filed', 'in_review', 'mediation')" in captured_sql["sql"]
    assert "sla_deadline < NOW()" in captured_sql["sql"]
    assert "tenant_id = %s::uuid" in captured_sql["sql"]
    assert "status = 'escalated'" in captured_sql["sql"]
    assert "escalated_to = 'ops_director'" in captured_sql["sql"]
    assert captured_sql["args"] == ("tenant-1",)


@pytest.mark.asyncio
async def test_run_once_without_tenant_id_no_filter(monkeypatch):
    """tenant_id 不給時 → SQL 不含 tenant_id 條件（admin 全 tenant 全掃）。"""
    import realtime.dispute_escalation_cron as cron_mod
    import core.db as db_module

    captured_sql = {}

    class FakeCur:
        rowcount = 0

    class FakeConn:
        async def execute(self, sql, args):
            captured_sql["sql"] = sql
            captured_sql["args"] = args
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(cron_mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    w = DisputeEscalationCron()
    await w.run_once()
    assert "tenant_id" not in captured_sql["sql"]
    assert captured_sql["args"] == ()


@pytest.mark.asyncio
async def test_start_stop_idempotent():
    w = DisputeEscalationCron()
    # 不實 run task
    w._run = lambda: None  # type: ignore[assignment]
    await w.stop()  # 無 task 不該炸
    w._task = MagicMock()
    w._task.done.return_value = False
    w.start()  # second call short-circuits


@pytest.mark.asyncio
async def test_run_once_rowcount_zero_when_no_overdue(monkeypatch):
    """無 overdue dispute → rowcount=0 不該 raise。"""
    import realtime.dispute_escalation_cron as cron_mod
    import core.db as db_module

    class FakeCur:
        rowcount = 0

    class FakeConn:
        async def execute(self, sql, args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(cron_mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    w = DisputeEscalationCron()
    assert await w.run_once() == 0
