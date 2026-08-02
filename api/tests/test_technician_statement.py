"""Technician AP Statement — FR-0045 MVP tests (DB mocked)。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services import technician_statement_service as svc


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


def _row(
    *, status="draft", year=2026, month=6,
    dispute_window_ends_at=None,
):
    now = datetime.now(timezone.utc)
    return (
        "stmt-1", "t1", "tech-1", year, month,
        10, 50000.0, 5000.0, 2000.0, 0.0, 0.0, 43000.0,
        status, dispute_window_ends_at, None, None,
        None, None, None, None, now, now,
    )


# ----------------------------- 狀態機 -----------------------------

def test_allowed_transitions_complete():
    """完整 6 狀態 mapping。"""
    expected = {
        "draft", "pending_review", "disputed",
        "approved", "rejected", "paid",
    }
    assert set(svc._ALLOWED_TRANSITIONS.keys()) == expected


def test_paid_is_terminal():
    assert svc._ALLOWED_TRANSITIONS["paid"] == set()


def test_check_transition_valid():
    svc._check_transition("draft", "pending_review")
    svc._check_transition("pending_review", "approved")
    svc._check_transition("approved", "paid")


def test_check_transition_invalid():
    from core.errors import ApiError

    with pytest.raises(ApiError) as e:
        svc._check_transition("draft", "approved")  # skip pending_review
    assert e.value.status_code == 409


# ----------------------------- generate -----------------------------

@pytest.mark.asyncio
async def test_generate_statement_happy(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=None),  # SELECT existing → none
        FakeCur(row=("stmt-1",)),  # INSERT RETURNING
        FakeCur(row=_row()),  # _get SELECT
    ])

    result = await svc.generate_statement(
        tenant_id="t1", technician_id="tech-1",
        period_year=2026, period_month=6,
        gross_amount=50000, travel_fee_deduction=5000,
        cash_collection_deduction=2000,
    )
    assert result["status"] == "draft"
    assert result["net_amount"] == "43000.00"


@pytest.mark.asyncio
async def test_generate_idempotent_on_existing(monkeypatch):
    """同 tech + period 已存 → 回 existing 不重複 INSERT。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("existing-id",)),  # SELECT existing → found
        FakeCur(row=_row()),  # _get
    ])

    result = await svc.generate_statement(
        tenant_id="t1", technician_id="tech-1",
        period_year=2026, period_month=6,
    )
    assert result["status"] == "draft"


@pytest.mark.asyncio
async def test_generate_invalid_month(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.generate_statement(
            tenant_id="t1", technician_id="tech-1",
            period_year=2026, period_month=13,
        )
    assert e.value.error_code == "VALIDATION_ERROR"


# ----------------------------- submit -----------------------------

@pytest.mark.asyncio
async def test_submit_sets_dispute_window_7_days(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    window_ends = now + timedelta(days=7)
    db_module._conn = FakeConn([
        FakeCur(row=("t1",)),  # _assert_tenant 的 SELECT tenant_id
        FakeCur(row=("draft",)),  # SELECT status
        FakeCur(),  # UPDATE
        FakeCur(row=_row(
            status="pending_review",
            dispute_window_ends_at=window_ends,
        )),
    ])

    result = await svc.submit_for_review(statement_id="stmt-1", tenant_id="t1")
    assert result["status"] == "pending_review"
    assert result["dispute_window_ends_at"] is not None


@pytest.mark.asyncio
async def test_submit_not_from_draft_rejected(monkeypatch):
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("t1",)),  # _assert_tenant 的 SELECT tenant_id
        FakeCur(row=("approved",)),
    ])

    with pytest.raises(ApiError) as e:
        await svc.submit_for_review(statement_id="stmt-1", tenant_id="t1")
    assert e.value.status_code == 409


# ----------------------------- dispute -----------------------------

@pytest.mark.asyncio
async def test_dispute_within_window_happy(monkeypatch):
    """pending_review + 在 window 內 → disputed。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    future = datetime.now(timezone.utc) + timedelta(days=3)
    db_module._conn = FakeConn([
        FakeCur(row=("t1",)),  # _assert_tenant 的 SELECT tenant_id
        FakeCur(row=("pending_review", future)),
        FakeCur(row=("stmt-1",)),  # UPDATE RETURNING
        FakeCur(row=_row(status="disputed")),
    ])

    result = await svc.dispute_statement(
        statement_id="stmt-1", tenant_id="t1", dispute_reason="車馬費扣多了",
    )
    assert result["status"] == "disputed"


@pytest.mark.asyncio
async def test_dispute_window_expired_rejected(monkeypatch):
    """window 過期 → 409 STATE_CONFLICT。"""
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    past = datetime.now(timezone.utc) - timedelta(days=1)
    db_module._conn = FakeConn([
        FakeCur(row=("t1",)),  # _assert_tenant 的 SELECT tenant_id
        FakeCur(row=("pending_review", past)),
    ])

    with pytest.raises(ApiError) as e:
        await svc.dispute_statement(
            statement_id="stmt-1", tenant_id="t1", dispute_reason="window 已過期想申訴",
        )
    assert e.value.status_code == 409
    assert "過期" in e.value.message


@pytest.mark.asyncio
async def test_dispute_short_reason_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.dispute_statement(
            statement_id="stmt-1", tenant_id="t1", dispute_reason="x",
        )
    assert e.value.error_code == "VALIDATION_ERROR"


# ----------------------------- approve/reject/mark_paid -----------------------------

@pytest.mark.asyncio
async def test_approve_happy(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("t1",)),  # _assert_tenant 的 SELECT tenant_id
        FakeCur(row=("pending_review",)),
        FakeCur(row=("stmt-1",)),
        FakeCur(row=_row(status="approved")),
    ])

    result = await svc.approve_statement(
        statement_id="stmt-1", tenant_id="t1", reviewer_id="admin-1",
    )
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_mark_paid_only_from_approved(monkeypatch):
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("t1",)),  # _assert_tenant 的 SELECT tenant_id
        FakeCur(row=("pending_review",)),  # 非 approved
    ])

    with pytest.raises(ApiError) as e:
        await svc.mark_paid(statement_id="stmt-1", tenant_id="t1")
    assert e.value.status_code == 409


# ----------------------------- constants -----------------------------

def test_dispute_window_7_days():
    assert svc.DISPUTE_WINDOW_DAYS == 7


# ----------------------------- router -----------------------------

def test_router_has_8_endpoints():
    from routers import technician_statement_v2 as mod
    assert len(mod.router.routes) == 8


def test_router_expected_operation_ids():
    from routers import technician_statement_v2 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    expected = {
        "generateTechStatement",
        "listTechStatements",
        "getTechStatement",
        "submitTechStatementForReview",
        "disputeTechStatement",
        "approveTechStatement",
        "rejectTechStatement",
        "markTechStatementPaid",
    }
    assert ids == expected
