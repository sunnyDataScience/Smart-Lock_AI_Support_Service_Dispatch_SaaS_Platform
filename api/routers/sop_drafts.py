"""SOP Drafts router — listSopDrafts + getSopDraft (read-only)。

operationId 對齊 openapi.yaml：
  listSopDrafts, getSopDraft

不含 reviewSopDraft / adoptSopDraft — 等審核 + 家族覆核 pipeline 接入再開放。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from models.generated import (
    SopDraft,
    SopDraftEnvelope,
    SopDraftPage,
    SopDraftStatus,
)
from services import sop_draft_service

router = APIRouter()


@router.get(
    "/sop-drafts",
    operation_id="listSopDrafts",
    summary="SOP 草稿列表（cursor 分頁）",
    response_model=SopDraftPage,
)
async def list_sop_drafts(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: SopDraftStatus | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await sop_draft_service.list_drafts(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
    )
    return {
        "items": [SopDraft(**d).model_dump(mode="json") for d in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/sop-drafts/{id}",
    operation_id="getSopDraft",
    summary="取得 SOP 草稿詳情",
    response_model=SopDraftEnvelope,
)
async def get_sop_draft(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    draft = await sop_draft_service.get_draft(
        tenant_id=user.tenant_id, draft_id=id,
    )
    return {"data": SopDraft(**draft).model_dump(mode="json")}
