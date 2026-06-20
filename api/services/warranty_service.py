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

import calendar
import logging
from datetime import date, timedelta
from typing import Any

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.warranty_service")


_VALID_API_STATUS = {"filed", "approved", "rejected", "in_progress", "closed"}


# ─────────────────────────────────────────────────────────────────────────────
# Warranty 5-mode 起算（ADR-0044 v2 / FR-0015 / BR-WARRANTY-001..007）
# Default configurable plane — embed 到 system_config.warranty namespace。
# ─────────────────────────────────────────────────────────────────────────────

# warranty_start_mode 正典詞彙（ADR-0044 v2，非舊版 purchase/handover/activation）：
#   purchase_date        — B2C 零售用購買日
#   install_date         — 零售安裝完工日
#   handover_date        — 建商點交日（建商案件 default）
#   brand_warranty_date  — 品牌另計保固起算
#   contract_date        — B2B 合約起算
#   manual_override      — 缺資料時人工 + 主管核可
DEFAULT_WARRANTY_CONFIG: dict[str, Any] = {
    "version_note": "ADR-0044 v2 defaults (FR-0015 / BR-WARRANTY-001..007)",
    "default_period_months": 24,
    # B2B override 上限 5 年 = 60 個月（BR-WARRANTY-006）
    "b2b_override_max_months": 60,
    # 換新主鎖獨立保固 buffer（BR-WARRANTY-005）：完工日 + 原期 + 此天數
    "replaced_main_lock_buffer_days": 90,
    # 品牌特定保固期 override（月）。未命中 → default_period_months
    "brand_period_overrides": {
        "Yale": 36,
        "Dormakaba": 60,
    },
    # mode 預設規則（情境 → 預設 mode），供 router/編排層參考
    "mode_defaults": {
        "b2c_retail": "purchase_date",
        "retail_installed": "install_date",
        "developer_project": "handover_date",
        "b2b_contract": "contract_date",
    },
    "valid_start_modes": [
        "purchase_date",
        "install_date",
        "handover_date",
        "brand_warranty_date",
        "contract_date",
        "manual_override",
    ],
}

# mode → resolve_start_date 取用的 anchor 參數名（manual_override 不在此表）
_MODE_TO_ANCHOR: dict[str, str] = {
    "purchase_date": "purchase_date",
    "install_date": "install_date",
    "handover_date": "handover_date",
    "brand_warranty_date": "brand_warranty_date",
    "contract_date": "contract_date",
}


# ─────────────────────────────────────────────────────────────────────────────
# PURE 規則函式（無 DB — 單元測試覆蓋）
# ─────────────────────────────────────────────────────────────────────────────

def resolve_start_date(
    mode: str,
    *,
    purchase_date: date | None = None,
    install_date: date | None = None,
    handover_date: date | None = None,
    brand_warranty_date: date | None = None,
    contract_date: date | None = None,
) -> date:
    """依 warranty_start_mode 取對應錨點日期（ADR-0044 v2 / BR-WARRANTY-001/002/004）。

    - manual_override：不從錨點推算（需人工 + 主管核可，走 PATCH 流程）→ 422 引導。
    - 未知 mode → 422 WARRANTY_MODE_UNKNOWN。
    - mode 對應的錨點缺值 → 422 WARRANTY_ANCHOR_MISSING。
    """
    if mode == "manual_override":
        raise ApiError(
            "WARRANTY_ANCHOR_MISSING",
            "manual_override mode requires explicit start_date via supervisor-approved PATCH",
            422,
        )
    anchor_name = _MODE_TO_ANCHOR.get(mode)
    if anchor_name is None:
        raise ApiError(
            "WARRANTY_MODE_UNKNOWN",
            f"Unknown warranty_start_mode '{mode}'",
            422,
        )
    anchors = {
        "purchase_date": purchase_date,
        "install_date": install_date,
        "handover_date": handover_date,
        "brand_warranty_date": brand_warranty_date,
        "contract_date": contract_date,
    }
    value = anchors[anchor_name]
    if value is None:
        raise ApiError(
            "WARRANTY_ANCHOR_MISSING",
            f"warranty_start_mode '{mode}' requires anchor date '{anchor_name}'",
            422,
        )
    return value


def _add_months(d: date, months: int) -> date:
    """日曆月加法，遇月底自動 clamp（避免 day overflow，如 1/31 + 1m → 2/28）。"""
    total = (d.year * 12 + (d.month - 1)) + months
    year, month = divmod(total, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def compute_warranty_end(start_date: date, period_months: int) -> date:
    """保固到期日 = 起算日 + period_months（取代舊寫死 +90 days）。"""
    return _add_months(start_date, int(period_months))


def is_within_warranty(claim_date: date, end_date: date) -> bool:
    """保固邊界判定（BR-WARRANTY-003）：claim_date == end_date 仍視為在保固內。"""
    return claim_date <= end_date


def recalc_after_rma(
    end_date: date,
    *,
    rma_in: date,
    rma_out: date,
    replaced_main_lock: bool,
    rma_complete_date: date,
    period_months: int = 24,
    config: dict | None = None,
) -> date:
    """RMA 重算（BR-WARRANTY-005）。

    - 被修期間延長：end += (rma_out - rma_in) days。
    - 換新主鎖：從 RMA 完工日起算原期 (period_months) + buffer 天數獨立保固。
    """
    if replaced_main_lock:
        cfg = config or DEFAULT_WARRANTY_CONFIG
        buffer_days = int(cfg.get("replaced_main_lock_buffer_days", 90))
        fresh_end = compute_warranty_end(rma_complete_date, period_months)
        return fresh_end + timedelta(days=buffer_days)
    repair_days = (rma_out - rma_in).days
    return end_date + timedelta(days=repair_days)


def validate_b2b_override(months: int, config: dict | None = None) -> None:
    """B2B override 上限驗證（BR-WARRANTY-006）：1 ≤ months ≤ 60，否則 422。"""
    cfg = config or DEFAULT_WARRANTY_CONFIG
    cap = int(cfg.get("b2b_override_max_months", 60))
    if months <= 0:
        raise ApiError(
            "WARRANTY_OVERRIDE_INVALID",
            "warranty_period_months_override must be a positive integer",
            422,
        )
    if months > cap:
        raise ApiError(
            "WARRANTY_OVERRIDE_EXCEEDS_CAP",
            f"warranty_period_months_override {months} exceeds B2B cap {cap} months",
            422,
        )


def resolve_period_months(brand: str | None, config: dict | None = None) -> int:
    """依品牌取保固期（月）。品牌 override map 命中用 override，否則 default。"""
    cfg = config or DEFAULT_WARRANTY_CONFIG
    overrides = cfg.get("brand_period_overrides", {}) or {}
    if brand and brand in overrides:
        return int(overrides[brand])
    return int(cfg.get("default_period_months", 24))


def select_warranty_source(
    *,
    inherit_from_site_group: bool,
    site_group_mode: str | None,
    device_mode: str | None,
) -> str | None:
    """site_group 繼承選擇邏輯（BR-WARRANTY-005 / ADR-0044 §v2.5）。

    建商案件 inherit=True 且 site_group 有設 mode → 採 site_group mode；
    否則回 device 自身 mode。DB 來源接入見 TODO（本切片僅純函式）。
    """
    # TODO(P3): site_group_mode / device_mode 由 device_warranty + site_group 表載入
    if inherit_from_site_group and site_group_mode:
        return site_group_mode
    return device_mode


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

    customer_id 必須屬於 tenant。warranty_start_date / warranty_end_date /
    is_within_warranty 改用 5-mode 起算（ADR-0044 v2 / FR-0015）：
      - 只給 purchase_date 的舊呼叫 → purchase_date mode + default 24 months
      - 缺 purchase_date → 退回 install_date=today（建單日）作起算 best-effort
    取代舊寫死的 +90 days；is_within_warranty 採邊界=仍在保（BR-WARRANTY-003）。

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

    # 3. 5-mode 保固起算（ADR-0044 v2 / FR-0015）— 取代舊寫死 +90 days。
    #    舊呼叫只給 purchase_date → purchase_date mode；缺則用建單日（today）作起算。
    today = date.today()
    if purchase_date:
        purchase_d = date.fromisoformat(purchase_date)
        start_date = resolve_start_date("purchase_date", purchase_date=purchase_d)
        start_mode = "purchase_date"
    else:
        # 缺 purchase_date：以建單日作 best-effort 起算（install_date 語意）
        start_date = today
        purchase_d = None
        start_mode = "install_date"
    period_months = resolve_period_months(device_brand, DEFAULT_WARRANTY_CONFIG)
    end_date = compute_warranty_end(start_date, period_months)
    within = is_within_warranty(today, end_date)

    # 4. INSERT + 自動 doc number
    cur = await db_module._conn.execute(
        "INSERT INTO warranty_claims "
        "  (work_order_id, customer_id, device_brand, device_model, "
        "   purchase_date, warranty_start_date, warranty_end_date, "
        "   claim_date, is_within_warranty, status, dispute_reason, "
        "   claim_type, requested_by_role, document_number, "
        "   warranty_start_mode, warranty_period_months) "
        "VALUES (%s, %s::uuid, %s, %s, "
        "        %s::date, %s::date, %s::date, "
        "        CURRENT_DATE, %s, "
        "        'filed', %s, %s, %s, generate_doc_number('WC', 'doc_seq_wc'), "
        "        %s, %s) "
        "RETURNING id",
        (
            work_order_id, customer_id, device_brand, device_model,
            purchase_d.isoformat() if purchase_d else None,
            start_date.isoformat(), end_date.isoformat(),
            within,
            dispute_reason, claim_type, requested_by_role,
            start_mode, period_months,
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


async def check_rma_abuse(
    *, customer_id: str, device_brand: str | None = None, device_model: str | None = None,
    window_days: int = 30, threshold: int = 3,
) -> dict:
    """CR-0064 / TI-RMA-04 / BR-WARRANTY-003：同客戶同機種短期 RMA 頻次偵測。

    視窗內（預設 30 天）同 customer + device_brand/model 的 warranty_claims 數 ≥ threshold（預設 3）
    → abuse_flagged，供風控告警/人工複核。回 {count, threshold, abuse_flagged}。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT count(*) FROM warranty_claims "
        "WHERE customer_id = %s::uuid "
        "  AND (%s::text IS NULL OR device_brand = %s) "
        "  AND (%s::text IS NULL OR device_model = %s) "
        "  AND claim_date >= (CURRENT_DATE - make_interval(days => %s))",
        (customer_id, device_brand, device_brand, device_model, device_model, window_days),
    )
    cnt = int((await cur.fetchone())[0] or 0)
    return {"count": cnt, "threshold": threshold, "abuse_flagged": cnt >= threshold}
