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

from fastapi import APIRouter, Path

from core.errors import ApiError
from services.public_token import (
    TokenExpiredError,
    TokenInvalidError,
    mask_technician_name,
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
