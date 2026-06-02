"""SOPs Review v2 router — flat-path 審核端點（CR-0003 P2-W3）。

對齊 frozen spec (openapi.yaml L754/761)：
  POST /sops/{id}/review/dual    → sopDualReview   (雙人初審 approve/reject)
  POST /sops/{id}/review/family  → sopFamilyReview (家族覆核 approved/rejected)

設計原則：
  - flat path（無 /tenants/{tenantId}）→ tenant 從 require_tenant header (X-Tenant-ID) 取得，
    不需 cross-tenant-path guard。
  - 呼既有 sop_draft_service.review_draft + family_review_service.create_review，
    零 SQL 重寫。
  - POST 皆掛 idempotency_guard（Idempotency-Key header）。
  - response_model 對齊 service 輸出型別：
      dual   → SopDraftEnvelope（data: SopDraft）
      family → FamilyReview（直接回 review 物件，201）
  - 425 Too Early：family review 在 dual 未完成時由 family_review_service.create_review
    內部拋 ApiError(CONFLICT, 409)；spec 425 對應「dual review not done」
    → 偵測 CONFLICT + "Only admin-approved" → 回 425。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Path
from fastapi.responses import JSONResponse

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import (
    Decision2,
    FamilyReview,
    FamilyReviewAction,
    FamilyReviewCreateRequest,
    SopDraft,
    SopDraftEnvelope,
    SopDraftReviewRequest,
)
from services import family_review_service, sop_draft_service

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /sops/{id}/review/dual — 雙人初審（CS supervisor + Domain Expert）
# ---------------------------------------------------------------------------


@router.post(
    "/sops/{id}/review/dual",
    operation_id="sopDualReview",
    summary="Dual review (CS supervisor + Domain Expert)",
    response_model=SopDraftEnvelope,
    tags=["SOP Review"],
)
async def sop_dual_review(
    body: SopDraftReviewRequest,
    id: str = Path(..., description="SOP draft UUID"),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """雙人初審 — approve / reject。

    呼叫 sop_draft_service.review_draft：
      - 只允許 pending_review → approved / rejected
      - 其他狀態 → 409 Conflict
    reviewer_id 從 JWT token 取得（user.user_id）。
    """
    decision = body.decision.value if hasattr(body.decision, "value") else str(body.decision)
    draft = await sop_draft_service.review_draft(
        tenant_id=user.tenant_id,
        draft_id=id,
        decision=decision,
        comment=body.comment,
        reviewer_id=user.user_id,
    )
    payload = {"data": SopDraft(**draft).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ---------------------------------------------------------------------------
# POST /sops/{id}/review/family — 家族覆核 100% gate（SLA 24h）
# ---------------------------------------------------------------------------


@router.post(
    "/sops/{id}/review/family",
    operation_id="sopFamilyReview",
    summary="Family Reviewer 100% gate (SLA 24h)",
    response_model=FamilyReview,
    status_code=200,
    tags=["SOP Review"],
    responses={
        "200": {"description": "approved or rejected"},
        "425": {"description": "too early - dual review not done"},
    },
)
async def sop_family_review(
    body: FamilyReviewCreateRequest,
    id: str = Path(..., description="SOP draft UUID"),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """家族覆核 — approved / rejected。

    呼叫 family_review_service.create_review：
      - sop_draft.status 必須是 'approved'（雙人初審已通過）
      - 未完成初審 → family_review_service 拋 ApiError(CONFLICT, 409)；
        此處攔截並轉為 spec 要求的 425 Too Early。
      - 重複覆核（DB uniq） → 409 Conflict（不重新映射，讓全局 error handler 處理）

    body.sop_draft_id 必須等於 path id，避免 path/body 不一致。
    """
    # path / body sop_draft_id 一致性檢查
    body_draft_id = str(body.sop_draft_id)
    if body_draft_id != id:
        raise ApiError(
            "VALIDATION_ERROR",
            f"Path id '{id}' does not match body sop_draft_id '{body_draft_id}'",
            422,
        )

    action = body.action.value if hasattr(body.action, "value") else str(body.action)

    try:
        review = await family_review_service.create_review(
            tenant_id=user.tenant_id,
            sop_draft_id=id,
            action=action,
            comment=body.comment,
            reviewer_id=user.user_id,
        )
    except ApiError as exc:
        # 將「雙人初審未完成」的 409 CONFLICT 映射為 spec 要求的 425 Too Early
        if exc.status_code == 409 and "Only admin-approved" in str(exc.message):
            raise ApiError(
                "TOO_EARLY",
                "Dual review (admin approval) has not been completed for this SOP draft",
                425,
            )
        raise

    payload = FamilyReview(**review).model_dump(mode="json")
    if idem is not None:
        await idem.save(200, payload)
    return payload
