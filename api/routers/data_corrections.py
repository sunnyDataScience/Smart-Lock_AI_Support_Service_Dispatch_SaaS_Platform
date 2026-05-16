"""DataCorrections router — admin review queue endpoints。

operationId（待 openapi.yaml 對齊）：
  listDataCorrections, getDataCorrection,
  approveDataCorrection, rejectDataCorrection

對應 CR-0001 §3 / ADR-0029 三件組之 Review Queue：客服 ``#資料修正``
進 data_corrections 表（status='pending'），admin 透過此 router 消費。

權限：tenant-scoped，預期由客服主管 / 知識管理員操作。為避免一上線就
全綁 admin role，本期沿用 require_tenant；後續加 require_admin 留 V2。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from services import data_corrections_service

logger = logging.getLogger("api.routers.data_corrections")

router = APIRouter()


@router.get(
    "/data-corrections",
    operation_id="listDataCorrections",
    summary="資料修正 review queue 列表（cursor 分頁，預設 pending）",
)
async def list_data_corrections(
    status: str | None = Query(
        default="pending",
        description="過濾狀態：pending / approved / rejected（空字串 = 全部）",
    ),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await data_corrections_service.list_corrections(
        status=status or None,
        cursor=cursor,
        limit=limit,
    )
    return page


@router.get(
    "/data-corrections/{id}",
    operation_id="getDataCorrection",
    summary="資料修正詳情",
)
async def get_data_correction(
    id: int = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    return await data_corrections_service.get_correction(id)


@router.post(
    "/data-corrections/{id}/approve",
    operation_id="approveDataCorrection",
    summary="核准資料修正（轉 approved，下游 SOP draft 由 Knowledge Owner 處理）",
)
async def approve_data_correction(
    id: int = Path(...),
    body: dict | None = Body(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    review_note = (body or {}).get("review_note") if body else None
    return await data_corrections_service.approve_correction(
        id,
        reviewer_id=user.user_id,
        review_note=review_note,
    )


@router.post(
    "/data-corrections/{id}/reject",
    operation_id="rejectDataCorrection",
    summary="駁回資料修正",
)
async def reject_data_correction(
    id: int = Path(...),
    body: dict | None = Body(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    review_note = (body or {}).get("review_note") if body else None
    return await data_corrections_service.reject_correction(
        id,
        reviewer_id=user.user_id,
        review_note=review_note,
    )
