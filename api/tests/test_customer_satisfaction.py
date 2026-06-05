"""Customer satisfaction service + router unit tests (DB mocked)。"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from services import customer_satisfaction_service as svc


class FakeCur:
    def __init__(self, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    async def fetchall(self):
        return self._rows

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


# ----------------------------- service -----------------------------

@pytest.mark.asyncio
async def test_satisfaction_happy_path(monkeypatch):
    """3 query 結果 → 算出 avg / distribution / rates / top。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        # 1. (total_completed, total_rated, avg_rating)
        FakeCur(row=(50, 40, 4.25)),
        # 2. rating distribution rows
        FakeCur(rows=[(1, 2), (2, 3), (3, 5), (4, 10), (5, 20)]),
        # 3. top_low_rating recent rows
        FakeCur(rows=[
            ("wo-1", "tech-1", 1, "服務不好", datetime(2026, 6, 1, tzinfo=timezone.utc)),
            ("wo-2", "tech-2", 2, "時間久", datetime(2026, 5, 30, tzinfo=timezone.utc)),
        ]),
    ])

    result = await svc.get_customer_satisfaction(tenant_id="t1")
    assert result["tenant_id"] == "t1"
    assert result["totals"]["total_completed"] == 50
    assert result["totals"]["total_rated"] == 40
    assert result["totals"]["rated_pct"] == 80.0  # 40/50
    assert result["avg_rating"] == 4.25
    assert result["rating_distribution"] == {1: 2, 2: 3, 3: 5, 4: 10, 5: 20}
    # low (1+2)=5, 5/40 = 12.5%
    assert result["rates"]["low_rating_pct"] == 12.5
    # five_star: 20/40 = 50%
    assert result["rates"]["five_star_pct"] == 50.0
    assert len(result["top_low_rating_recent"]) == 2
    assert result["top_low_rating_recent"][0]["rating"] == 1
    assert result["top_low_rating_recent"][0]["feedback"] == "服務不好"


@pytest.mark.asyncio
async def test_satisfaction_no_completed_no_div_by_zero(monkeypatch):
    """無完工 → rated_pct=0 不該 ZeroDivisionError。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=(0, 0, None)),
        FakeCur(rows=[]),
        FakeCur(rows=[]),
    ])

    result = await svc.get_customer_satisfaction(tenant_id="t1")
    assert result["totals"]["total_completed"] == 0
    assert result["totals"]["rated_pct"] == 0.0
    assert result["avg_rating"] is None
    assert result["rates"]["low_rating_pct"] == 0.0
    assert result["rates"]["five_star_pct"] == 0.0


@pytest.mark.asyncio
async def test_satisfaction_with_date_range(monkeypatch):
    """date range 給時 SQL 應含 time_clause。"""
    import core.db as db_module

    captured = {}

    class CaptureConn(FakeConn):
        async def execute(self, sql, args):
            captured.setdefault("calls", []).append((sql, args))
            return await super().execute(sql, args)

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = CaptureConn([
        FakeCur(row=(10, 8, 4.0)),
        FakeCur(rows=[(5, 5), (4, 3)]),
        FakeCur(rows=[]),
    ])

    await svc.get_customer_satisfaction(
        tenant_id="t1",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 1),
    )
    first_sql = captured["calls"][0][0]
    assert "completed_at::date BETWEEN" in first_sql


@pytest.mark.asyncio
async def test_satisfaction_db_unavailable(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return False

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.get_customer_satisfaction(tenant_id="t1")
    assert e.value.error_code == "DB_UNAVAILABLE"


# ----------------------------- router -----------------------------

def test_router_endpoint_registered():
    from routers import reports_customer_satisfaction as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert "getCustomerSatisfactionReport" in ids
