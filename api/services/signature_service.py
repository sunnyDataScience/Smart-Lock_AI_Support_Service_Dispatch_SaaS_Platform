"""WorkOrder 雙方電子簽章 — submitWorkOrderSignature。

operationId 對齊 openapi.yaml：submitWorkOrderSignature

設計：
  - 寫入 digital_signatures 兩列（customer / technician）
  - signer_id 取：
      customer   ← problem_cards.conversation.user_id（LINE 用戶於 users 表）
      technician ← work_orders.technician_id
  - 同 work_order 已存在雙方簽章 → 409 STATE_CONFLICT
  - work_order 未指派技師（technician_id IS NULL）→ 422 VALIDATION_ERROR
  - integrity_hash = sha256("{role}|{wo_id}|{signed_at}|{base64 前 100 字}")

簽章資料以 JSONB 存於 signature_data：
  {
    "data": "<base64>",     # 客戶端原始 base64 影像 / SVG path
    "gps_lat": <float>?,
    "gps_lng": <float>?,
    "signed_at": "<iso8601>"
  }
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.signature_service")


_SIGNATURE_METHOD = "image_base64"


def _hash_signature(role: str, wo_id: str, signed_at: str, data: str) -> str:
    """以 sha256 產整合校驗碼，避免同字串 race。"""
    digest_input = f"{role}|{wo_id}|{signed_at}|{data[:100]}".encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


# TI-M08-03：簽名擷取通道 fallback 鏈 —— LIFF 初始化失敗 → QR code → 紙本。
# fallback_method 記錄「這份簽名實際是怎麼取得的」，供結案稽核（紙本 fallback 須留痕）。
_VALID_FALLBACK_METHODS = {"liff", "qr", "paper"}


async def submit_work_order_signature(
    *,
    tenant_id: str,
    wo_id: str,
    customer_signature: str,
    technician_signature: str,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    signed_at: str | None = None,
    fallback_method: str = "liff",
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if not customer_signature or not customer_signature.strip():
        raise ApiError("VALIDATION_ERROR", "customer_signature is required", 422)
    if not technician_signature or not technician_signature.strip():
        raise ApiError("VALIDATION_ERROR", "technician_signature is required", 422)
    if fallback_method not in _VALID_FALLBACK_METHODS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"fallback_method must be one of {sorted(_VALID_FALLBACK_METHODS)}",
            422,
        )

    # 取 work_order + customer + technician 的 user_id（含 tenant guard）。
    # 注意：digital_signatures.signer_id FK→users.id，而 wo.technician_id FK→technicians.id，
    # 兩者不同主鍵；技師簽名的 signer 必須取 technicians.user_id（否則 FK violation）。
    cur = await db_module._conn.execute(
        "SELECT wo.id, wo.technician_id, c.user_id, t.user_id "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "LEFT JOIN technicians t ON wo.technician_id = t.id "
        "WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)

    wo_technician_id = row[1]
    customer_id = row[2]
    technician_user_id = row[3]  # technicians.user_id（簽名 signer 用此，非 technicians.id）

    if wo_technician_id is None:
        raise ApiError(
            "VALIDATION_ERROR",
            "Work order must be assigned to a technician before signature",
            422,
        )
    if technician_user_id is None:
        raise ApiError(
            "VALIDATION_ERROR",
            "Assigned technician has no linked user account; cannot sign",
            422,
        )
    technician_id = technician_user_id

    # 已存在雙方簽章 → 409
    cur = await db_module._conn.execute(
        "SELECT signer_role FROM digital_signatures "
        "WHERE document_type = 'work_order' AND document_id = %s::uuid",
        (wo_id,),
    )
    existing_roles = {r[0] for r in await cur.fetchall()}
    if {"customer", "technician"}.issubset(existing_roles):
        raise ApiError(
            "STATE_CONFLICT",
            "Work order already fully signed",
            409,
        )

    iso_signed_at = signed_at or datetime.now(timezone.utc).isoformat()

    rows_to_insert: list[tuple] = []
    if "customer" not in existing_roles:
        cust_data = {
            "data": customer_signature,
            "gps_lat": gps_lat,
            "gps_lng": gps_lng,
            "signed_at": iso_signed_at,
            "fallback_method": fallback_method,  # TI-M08-03 稽核留痕
        }
        rows_to_insert.append(
            (
                customer_id,
                "customer",
                "work_order",
                wo_id,
                _SIGNATURE_METHOD,
                json.dumps(cust_data),
                _hash_signature("customer", wo_id, iso_signed_at, customer_signature),
            )
        )
    if "technician" not in existing_roles:
        tech_data = {
            "data": technician_signature,
            "gps_lat": gps_lat,
            "gps_lng": gps_lng,
            "signed_at": iso_signed_at,
            "fallback_method": fallback_method,  # TI-M08-03 稽核留痕
        }
        rows_to_insert.append(
            (
                technician_id,
                "technician",
                "work_order",
                wo_id,
                _SIGNATURE_METHOD,
                json.dumps(tech_data),
                _hash_signature("technician", wo_id, iso_signed_at, technician_signature),
            )
        )

    for r in rows_to_insert:
        await db_module._conn.execute(
            "INSERT INTO digital_signatures "
            "  (signer_id, signer_role, document_type, document_id, "
            "   signature_method, signature_data, integrity_hash) "
            "VALUES (%s, %s, %s, %s::uuid, %s, %s::jsonb, %s)",
            r,
        )

    return {
        "success": True,
        "message": f"Work order signed by both parties ({len(rows_to_insert)} new row(s))",
        "request_id": None,
    }
