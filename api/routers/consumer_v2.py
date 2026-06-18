"""M16 Consumer v2 router — 消費者匿名工單追蹤端點（CR-0002-α / spec-alignment P2-α）。

對齊 frozen spec §2.2 M16 Consumer Tracking：
    GET /consumer/work-orders/{trackingToken}
        → getConsumerWorkOrderV2 (operationId)
        → 回 ConsumerWOView（FR-0022）

## 設計決策

1. **無 tenant-scope、無 require_tenant**：
   consumer 端點是公開 token-based 存取，不是 admin JWT flow。
   tenant_id 已封進 token payload（由 public_token.py verify_token 讀取）。

2. **沿用 legacy public router 的 token 驗證機制**：
   `_verify_or_404(token, "work_order_status")` — 和
   `routers/public.py::get_work_order_public_status` 完全對齊，
   purpose check 一致，任何 token 失效/過期/用途不符一律 404，不洩露原因。

3. **零重寫 service 層**：
   呼 `work_order_service.get_public_status(work_order_id=payload.subject_id)` —
   與 legacy handler 同一函式，不重寫 SQL。

4. **回應格式對齊 ConsumerWOView schema**：
   - `work_order_state`（spec 欄位名，對應 legacy 的 `status`）
   - `eta_minutes`（None 時省略）
   - `technician_display_name`（mask 後的技師名，遮至「李師傅」）
   - `last_update_at`（從 scheduled_at 或 completed_at 推算）

舊路徑 `GET /api/v1/public/work-orders/{token}/status`（routers/public.py）不動，
由 DeprecationMiddleware 自動加 Deprecation header（D3 雙掛過渡）。
前端遷移到此路徑後，P3 波次再退場 legacy。

## Token 驗證流（同 public.py）

  1. verify_token(token) → 失敗 / 過期 / 撤銷 → 404
  2. payload.purpose != "work_order_status" → 404（防 cross-use）
  3. work_order_service.get_public_status → 查 DB

PII 遮罩在 router 層呼叫（technician_name → mask_technician_name）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Request, Response

from core.errors import ApiError
from services.public_token import (
    TokenExpiredError,
    TokenInvalidError,
    mask_technician_name,
    token_hash_for_audit,
    verify_token,
)

logger = logging.getLogger("api.consumer_v2")

router = APIRouter()


def _verify_consumer_token(token: str):
    """驗證 consumer tracking token；失敗一律 404，不洩露原因。"""
    try:
        payload = verify_token(token)
    except (TokenInvalidError, TokenExpiredError) as exc:
        logger.info("consumer_v2 token verify failed: %s", exc)
        raise ApiError("NOT_FOUND", "token invalid or expired", 404)

    if payload.purpose != "work_order_status":
        logger.info(
            "consumer_v2 token purpose mismatch: got=%s expected=work_order_status",
            payload.purpose,
        )
        raise ApiError("NOT_FOUND", "token purpose mismatch", 404)
    return payload


@router.get(
    "/consumer/work-orders/{trackingToken}",
    operation_id="getConsumerWorkOrderV2",
    summary="消費者匿名工單追蹤（M16 / FR-0022）",
    tags=["M16 Consumer"],
)
async def get_consumer_work_order(
    trackingToken: str = Path(..., min_length=32, max_length=512),
) -> dict:
    """消費者匿名工單狀態查詢 v2（CR-0002-α，spec path: /consumer/work-orders/{trackingToken}）。

    不需 JWT / X-Tenant-ID — token 本身攜帶 tenant_id + subject_id。
    回應格式對齊 spec ConsumerWOView schema。
    """
    from services import work_order_service

    payload = _verify_consumer_token(trackingToken)

    record = await work_order_service.get_public_status(
        work_order_id=payload.subject_id
    )
    if record is None:
        raise ApiError("NOT_FOUND", "work order not found", 404)

    # 決定 last_update_at：已完工用 completed_at，否則用 scheduled_at，再 fallback 空字串
    last_update_at = record.get("completed_at") or record.get("scheduled_at") or ""

    return {
        "work_order_state": record["public_status"],
        "eta_minutes": None,  # ETA 由即時追蹤系統提供（本階段留 None）
        "technician_display_name": mask_technician_name(record["technician_name"]),
        "last_update_at": last_update_at,
    }


@router.get(
    "/consumer/work-orders/{trackingToken}/document",
    operation_id="getConsumerWorkOrderDocumentV2",
    summary="消費者匿名下載電子工單 PDF（M16 / CR-0027；只露最終價 + 關防）",
    tags=["M16 Consumer"],
)
async def get_consumer_work_order_document(
    trackingToken: str = Path(..., min_length=32, max_length=512),
) -> Response:
    """消費者用同一 tracking token 下載電子工單 PDF（決議 4：客戶只看最終價）。

    公開 token-based，無 JWT；tenant_id + work_order_id 封在 token。
    PDF 由 work_order_document_service 產（結構上不含成本 unit_price）。
    """
    from services import work_order_document_service

    payload = _verify_consumer_token(trackingToken)
    if not payload.tenant_id:
        raise ApiError("NOT_FOUND", "token missing tenant scope", 404)
    pdf = await work_order_document_service.render_document(
        tenant_id=payload.tenant_id, work_order_id=payload.subject_id,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="work-order.pdf"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scope-change proposal 消費者匿名查 / 回覆 v2（Q9=B）
#   遷自 routers/public.py 的 GET/POST /api/v1/public/scope-changes/{token}
#   無 tenant-scope（公開 token-based）；purpose=scope_change
# ─────────────────────────────────────────────────────────────────────────────


def _verify_scope_change_token(token: str):
    """驗 scope_change 用途 token；失敗一律 404 不洩露原因。"""
    try:
        payload = verify_token(token)
    except (TokenInvalidError, TokenExpiredError) as exc:
        logger.info("scope_change token verify failed: %s", exc)
        raise ApiError("NOT_FOUND", "token invalid or expired", 404)

    if payload.purpose != "scope_change":
        logger.info(
            "scope_change token purpose mismatch: got=%s expected=scope_change",
            payload.purpose,
        )
        raise ApiError("NOT_FOUND", "token purpose mismatch", 404)
    return payload


@router.get(
    "/consumer/scope-changes/{token}",
    operation_id="getScopeChangeProposalV2",
    summary="消費者匿名取得 Scope Change 提案 v2（Q9=B）",
    tags=["M16 Consumer"],
)
async def get_scope_change_proposal_v2(
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    from services import scope_change_service

    payload = _verify_scope_change_token(token)

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
    "/consumer/scope-changes/{token}",
    operation_id="respondScopeChangeV2",
    summary="消費者匿名回覆 Scope Change 提案 v2（Q9=B 同意/拒絕）",
    tags=["M16 Consumer"],
)
async def respond_scope_change_v2(
    body: dict,
    request: Request,
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    from services import scope_change_service

    payload = _verify_scope_change_token(token)

    decision = (body or {}).get("decision")
    comment = (body or {}).get("comment")
    if decision not in {"accept", "reject"}:
        raise ApiError(
            "VALIDATION_ERROR",
            "decision must be 'accept' or 'reject'",
            422,
        )

    client_ip = request.client.host if request.client else None
    return await scope_change_service.respond_public(
        proposal_id=payload.subject_id,
        decision=decision,
        comment=comment,
        token_hash=token_hash_for_audit(token),
        ip_address=client_ip,
    )


# ============================================================
# CR-0013 Stage 2 — LINE Binding endpoints (HD-03=b 主動綁定)
# ============================================================

@router.post(
    "/consumer/bindings:generate-token",
    operation_id="generateLineBindingTokenV2",
    summary="產 24h TTL 一次性 LINE binding link token（需 JWT）",
    tags=["M16 Consumer"],
)
async def generate_line_binding_token(
    user: "object" = Depends(__import__("core.deps", fromlist=["require_tenant"]).require_tenant),
) -> dict:
    """主動 binding 流程 step 1：客戶登入 web/track 後按「綁定」鈕。

    回傳 token 給客戶端 → 跳 LIFF 或 LINE 內瀏覽器顯示綁定 form，
    收 line_user_id 後呼 `:consume`。

    需要 JWT；user_id + tenant_id 從 token claims 取。
    """
    from services import line_binding_service

    tenant_id = getattr(user, "tenant_id", None)
    user_id = getattr(user, "user_id", None) or getattr(user, "sub", None)
    if not tenant_id or not user_id:
        raise ApiError("VALIDATION_ERROR", "tenant_id/user_id missing in token", 422)
    return await line_binding_service.generate_link_token(
        tenant_id=tenant_id, user_id=user_id,
    )


@router.post(
    "/consumer/bindings:consume",
    operation_id="consumeLineBindingTokenV2",
    summary="LINE LIFF 端 form 提交 token + line_user_id 完成綁定",
    tags=["M16 Consumer"],
)
async def consume_line_binding_token(body: dict) -> dict:
    """主動 binding 流程 step 2 — 完成綁定。

    body 必填:
      - token: 24h TTL one-time
      - line_user_id: 從 LIFF SDK getProfile() 取得

    Errors:
      - 404 token 不存在
      - 410 token 過期或已消費
      - 409 line_user_id 已綁別 user
    """
    from services import line_binding_service

    token = (body or {}).get("token")
    line_uid = (body or {}).get("line_user_id")
    if not token or not line_uid:
        raise ApiError(
            "VALIDATION_ERROR",
            "token + line_user_id required",
            422,
        )
    return await line_binding_service.consume_link_token(
        token=token, line_user_id=line_uid,
    )
