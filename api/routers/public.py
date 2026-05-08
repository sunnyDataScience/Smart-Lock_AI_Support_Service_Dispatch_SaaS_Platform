"""Public anonymous router — Q3=C / Q9=B 共用機制。

operationId 對齊 openapi.yaml：
    getWorkOrderPublicStatus, getScopeChangeProposalPublic, respondScopeChangePublic

注意：本 router 透過 ``security: []`` 在 OpenAPI 上聲明免登入；
實際 FastAPI 層級的 auth middleware 也應略過 ``/api/v1/public/*`` 前綴。

## Token 驗證流

每個 handler 開頭都會：
  1. 呼叫 ``verify_token(token)`` → 失敗 / 過期 / 撤銷 → 404
  2. 比對 ``payload.purpose`` 與 endpoint 預期 → 不符 → 404（防 cross-use）
  3. 進入 service 層查資料

PII 遮罩 + audit log 在 router 層調用。

## TODO

  - rate limit middleware（per-token + per-IP，60 req/min）尚未實作
  - audit log（token_hash + IP + UA）尚未連線到中央 audit pipeline
  - 完工 90 天封存：work_order_service 已實作；scope_change 過期由 token TTL 守護
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Path, Request

from core.errors import ApiError
from services.public_token import (
    TokenExpiredError,
    TokenInvalidError,
    mask_phone,
    mask_technician_name,
    token_hash_for_audit,
    verify_token,
)

logger = logging.getLogger("api.public")

router = APIRouter()


def _verify_or_404(token: str, expected_purpose: str):
    """共用 token 驗證 + purpose 檢查；任何失敗一律 404 不洩露原因。"""
    try:
        payload = verify_token(token)
    except (TokenInvalidError, TokenExpiredError) as exc:
        logger.info("public token verify failed: %s", exc)
        raise ApiError("NOT_FOUND", "token invalid or expired", 404)

    if payload.purpose != expected_purpose:
        logger.info(
            "public token purpose mismatch: got=%s expected=%s",
            payload.purpose,
            expected_purpose,
        )
        raise ApiError("NOT_FOUND", "token purpose mismatch", 404)
    return payload


@router.get(
    "/public/work-orders/{token}/status",
    operation_id="getWorkOrderPublicStatus",
    summary="消費者匿名查工單狀態（Q3=C）",
    tags=["public"],
)
async def get_work_order_public_status(
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    """匿名工單狀態查詢（Q3=C）。"""
    from services import work_order_service

    payload = _verify_or_404(token, "work_order_status")

    record = await work_order_service.get_public_status(
        work_order_id=payload.subject_id
    )
    if record is None:
        raise ApiError("NOT_FOUND", "work order not found", 404)

    return {
        "work_order_id": record["work_order_id"],
        "status": record["public_status"],
        "scheduled_at": record["scheduled_at"],
        "completed_at": record["completed_at"],
        "technician_name": mask_technician_name(record["technician_name"]),
        "technician_phone_masked": mask_phone(record["technician_phone"]),
        "eta_minutes": None,
        "tracking_url": None,
    }


@router.get(
    "/public/scope-changes/{token}",
    operation_id="getScopeChangeProposalPublic",
    summary="消費者匿名取得 Scope Change 提案（Q9=B）",
    tags=["public"],
)
async def get_scope_change_proposal_public(
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    """取得 scope_change 提案明細給消費者瀏覽。"""
    from services import scope_change_service

    payload = _verify_or_404(token, "scope_change")

    proposal = await scope_change_service.get_proposal_public(
        proposal_id=payload.subject_id
    )
    if proposal is None:
        raise ApiError("NOT_FOUND", "scope change proposal not found", 404)

    return {
        "proposal_id": proposal["proposal_id"],
        "work_order_id": proposal["work_order_id"],
        "status": proposal["status"],
        "reason": proposal["reason"],
        "items": proposal["items"],
        "total_delta": proposal["total_delta"],
        "expires_at": payload.expires_at.isoformat(),
    }


@router.post(
    "/public/scope-changes/{token}",
    operation_id="respondScopeChangePublic",
    summary="消費者匿名回覆 Scope Change 提案（Q9=B 同意/拒絕）",
    tags=["public"],
)
async def respond_scope_change_public(
    body: dict,
    request: Request,
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    """收到消費者 accept/reject 後寫入 DB 並觸發後續流程。"""
    from services import scope_change_service

    payload = _verify_or_404(token, "scope_change")

    decision = (body or {}).get("decision")
    comment = (body or {}).get("comment")
    if decision not in {"accept", "reject"}:
        raise ApiError(
            "VALIDATION_ERROR",
            "decision must be 'accept' or 'reject'",
            422,
        )

    client_ip = request.client.host if request.client else None
    result = await scope_change_service.respond_public(
        proposal_id=payload.subject_id,
        decision=decision,
        comment=comment,
        token_hash=token_hash_for_audit(token),
        ip_address=client_ip,
    )
    return result
