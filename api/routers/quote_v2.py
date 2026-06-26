"""Quote v2 router — 報價引擎（CR-0032 Phase B）。

  - POST /tenants/{tid}/work-orders/{woId}/quotes        建報價（draft）
  - GET  /tenants/{tid}/quotes/{id}                       報價詳情（internal cost RBAC 遮蔽）
  - POST /tenants/{tid}/quotes/{id}/lines                 加報價項（從 catalog 帶價）
  - POST /tenants/{tid}/quotes/{id}:submit|:send|:accept  狀態機（一般角色）
  - POST /tenants/{tid}/quotes/{id}:approve|:reject       核准（管理角色）

數值走 CR-0034 mock 主檔；正式門檻待 esales Q-01~Q-12。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import quote_engine_service as qe

router = APIRouter()

_COST_VISIBLE_ROLES = {"admin", "operations_manager", "tenant_admin"}
_APPROVE_ROLES = ("admin", "operations_manager", "tenant_admin")


def _xt(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId does not match authenticated tenant", 403)


def _cost(user: CurrentUser) -> bool:
    return (user.role or "") in _COST_VISIBLE_ROLES


class _QuoteCreateBody(BaseModel):
    urgent: bool = Field(default=False, description="急件 → 有效期 3d")


class _AddLineBody(BaseModel):
    service_code: str | None = Field(default=None)
    material_code: str | None = Field(default=None)
    quantity: int = Field(default=1, ge=1, le=999)
    item_name: str | None = Field(default=None, max_length=120)


class _DecisionBody(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


@router.post(
    "/tenants/{tenantId}/work-orders/{woId}/quotes",
    operation_id="createQuoteV2", status_code=201,
    summary="建報價 v2（draft，CR-0032）", tags=["M04 Quote"],
)
async def create_quote_v2(
    body: _QuoteCreateBody,
    tenantId: str = Path(...), woId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _xt(user, tenantId)
    return {"data": await qe.create_quote(
        tenant_id=tenantId, work_order_id=woId, created_by=user.user_id, urgent=body.urgent)}


@router.get(
    "/tenants/{tenantId}/quotes",
    operation_id="listQuotesV2",
    summary="報價列表 v2（CR-0095：含公單號 TP + 狀態，供報價 dashboard）", tags=["M04 Quote"],
)
async def list_quotes_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _xt(user, tenantId)
    return {"data": await qe.list_quotes(tenant_id=tenantId)}


@router.get(
    "/tenants/{tenantId}/quotes/{id}",
    operation_id="getQuoteV2", summary="報價詳情 v2（成本 RBAC 遮蔽）", tags=["M04 Quote"],
)
async def get_quote_v2(
    tenantId: str = Path(...), id: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    _xt(user, tenantId)
    return {"data": await qe.get_quote(tenant_id=tenantId, quote_id=id, include_cost=_cost(user))}


@router.get(
    "/tenants/{tenantId}/quotes/{id}/public-link",
    operation_id="getQuotePublicLinkV2",
    summary="取得客戶端報價查看連結 v2（已送報價才有）", tags=["M04 Quote"],
)
async def get_quote_public_link_v2(
    tenantId: str = Path(...), id: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _xt(user, tenantId)
    return {"data": await qe.mint_view_token(tenant_id=tenantId, quote_id=id)}


@router.post(
    "/tenants/{tenantId}/quotes/{id}/lines",
    operation_id="addQuoteLineV2", status_code=201,
    summary="加報價項 v2（從 catalog 帶價）", tags=["M04 Quote"],
)
async def add_quote_line_v2(
    body: _AddLineBody,
    tenantId: str = Path(...), id: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _xt(user, tenantId)
    return {"data": await qe.add_line(
        tenant_id=tenantId, quote_id=id, quantity=body.quantity,
        service_code=body.service_code, material_code=body.material_code, item_name=body.item_name)}


@router.delete(
    "/tenants/{tenantId}/quotes/{id}/lines/{lineId}",
    operation_id="removeQuoteLineV2",
    summary="移除報價項 v2（draft/pending_approval 可改，移除後重算總額）", tags=["M04 Quote"],
)
async def remove_quote_line_v2(
    tenantId: str = Path(...), id: str = Path(...), lineId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _xt(user, tenantId)
    return {"data": await qe.remove_line(tenant_id=tenantId, quote_id=id, line_id=lineId)}


async def _transition(tenantId: str, id: str, action: str, user: CurrentUser, comment: str | None = None) -> dict:
    _xt(user, tenantId)
    return {"data": await qe.transition(
        tenant_id=tenantId, quote_id=id, action=action, actor_id=user.user_id, comment=comment)}


@router.post("/tenants/{tenantId}/quotes/{id}:submit", operation_id="submitQuoteV2", summary="送審 v2", tags=["M04 Quote"])
async def submit_quote_v2(tenantId: str = Path(...), id: str = Path(...), user: CurrentUser = Depends(role_required(*OPS_ROLES))) -> dict:
    return await _transition(tenantId, id, "submit", user)


@router.post("/tenants/{tenantId}/quotes/{id}:send", operation_id="sendQuoteV2", summary="送客戶 v2（凍結 snapshot）", tags=["M04 Quote"])
async def send_quote_v2(tenantId: str = Path(...), id: str = Path(...), user: CurrentUser = Depends(role_required(*OPS_ROLES))) -> dict:
    return await _transition(tenantId, id, "send", user)


@router.post("/tenants/{tenantId}/quotes/{id}:accept", operation_id="acceptQuoteV2", summary="客戶接受 v2", tags=["M04 Quote"])
async def accept_quote_v2(tenantId: str = Path(...), id: str = Path(...), user: CurrentUser = Depends(role_required(*OPS_ROLES))) -> dict:
    return await _transition(tenantId, id, "accept", user)


@router.post("/tenants/{tenantId}/quotes/{id}:approve", operation_id="approveQuoteV2", summary="核准報價 v2（管理角色）", tags=["M04 Quote"])
async def approve_quote_v2(body: _DecisionBody, tenantId: str = Path(...), id: str = Path(...),
                           user: CurrentUser = Depends(role_required(*_APPROVE_ROLES))) -> dict:
    return await _transition(tenantId, id, "approve", user, body.comment)


@router.post("/tenants/{tenantId}/quotes/{id}:reject", operation_id="rejectQuoteV2", summary="駁回報價 v2（管理角色）", tags=["M04 Quote"])
async def reject_quote_v2(body: _DecisionBody, tenantId: str = Path(...), id: str = Path(...),
                          user: CurrentUser = Depends(role_required(*_APPROVE_ROLES))) -> dict:
    return await _transition(tenantId, id, "reject", user, body.comment)
