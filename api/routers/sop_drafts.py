"""SOP Drafts router — read + 寫入路徑（review / adopt）。

operationId 對齊 openapi.yaml：
  listSopDrafts, getSopDraft, reviewSopDraft, adoptSopDraft
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    CaseEntry,
    CaseEntryEnvelope,
    SopDraft,
    SopDraftAdoptRequest,
    SopDraftEnvelope,
    SopDraftPage,
    SopDraftReviewRequest,
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


@router.patch(
    "/sop-drafts/{id}/review",
    operation_id="reviewSopDraft",
    summary="管理員初審 SOP 草稿（approve / reject）",
    response_model=SopDraftEnvelope,
)
async def review_sop_draft(
    body: SopDraftReviewRequest,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    draft = await sop_draft_service.review_draft(
        tenant_id=user.tenant_id,
        draft_id=id,
        decision=body.decision.value,
        comment=body.comment,
        reviewer_id=user.user_id,
    )
    payload = {"data": SopDraft(**draft).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.post(
    "/sop-drafts/{id}/adopt",
    operation_id="adoptSopDraft",
    summary="採納 SOP 草稿（核准後入庫成為案例）",
    response_model=CaseEntryEnvelope,
)
async def adopt_sop_draft(
    body: SopDraftAdoptRequest | None = None,
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    target_case_id = None
    if body is not None and body.target_case_id is not None:
        target_case_id = str(body.target_case_id)
    case = await sop_draft_service.adopt_draft(
        tenant_id=user.tenant_id,
        draft_id=id,
        target_case_id=target_case_id,
        approver_id=user.user_id,
    )
    payload = {"data": CaseEntry(**case).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
