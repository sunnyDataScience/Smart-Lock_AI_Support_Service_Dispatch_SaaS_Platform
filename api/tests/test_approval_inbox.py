"""Approval Inbox MVP — FR-0049 service + router tests (DB mocked)。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services import approval_inbox_service as svc


class FakeCur:
    def __init__(self, rows=None):
        self._rows = rows or []

    async def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, results):
        self._results = list(results)
        self._idx = 0

    async def execute(self, sql, *args):
        result = (
            self._results[self._idx] if self._idx < len(self._results)
            else FakeCur(rows=[])
        )
        self._idx += 1
        return result


# ----------------------------- happy path -----------------------------

@pytest.mark.asyncio
async def test_inbox_aggregates_all_5_types(monkeypatch):
    """type_filter='all' → 5 query 全跑，各回若干 row。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    now = datetime.now(timezone.utc)
    db_module._conn = FakeConn([
        # 1. scope_changes
        FakeCur(rows=[("sc-1", "wo-1", "新增材料", now - timedelta(days=2))]),
        # 2. refund_requests
        FakeCur(rows=[("rr-1", "wo-2", 500.0, "客戶不滿", "pending", now)]),
        # 3. saas.dispute
        FakeCur(rows=[("d-1", "wo-3", "filed", "工程瑕疵", now - timedelta(days=10))]),
        # 4. saas.reschedule_proposal
        FakeCur(rows=[("rp-1", "wo-4", "明天可否？", now)]),
        # 5. saas.reconciliation_exception
        FakeCur(rows=[("ex-1", "recon-1", "amount_mismatch", "差 100", now)]),
    ])

    result = await svc.list_pending_approvals(tenant_id="t1", type_filter="all")
    assert result["total"] == 5
    assert result["by_type"] == {
        "scope_change": 1, "refund": 1, "dispute": 1,
        "reschedule": 1, "recon_exception": 1,
    }
    # severity sort: high (dispute/refund) → medium (scope/recon) → low (reschedule)
    types_in_order = [it["type"] for it in result["items"]]
    # 第一個必為 high
    assert result["items"][0]["severity"] == "high"
    # reschedule low 應排尾
    assert result["items"][-1]["type"] == "reschedule"


@pytest.mark.asyncio
async def test_inbox_type_filter_scope_change_only(monkeypatch):
    """type_filter='scope_change' → 只跑 1 個 query 其他略過。"""
    import core.db as db_module

    captured_sqls = []

    class CaptureConn(FakeConn):
        async def execute(self, sql, args):
            captured_sqls.append(sql[:50])
            return await super().execute(sql, args)

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = CaptureConn([
        FakeCur(rows=[("sc-1", "wo-1", "x", datetime.now(timezone.utc))]),
    ])

    result = await svc.list_pending_approvals(
        tenant_id="t1", type_filter="scope_change",
    )
    assert result["total"] == 1
    assert result["items"][0]["type"] == "scope_change"
    # 只跑 1 個 query
    assert len(captured_sqls) == 1


@pytest.mark.asyncio
async def test_inbox_severity_mapping():
    """嚴重度對應業務優先順序：dispute/refund high, scope/recon medium, reschedule low。"""
    assert svc._SEVERITY_BY_TYPE["dispute"] == "high"
    assert svc._SEVERITY_BY_TYPE["refund"] == "high"
    assert svc._SEVERITY_BY_TYPE["scope_change"] == "medium"
    assert svc._SEVERITY_BY_TYPE["recon_exception"] == "medium"
    assert svc._SEVERITY_BY_TYPE["reschedule"] == "low"


@pytest.mark.asyncio
async def test_inbox_days_overdue_calculation(monkeypatch):
    """5 天前的 scope_change SLA=1day → days_overdue=4。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
    db_module._conn = FakeConn([
        FakeCur(rows=[("sc-1", "wo-1", "old", five_days_ago)]),
    ])

    result = await svc.list_pending_approvals(
        tenant_id="t1", type_filter="scope_change",
    )
    assert result["items"][0]["days_overdue"] == 4  # 5 - 1


@pytest.mark.asyncio
async def test_inbox_invalid_type_filter_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.list_pending_approvals(
            tenant_id="t1", type_filter="foo_bar",
        )
    assert e.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_inbox_limit_validation(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.list_pending_approvals(tenant_id="t1", limit=0)
    assert e.value.error_code == "VALIDATION_ERROR"

    with pytest.raises(ApiError) as e:
        await svc.list_pending_approvals(tenant_id="t1", limit=501)
    assert e.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_inbox_db_unavailable(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return False

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.list_pending_approvals(tenant_id="t1")
    assert e.value.error_code == "DB_UNAVAILABLE"


@pytest.mark.asyncio
async def test_inbox_empty_returns_zero(monkeypatch):
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    db_module._conn = FakeConn([
        FakeCur(rows=[]), FakeCur(rows=[]), FakeCur(rows=[]),
        FakeCur(rows=[]), FakeCur(rows=[]),
    ])

    result = await svc.list_pending_approvals(tenant_id="t1", type_filter="all")
    assert result["total"] == 0
    assert result["items"] == []
    assert all(c == 0 for c in result["by_type"].values())


# ----------------------------- router -----------------------------

def test_router_endpoint_registered():
    from routers import approval_inbox_v2 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert "listApprovalInbox" in ids


def test_router_tenant_scoped_path():
    from routers import approval_inbox_v2 as mod
    paths = [getattr(r, "path", "") for r in mod.router.routes]
    assert "/tenants/{tenantId}/approval-inbox" in paths
