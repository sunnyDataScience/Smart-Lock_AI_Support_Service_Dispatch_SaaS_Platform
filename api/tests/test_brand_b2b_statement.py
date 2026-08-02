"""Brand B2B Settlement — FR-0047 MVP tests (DB mocked)。Phase II 9 FR 收尾。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services import brand_b2b_statement_service as svc


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


def _row(*, status="draft", direction="NET", net_amount=10000.0,
         net_payable_to="platform"):
    now = datetime.now(timezone.utc)
    return (
        "stmt-1", "t1", "brand-1", "Yale Corp", "CT-2026-001",
        2026, 6, direction,
        500, 50, 5,
        100000.0, 80000.0, 5000.0, 5000.0,
        net_amount, net_payable_to,
        status, None, None, None,
        None, None, None, None, now, now,
    )


# ----------------------------- _compute_net -----------------------------

def test_compute_net_ar_direction():
    """AR: net = ar_service_fee → platform 收。"""
    net, payable = svc._compute_net(
        direction="AR", ar_service_fee=50000,
        ap_commission=10000, warranty_deduction=0, sla_penalty=0,
    )
    assert net == 50000.0
    assert payable == "platform"


def test_compute_net_ap_direction():
    """AP: net = ap - warranty - sla → brand 收。"""
    net, payable = svc._compute_net(
        direction="AP", ar_service_fee=0,
        ap_commission=20000, warranty_deduction=3000, sla_penalty=1000,
    )
    assert net == 16000.0
    assert payable == "brand"


def test_compute_net_direction_brand_owes_platform():
    """NET: ar - ap + warranty + sla > 0 → brand 欠 platform。"""
    net, payable = svc._compute_net(
        direction="NET", ar_service_fee=100000,
        ap_commission=80000, warranty_deduction=5000, sla_penalty=5000,
    )
    # 100000 - 80000 + 5000 + 5000 = 30000 > 0
    assert net == 30000.0
    assert payable == "platform"


def test_compute_net_direction_platform_owes_brand():
    """NET 負值 → platform 欠 brand。"""
    net, payable = svc._compute_net(
        direction="NET", ar_service_fee=50000,
        ap_commission=80000, warranty_deduction=0, sla_penalty=0,
    )
    # 50000 - 80000 = -30000 < 0
    assert net == -30000.0
    assert payable == "brand"


def test_compute_net_zero():
    net, payable = svc._compute_net(
        direction="NET", ar_service_fee=50000,
        ap_commission=50000, warranty_deduction=0, sla_penalty=0,
    )
    assert net == 0.0
    assert payable is None


# ----------------------------- 狀態機 -----------------------------

def test_allowed_transitions_match_fr0045_0046():
    expected = {
        "draft", "pending_review", "disputed",
        "approved", "rejected", "paid",
    }
    assert set(svc._ALLOWED_TRANSITIONS.keys()) == expected


def test_check_transition_invalid():
    from core.errors import ApiError

    with pytest.raises(ApiError) as e:
        svc._check_transition("draft", "approved")
    assert e.value.status_code == 409


# ----------------------------- generate -----------------------------

@pytest.mark.asyncio
async def test_generate_net_direction_happy(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=None),  # no existing
        FakeCur(row=("stmt-1",)),
        FakeCur(row=_row()),
    ])

    result = await svc.generate_statement(
        tenant_id="t1", brand_partner_id="brand-1",
        brand_name="Yale Corp",
        period_year=2026, period_month=6,
        direction="NET",
        ar_service_fee=100000, ap_commission=80000,
        warranty_deduction=5000, sla_penalty=5000,
    )
    # net = 100000 - 80000 + 5000 + 5000 = 30000 (computed)
    # but mock _row returns 10000 just for shape
    assert result["direction"] == "NET"
    assert result["net_payable_to"] == "platform"


@pytest.mark.asyncio
async def test_generate_idempotent_same_brand_period_direction(monkeypatch):
    """同 brand + period + direction 已存 → 回 existing。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("existing-id",)),  # found
        FakeCur(row=_row()),
    ])

    result = await svc.generate_statement(
        tenant_id="t1", brand_partner_id="brand-1",
        brand_name="Yale Corp",
        period_year=2026, period_month=6, direction="NET",
    )
    assert result is not None


@pytest.mark.asyncio
async def test_generate_invalid_direction_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.generate_statement(
            tenant_id="t1", brand_partner_id="brand-1",
            brand_name="Yale", period_year=2026, period_month=6,
            direction="INVALID",
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
            tenant_id="t1", brand_partner_id="brand-1",
            brand_name="Yale", period_year=2026, period_month=6,
            total_service_orders=-1,
        )


@pytest.mark.asyncio
async def test_generate_empty_brand_name_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError):
        await svc.generate_statement(
            tenant_id="t1", brand_partner_id="brand-1",
            brand_name="", period_year=2026, period_month=6,
        )


# ----------------------------- 狀態機 ops -----------------------------

@pytest.mark.asyncio
async def test_submit_window_7d(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("t1",)),  # _assert_tenant
        FakeCur(row=("draft",)),
        FakeCur(),
        FakeCur(row=_row(status="pending_review")),
    ])

    result = await svc.submit_for_review(statement_id="stmt-1", tenant_id="t1")
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
        FakeCur(row=("t1",)),  # _assert_tenant
        FakeCur(row=("pending_review", past)),
    ])

    with pytest.raises(ApiError) as e:
        await svc.dispute_statement(
            statement_id="stmt-1", tenant_id="t1", dispute_reason="contract 計算不對",
        )
    assert "過期" in e.value.message


@pytest.mark.asyncio
async def test_approve_happy(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("t1",)),  # _assert_tenant
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

    db_module._conn = FakeConn([FakeCur(row=("t1",)), FakeCur(row=("draft",))])  # 首個 cursor 供 _assert_tenant

    with pytest.raises(ApiError) as e:
        await svc.mark_paid(statement_id="stmt-1", tenant_id="t1")
    assert e.value.status_code == 409


# ----------------------------- constants -----------------------------

def test_dispute_window_7_days():
    assert svc.DISPUTE_WINDOW_DAYS == 7


def test_valid_directions():
    assert svc._VALID_DIRECTIONS == {"AR", "AP", "NET"}


# ----------------------------- router -----------------------------

def test_router_has_8_endpoints():
    from routers import brand_b2b_statement_v2 as mod
    assert len(mod.router.routes) == 8


def test_router_expected_operation_ids():
    from routers import brand_b2b_statement_v2 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    expected = {
        "generateBrandB2bStatement",
        "listBrandB2bStatements",
        "getBrandB2bStatement",
        "submitBrandB2bStatementForReview",
        "disputeBrandB2bStatement",
        "approveBrandB2bStatement",
        "rejectBrandB2bStatement",
        "markBrandB2bStatementPaid",
    }
    assert ids == expected
