"""Dispatcher Commission Statement — FR-0046 MVP tests (DB mocked)。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services import dispatcher_commission_service as svc


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
        result = (
            self._results[self._idx] if self._idx < len(self._results)
            else FakeCur()
        )
        self._idx += 1
        return result


def _row(*, status="draft", dispatched=100, completed=85):
    now = datetime.now(timezone.utc)
    return (
        "comm-1", "t1", "dispatcher-1", 2026, 6,
        dispatched, completed, 85.0, 4.2,
        50000.0, 10000.0, 2000.0, 58000.0,
        status, None, None, None,
        None, None, None, None, now, now,
    )


# ----------------------------- 狀態機 -----------------------------

def test_allowed_transitions_match_fr0045():
    """FR-0046 與 FR-0045 共用狀態機 pattern。"""
    expected = {
        "draft", "pending_review", "disputed",
        "approved", "rejected", "paid",
    }
    assert set(svc._ALLOWED_TRANSITIONS.keys()) == expected


def test_paid_terminal():
    assert svc._ALLOWED_TRANSITIONS["paid"] == set()


def test_check_transition_valid_paths():
    svc._check_transition("draft", "pending_review")
    svc._check_transition("pending_review", "approved")
    svc._check_transition("approved", "paid")


def test_check_transition_invalid():
    from core.errors import ApiError

    with pytest.raises(ApiError) as e:
        svc._check_transition("draft", "paid")
    assert e.value.status_code == 409


# ----------------------------- generate -----------------------------

@pytest.mark.asyncio
async def test_generate_completion_rate_85pct(monkeypatch):
    """100 dispatched / 85 completed → completion_rate=85%。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=None),  # no existing
        FakeCur(row=("comm-1",)),
        FakeCur(row=_row()),
    ])

    result = await svc.generate_statement(
        tenant_id="t1", dispatcher_user_id="dispatcher-1",
        period_year=2026, period_month=6,
        total_dispatched_orders=100, total_completed_orders=85,
        base_commission=50000, performance_bonus=10000, penalty=2000,
    )
    assert result["completion_rate_pct"] == "85.00"
    # net = 50000 + 10000 - 2000 = 58000
    assert result["net_commission"] == "58000.00"


@pytest.mark.asyncio
async def test_generate_zero_dispatched_no_div_by_zero(monkeypatch):
    """無派工 → completion_rate=0 不 ZeroDivisionError。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=None),
        FakeCur(row=("comm-1",)),
        FakeCur(row=_row(dispatched=0, completed=0)),
    ])

    result = await svc.generate_statement(
        tenant_id="t1", dispatcher_user_id="dispatcher-1",
        period_year=2026, period_month=6,
    )
    assert result is not None  # no exception


@pytest.mark.asyncio
async def test_generate_completed_exceeds_dispatched_rejected(monkeypatch):
    """completed > dispatched → 422。"""
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.generate_statement(
            tenant_id="t1", dispatcher_user_id="dispatcher-1",
            period_year=2026, period_month=6,
            total_dispatched_orders=10, total_completed_orders=15,
        )
    assert e.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_generate_negative_orders_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.generate_statement(
            tenant_id="t1", dispatcher_user_id="dispatcher-1",
            period_year=2026, period_month=6,
            total_dispatched_orders=-1,
        )


@pytest.mark.asyncio
async def test_generate_invalid_month_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.generate_statement(
            tenant_id="t1", dispatcher_user_id="dispatcher-1",
            period_year=2026, period_month=0,
        )


# ----------------------------- submit / dispute / approve / paid -----------------------------

@pytest.mark.asyncio
async def test_submit_window_7d(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("draft",)),
        FakeCur(),
        FakeCur(row=_row(status="pending_review")),
    ])

    result = await svc.submit_for_review(statement_id="comm-1")
    assert result["status"] == "pending_review"


@pytest.mark.asyncio
async def test_dispute_window_expired(monkeypatch):
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    past = datetime.now(timezone.utc) - timedelta(days=1)
    db_module._conn = FakeConn([
        FakeCur(row=("pending_review", past)),
    ])

    with pytest.raises(ApiError) as e:
        await svc.dispute_statement(
            statement_id="comm-1", dispute_reason="算錯 commission",
        )
    assert "過期" in e.value.message


@pytest.mark.asyncio
async def test_dispute_short_reason_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.dispute_statement(
            statement_id="comm-1", dispute_reason="x",
        )
    assert e.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_approve_happy(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("pending_review",)),
        FakeCur(row=("comm-1",)),
        FakeCur(row=_row(status="approved")),
    ])

    result = await svc.approve_statement(
        statement_id="comm-1", reviewer_id="admin-1",
    )
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_mark_paid_only_from_approved(monkeypatch):
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([FakeCur(row=("draft",))])

    with pytest.raises(ApiError) as e:
        await svc.mark_paid(statement_id="comm-1")
    assert e.value.status_code == 409


# ----------------------------- constants -----------------------------

def test_dispute_window_7_days():
    assert svc.DISPUTE_WINDOW_DAYS == 7


# ----------------------------- router -----------------------------

def test_router_has_8_endpoints():
    from routers import dispatcher_commission_v2 as mod
    assert len(mod.router.routes) == 8


def test_router_expected_operation_ids():
    from routers import dispatcher_commission_v2 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    expected = {
        "generateDispatcherCommission",
        "listDispatcherCommissions",
        "getDispatcherCommission",
        "submitDispatcherCommissionForReview",
        "disputeDispatcherCommission",
        "approveDispatcherCommission",
        "rejectDispatcherCommission",
        "markDispatcherCommissionPaid",
    }
    assert ids == expected
