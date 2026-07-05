"""Technician Lifecycle service + router structure tests (DB mocked) — FR-0044 MVP。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services import technician_lifecycle_service as svc


# ----------------------------- 狀態機 -----------------------------

def test_allowed_transitions_pending_approval():
    """pending_approval → active|rejected。"""
    assert svc._ALLOWED_TRANSITIONS["pending_approval"] == {"active", "rejected"}


def test_allowed_transitions_active_can_suspend_or_terminate():
    assert svc._ALLOWED_TRANSITIONS["active"] == {"suspended", "terminated"}


def test_allowed_transitions_suspended_can_reactivate_or_terminate():
    assert svc._ALLOWED_TRANSITIONS["suspended"] == {"active", "terminated"}


def test_allowed_transitions_terminated_is_terminal():
    """terminated 終態 — 不可再變。"""
    assert svc._ALLOWED_TRANSITIONS["terminated"] == set()


def test_check_transition_allows_valid():
    svc._check_transition("pending_approval", "active")
    svc._check_transition("active", "suspended")
    svc._check_transition("suspended", "active")


def test_check_transition_rejects_invalid():
    from core.errors import ApiError

    with pytest.raises(ApiError) as e:
        svc._check_transition("pending_approval", "suspended")
    assert e.value.error_code == "STATE_CONFLICT"
    assert e.value.status_code == 409


def test_check_transition_rejects_terminated_outgoing():
    from core.errors import ApiError

    with pytest.raises(ApiError):
        svc._check_transition("terminated", "active")


# ----------------------------- service ops (mocked DB) -----------------------------

class FakeCur:
    def __init__(self, row=None):
        self._row = row

    async def fetchone(self):
        return self._row


class FakeConn:
    def __init__(self, results):
        self._results = list(results)
        self._idx = 0
        self.last_args = None

    async def execute(self, sql, *args):
        self.last_args = args
        result = (
            self._results[self._idx] if self._idx < len(self._results)
            else FakeCur()
        )
        self._idx += 1
        return result


@pytest.mark.asyncio
async def test_approve_onboarding_pending_to_active(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("pending_approval",)),  # _fetch_status
        FakeCur(row=("tech-1", "active",
                     datetime.now(timezone.utc))),  # UPDATE RETURNING
        FakeCur(row=None),  # audit INSERT
    ])

    result = await svc.approve_onboarding(
        tenant_id="t1", tech_id="tech-1", actor_user_id="admin-1",
    )
    assert result["previous_status"] == "pending_approval"
    assert result["new_status"] == "active"
    assert result["event_type"] == "onboarding_approved"


@pytest.mark.asyncio
async def test_suspend_active_to_suspended(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("active",)),
        FakeCur(row=("tech-1", "suspended", datetime.now(timezone.utc))),
        FakeCur(),
    ])

    result = await svc.suspend(
        tenant_id="t1", tech_id="tech-1", actor_user_id="admin-1",
        reason="證照過期",
    )
    assert result["new_status"] == "suspended"
    assert result["event_type"] == "suspended"


@pytest.mark.asyncio
async def test_terminate_from_active(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("active",)),
        FakeCur(row=("tech-1", "terminated", datetime.now(timezone.utc))),
        FakeCur(),
    ])

    result = await svc.terminate(
        tenant_id="t1", tech_id="tech-1", actor_user_id="admin-1",
        reason="主動離職",
    )
    assert result["new_status"] == "terminated"


@pytest.mark.asyncio
async def test_terminate_from_suspended(monkeypatch):
    """suspended → terminated 允許（永久終止）。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("suspended",)),
        FakeCur(row=("tech-1", "terminated", datetime.now(timezone.utc))),
        FakeCur(),
    ])

    result = await svc.terminate(
        tenant_id="t1", tech_id="tech-1", actor_user_id="admin-1",
        reason="重大客訴",
    )
    assert result["new_status"] == "terminated"


@pytest.mark.asyncio
async def test_suspend_pending_rejected(monkeypatch):
    """pending_approval → suspended 不允許 (狀態機 reject)。"""
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=("pending_approval",)),  # current 是 pending
    ])

    with pytest.raises(ApiError) as e:
        await svc.suspend(
            tenant_id="t1", tech_id="tech-1", actor_user_id="admin-1",
            reason="證照過期需停權",  # 足夠長避被 reason validation 先攔
        )
    assert e.value.error_code == "STATE_CONFLICT"


@pytest.mark.asyncio
async def test_reason_validation_too_short(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.suspend(
            tenant_id="t1", tech_id="tech-1", actor_user_id="admin-1",
            reason="ab",  # 2 字元 < 3
        )
    assert e.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_tech_not_found_returns_404(monkeypatch):
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(row=None),  # _fetch_status 找不到
    ])

    with pytest.raises(ApiError) as e:
        await svc.suspend(
            tenant_id="t1", tech_id="nope", actor_user_id="admin-1",
            reason="x reason",
        )
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_list_lifecycle_events_with_filters(monkeypatch):
    import core.db as db_module

    class CapConn:
        async def execute(self, sql, *args):
            class C:
                async def fetchall(self):
                    return [
                        (
                            "ev-1", "tech-1", "suspended", "active",
                            "suspended", "證照", None, "admin-1",
                            "operations_manager", datetime.now(timezone.utc),
                        ),
                    ]
            return C()

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = CapConn()

    result = await svc.list_lifecycle_events(
        tenant_id="t1", tech_id="tech-1", event_type="suspended",
    )
    assert result["total"] == 1
    assert result["items"][0]["event_type"] == "suspended"
    assert result["items"][0]["previous_status"] == "active"


# ----------------------------- router -----------------------------

def test_brand_router_readonly_only_lifecycle_events():
    """CR-0114 R3:師傅生命週期寫端點已搬平台方 → 品牌 router 只剩唯讀 audit。"""
    from routers import technician_lifecycle_v2 as mod
    assert len(mod.router.routes) == 1
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert ids == {"listTechnicianLifecycleEvents"}


def test_platform_router_has_lifecycle_write_endpoints():
    """CR-0114 R3:5 個生命週期寫端點 + 清單 + audit 全在平台 router。"""
    from routers import platform_technicians as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    expected = {
        "listPlatformTechnicians",
        "platformApproveTechnician",
        "platformRejectTechnician",
        "platformSuspendTechnician",
        "platformReactivateTechnician",
        "platformTerminateTechnician",
        "listPlatformTechnicianLifecycleEvents",
    }
    assert ids == expected
