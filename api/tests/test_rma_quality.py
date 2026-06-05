"""RMA Quality Feedback Loop — FR-0048 MVP tests (DB mocked)。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services import rma_quality_service as svc


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


# ----------------------------- log_finding -----------------------------

@pytest.mark.asyncio
async def test_log_finding_happy(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        FakeCur(row=("rma-1", now)),
    ])

    result = await svc.log_finding(
        tenant_id="t1",
        failure_mode="battery_drain",
        brand="Yale",
        device_model="YDM4109",
        brand_quality_score=2.5,
        technician_quality_score=4.0,
    )
    assert result["id"] == "rma-1"
    assert result["failure_mode"] == "battery_drain"
    assert result["cascade_sop_feedback"] is False  # no propagate args


@pytest.mark.asyncio
async def test_log_finding_short_failure_mode_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.log_finding(
            tenant_id="t1", failure_mode="x",
        )


@pytest.mark.asyncio
async def test_log_finding_invalid_ai_accuracy(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.log_finding(
            tenant_id="t1", failure_mode="battery_drain",
            ai_diagnosis_accuracy="totally_bogus",
        )


@pytest.mark.asyncio
async def test_log_finding_score_out_of_range(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.log_finding(
            tenant_id="t1", failure_mode="x mode",
            brand_quality_score=6.0,
        )


# ----------------------------- cascade SOP feedback -----------------------------

@pytest.mark.asyncio
async def test_log_finding_cascade_to_sop_when_wrong(monkeypatch):
    """ai_diagnosis_accuracy='wrong' + propagate args → 自動呼 sop_feedback_service.log_feedback。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        FakeCur(row=("rma-1", now)),
    ])

    cascaded = {}
    from services import sop_feedback_service

    async def fake_log_fb(**kwargs):
        cascaded.update(kwargs)
        return {"id": "fb-1"}

    monkeypatch.setattr(sop_feedback_service, "log_feedback", fake_log_fb)

    result = await svc.log_finding(
        tenant_id="t1", failure_mode="battery_drain",
        ai_diagnosis_accuracy="wrong",
        propagate_to_sop_feedback_sop_id="sop-1",
        propagate_to_sop_feedback_sop_type="case_entry",
    )
    assert result["cascade_sop_feedback"] is True
    assert cascaded["source"] == "rma_finding"
    assert cascaded["sentiment"] == "negative"  # wrong → negative
    assert cascaded["sop_id"] == "sop-1"
    assert "rma_quality_finding_id" in cascaded["metadata"]


@pytest.mark.asyncio
async def test_log_finding_cascade_partial_sentiment_neutral(monkeypatch):
    """ai_diagnosis_accuracy='partial' → sentiment='neutral'。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([FakeCur(row=("rma-1", now))])

    cascaded = {}

    async def fake_log_fb(**kwargs):
        cascaded.update(kwargs)
        return {"id": "fb-1"}

    from services import sop_feedback_service
    monkeypatch.setattr(sop_feedback_service, "log_feedback", fake_log_fb)

    await svc.log_finding(
        tenant_id="t1", failure_mode="motor_jam",
        ai_diagnosis_accuracy="partial",
        propagate_to_sop_feedback_sop_id="sop-1",
        propagate_to_sop_feedback_sop_type="case_entry",
    )
    assert cascaded["sentiment"] == "neutral"


@pytest.mark.asyncio
async def test_log_finding_no_cascade_when_accurate(monkeypatch):
    """ai_diagnosis_accuracy='accurate' → 不 cascade (好的 AI 不需 negative sop feedback)。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([FakeCur(row=("rma-1", now))])

    cascaded = {"called": False}

    async def fake_log_fb(**kwargs):
        cascaded["called"] = True
        return {"id": "fb-1"}

    from services import sop_feedback_service
    monkeypatch.setattr(sop_feedback_service, "log_feedback", fake_log_fb)

    result = await svc.log_finding(
        tenant_id="t1", failure_mode="working_well",
        ai_diagnosis_accuracy="accurate",
        propagate_to_sop_feedback_sop_id="sop-1",
        propagate_to_sop_feedback_sop_type="case_entry",
    )
    assert cascaded["called"] is False
    assert result["cascade_sop_feedback"] is False


@pytest.mark.asyncio
async def test_log_finding_cascade_failure_swallowed(monkeypatch):
    """sop_feedback.log_feedback 拋例外 → 不該 leak 例外（主流程 finding 已寫入）。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([FakeCur(row=("rma-1", now))])

    async def fake_log_fb(**kwargs):
        raise RuntimeError("sop_feedback DB down")

    from services import sop_feedback_service
    monkeypatch.setattr(sop_feedback_service, "log_feedback", fake_log_fb)

    # 不該 raise
    result = await svc.log_finding(
        tenant_id="t1", failure_mode="x mode",
        ai_diagnosis_accuracy="wrong",
        propagate_to_sop_feedback_sop_id="sop-1",
        propagate_to_sop_feedback_sop_type="case_entry",
    )
    assert result["id"] == "rma-1"


# ----------------------------- list_findings -----------------------------

@pytest.mark.asyncio
async def test_list_findings_all_filters(monkeypatch):
    """SQL 包含所有 filter clauses。"""
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

    await svc.list_findings(
        tenant_id="t1", failure_mode="motor_jam",
        brand="Samsung", technician_id="tech-1",
        is_repeat_failure=True,
        start_date=date(2026, 5, 1), end_date=date(2026, 6, 1),
    )
    sql = captured["sql"]
    assert "failure_mode = %s" in sql
    assert "brand = %s" in sql
    assert "technician_id = %s::uuid" in sql
    assert "is_repeat_failure = %s" in sql
    assert "BETWEEN" in sql


# ----------------------------- brand_summary -----------------------------

@pytest.mark.asyncio
async def test_brand_summary_aggregates(monkeypatch):
    """top failure_modes + avg_brand_quality + repeat_failure_pct。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        # 1. top failure modes
        FakeCur(rows=[("battery_drain", 30), ("motor_jam", 10)]),
        # 2. aggregate: total / avg / repeat
        FakeCur(row=(40, 3.2, 8)),
    ])

    result = await svc.get_brand_summary(tenant_id="t1", brand="Yale")
    assert result["brand"] == "Yale"
    assert result["total_findings"] == 40
    assert result["avg_brand_quality_score"] == 3.2
    # 8/40 = 20%
    assert result["repeat_failure_pct"] == 20.0
    assert result["top_failure_modes"][0]["failure_mode"] == "battery_drain"


@pytest.mark.asyncio
async def test_brand_summary_empty_no_div_by_zero(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(rows=[]),
        FakeCur(row=(0, None, 0)),
    ])

    result = await svc.get_brand_summary(tenant_id="t1")
    assert result["total_findings"] == 0
    assert result["repeat_failure_pct"] == 0.0
    assert result["avg_brand_quality_score"] is None


# ----------------------------- technician_summary -----------------------------

@pytest.mark.asyncio
async def test_technician_summary_aggregates(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        # total / avg_tq / avg_cs / repeat
        FakeCur(row=(20, 4.5, 4.2, 1)),
    ])

    result = await svc.get_technician_summary(
        tenant_id="t1", technician_id="tech-1",
    )
    assert result["total_findings"] == 20
    assert result["avg_technician_quality_score"] == 4.5
    assert result["avg_customer_satisfaction_score"] == 4.2
    # 1/20 = 5%
    assert result["repeat_failure_pct"] == 5.0


# ----------------------------- router -----------------------------

def test_router_has_4_endpoints():
    from routers import rma_quality_v2 as mod
    assert len(mod.router.routes) == 4


def test_router_expected_operation_ids():
    from routers import rma_quality_v2 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    expected = {
        "logRmaQualityFinding",
        "listRmaQualityFindings",
        "getRmaQualityBrandSummary",
        "getRmaQualityTechnicianSummary",
    }
    assert ids == expected
