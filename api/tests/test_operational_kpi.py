"""Operational KPI (FTFR + SLA on-time) service + router tests (DB mocked)。"""

from __future__ import annotations

from datetime import date

import pytest

from services import operational_kpi_service as svc


class FakeCur:
    def __init__(self, row=None):
        self._row = row

    async def fetchone(self):
        return self._row


class FakeConn:
    def __init__(self, results):
        self._results = list(results)
        self._idx = 0

    async def execute(self, sql, *args):
        result = self._results[self._idx]
        self._idx += 1
        return result


# ----------------------------- happy path -----------------------------

@pytest.mark.asyncio
async def test_kpi_happy_path(monkeypatch):
    """3 query 結果 → FTFR + dispatch + arrival 計算正確。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        # 1. (total_completed, rework_source_count)
        FakeCur(row=(100, 8)),
        # 2. (dispatch_total, dispatch_on_time)
        FakeCur(row=(100, 75)),
        # 3. (arrival_total, arrival_on_time)
        FakeCur(row=(80, 60)),
    ])

    result = await svc.get_operational_kpi(tenant_id="t1")
    # FTFR = (100-8)/100 = 92%
    assert result["ftfr"]["total_completed"] == 100
    assert result["ftfr"]["rework_source_count"] == 8
    assert result["ftfr"]["ftfr_pct"] == 92.0

    # dispatch 75/100 = 75%
    assert result["sla"]["dispatch_on_time_pct"] == 75.0
    # arrival 60/80 = 75%
    assert result["sla"]["arrival_on_time_pct"] == 75.0
    # thresholds 暴露
    assert result["sla"]["dispatch_delay_threshold_min"] == svc.DISPATCH_DELAY_MINUTES
    assert result["sla"]["arrival_overdue_threshold_min"] == svc.ARRIVAL_OVERDUE_MINUTES


@pytest.mark.asyncio
async def test_kpi_no_completed_no_div_by_zero(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=(0, 0)),
        FakeCur(row=(0, 0)),
        FakeCur(row=(0, 0)),
    ])

    result = await svc.get_operational_kpi(tenant_id="t1")
    assert result["ftfr"]["ftfr_pct"] == 0.0
    assert result["sla"]["dispatch_on_time_pct"] == 0.0
    assert result["sla"]["arrival_on_time_pct"] == 0.0


@pytest.mark.asyncio
async def test_kpi_with_date_range_passes_to_sql(monkeypatch):
    """date range → SQL 包含 BETWEEN clause。"""
    import core.db as db_module

    captured = {"sqls": []}

    class CaptureConn(FakeConn):
        async def execute(self, sql, args):
            captured["sqls"].append(sql)
            return await super().execute(sql, args)

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = CaptureConn([
        FakeCur(row=(10, 0)),
        FakeCur(row=(10, 10)),
        FakeCur(row=(10, 10)),
    ])

    await svc.get_operational_kpi(
        tenant_id="t1",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
    )
    assert any("BETWEEN" in s for s in captured["sqls"])


@pytest.mark.asyncio
async def test_kpi_db_unavailable(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return False

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.get_operational_kpi(tenant_id="t1")
    assert e.value.error_code == "DB_UNAVAILABLE"


# ----------------------------- 100% FTFR -----------------------------

@pytest.mark.asyncio
async def test_kpi_perfect_ftfr(monkeypatch):
    """無 rework → FTFR=100%。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=(50, 0)),  # 0 rework
        FakeCur(row=(50, 50)),
        FakeCur(row=(50, 50)),
    ])

    result = await svc.get_operational_kpi(tenant_id="t1")
    assert result["ftfr"]["ftfr_pct"] == 100.0


# ----------------------------- router -----------------------------

def test_router_endpoint_registered():
    from routers import reports_operational_kpi as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert "getOperationalKpiReport" in ids
