"""OHS requote command 端點(WBS 2.4.3/CR-0144)— 對齊 16_API_Spec.yaml:391。

兩個入口:
  /internal/requote-requests — 技師平台 service-to-service(internal token)
  /tenants/{tid}/work-orders/{woId}/requote-requests — browser 入口
    (technician=本人發起;BACKOFFICE=cs_fallback 降級代發起,ADR-027)
"""

import uuid as _uuid

import core.db as db_module
from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from core.deps import CurrentUser, TECH_ACTION_ROLES, require_internal_token, role_required
from core.errors import ApiError
from services import requote_service

router = APIRouter()


class RequoteBody(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    work_order_id: str
    technician_id: str
    reason: str
    # CR-0150:收緊為必填非空(16_API required;空修正單無語意)
    item_diffs: list = Field(min_length=1)
    initiated_via: str = "technician_command"
    tenant_id: str | None = None  # 單品牌 stack 可省略(退 AGENT_TENANT_ID)


@router.post(
    "/internal/requote-requests",
    operation_id="submitRequoteRequest",
    summary="技師平台發起現場報價修正 command(ADR-027;冪等回放)",
    dependencies=[Depends(require_internal_token)],
    status_code=201,
)
async def submit_requote_request(body: RequoteBody, response: Response) -> dict:
    data, replayed = await requote_service.submit_requote(
        request_id=body.request_id, work_order_id=body.work_order_id,
        technician_id=body.technician_id, reason=body.reason,
        item_diffs=body.item_diffs, initiated_via=body.initiated_via,
        tenant_id=body.tenant_id,
    )
    if replayed:
        response.status_code = 200  # 冪等回放(非新建)
    return {"data": data, "error": None}


class TechRequoteBody(BaseModel):
    reason: str
    # CR-0150:收緊為必填非空(同 internal 入口)
    item_diffs: list = Field(min_length=1)
    request_id: str | None = None  # 未帶=以 Idempotency-Key 為冪等鍵


@router.post(
    "/tenants/{tenantId}/work-orders/{workOrderId}/requote-requests",
    operation_id="submitRequoteRequestAsTech",
    summary="現場報價修正 browser 入口(技師本人;後台角色=cs_fallback 降級)",
    status_code=201,
)
async def submit_requote_as_tech(
    tenantId: str, workOrderId: str, body: TechRequoteBody, response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(role_required(*TECH_ACTION_ROLES)),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("TENANT_MISMATCH", "path tenantId 與 token 不符", 403)

    if user.role == "technician":
        # 技師本人:users.id → technicians.id(service 再驗 assignee)
        cur = await db_module._conn.execute(
            "SELECT id FROM technicians WHERE user_id=%s::uuid", (user.user_id,))
        row = await cur.fetchone()
        if not row:
            raise ApiError("FORBIDDEN", "無對應技師主檔", 403)
        technician_id, via = str(row[0]), "technician_command"
    else:
        # 後台代發起(降級):technician_id 取工單 assignee
        cur = await db_module._conn.execute(
            "SELECT technician_id FROM work_orders WHERE id=%s::uuid", (workOrderId,))
        row = await cur.fetchone()
        if not row or not row[0]:
            raise ApiError("VALIDATION_ERROR", "工單無 assignee,無從代發起", 422)
        technician_id, via = str(row[0]), "cs_fallback"

    request_id = body.request_id or idempotency_key or f"ui-{_uuid.uuid4().hex}"
    data, replayed = await requote_service.submit_requote(
        request_id=request_id, work_order_id=workOrderId,
        technician_id=technician_id, reason=body.reason,
        item_diffs=body.item_diffs, initiated_via=via, tenant_id=tenantId,
    )
    if replayed:
        response.status_code = 200
    return {"data": data, "error": None}
