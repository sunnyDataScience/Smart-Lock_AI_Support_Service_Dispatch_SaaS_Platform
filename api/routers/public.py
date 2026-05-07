"""Public anonymous router — Q3=C / Q9=B 共用機制（SKELETON）。

operationId 對齊 openapi.yaml：
    getWorkOrderPublicStatus, getScopeChangeProposalPublic, respondScopeChangePublic

注意：本 router 透過 `security: []` 在 OpenAPI 上聲明免登入；
實際 FastAPI 層級的 auth middleware 也應略過 `/api/v1/public/*` 前綴
（後續若加 global auth dependency，請以 `dependencies=[]` 或 path 排除清單避開）。

## Q3=C/Q9=B Implementation TODO

  1. 實作 token 驗證流：呼叫 `services.public_token.verify_token` →
     依 `purpose` 分流到對應 handler；不符 purpose 一律 404
  2. 引入 rate limit middleware（per-token + per-IP，60 req/min）
  3. 實作真實 service 函式：
       - work_order_service.get_public_status(work_order_id)
       - scope_change_service.get_proposal_public(proposal_id)
       - scope_change_service.respond_public(proposal_id, decision, comment)
  4. 完工 90 天封存：work_order_service 應檢查 completed_at + 90d → raise GoneError
  5. Audit log：寫 token_hash + IP + UA，**禁止**寫完整 token / 客戶 PII
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Path

from services.public_token import (
    TokenExpiredError,
    TokenInvalidError,
    mask_phone,
    mask_technician_name,
    verify_token,
)

router = APIRouter()


def _token_path() -> Path:
    """共用 path param 定義（避開 mutable default 警告）。"""
    return Path(min_length=32, max_length=512, description="HMAC 簽章後的 token")


@router.get(
    "/public/work-orders/{token}/status",
    operation_id="getWorkOrderPublicStatus",
    summary="消費者匿名查工單狀態（Q3=C）",
    tags=["public"],
)
async def get_work_order_public_status(
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    """匿名工單狀態查詢（Q3=C）— 從 PR #40 stub 升級為真實查詢。

    TODO（user 後續處理）：
      - services.public_token.verify_token 仍為 stub，未做真實 HMAC 簽章
      - rate limit / audit log（per-token + per-IP）尚未實作
    """
    from core.errors import ApiError
    from services import work_order_service

    try:
        payload = verify_token(token)
    except TokenInvalidError:
        raise ApiError("NOT_FOUND", "token invalid or expired", 404)
    except TokenExpiredError:
        raise ApiError("NOT_FOUND", "token expired", 404)

    # purpose 不符 → 一律 404，避免 token 跨 endpoint 重用
    if payload.purpose != "work_order_status":
        raise ApiError("NOT_FOUND", "token purpose mismatch", 404)

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
    """SKELETON — 回 placeholder 提案。

    TODO Q3=C/Q9=B impl:
      - verify_token → purpose 必須是 "scope_change"
      - scope_change_service.get_proposal_public(proposal_id)
      - status != pending → 仍回 200 但帶當前狀態（前端決定顯示）
      - expires_at < now → 410 Gone
    """
    try:
        payload = verify_token(token)
    except (TokenInvalidError, TokenExpiredError):
        from core.errors import ApiError
        raise ApiError("NOT_FOUND", "token invalid or expired", 404)

    # TODO Q3=C/Q9=B impl: 從 DB 取真實提案
    return {
        "proposal_id": payload.subject_id,
        "work_order_id": "00000000-0000-0000-0000-000000000000",
        "status": "pending",
        "reason": "現場拆解後發現鎖芯內部彈簧老化，建議一併更換以避免短期再損壞。",
        "items": [
            {
                "name": "鎖芯總成更換",
                "description": "原廠同型號替換",
                "quantity": 1,
                "amount_delta": 1800.0,
            },
        ],
        "total_delta": 1800.0,
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
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    """SKELETON — 接受 accept/reject 並回 placeholder 結果。

    TODO Q3=C/Q9=B impl:
      - 改用 Pydantic model（PublicScopeChangeResponse）
      - verify_token → 比對 purpose
      - 雙重檢查 status: pending → 寫入 decision；其他狀態 → 409
      - 寫 audit log：proposal_id, decision, token_hash, IP, UA
      - 觸發 webhook：通知技師 / 後台
    """
    try:
        payload = verify_token(token)
    except (TokenInvalidError, TokenExpiredError):
        from core.errors import ApiError
        raise ApiError("NOT_FOUND", "token invalid or expired", 404)

    decision = (body or {}).get("decision")
    if decision not in {"accept", "reject"}:
        from core.errors import ApiError
        raise ApiError("VALIDATION_ERROR", "decision must be 'accept' or 'reject'", 422)

    # TODO Q3=C/Q9=B impl: 寫入 DB + audit + 推播
    return {
        "proposal_id": payload.subject_id,
        "decision": decision,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "next_step": (
            "技師將於 5 分鐘內收到通知並繼續施工。" if decision == "accept"
            else "我們已通知技師，請等待後續聯絡。"
        ),
    }
