"""Scheduled Reports V2 Router — admin 報表排程 endpoints。

POST  /tenants/{tid}/scheduled-reports        → createSchedule
GET   /tenants/{tid}/scheduled-reports        → listSchedules
DELETE/tenants/{tid}/scheduled-reports/{id}   → cancelSchedule
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, OPS_ROLES, require_tenant, role_required
from core.errors import ApiError
from services import scheduled_report_service as svc


router = APIRouter()


class CreateScheduleBody(BaseModel):
    report_type: Literal["kpi", "revenue", "technician_ranking", "settlements"]
    cadence: Literal["weekly", "monthly", "quarterly"]
    recipients: list[str] = Field(..., min_length=1, max_length=20)
    format: Literal["csv", "xlsx", "pdf"] = "csv"
    filters: dict | None = None


@router.post(
    "/tenants/{tenantId}/scheduled-reports",
    operation_id="createScheduledReport",
    summary="建立報表排程 (週/月/季發送)",
    response_model=dict,
    status_code=201,
)
async def create_scheduled_report(
    body: CreateScheduleBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    schedule = await svc.create_schedule(
        tenant_id=tenantId,
        report_type=body.report_type,
        cadence=body.cadence,
        recipients=body.recipients,
        format=body.format,
        filters=body.filters,
        created_by=user.user_id if hasattr(user, "user_id") else None,
    )
    return {"data": schedule}


@router.get(
    "/tenants/{tenantId}/scheduled-reports",
    operation_id="listScheduledReports",
    summary="列出 tenant 報表排程",
    response_model=dict,
)
async def list_scheduled_reports(
    tenantId: str = Path(...),
    report_type: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    # CR-0211 D1：原本只有 require_tenant（任何已登入的同租戶使用者都讀得到），
    # 同檔的 create（:41）與 cancel（:95）都掛 OPS_ROLES —— 三支裡只有 list 沒掛，
    # 這種不對稱是漏設而非設計。回傳內容含 `recipients`（收件人 email 清單）＝PII，
    # 任何技師或客服帳號都能列出整個租戶的報表收件人。
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    return await svc.list_schedules(
        tenant_id=tenantId,
        report_type=report_type,
        active_only=active_only,
    )


@router.delete(
    "/tenants/{tenantId}/scheduled-reports/{scheduleId}",
    operation_id="cancelScheduledReport",
    summary="取消報表排程 (is_active=false)",
    response_model=dict,
)
async def cancel_scheduled_report(
    tenantId: str = Path(...),
    scheduleId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    result = await svc.cancel_schedule(
        tenant_id=tenantId, schedule_id=scheduleId,
    )
    return {"data": result}
