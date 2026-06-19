"""M18 canary auto-advance — cron worker + service helper tests (DB mocked)。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from realtime.config_canary_advance_cron import (
    DEFAULT_INTERVAL_S,
    ConfigCanaryAdvanceCron,
)


# ----------------------------- cron constants -----------------------------

def test_default_interval_is_5min():
    """5 分鐘 interval 對齊 M18 observation 通常 10-15min，掃描頻率合理。"""
    assert DEFAULT_INTERVAL_S == 300


# ----------------------------- run_once -----------------------------

@pytest.mark.asyncio
async def test_run_once_db_unavailable_returns_skipped(monkeypatch):
    import realtime.config_canary_advance_cron as mod

    async def fake_ensure():
        return False

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    w = ConfigCanaryAdvanceCron()
    result = await w.run_once()
    assert result == {"skipped": "db_unavailable", "advanced": 0, "errors": 0}


@pytest.mark.asyncio
async def test_run_once_no_due_rollouts(monkeypatch):
    """無 due rollout → advanced=0 errors=0。"""
    import realtime.config_canary_advance_cron as mod
    import core.db as db_module

    class FakeCur:
        async def fetchall(self):
            return []

    class FakeConn:
        async def execute(self, sql, *args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    w = ConfigCanaryAdvanceCron()
    result = await w.run_once()
    assert result["advanced"] == 0 and result["errors"] == 0


@pytest.mark.asyncio
async def test_run_once_advances_due_rollouts(monkeypatch):
    """2 個 due rollout → 兩個都呼 service.advance 並計數。"""
    import realtime.config_canary_advance_cron as mod
    import core.db as db_module

    class FakeCur:
        async def fetchall(self):
            return [("rollout-1",), ("rollout-2",)]

    class FakeConn:
        async def execute(self, sql, *args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    advanced_ids = []

    async def fake_advance(*, rollout_id):
        advanced_ids.append(rollout_id)
        return {"new_stage": "50%", "rollout_id": rollout_id,
                "version_id": "v1", "next_stage_eta": "2026-06-05T00:00:00+00:00"}

    from services import config_m18_service
    monkeypatch.setattr(
        config_m18_service, "_advance_canary_stage", fake_advance,
    )

    w = ConfigCanaryAdvanceCron()
    result = await w.run_once()
    assert result["advanced"] == 2 and result["errors"] == 0
    assert advanced_ids == ["rollout-1", "rollout-2"]


@pytest.mark.asyncio
async def test_run_once_per_rollout_error_isolated(monkeypatch):
    """一個 rollout advance 失敗，其他繼續；errors 計數。"""
    import realtime.config_canary_advance_cron as mod
    import core.db as db_module

    class FakeCur:
        async def fetchall(self):
            return [("rollout-1",), ("rollout-2",), ("rollout-3",)]

    class FakeConn:
        async def execute(self, sql, *args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(mod, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    async def fake_advance(*, rollout_id):
        if rollout_id == "rollout-2":
            raise RuntimeError("DB conflict")
        return {"new_stage": "50%", "rollout_id": rollout_id,
                "version_id": "v1", "next_stage_eta": None}

    from services import config_m18_service
    monkeypatch.setattr(
        config_m18_service, "_advance_canary_stage", fake_advance,
    )

    w = ConfigCanaryAdvanceCron()
    result = await w.run_once()
    assert result["advanced"] == 2 and result["errors"] == 1


# ----------------------------- service _advance_canary_stage logic -----------------------------

@pytest.mark.asyncio
async def test_advance_5_to_50_writes_stage_and_audit(monkeypatch):
    """5% → 50%：UPDATE rollout + audit stage_advanced。"""
    from services import config_m18_service as svc
    import core.db as db_module

    captured_updates = []
    captured_audits = []

    stage_start = datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc)
    next_eta = stage_start + timedelta(minutes=10)

    class FakeCur:
        def __init__(self, row=None):
            self._row = row

        async def fetchone(self):
            return self._row

    class FakeConn:
        async def execute(self, sql, *args):
            if "SELECT cr.id" in sql:
                return FakeCur((
                    "rollout-1", "version-1", "5%",
                    stage_start, next_eta,
                    "tenant-1", "ns", "key", "user-init", "user-approve",
                ))
            if "UPDATE saas.config_rollout SET" in sql:
                captured_updates.append((sql, args))
            return FakeCur()

    db_module._conn = FakeConn()

    async def fake_audit(**kwargs):
        captured_audits.append(kwargs)

    monkeypatch.setattr(svc, "_append_audit", fake_audit)

    result = await svc._advance_canary_stage(rollout_id="rollout-1")
    assert result["new_stage"] == "50%"
    assert result["next_stage_eta"] is not None
    assert len(captured_updates) >= 1
    # audit 應有 stage_advanced
    assert any(a["action"] == "stage_advanced" for a in captured_audits)
    advance_audit = next(a for a in captured_audits if a["action"] == "stage_advanced")
    assert advance_audit["diff"]["from"] == "5%"
    assert advance_audit["diff"]["to"] == "50%"
    assert advance_audit["diff"]["auto_advanced"] is True


@pytest.mark.asyncio
async def test_advance_50_to_100_activates_and_dethrones(monkeypatch):
    """50% → 100%：dethrone 舊 active + activate 本版 + audit×2 (stage_advanced + activated)。"""
    from services import config_m18_service as svc
    import core.db as db_module

    captured_audits = []
    dethrone_called = {}

    stage_start = datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc)
    next_eta = stage_start + timedelta(minutes=10)

    class FakeCur:
        def __init__(self, row=None):
            self._row = row

        async def fetchone(self):
            return self._row

    class FakeConn:
        async def execute(self, sql, *args):
            if "SELECT cr.id" in sql:
                return FakeCur((
                    "rollout-1", "version-1", "50%",
                    stage_start, next_eta,
                    "tenant-1", "ns", "key", "user-init", "user-approve",
                ))
            return FakeCur()

    db_module._conn = FakeConn()

    async def fake_dethrone(tenant_id, namespace, key):
        dethrone_called["called"] = (tenant_id, namespace, key)
        return "dethroned-uuid"

    async def fake_audit(**kwargs):
        captured_audits.append(kwargs)

    def fake_cache_inv(*args, **kwargs):
        pass

    monkeypatch.setattr(svc, "_dethrone_active", fake_dethrone)
    monkeypatch.setattr(svc, "_append_audit", fake_audit)
    monkeypatch.setattr(svc, "_cache_invalidate", fake_cache_inv)

    result = await svc._advance_canary_stage(rollout_id="rollout-1")
    assert result["new_stage"] == "100%"
    assert result["next_stage_eta"] is None
    assert dethrone_called["called"] == ("tenant-1", "ns", "key")
    # audit 應有 stage_advanced + activated
    actions = [a["action"] for a in captured_audits]
    assert "stage_advanced" in actions
    assert "activated" in actions


@pytest.mark.asyncio
async def test_advance_rollout_not_found_raises_404(monkeypatch):
    from services import config_m18_service as svc
    from core.errors import ApiError
    import core.db as db_module

    class FakeCur:
        async def fetchone(self):
            return None

    class FakeConn:
        async def execute(self, sql, *args):
            return FakeCur()

    db_module._conn = FakeConn()

    with pytest.raises(ApiError) as e:
        await svc._advance_canary_stage(rollout_id="nope")
    assert e.value.error_code == "CONFIG_NOT_FOUND"
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_advance_already_100_rejects_409(monkeypatch):
    from services import config_m18_service as svc
    from core.errors import ApiError
    import core.db as db_module

    class FakeCur:
        async def fetchone(self):
            return (
                "rollout-1", "version-1", "100%",
                datetime.now(timezone.utc), None,
                "tenant-1", "ns", "key", "user-i", "user-a",
            )

    class FakeConn:
        async def execute(self, sql, *args):
            return FakeCur()

    db_module._conn = FakeConn()

    with pytest.raises(ApiError) as e:
        await svc._advance_canary_stage(rollout_id="rollout-1")
    assert e.value.status_code == 409


# ----------------------------- lifespan -----------------------------

@pytest.mark.asyncio
async def test_cron_start_stop_idempotent():
    w = ConfigCanaryAdvanceCron()
    w._run = lambda: None  # type: ignore[assignment]
    await w.stop()
    w._task = MagicMock()
    w._task.done.return_value = False
    w.start()
