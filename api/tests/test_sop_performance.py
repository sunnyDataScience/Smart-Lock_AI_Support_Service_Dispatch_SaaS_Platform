"""SOP 績效 metrics service + router unit tests (DB mocked)。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services import sop_performance_service as svc


# ----------------------------- service aggregation -----------------------------

class FakeCur:
    def __init__(self, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    async def fetchall(self):
        return self._rows

    async def fetchone(self):
        return self._row


class FakeConn:
    """模擬多次 execute 回不同結果（按呼叫順序）。"""

    def __init__(self, results):
        self._results = list(results)
        self._idx = 0

    async def execute(self, sql, *args):
        result = self._results[self._idx]
        self._idx += 1
        return result


@pytest.mark.asyncio
async def test_metrics_happy_path(monkeypatch):
    """4 query 對應結果 → metrics 計算正確。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        # 1. status distribution
        FakeCur(rows=[
            ("pending_review", 5),
            ("approved", 10),
            ("rejected", 2),
            ("published", 8),
        ]),
        # 2. totals (active, deleted, total)
        FakeCur(row=(25, 3, 28)),
        # 3. window (new_drafts, newly_published)
        FakeCur(row=(7, 3)),
        # 4. top_recent_published
        FakeCur(rows=[
            ("sop-1", "工單 A SOP", datetime(2026, 6, 1, tzinfo=timezone.utc), "case-1"),
            ("sop-2", "工單 B SOP", datetime(2026, 5, 28, tzinfo=timezone.utc), None),
        ]),
        # 5. retire_candidates_count
        FakeCur(row=(4,)),
    ])

    result = await svc.get_sop_metrics(tenant_id="t1", window_days=30)
    assert result["tenant_id"] == "t1"
    assert result["window_days"] == 30
    assert result["status_distribution"] == {
        "pending_review": 5, "approved": 10, "rejected": 2, "published": 8,
    }
    assert result["totals"] == {"total": 28, "deleted": 3, "active": 25}
    # approval_rate = 10/(10+2) = 83.33%
    assert result["rates"]["approval_rate_pct"] == 83.33
    # publish_rate = 8/10 = 80%
    assert result["rates"]["publish_rate_pct"] == 80.0
    assert result["window"] == {"new_drafts": 7, "newly_published": 3}
    assert len(result["top_recent_published"]) == 2
    assert result["top_recent_published"][0]["id"] == "sop-1"
    assert result["retire_candidates_count"] == 4


@pytest.mark.asyncio
async def test_metrics_division_by_zero_safe(monkeypatch):
    """無 approved / decided → rates = 0 不該 ZeroDivisionError。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(rows=[("pending_review", 3)]),  # 全 pending
        FakeCur(row=(3, 0, 3)),
        FakeCur(row=(3, 0)),
        FakeCur(rows=[]),
        FakeCur(row=(0,)),
    ])

    result = await svc.get_sop_metrics(tenant_id="t1", window_days=30)
    assert result["rates"]["approval_rate_pct"] == 0.0
    assert result["rates"]["publish_rate_pct"] == 0.0
    assert result["top_recent_published"] == []


@pytest.mark.asyncio
async def test_metrics_db_unavailable(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return False

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.get_sop_metrics(tenant_id="t1")
    assert e.value.error_code == "DB_UNAVAILABLE"


@pytest.mark.asyncio
async def test_metrics_window_days_validation(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.get_sop_metrics(tenant_id="t1", window_days=0)
    assert e.value.error_code == "VALIDATION_ERROR"

    with pytest.raises(ApiError) as e:
        await svc.get_sop_metrics(tenant_id="t1", window_days=366)
    assert e.value.error_code == "VALIDATION_ERROR"


# ----------------------------- router -----------------------------

def test_router_has_metrics_endpoint():
    from routers import sop_performance_v2 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert "getSopPerformanceMetrics" in ids


def test_router_metrics_path_tenant_scoped():
    from routers import sop_performance_v2 as mod
    paths = [getattr(r, "path", "") for r in mod.router.routes]
    assert any(
        p == "/tenants/{tenantId}/sop-performance/metrics" for p in paths
    )
