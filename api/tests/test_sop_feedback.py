"""SOP Feedback Spiral — FR-0051 MVP service + router tests (DB mocked)。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services import sop_feedback_service as svc


class FakeCur:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    async def fetchone(self):
        return self._row

    async def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, results):
        self._results = list(results)
        self._idx = 0

    async def execute(self, sql, *args):
        result = (
            self._results[self._idx] if self._idx < len(self._results)
            else FakeCur()
        )
        self._idx += 1
        return result


# ----------------------------- log_feedback -----------------------------

@pytest.mark.asyncio
async def test_log_feedback_happy(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        FakeCur(row=("fb-1", now)),
    ])

    result = await svc.log_feedback(
        tenant_id="t1", sop_id="sop-1", sop_type="draft",
        source="customer_thumbs", sentiment="positive", score=5.0,
        comment="非常清楚",
    )
    assert result["id"] == "fb-1"
    assert result["source"] == "customer_thumbs"
    assert result["sentiment"] == "positive"


@pytest.mark.asyncio
async def test_log_invalid_source(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.log_feedback(
            tenant_id="t1", sop_id="sop-1", sop_type="draft",
            source="bogus_source", sentiment="positive",
        )


@pytest.mark.asyncio
async def test_log_invalid_sentiment(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.log_feedback(
            tenant_id="t1", sop_id="sop-1", sop_type="draft",
            source="customer_thumbs", sentiment="meh",
        )


@pytest.mark.asyncio
async def test_log_invalid_sop_type(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.log_feedback(
            tenant_id="t1", sop_id="sop-1", sop_type="invalid",
            source="customer_thumbs", sentiment="positive",
        )


@pytest.mark.asyncio
async def test_log_score_out_of_range(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.log_feedback(
            tenant_id="t1", sop_id="sop-1", sop_type="draft",
            source="customer_thumbs", sentiment="positive", score=6.0,
        )


# ----------------------------- list_feedback -----------------------------

@pytest.mark.asyncio
async def test_list_with_all_filters(monkeypatch):
    """SQL 應含 sop_id / source / sentiment / date clauses。"""
    import core.db as db_module
    from datetime import date

    captured = {}

    class CapConn:
        async def execute(self, sql, args):
            captured["sql"] = sql
            class C:
                async def fetchall(self):
                    return []
            return C()

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = CapConn()

    await svc.list_feedback(
        tenant_id="t1", sop_id="sop-1",
        source="rma_finding", sentiment="negative",
        start_date=date(2026, 5, 1), end_date=date(2026, 6, 1),
    )
    sql = captured["sql"]
    assert "sop_id = %s::uuid" in sql
    assert "source = %s" in sql
    assert "sentiment = %s" in sql
    assert "BETWEEN" in sql


@pytest.mark.asyncio
async def test_list_invalid_source(monkeypatch):
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn([])

    with pytest.raises(ApiError):
        await svc.list_feedback(tenant_id="t1", source="bogus")


# ----------------------------- get_sop_summary -----------------------------

@pytest.mark.asyncio
async def test_summary_computes_sentiment_score(monkeypatch):
    """positive=70, negative=10, neutral=20, total=100 → sentiment_score=60。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        # 1. by source
        FakeCur(rows=[
            ("customer_thumbs", 60), ("technician_onsite", 30),
            ("ai_eval", 10),
        ]),
        # 2. by sentiment
        FakeCur(rows=[
            ("positive", 70), ("neutral", 20), ("negative", 10),
        ]),
        # 3. avg score
        FakeCur(row=(4.2,)),
    ])

    result = await svc.get_sop_summary(tenant_id="t1", sop_id="sop-1")
    assert result["total_feedback"] == 100
    assert result["by_source"]["customer_thumbs"] == 60
    assert result["by_sentiment"]["positive"] == 70
    assert result["by_sentiment"]["negative"] == 10
    # (70 - 10) / 100 × 100 = 60
    assert result["sentiment_score"] == 60.0
    assert result["avg_score"] == 4.2


@pytest.mark.asyncio
async def test_summary_empty_no_div_by_zero(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(rows=[]), FakeCur(rows=[]), FakeCur(row=(None,)),
    ])

    result = await svc.get_sop_summary(tenant_id="t1", sop_id="sop-1")
    assert result["total_feedback"] == 0
    assert result["sentiment_score"] == 0.0
    assert result["avg_score"] is None


@pytest.mark.asyncio
async def test_summary_all_negative_sentiment_score_minus_100(monkeypatch):
    """全 negative → sentiment_score = -100。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(rows=[("rma_finding", 5)]),
        FakeCur(rows=[("negative", 5)]),
        FakeCur(row=(1.2,)),
    ])

    result = await svc.get_sop_summary(tenant_id="t1", sop_id="sop-1")
    assert result["sentiment_score"] == -100.0


# ----------------------------- router -----------------------------

def test_router_has_3_endpoints():
    from routers import sop_feedback_v2 as mod
    assert len(mod.router.routes) == 3


def test_router_expected_operation_ids():
    from routers import sop_feedback_v2 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    expected = {
        "logSopFeedback",
        "listSopFeedback",
        "getSopFeedbackSummary",
    }
    assert ids == expected
