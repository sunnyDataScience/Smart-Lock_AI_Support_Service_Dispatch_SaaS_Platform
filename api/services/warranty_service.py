"""Warranty Claims 業務邏輯。

範圍：listWarrantyClaims（cursor + limit + status + customer_id + work_order_id）、
      getWarrantyClaim、submitWarrantyDecision（filed | in_progress → approved /
      rejected / in_progress 三選一）。
不含：createWarrantyClaim / submitEvidence 等其他寫入路徑。

OpenAPI WarrantyClaim schema：
    id, customer_id, device_brand, device_model, warranty_start_date,
    warranty_end_date, claim_date, is_within_warranty, status, created_at,
    updated_at; work_order_id?, purchase_date?, dispute_reason?,
    verification_source?, resolution?, discount_offered?

DB ↔ API 對齊：
  - status (varchar(50))   → API WarrantyClaimStatus 5 enum，
        非預期值 fallback 為 'filed'（避免破壞 enum 約束）
  - discount_offered (FLOAT) → 2 位小數 decimal string；NULL → 不傳
  - 其他欄位 type 對齊，date / datetime 直通 isoformat

租戶隔離：warranty_claims.customer_id 直接 FK → users，
JOIN 1 層即可取 tenant_id 過濾（比 refund_requests 4 層 JOIN 簡單）。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.warranty_service")


_VALID_API_STATUS = {"filed", "approved", "rejected", "in_progress", "closed"}


def _coerce_status(raw: str | None) -> str:
    if raw and raw in _VALID_API_STATUS:
        return raw
    return "filed"


def _coerce_decimal(amount) -> str | None:
    if amount is None:
        return None
    return f"{float(amount):.2f}"


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    return {
        "id": str(row[0]),
        "work_order_id": str(row[1]) if row[1] else None,
        "customer_id": str(row[2]),
        "device_brand": row[3] or "",
        "device_model": row[4] or "",
        "purchase_date": row[5].isoformat() if row[5] else None,
        "warranty_start_date": row[6].isoformat() if row[6] else None,
        "warranty_end_date": row[7].isoformat() if row[7] else None,
        "claim_date": row[8].isoformat() if row[8] else None,
        "is_within_warranty": bool(row[9]),
        "status": _coerce_status(row[10]),
        "dispute_reason": row[11],
        "verification_source": row[12],
        "resolution": row[13],
        "discount_offered": _coerce_decimal(row[14]),
        "created_at": row[15].isoformat() if row[15] else None,
        "updated_at": row[16].isoformat() if row[16] else None,
        "document_number": row[17] if len(row) > 17 else None,
    }


_SELECT = (
    "w.id, w.work_order_id, w.customer_id, w.device_brand, w.device_model, "
    "w.purchase_date, w.warranty_start_date, w.warranty_end_date, w.claim_date, "
    "w.is_within_warranty, w.status, w.dispute_reason, w.verification_source, "
    "w.resolution, w.discount_offered, w.created_at, w.updated_at, w.document_number"
)

_TENANT_JOIN = (
    "FROM warranty_claims w "
    "JOIN users u ON w.customer_id = u.id"
)


async def list_warranty_claims(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None = None,
    customer_id: str | None = None,
    work_order_id: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["u.tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        if status not in _VALID_API_STATUS:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid status filter: {status}",
                422,
            )
        where.append("w.status = %s")
        args.append(status)

    if customer_id:
        where.append("w.customer_id = %s::uuid")
        args.append(customer_id)

    if work_order_id:
        where.append("w.work_order_id = %s::uuid")
        args.append(work_order_id)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(w.created_at, w.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY w.created_at DESC, w.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)

    cur = await db_module._conn.execute(sql, tuple(args))
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [_row_to_dict(r) for r in page_rows]

    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = encode_cursor({"ts": last[15].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_warranty_claim(*, tenant_id: str, claim_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT {_SELECT} {_TENANT_JOIN} "
        f"WHERE w.id = %s::uuid AND u.tenant_id = %s::uuid "
        f"LIMIT 1"
    )
    cur = await db_module._conn.execute(sql, (claim_id, tenant_id))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Warranty claim {claim_id} not found", 404)
    return _row_to_dict(row)


async def create_warranty_claim(
    *,
    tenant_id: str,
    customer_id: str,
    device_brand: str,
    device_model: str,
    claim_type: str,
    requested_by_role: str,
    work_order_id: str | None = None,
    purchase_date: str | None = None,
    dispute_reason: str | None = None,
) -> tuple[dict, bool]:
    """F-015 WarrantyClaim 建立（ADR-009 D pattern, dual-trigger）。

    Idempotency: business unique key (work_order_id, claim_type) — 同 WO 同
    類型若已有 active row（非 rejected/closed），回 200 既存。

    customer_id 必須屬於 tenant；warranty_start_date / warranty_end_date /
    is_within_warranty 在本實作預設用 90 天試算（後續可改抓 customer 購入紀錄）。

    Returns: (claim_dict, created_flag)
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. 驗證 customer 同 tenant
    cur = await db_module._conn.execute(
        "SELECT tenant_id FROM users WHERE id = %s::uuid",
        (customer_id,),
    )
    user_row = await cur.fetchone()
    if not user_row:
        raise ApiError("NOT_FOUND", "Customer not found", 404)
    if str(user_row[0]) != tenant_id:
        raise ApiError("NOT_FOUND", "Customer not found", 404)  # tenant 偽裝 404

    # 2. Idempotency check（僅當 work_order_id 提供時）
    if work_order_id:
        cur = await db_module._conn.execute(
            "SELECT id FROM warranty_claims "
            "WHERE work_order_id = %s::uuid AND claim_type = %s "
            "  AND status NOT IN ('rejected', 'closed') "
            "ORDER BY created_at ASC LIMIT 1",
            (work_order_id, claim_type),
        )
        existing = await cur.fetchone()
        if existing:
            claim = await get_warranty_claim(
                tenant_id=tenant_id, claim_id=str(existing[0]),
            )
            return claim, False

    # 3. 預設保固試算：用 purchase_date + 90 天，缺 purchase_date 則用 today + 90 天
    #    後續可改抓真實合約日期；此處保持 MVP 簡單預設。
    purchase_date_clause = "%s::date" if purchase_date else "CURRENT_DATE"
    purchase_date_arg = [purchase_date] if purchase_date else []

    # 4. INSERT + 自動 doc number
    cur = await db_module._conn.execute(
        f"INSERT INTO warranty_claims "
        f"  (work_order_id, customer_id, device_brand, device_model, "
        f"   purchase_date, warranty_start_date, warranty_end_date, "
        f"   claim_date, is_within_warranty, status, dispute_reason, "
        f"   claim_type, requested_by_role, document_number) "
        f"VALUES (%s, %s::uuid, %s, %s, "
        f"        {purchase_date_clause}, "
        f"        COALESCE({purchase_date_clause}, CURRENT_DATE), "
        f"        COALESCE({purchase_date_clause}, CURRENT_DATE) + INTERVAL '90 days', "
        f"        CURRENT_DATE, "
        f"        (COALESCE({purchase_date_clause}, CURRENT_DATE) + INTERVAL '90 days') >= CURRENT_DATE, "
        f"        'filed', %s, %s, %s, generate_doc_number('WC', 'doc_seq_wc')) "
        f"RETURNING id",
        (
            work_order_id, customer_id, device_brand, device_model,
            *purchase_date_arg, *purchase_date_arg, *purchase_date_arg,
            *purchase_date_arg,
            dispute_reason, claim_type, requested_by_role,
        ),
    )
    new_row = await cur.fetchone()
    if not new_row:
        raise ApiError("INTERNAL_ERROR", "Failed to insert warranty claim", 500)
    new_claim_id = str(new_row[0])

    claim = await get_warranty_claim(tenant_id=tenant_id, claim_id=new_claim_id)
    return claim, True


# 決策狀態機：只有 filed / in_progress 可下決策；approved / rejected / closed 為終局
_DECISION_FROM = {"filed", "in_progress"}
_DECISION_TO_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "start_review": "in_progress",
}


async def submit_decision(
    *,
    tenant_id: str,
    claim_id: str,
    decision: str,
    resolution: str | None,
    discount_offered: str | None,
) -> dict:
    """filed | in_progress → approved / rejected / in_progress。

    - approve / reject 必填 resolution（500 字內）作為審批意見稽核軌跡
    - approve 時可帶 discount_offered（保固外折讓金額，2 位小數字串）
    - start_review 將狀態推到 in_progress 由客服繼續調查；resolution 可選
    """
    if decision not in _DECISION_TO_STATUS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"decision must be one of {sorted(_DECISION_TO_STATUS)}",
            422,
        )

    resolution_clean: str | None = None
    if resolution and resolution.strip():
        resolution_clean = resolution.strip()[:500]

    if decision in ("approve", "reject") and not resolution_clean:
        raise ApiError(
            "VALIDATION_ERROR",
            "resolution is required for approve / reject decisions",
            422,
        )

    discount_value: float | None = None
    if discount_offered is not None and decision == "approve":
        try:
            discount_value = float(discount_offered)
        except ValueError as e:
            raise ApiError(
                "VALIDATION_ERROR",
                "discount_offered is not a valid decimal",
                422,
            ) from e

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT w.status {_TENANT_JOIN} "
        f"WHERE w.id = %s::uuid AND u.tenant_id = %s::uuid",
        (claim_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Warranty claim {claim_id} not found", 404)

    current = row[0]
    if current not in _DECISION_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot decide warranty claim in status '{current}'; expected one of {sorted(_DECISION_FROM)}",
            409,
        )

    new_status = _DECISION_TO_STATUS[decision]

    await db_module._conn.execute(
        "UPDATE warranty_claims SET "
        "  status = %s, "
        "  resolution = COALESCE(%s, resolution), "
        "  discount_offered = COALESCE(%s, discount_offered), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_status, resolution_clean, discount_value, claim_id),
    )
    return await get_warranty_claim(tenant_id=tenant_id, claim_id=claim_id)
