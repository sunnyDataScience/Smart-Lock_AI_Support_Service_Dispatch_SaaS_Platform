"""Technician Penalty/Bonus v2 router — CR-0107 師傅獎懲明細（tenant-scoped）。

  - GET    /tenants/{tenantId}/technicians/{techId}/penalty-bonus           → 列獎懲（手動 + 自動取消罰）
  - POST   /tenants/{tenantId}/technicians/{techId}/penalty-bonus           → 後台手動登錄（admin/主管）
  - DELETE /tenants/{tenantId}/technicians/{techId}/penalty-bonus/{entryId} → 刪除手動登錄

獎懲金額為財務敏感 + Q121 師傅扣款須主管拍板 → 全限 DISPATCH_ROLES。自動帶入的取消失約扣款唯讀。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Path, Response

from core.deps import DISPATCH_ROLES, CurrentUser, role_required
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import technician_penalty_bonus_service as pb_service

router = APIRouter()


class _EntryCreateRequest(BaseModel):
    entry_type: str = Field(..., description="bonus 或 penalty")
    title: str = Field(..., description="事由（如「高評價獎金」「遲到扣款」）")
    amount: float = Field(..., ge=0, description="金額（正值；類型決定加減）")
    occurred_date: str = Field(..., description="事件發生日 YYYY-MM-DD")
    reason: str | None = Field(default=None, description="詳細說明（選填）")
    source_work_order_id: str | None = Field(default=None, description="關聯工單（選填）")


def _guard(user: CurrentUser, tenant_id: str, write: bool) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


@router.get(
    "/tenants/{tenantId}/technicians/{techId}/penalty-bonus",
    operation_id="listTechnicianPenaltyBonus",
    summary="師傅獎懲明細（手動登錄 + 自動取消罰，tenant-scoped）",
    tags=["M05 Technician"],
)
async def list_penalty_bonus(
    tenantId: str = Path(...),
    techId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    _guard(user, tenantId, write=False)
    items = await pb_service.list_entries(tenant_id=tenantId, technician_id=techId)
    return {"data": items}


@router.post(
    "/tenants/{tenantId}/technicians/{techId}/penalty-bonus",
    operation_id="createTechnicianPenaltyBonus",
    summary="後台登錄師傅獎懲（admin/主管；Q121 主管拍板）",
    status_code=201,
    tags=["M05 Technician"],
)
async def create_penalty_bonus(
    body: _EntryCreateRequest,
    response: Response,
    tenantId: str = Path(...),
    techId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _guard(user, tenantId, write=True)
    entry = await pb_service.create_entry(
        tenant_id=tenantId,
        technician_id=techId,
        entry_type=body.entry_type,
        title=body.title,
        amount=body.amount,
        occurred_date=body.occurred_date,
        reason=body.reason,
        source_work_order_id=body.source_work_order_id,
        created_by=user.user_id,
    )
    response.status_code = 201
    payload = {"data": entry}
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.delete(
    "/tenants/{tenantId}/technicians/{techId}/penalty-bonus/{entryId}",
    operation_id="deleteTechnicianPenaltyBonus",
    summary="刪除手動登錄的師傅獎懲（自動取消罰不可刪）",
    tags=["M05 Technician"],
)
async def delete_penalty_bonus(
    tenantId: str = Path(...),
    techId: str = Path(...),
    entryId: str = Path(...),
    user: CurrentUser = Depends(role_required(*DISPATCH_ROLES)),
) -> dict:
    _guard(user, tenantId, write=True)
    await pb_service.delete_entry(tenant_id=tenantId, technician_id=techId, entry_id=entryId)
    return {"data": None}
