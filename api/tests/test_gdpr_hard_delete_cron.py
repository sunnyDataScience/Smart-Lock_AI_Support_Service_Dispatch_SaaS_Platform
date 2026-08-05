"""GDPR Hard-Delete Cron — FR-0053 T+30 自動硬刪測試 (DB mocked)。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

TID = "00000000-0000-0000-0000-000000000001"

from realtime.gdpr_hard_delete_cron import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_INTERVAL_S,
    GdprHardDeleteCron,
)


def test_default_interval_1_day():
    """1 day interval — 30 day cooldown 一天掃一次足夠。"""
    assert DEFAULT_INTERVAL_S == 86400


def test_default_batch_50():
    assert DEFAULT_BATCH_SIZE == 50


@pytest.mark.asyncio
async def test_run_once_db_unavailable(monkeypatch):
    import realtime.gdpr_hard_delete_cron as mod

    async def fake_ensure():
        return False

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    w = GdprHardDeleteCron()
    result = await w.run_once()
    assert result == {"skipped": "db_unavailable", "processed": 0, "errors": 0}


@pytest.mark.asyncio
async def test_run_once_processes_eligible_rows(monkeypatch):
    """SELECT 找到 3 個 eligible row → 呼 service.hard_delete 3 次。"""
    import realtime.gdpr_hard_delete_cron as mod
    import core.db as db_module

    class FakeCur:
        async def fetchall(self):
            return [("req-1", TID), ("req-2", TID), ("req-3", TID)]

    class FakeConn:
        async def execute(self, sql, args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    processed_ids = []

    async def fake_hard_delete(*, request_id, tenant_id, actor_user_id):
        # tenant_id 必須出現在簽名裡 —— 少了它 fake 就與真實的
        # gdpr_forget_service.hard_delete 不一致，測試會綠但 cron 實跑 TypeError
        assert tenant_id == TID
        processed_ids.append(request_id)
        return {"id": request_id, "status": "hard_deleted"}

    from services import gdpr_forget_service
    monkeypatch.setattr(gdpr_forget_service, "hard_delete", fake_hard_delete)

    w = GdprHardDeleteCron()
    result = await w.run_once()
    assert result["processed"] == 3
    assert result["errors"] == 0
    assert processed_ids == ["req-1", "req-2", "req-3"]


@pytest.mark.asyncio
async def test_run_once_passes_actor_none_for_system_auto(monkeypatch):
    """actor_user_id=None 表系統自動觸發。"""
    import realtime.gdpr_hard_delete_cron as mod
    import core.db as db_module

    class FakeCur:
        async def fetchall(self):
            return [("req-1", TID)]

    class FakeConn:
        async def execute(self, sql, args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    captured = {}

    async def fake_hard_delete(*, request_id, tenant_id, actor_user_id):
        captured["actor"] = actor_user_id

    from services import gdpr_forget_service
    monkeypatch.setattr(gdpr_forget_service, "hard_delete", fake_hard_delete)

    w = GdprHardDeleteCron()
    await w.run_once()
    assert captured["actor"] is None  # 系統自動


@pytest.mark.asyncio
async def test_run_once_per_row_error_isolated(monkeypatch):
    """單 row 失敗不阻其他；errors 計數。"""
    import realtime.gdpr_hard_delete_cron as mod
    import core.db as db_module

    class FakeCur:
        async def fetchall(self):
            return [("req-1", TID), ("req-2", TID), ("req-3", TID)]

    class FakeConn:
        async def execute(self, sql, args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    async def fake_hard_delete(*, request_id, tenant_id, actor_user_id):
        if request_id == "req-2":
            raise RuntimeError("DELETE failed")

    from services import gdpr_forget_service
    monkeypatch.setattr(gdpr_forget_service, "hard_delete", fake_hard_delete)

    w = GdprHardDeleteCron()
    result = await w.run_once()
    assert result["processed"] == 2  # req-1 + req-3
    assert result["errors"] == 1


@pytest.mark.asyncio
async def test_run_once_sql_includes_eligibility_filter(monkeypatch):
    """SQL 必含 status='soft_deleted' + hard_delete_eligible_at <= NOW。"""
    import realtime.gdpr_hard_delete_cron as mod
    import core.db as db_module

    captured = {}

    class FakeCur:
        async def fetchall(self):
            return []

    class FakeConn:
        async def execute(self, sql, args):
            captured["sql"] = sql
            captured["args"] = args
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    w = GdprHardDeleteCron(batch_size=25)
    await w.run_once()
    sql = captured["sql"]
    assert "status = 'soft_deleted'" in sql
    assert "hard_delete_eligible_at <= NOW()" in sql
    assert captured["args"] == (25,)


@pytest.mark.asyncio
async def test_start_stop_idempotent():
    w = GdprHardDeleteCron()
    w._run = lambda: None  # type: ignore[assignment]
    await w.stop()
    w._task = MagicMock()
    w._task.done.return_value = False
    w.start()
