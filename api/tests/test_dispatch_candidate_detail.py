"""A37 Dispatch candidate detail v2 — endpoint smoke tests (DB mocked)。"""

from __future__ import annotations

import pytest

from services import dispatch_service as svc


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


@pytest.mark.asyncio
async def test_get_candidate_detail_returns_combined_shape(monkeypatch):
    """smoke — 確認 service 回傳 technician + dispatch_context + workload_heatmap 三段。"""
    import core.db as db_module

    async def fake_ensure():
        return True
    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    # mock get_technician
    async def fake_get_tech(*, tenant_id, technician_id):
        return {
            "id": technician_id,
            "tenant_id": tenant_id,
            "name": "UAT Tech",
            "phone": "0900000000",
            "capabilities": ["Yale", "Samsung"],
            "regions": ["台北市"],
            "rating": 4.5,
            "status": "available",
        }

    # mock workload (best-effort)
    async def fake_workload(*, tenant_id, technician_id):
        return {"hours": [4, 6, 5, 7, 3]}

    from services import technician_service
    monkeypatch.setattr(
        technician_service, "get_technician", fake_get_tech,
    )
    monkeypatch.setattr(
        technician_service,
        "get_technician_workload_heatmap",
        fake_workload,
        raising=False,
    )

    # mock DB for wo lookup
    db_module._conn = FakeConn([
        FakeCur(row=("Yale", "台北市中山區XX路")),
    ])

    result = await svc.get_candidate_detail(
        tenant_id="t1",
        work_order_id="wo-001",
        technician_id="tech-001",
    )

    assert "technician" in result
    assert "dispatch_context" in result
    assert "workload_heatmap" in result
    assert result["technician"]["id"] == "tech-001"
    assert result["dispatch_context"]["work_order_id"] == "wo-001"
    assert result["dispatch_context"]["wo_brand"] == "Yale"


@pytest.mark.asyncio
async def test_get_candidate_detail_wo_not_found(monkeypatch):
    """smoke — 工單不存在回 NOT_FOUND。"""
    import core.db as db_module
    from core.errors import ApiError

    async def fake_ensure():
        return True
    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    async def fake_get_tech(*, tenant_id, technician_id):
        return {"id": technician_id, "tenant_id": tenant_id}

    from services import technician_service
    monkeypatch.setattr(
        technician_service, "get_technician", fake_get_tech,
    )

    db_module._conn = FakeConn([
        FakeCur(row=None),  # wo not found
    ])

    with pytest.raises(ApiError) as exc:
        await svc.get_candidate_detail(
            tenant_id="t1",
            work_order_id="wo-missing",
            technician_id="tech-001",
        )
    assert exc.value.error_code == "NOT_FOUND"


def test_router_has_endpoint():
    """確認 router operation_id 註冊。"""
    from routers import dispatch_v2
    ops = [
        getattr(r, "operation_id", None) for r in dispatch_v2.router.routes
    ]
    assert "getDispatchCandidateDetailV2" in ops
