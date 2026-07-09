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

from typing import Any

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import JSONResponse

from core.deps import BACKOFFICE_ROLES, CurrentUser, REVIEW_ROLES, require_tenant, role_required
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
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
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
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
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


# ─────────────────────────────────────────────────────────────────────────────
# CR-0006 step 2/3：sop_drafts CRUD list/get/create/patch/delete
#   HD-01=(a) meta-wrap shape（與 KB 對齊；本實作走 _sop_to_kb_document helper）
#   HD-02=(a) DELETE 軟刪（sop_drafts.deleted_at）
#   HD-03=(a) audit log 共用 saas.kb_audit_log（doc_type='sop'）
# ─────────────────────────────────────────────────────────────────────────────


def _sop_to_kb_document(draft: dict) -> dict:
    """SOP draft row → KBDocument meta-wrap shape（HD-01 對齊 KB）。"""
    return {
        "id": draft.get("id"),
        "doc_type": "sop",
        "title": draft.get("title", ""),
        "tenant_scope": [],
        "brand_scope": [],
        "project_scope": [],
        "version": None,
        "effective_date": None,
        "meta": {
            "status": draft.get("status"),
            "steps": draft.get("steps", []),
            "source_problem_card_id": draft.get("source_problem_card_id"),
            "reviewer_id": draft.get("reviewer_id"),
            "review_note": draft.get("review_note"),
            "created_at": draft.get("created_at"),
            "updated_at": draft.get("updated_at"),
        },
    }


async def _write_sop_audit_log(
    *,
    tenant_id: str,
    doc_id: str,
    action: str,
    before_state: dict | None,
    after_state: dict | None,
    actor_user_id: str,
    actor_role: str,
) -> None:
    """寫 saas.kb_audit_log（doc_type='sop'，CR-0006 HD-03=a）；best-effort。"""
    try:
        import json as _json
        import core.db as db_module_a
        from core.db import _ensure_conn as _conn

        if not await _conn():
            return
        await db_module_a._conn.execute(
            "INSERT INTO saas.kb_audit_log "
            "  (tenant_id, doc_id, doc_type, action, "
            "   before_state, after_state, actor_user_id, actor_role) "
            "VALUES (%s::uuid, %s::uuid, 'sop', %s, "
            "        %s::jsonb, %s::jsonb, %s::uuid, %s)",
            (
                tenant_id,
                doc_id,
                action,
                _json.dumps(before_state, ensure_ascii=False) if before_state is not None else None,
                _json.dumps(after_state, ensure_ascii=False) if after_state is not None else None,
                actor_user_id,
                actor_role,
            ),
        )
    except Exception:
        import logging
        logging.getLogger("sops_v2.audit").warning(
            "sop audit_log write failed (non-fatal)", exc_info=True
        )


@router.get(
    "/tenants/{tenantId}/sops/drafts",
    operation_id="listSopDraftsV2",
    summary="SOP 草稿列表 v2（CR-0006 / tenant-scoped / 軟刪過濾 / meta-wrap）",
    tags=["SOP Drafts"],
)
async def list_sop_drafts_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="pending_review|approved|rejected|adopted"),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId mismatch", 403)
    page = await sop_draft_service.list_drafts(
        tenant_id=tenantId, cursor=cursor, limit=limit, status=status,
    )
    return {
        "items": [_sop_to_kb_document(d) for d in page.get("items", [])],
        "next_cursor": page.get("next_cursor"),
        "has_more": page.get("has_more", False),
        "total_count": page.get("total_count", 0),
    }


@router.get(
    "/tenants/{tenantId}/sops/drafts/{draftId}",
    operation_id="getSopDraftV2",
    summary="SOP 草稿詳情 v2",
    tags=["SOP Drafts"],
)
async def get_sop_draft_v2(
    tenantId: str = Path(...),
    draftId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId mismatch", 403)
    draft = await sop_draft_service.get_draft(tenant_id=tenantId, draft_id=draftId)
    return _sop_to_kb_document(draft)


@router.post(
    "/tenants/{tenantId}/sops/drafts",
    operation_id="createSopDraftV2",
    summary="建立 SOP 草稿 v2（agent 異步或人工手動建）",
    status_code=201,
    tags=["SOP Drafts"],
)
async def create_sop_draft_v2(
    body: dict[str, Any],
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId mismatch", 403)
    if not isinstance(body, dict):
        raise ApiError("VALIDATION_ERROR", "body must be a JSON object", 422)

    draft = await sop_draft_service.create_draft(
        tenant_id=tenantId,
        title=body.get("title", ""),
        steps=body.get("steps", []),
        source_problem_card_id=body.get("source_problem_card_id"),
    )
    await _write_sop_audit_log(
        tenant_id=tenantId,
        doc_id=str(draft.get("id")),
        action="create",
        before_state=None,
        after_state=draft,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    payload = _sop_to_kb_document(draft)
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.delete(
    "/tenants/{tenantId}/sops/drafts/{draftId}",
    operation_id="deleteSopDraftV2",
    summary="SOP 草稿軟刪 v2（CR-0006 HD-02=a）",
    status_code=204,
    tags=["SOP Drafts"],
)
async def delete_sop_draft_v2(
    tenantId: str = Path(...),
    draftId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
) -> None:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId mismatch", 403)

    # before snapshot for audit
    try:
        before = await sop_draft_service.get_draft(tenant_id=tenantId, draft_id=draftId)
    except ApiError:
        raise

    await sop_draft_service.soft_delete_draft(tenant_id=tenantId, draft_id=draftId)
    await _write_sop_audit_log(
        tenant_id=tenantId,
        doc_id=draftId,
        action="delete",
        before_state=before,
        after_state=None,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CR-0006 step 2/3：family-reviews list + pending
#   HD-04=(a) POST /sops/family-reviews 廢棄（不在此 router）
#   HD-05=(a) pending 即時查（每次計算）
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tenants/{tenantId}/sops/family-reviews",
    operation_id="listFamilyReviewsV2",
    summary="家族覆核歷史列表 v2（CR-0006）",
    tags=["SOP Family Review"],
)
async def list_family_reviews_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None, description="approved|rejected"),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId mismatch", 403)
    return await family_review_service.list_history(
        tenant_id=tenantId, cursor=cursor, limit=limit, action=action,
    )


@router.get(
    "/tenants/{tenantId}/sops/family-reviews:pending",
    operation_id="listFamilyReviewsPendingV2",
    summary="待家族覆核的 SOP（CR-0006 HD-05=a 即時查）",
    tags=["SOP Family Review"],
)
async def list_family_reviews_pending_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_READ", "Path tenantId mismatch", 403)
    items = await family_review_service.list_pending(tenant_id=tenantId)
    return {"items": items}


# ─────────────────────────────────────────────────────────────────────────────
# Adopt v2（採納 SOP 草稿 → 入庫成案例）
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/tenants/{tenantId}/sops/drafts/{draftId}/adopt",
    operation_id="adoptSopDraftV2",
    summary="採納 SOP 草稿 v2（核准後入庫成案例）",
    tags=["SOP Drafts"],
)
async def adopt_sop_draft_v2(
    tenantId: str = Path(...),
    draftId: str = Path(...),
    body: dict[str, Any] | None = None,
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError("CROSS_TENANT_WRITE", "Path tenantId mismatch", 403)

    target_case_id = None
    if body and isinstance(body.get("target_case_id"), str):
        target_case_id = body["target_case_id"]

    case = await sop_draft_service.adopt_draft(
        tenant_id=tenantId,
        draft_id=draftId,
        target_case_id=target_case_id,
        approver_id=user.user_id,
    )
    payload = {"data": case}
    if idem is not None:
        await idem.save(200, payload)
    return payload
