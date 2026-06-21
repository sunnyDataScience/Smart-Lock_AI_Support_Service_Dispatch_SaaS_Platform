"""CR-0088 技師端決策屏聚合端點 — 單元測試（FakeConn，無 DB 依賴）。

涵蓋：
- get_my_dashboard_summary 聚合數學（收入/毛額/完成率/到場/評分）
- 不含租戶內排名（業主 §8-3 裁決）
- 完成率 zero-guard（本月 0 單不 ZeroDivisionError）
- get_my_workload_heatmap self-scoped（由 user_id 解析 technician_id）
- 兩個新 /me 路由註冊 + path 格式
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services import technician_service as svc


class _FakeCur:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many

    async def fetchone(self):
        return self._one

    async def fetchall(self):
        return self._many or []


def _make_conn(*, tech_id="tech-uuid-1", agg=None, feedback=None):
    """依 SQL 內容路由：technicians 解析 / 聚合 / 近期評價。"""

    class _FakeConn:
        async def execute(self, sql, args=None):
            if "FROM technicians" in sql:
                return _FakeCur(one=(tech_id,) if tech_id else None)
            if "feedback IS NOT NULL" in sql:
                return _FakeCur(many=feedback or [])
            return _FakeCur(one=agg)

    return _FakeConn()


@pytest.mark.asyncio
async def test_dashboard_summary_aggregates(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    # (today_e, week_e, month_done_e, pending_e, month_total, month_done,
    #  today_new, avg_arr, avg_rating, rating_count)
    agg = (1200.0, 4500.0, 18000.0, 6000.0, 10, 8, 2, 35.5, 4.6, 12)
    fb = [(5, "很專業", datetime(2026, 6, 20, tzinfo=timezone.utc))]

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = _make_conn(agg=agg, feedback=fb)

    r = await svc.get_my_dashboard_summary(tenant_id="t1", user_id="u1")

    assert r["technician_id"] == "tech-uuid-1"
    assert r["today_earnings"] == 1200.0
    assert r["week_earnings"] == 4500.0
    assert r["month_gross_est"] == 24000.0  # 18000 完工 + 6000 未結預估
    assert r["month_completed_earnings"] == 18000.0
    assert r["month_pending_est"] == 6000.0
    assert r["completion_rate_pct"] == 80.0  # 8 / 10
    assert r["today_new_orders"] == 2
    assert r["avg_arrival_minutes"] == 35.5
    assert r["avg_rating"] == 4.6
    assert r["rating_count"] == 12
    assert len(r["recent_feedback"]) == 1
    assert r["recent_feedback"][0]["rating"] == 5
    assert r["recent_feedback"][0]["feedback"] == "很專業"

    # 業主 §8-3 裁決：不對技師開放租戶內排名
    assert "rank_in_tenant" not in r
    assert "rank" not in r


@pytest.mark.asyncio
async def test_dashboard_summary_zero_month_no_div_error(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    # month_total=0 → completion_rate_pct 應為 None，不可 ZeroDivisionError
    agg = (0, 0, 0, 0, 0, 0, 0, None, None, 0)
    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = _make_conn(agg=agg, feedback=[])

    r = await svc.get_my_dashboard_summary(tenant_id="t1", user_id="u1")
    assert r["completion_rate_pct"] is None
    assert r["avg_arrival_minutes"] is None
    assert r["avg_rating"] is None
    assert r["today_earnings"] == 0.0
    assert r["recent_feedback"] == []


@pytest.mark.asyncio
async def test_dashboard_summary_missing_technician_404(monkeypatch):
    import core.db as db_module
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = _make_conn(tech_id=None)

    with pytest.raises(ApiError) as e:
        await svc.get_my_dashboard_summary(tenant_id="t1", user_id="ghost")
    assert e.value.error_code == "TECHNICIAN_NOT_FOUND"


@pytest.mark.asyncio
async def test_my_workload_heatmap_self_scoped(monkeypatch):
    """get_my_workload_heatmap 由 user_id 解析 technician_id 後重用既有聚合。"""
    import core.db as db_module
    from datetime import date

    async def fake_ensure():
        return True

    class _Conn:
        async def execute(self, sql, args=None):
            if "FROM technicians" in sql:
                return _FakeCur(one=("tech-uuid-9",))
            # workload group-by rows
            return _FakeCur(many=[(date(2026, 6, 20), "completed", 3)])

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = _Conn()

    r = await svc.get_my_workload_heatmap(tenant_id="t1", user_id="u9", days=30)
    assert r["technician_id"] == "tech-uuid-9"
    assert r["window_days"] == 30


# ----------------------------- 路由註冊 -----------------------------

def test_router_has_my_dashboard_endpoints():
    from routers import technicians as mod

    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert "getMyDashboardSummary" in ids
    assert "getMyWorkloadHeatmap" in ids


def test_my_endpoints_path_format():
    from routers import technicians as mod

    paths = [getattr(r, "path", "") for r in mod.router.routes]
    assert "/technicians/me/dashboard-summary" in paths
    assert "/technicians/me/workload-heatmap" in paths
