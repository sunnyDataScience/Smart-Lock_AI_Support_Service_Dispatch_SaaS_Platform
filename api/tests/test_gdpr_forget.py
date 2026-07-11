"""GDPR Forget MVP — service + router tests (DB mocked)。FR-0053 Phase II。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services import gdpr_forget_service as svc


class FakeCur:
    def __init__(self, row=None, rows=None, rowcount=1):
        self._row = row
        self._rows = rows or []
        self.rowcount = rowcount  # CR-0164 D：hard_delete 讀 del_cur.rowcount 判實刪

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


@pytest.fixture(autouse=True)
def _isolate_crosscutting(monkeypatch):
    """CR-0164 D：本檔為 mock 單元測試，隔離新增的橫切關注（audit / legal-hold
    前置查詢）——它們有各自的 component 測試（test_cr_0164_gdpr_forget.py）。
    否則新 DB 操作會打亂各測試精確的 FakeConn mock 序列。
    """
    async def _noop_audit(**_kw):
        return None

    async def _no_hold(_subject):
        return False

    monkeypatch.setattr(svc, "_forget_audit", _noop_audit)
    monkeypatch.setattr(svc, "_has_active_legal_hold", _no_hold)


# ----------------------------- create_forget_request -----------------------------

@pytest.mark.asyncio
async def test_create_request_happy_path(monkeypatch):
    """new request (no existing) → INSERT + return envelope。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        # 1. SELECT email
        FakeCur(row=("alice@example.com",)),
        # 2. SELECT existing (none)
        FakeCur(row=None),
        # 3. INSERT RETURNING id
        FakeCur(row=("req-1",)),
        # 4. _get_request SELECT
        FakeCur(row=(
            "req-1", "t1", "user-1", "alice@example.com", "received",
            "customer_self", None, None, now, None, None, None, "admin-1", None,
        )),
    ])

    result = await svc.create_forget_request(
        tenant_id="t1", subject_user_id="user-1",
        requested_by="customer_self", actor_user_id="admin-1",
    )
    assert result["id"] == "req-1"
    assert result["status"] == "received"
    assert result["requested_by"] == "customer_self"
    assert result["subject_email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_create_request_idempotent_on_existing(monkeypatch):
    """同 user 已 received → 回 existing，不 INSERT new row。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        # 1. SELECT email
        FakeCur(row=("alice@example.com",)),
        # 2. SELECT existing → found
        FakeCur(row=("existing-id", "received", now)),
        # 3. _get_request
        FakeCur(row=(
            "existing-id", "t1", "user-1", "alice@example.com",
            "received", "customer_self", None, None, now,
            None, None, None, "admin-1", None,
        )),
    ])

    result = await svc.create_forget_request(
        tenant_id="t1", subject_user_id="user-1",
    )
    assert result["id"] == "existing-id"


@pytest.mark.asyncio
async def test_create_request_invalid_requested_by(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.create_forget_request(
            tenant_id="t1", subject_user_id="user-1",
            requested_by="invalid_source",
        )
    assert e.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_request_user_not_found(monkeypatch):
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn([FakeCur(row=None)])  # email lookup fail

    with pytest.raises(ApiError) as e:
        await svc.create_forget_request(
            tenant_id="t1", subject_user_id="nope",
        )
    assert e.value.status_code == 404


# ----------------------------- deny_legal_hold -----------------------------

@pytest.mark.asyncio
async def test_deny_legal_hold_happy(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        FakeCur(row=("req-1",)),  # UPDATE RETURNING
        FakeCur(row=(
            "req-1", "t1", "user-1", "x", "legal_hold_denied",
            "customer_self", "active dispute", None, now,
            None, None, None, "admin-1", None,
        )),  # _get_request
    ])

    result = await svc.deny_legal_hold(
        request_id="req-1", legal_hold_reason="active dispute pending",
        actor_user_id="admin-1",
    )
    assert result["status"] == "legal_hold_denied"
    assert result["legal_hold_reason"] == "active dispute"


@pytest.mark.asyncio
async def test_deny_legal_hold_short_reason_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.deny_legal_hold(
            request_id="req-1", legal_hold_reason="x",
        )
    assert e.value.error_code == "VALIDATION_ERROR"


# ----------------------------- soft_delete -----------------------------

@pytest.mark.asyncio
async def test_soft_delete_sets_eligibility_30_days(monkeypatch):
    """soft_delete 後 hard_delete_eligible_at = NOW + 30 days。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        # 1. _get_request (status='received')
        FakeCur(row=(
            "req-1", "t1", "user-1", "alice@example.com", "received",
            "customer_self", None, None, now, None, None, None, None, None,
        )),
        # 2. UPDATE users PII
        FakeCur(),
        # 3. UPDATE forget_request RETURNING
        FakeCur(row=("req-1",)),
        # 4. _get_request (after update)
        FakeCur(row=(
            "req-1", "t1", "user-1", "alice@example.com", "soft_deleted",
            "customer_self", None, None, now, now,
            now + timedelta(days=30),
            None, "admin-1", None,
        )),
    ])

    result = await svc.soft_delete(request_id="req-1", actor_user_id="admin-1")
    assert result["status"] == "soft_deleted"
    assert result["soft_deleted_at"] is not None
    assert result["hard_delete_eligible_at"] is not None


@pytest.mark.asyncio
async def test_soft_delete_only_from_received(monkeypatch):
    """soft_delete on already-soft_deleted → 409。"""
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        FakeCur(row=(
            "req-1", "t1", "user-1", "x", "soft_deleted",
            "customer_self", None, None, now, now, now, None, None, None,
        )),
    ])

    with pytest.raises(ApiError) as e:
        await svc.soft_delete(request_id="req-1")
    assert e.value.status_code == 409


# ----------------------------- hard_delete -----------------------------

@pytest.mark.asyncio
async def test_hard_delete_cooldown_not_yet_passed(monkeypatch):
    """hard_delete 前 cooldown 未滿 → 409。"""
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        FakeCur(row=(
            "req-1", "t1", "user-1", "x", "soft_deleted", "customer_self",
            None, None, now, now,
            now + timedelta(days=10),  # 還 10 天才到
            None, None, None,
        )),
    ])

    with pytest.raises(ApiError) as e:
        await svc.hard_delete(request_id="req-1")
    assert e.value.status_code == 409
    assert "cooldown" in str(e.value.message)


@pytest.mark.asyncio
async def test_hard_delete_cooldown_passed_happy(monkeypatch):
    """cooldown 已過 → DELETE users + UPDATE forget_request hard_deleted。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=31)  # 31 天前 soft delete
    db_module._conn = FakeConn([
        # 1. _get_request
        FakeCur(row=(
            "req-1", "t1", "user-1", "x", "soft_deleted", "customer_self",
            None, None, old, old,
            old + timedelta(days=30),  # 30+1 天前可硬刪
            None, None, None,
        )),
        # 2. DELETE users
        FakeCur(),
        # 3. UPDATE forget_request
        FakeCur(row=("req-1",)),
        # 4. _get_request after
        FakeCur(row=(
            "req-1", "t1", "user-1", "x", "hard_deleted", "customer_self",
            None, None, old, old, old + timedelta(days=30), now, None, None,
        )),
    ])

    result = await svc.hard_delete(request_id="req-1")
    assert result["status"] == "hard_deleted"


# ----------------------------- cancel -----------------------------

@pytest.mark.asyncio
async def test_cancel_only_from_received(monkeypatch):
    """cancel on hard_deleted → 409。"""
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=None),  # UPDATE 0 rows
    ])

    with pytest.raises(ApiError) as e:
        await svc.cancel_request(request_id="req-1")
    assert e.value.status_code == 409


# ----------------------------- constants -----------------------------

def test_cooldown_30_days():
    """BR-PII-001 強制 30 天 cooldown。"""
    assert svc.HARD_DELETE_COOLDOWN_DAYS == 30


# ----------------------------- router -----------------------------

def test_router_has_7_endpoints():
    from routers import gdpr_forget_v2 as mod
    assert len(mod.router.routes) == 7


def test_router_expected_operation_ids():
    from routers import gdpr_forget_v2 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    expected = {
        "createGdprForgetRequest",
        "listGdprForgetRequests",
        "getGdprForgetRequest",
        "denyGdprForgetForLegalHold",
        "softDeleteGdprForgetRequest",
        "hardDeleteGdprForgetRequest",
        "cancelGdprForgetRequest",
    }
    assert ids == expected
