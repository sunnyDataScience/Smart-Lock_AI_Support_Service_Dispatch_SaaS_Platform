"""A37 candidate detail drawer — technician workload heatmap unit tests。

不依賴 DB：
- _classify_load 純函式 5 分級
- get_workload_heatmap router endpoint 註冊 + operation_id
"""

from __future__ import annotations

import pytest

from services import technician_service as svc


# ----------------------------- _classify_load -----------------------------

def test_classify_load_idle():
    assert svc._classify_load(0) == "idle"


def test_classify_load_low():
    assert svc._classify_load(1) == "low"


def test_classify_load_medium():
    assert svc._classify_load(2) == "medium"
    assert svc._classify_load(3) == "medium"


def test_classify_load_high():
    assert svc._classify_load(4) == "high"
    assert svc._classify_load(5) == "high"


def test_classify_load_saturated():
    assert svc._classify_load(6) == "saturated"
    assert svc._classify_load(100) == "saturated"


# ----------------------------- get_workload_heatmap aggregation -----------------------------

@pytest.mark.asyncio
async def test_heatmap_aggregates_by_day_and_status(monkeypatch):
    """SQL row (day, status, count) → daily dict with per-status counters。"""
    import core.db as db_module
    from datetime import date

    class FakeCur:
        async def fetchall(self):
            return [
                # (day, status, count)
                (date(2026, 5, 6), "completed", 2),
                (date(2026, 5, 6), "in_progress", 1),
                (date(2026, 5, 5), "completed", 1),
                (date(2026, 5, 5), "cancelled", 1),
            ]

    class FakeConn:
        async def execute(self, sql, args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    result = await svc.get_technician_workload_heatmap(
        tenant_id="t1", technician_id="tech-1", days=30,
    )
    assert result["technician_id"] == "tech-1"
    assert result["window_days"] == 30
    assert len(result["daily"]) == 2

    # 0526 日 total=3 (completed 2 + in_progress 1) → medium
    day_06 = next(d for d in result["daily"] if d["date"] == "2026-05-06")
    assert day_06["total"] == 3
    assert day_06["completed"] == 2
    assert day_06["in_progress"] == 1
    assert day_06["cancelled"] == 0
    assert day_06["load_intensity"] == "medium"

    # 0525 日 total=2 (completed 1 + cancelled 1) → medium
    day_05 = next(d for d in result["daily"] if d["date"] == "2026-05-05")
    assert day_05["total"] == 2
    assert day_05["completed"] == 1
    assert day_05["cancelled"] == 1


@pytest.mark.asyncio
async def test_heatmap_summary_computes_completion_rate(monkeypatch):
    """summary.completion_rate_pct = completed / (completed+cancelled) × 100"""
    import core.db as db_module
    from datetime import date

    class FakeCur:
        async def fetchall(self):
            return [
                (date(2026, 5, 6), "completed", 8),
                (date(2026, 5, 6), "cancelled", 2),
            ]

    class FakeConn:
        async def execute(self, sql, args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    result = await svc.get_technician_workload_heatmap(
        tenant_id="t1", technician_id="tech-1", days=30,
    )
    # 8 / (8+2) = 80%
    assert result["summary"]["completion_rate_pct"] == 80.0
    assert result["summary"]["total_completed"] == 8
    assert result["summary"]["total_cancelled"] == 2
    assert result["summary"]["peak_day"] == "2026-05-06"
    assert result["summary"]["avg_per_day"] == 10.0  # 1 day x 10 total


@pytest.mark.asyncio
async def test_heatmap_empty_no_division_by_zero(monkeypatch):
    """無 row → completion_rate_pct=0 不該 ZeroDivisionError。"""
    import core.db as db_module

    class FakeCur:
        async def fetchall(self):
            return []

    class FakeConn:
        async def execute(self, sql, args):
            return FakeCur()

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn()

    result = await svc.get_technician_workload_heatmap(
        tenant_id="t1", technician_id="tech-1", days=30,
    )
    assert result["daily"] == []
    assert result["summary"]["completion_rate_pct"] == 0.0
    assert result["summary"]["peak_day"] is None
    assert result["summary"]["avg_per_day"] == 0.0


@pytest.mark.asyncio
async def test_heatmap_days_validation(monkeypatch):
    """days < 1 or > 90 → 422 VALIDATION_ERROR。"""
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.get_technician_workload_heatmap(
            tenant_id="t1", technician_id="tech-1", days=0,
        )
    assert e.value.error_code == "VALIDATION_ERROR"

    with pytest.raises(ApiError) as e:
        await svc.get_technician_workload_heatmap(
            tenant_id="t1", technician_id="tech-1", days=91,
        )
    assert e.value.error_code == "VALIDATION_ERROR"


# ----------------------------- router 註冊 -----------------------------

def test_router_has_workload_heatmap_endpoint():
    from routers import technicians as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert "getTechnicianWorkloadHeatmap" in ids


def test_workload_heatmap_path_format():
    from routers import technicians as mod
    paths = [getattr(r, "path", "") for r in mod.router.routes]
    assert any(
        p == "/technicians/{technician_id}/workload-heatmap" for p in paths
    )
