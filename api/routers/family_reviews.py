"""Family Reviews router — 家族覆核 endpoints。

operationId 對齊 openapi.yaml：
  - listPendingFamilyReviews  GET  /family-reviews/pending
  - listFamilyReviews         GET  /family-reviews
  - createFamilyReview        POST /family-reviews
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    FamilyReview,
    FamilyReviewCreateRequest,
    FamilyReviewPage,
    FamilyReviewPendingResponse,
)
from services import family_review_service

router = APIRouter()


@router.get(
    "/family-reviews/pending",
    operation_id="listPendingFamilyReviews",
    summary="待家族覆核的 SOP 清單",
    response_model=FamilyReviewPendingResponse,
)
async def list_pending(
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    items = await family_review_service.list_pending(tenant_id=user.tenant_id)
    return {"data": items}


@router.get(
    "/family-reviews",
    operation_id="listFamilyReviews",
    summary="家族覆核歷史（cursor 分頁，可 action filter）",
    response_model=FamilyReviewPage,
)
async def list_history(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await family_review_service.list_history(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        action=action,
    )
    return {
        "items": [FamilyReview(**r).model_dump(mode="json") for r in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.post(
    "/family-reviews",
    operation_id="createFamilyReview",
    summary="提交家族覆核結果",
    response_model=FamilyReview,
    status_code=201,
)
async def create_family_review(
    body: FamilyReviewCreateRequest,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    review = await family_review_service.create_review(
        tenant_id=user.tenant_id,
        sop_draft_id=str(body.sop_draft_id),
        action=body.action.value,
        comment=body.comment,
        reviewer_id=user.user_id,
    )
    payload = FamilyReview(**review).model_dump(mode="json")
    if idem is not None:
        await idem.save(201, payload)
    return payload
