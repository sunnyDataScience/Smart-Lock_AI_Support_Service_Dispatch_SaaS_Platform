"""SOP Drafts router — read + 寫入路徑（create / review / adopt）。

operationId 對齊 openapi.yaml：
  listSopDrafts, getSopDraft, createSopDraft, reviewSopDraft, adoptSopDraft

createSopDraft 5/9 17:00 補（ADR-009 §8 D2 自進化機制）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response

from core.deps import BACKOFFICE_ROLES, CurrentUser, REVIEW_ROLES, require_tenant, role_required
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    CaseEntry,
    CaseEntryEnvelope,
    SopDraft,
    SopDraftAdoptRequest,
    SopDraftCreateRequest,
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


@router.post(
    "/sop-drafts",
    operation_id="createSopDraft",
    summary="建立 SOP 草稿（F-017 自進化；agent 異步觸發）",
    response_model=SopDraftEnvelope,
)
async def create_sop_draft(
    body: SopDraftCreateRequest,
    response: Response,
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    source_type = (
        body.source_type.value
        if hasattr(body.source_type, "value")
        else str(body.source_type)
    )
    draft, created = await sop_draft_service.create_draft(
        tenant_id=user.tenant_id,
        source_case_id=str(body.source_case_id),
        source_type=source_type,
        draft_content=body.draft_content,
        model_version=body.model_version,
        confidence_score=body.confidence_score,
    )
    response.status_code = 201 if created else 200
    payload = {"data": SopDraft(**draft).model_dump(mode="json")}
    if idem is not None:
        await idem.save(response.status_code, payload)
    return payload


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
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
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
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
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
