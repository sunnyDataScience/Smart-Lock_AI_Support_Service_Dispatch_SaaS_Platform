"""CR-0048 改派/改期強制原因 + 落 status_reason 測試（BR-M05-01）。"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import work_order_service as svc

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_reassign_empty_reason_422():
    """改派空原因 → 422（原因檢查在狀態檢查前，不需完整 seed）。"""
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await svc.reassign_order(
            tenant_id=TID, wo_id=str(uuid.uuid4()),
            new_technician_id=str(uuid.uuid4()), reason="   ")
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_request_reschedule_empty_reason_422():
    """改期空原因 → 422。"""
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await svc.request_reschedule(
            tenant_id=TID, wo_id=str(uuid.uuid4()),
            new_scheduled_at="2099-01-01T10:00:00Z", reason="  ",
            actor_user_id=str(uuid.uuid4()), actor_role="admin")
    assert ei.value.status_code == 422
