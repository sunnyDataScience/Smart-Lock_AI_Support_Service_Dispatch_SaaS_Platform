"""Statement Auto-Approval Cron — Phase II MVP 3 statement 表 dispute window 過期自動 approve。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from realtime.statement_auto_approval_cron import (
    DEFAULT_INTERVAL_S,
    StatementAutoApprovalCron,
    _STATEMENT_TABLES,
)


def test_default_interval_1hr():
    """1hr interval — 7d window 1hr 掃描足夠 timely。"""
    assert DEFAULT_INTERVAL_S == 3600


def test_three_statement_tables():
    """涵蓋 FR-0045/0046/0047 三表。"""
    assert len(_STATEMENT_TABLES) == 3
    assert "saas.technician_statement" in _STATEMENT_TABLES
    assert "saas.dispatcher_commission_statement" in _STATEMENT_TABLES
    assert "saas.brand_b2b_statement" in _STATEMENT_TABLES


@pytest.mark.asyncio
async def test_run_once_db_unavailable_returns_skipped(monkeypatch):
    import realtime.statement_auto_approval_cron as mod

    async def fake_ensure():
        return False

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    w = StatementAutoApprovalCron()
    result = await w.run_once()
    assert result == {"skipped": "db_unavailable"}


@pytest.mark.asyncio
async def test_run_once_updates_all_three_tables(monkeypatch):
    """3 表都被掃描；rowcount 記錄到 summary。"""
    import realtime.statement_auto_approval_cron as mod
    import core.db as db_module

    captured_sqls = []

    class FakeCur:
        def __init__(self, rc):
            self.rowcount = rc

    class FakeConn:
        def __init__(self):
            self._counts = iter([3, 5, 2])

        async def execute(self, sql):
            captured_sqls.append(sql)
            return FakeCur(next(self._counts))

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    w = StatementAutoApprovalCron()
    result = await w.run_once()
    assert result["saas.technician_statement"] == 3
    assert result["saas.dispatcher_commission_statement"] == 5
    assert result["saas.brand_b2b_statement"] == 2
    assert len(captured_sqls) == 3
    # 每個 SQL 都應包含 pending_review + dispute_window_ends_at + approved
    for sql in captured_sqls:
        assert "status = 'pending_review'" in sql
        assert "dispute_window_ends_at < NOW()" in sql
        assert "status = 'approved'" in sql


@pytest.mark.asyncio
async def test_run_once_table_error_isolated(monkeypatch):
    """一個表失敗不阻其他兩個；errors 計數。"""
    import realtime.statement_auto_approval_cron as mod
    import core.db as db_module

    class FakeCur:
        def __init__(self, rc):
            self.rowcount = rc

    class FakeConn:
        def __init__(self):
            self._call = 0

        async def execute(self, sql):
            self._call += 1
            if self._call == 2:  # 第二個表失敗
                raise RuntimeError("DB error")
            return FakeCur(1)

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    w = StatementAutoApprovalCron()
    result = await w.run_once()
    assert result["saas.technician_statement"] == 1
    assert result["saas.dispatcher_commission_statement"] == 0  # failed
    assert result["saas.brand_b2b_statement"] == 1
    assert result["errors"] == 1


@pytest.mark.asyncio
async def test_run_once_no_expired_rows(monkeypatch):
    """無過期 row → 3 表都 rowcount=0。"""
    import realtime.statement_auto_approval_cron as mod
    import core.db as db_module

    class FakeCur:
        rowcount = 0

    class FakeConn:
        async def execute(self, sql):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    w = StatementAutoApprovalCron()
    result = await w.run_once()
    assert all(v == 0 for v in result.values())


@pytest.mark.asyncio
async def test_auto_approve_sql_correct(monkeypatch):
    """SQL 應寫對：reviewed_by 留 NULL 表系統自動，與人工 approve 區分。"""
    import realtime.statement_auto_approval_cron as mod
    import core.db as db_module

    captured = {}

    class FakeCur:
        rowcount = 0

    class FakeConn:
        async def execute(self, sql):
            captured["sql"] = sql
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    w = StatementAutoApprovalCron()
    await w._auto_approve_table("saas.technician_statement")
    sql = captured["sql"]
    # reviewed_by 不在 UPDATE clause 中 (留 NULL 表系統)
    assert "reviewed_by" not in sql
    assert "reviewed_at = NOW()" in sql
    assert "saas.technician_statement" in sql


@pytest.mark.asyncio
async def test_start_stop_idempotent():
    w = StatementAutoApprovalCron()
    w._run = lambda: None  # type: ignore[assignment]
    await w.stop()
    w._task = MagicMock()
    w._task.done.return_value = False
    w.start()
