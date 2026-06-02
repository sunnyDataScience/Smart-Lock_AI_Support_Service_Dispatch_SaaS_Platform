"""Pricing Rules v2 業務邏輯（Track B S4 / CR-0004 §8 C3 / ADR-0046）。

範圍：
  - list_pricing_rules_v2（cursor + limit + brand + lock_type + is_active）
  - get_pricing_rule_v2（單筆，404 NOT_FOUND）
  - create_pricing_rule_v2（INSERT saas.price_rule + 並寫 saas.change_request）
  - update_pricing_rule_v2（UPDATE saas.price_rule + 並寫 saas.change_request）

設計決策（CR-0004 §8 C3）：
  - 每次 pricing mutation 並寫 saas.change_request（type_code='pricing_rule'）
    → governance 審計軌跡（ADR-0046）。
  - change_request.state 對 POST/PUT 寫 'effective'（路徑 C 短期直生效）。
  - change_request.created_by 為 plain uuid（actor from X-Initiator header），無 FK。
  - Phase II：pricing 納入 M18 staged rollout（待 config_m18 收斂）。
  - approval workflow 屬 Phase II M18，本波次省略 change_request_approval。
  - calculate v2（pricing_v2.py）已存在，本模組不動 calculate 邏輯。
  - 不動 legacy pricing_rule_service / public.price_rules / pricing_rules.py router。

HD-4 follow-up：
  calculate v2 入參格式 spec pc_id/contract vs code brand/lock_type domain model 分歧，
  屬 calculate 範疇，標 follow-up CR，非本波次任務。

decimal 規範：
  - API 輸入接受 decimal string 或 number，均轉為 float 後 INSERT/UPDATE numeric(12,2)。
  - API 輸出回傳 2 位小數字串（'1200.00'）。
  - _validate_decimal_str / _coerce_decimal 仿 legacy pricing_rule_service 風格。

surcharges / modifiers 正規化：
  - API 輸入 surcharges（PricingSurcharge[]）→ DB modifiers jsonb（list of dicts）。
  - API 輸出 modifiers jsonb → surcharges（PricingSurcharge[]）。
  - 邏輯複用 / 仿 legacy _normalize_surcharges / _normalize_surcharges_input。
"""

from __future__ import annotations

import json
import logging
import uuid

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.pricing_rule_v2_service")

# ─────────────────────────────────────────────────────────────────────────────
# Decimal helpers（仿 legacy pricing_rule_service）
# ─────────────────────────────────────────────────────────────────────────────


def _coerce_decimal(amount) -> str:
    """DB value → 2 位小數字串（API 輸出）。"""
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


def _validate_decimal_str(value, field: str) -> float:
    """API 輸入 decimal string 或 number → float，過程中驗證格式。"""
    if value is None:
        raise ApiError("VALIDATION_ERROR", f"{field} is required", 422)
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ApiError(
            "VALIDATION_ERROR",
            f"{field} must be a decimal string or number (e.g. '1200.00')",
            422,
        )
    if f < 0:
        raise ApiError("VALIDATION_ERROR", f"{field} must be non-negative", 422)
    return f


# ─────────────────────────────────────────────────────────────────────────────
# Surcharges / modifiers 正規化（仿 legacy pricing_rule_service）
# ─────────────────────────────────────────────────────────────────────────────


def _normalize_surcharges_output(modifiers) -> list[dict]:
    """DB modifiers jsonb → API PricingSurcharge[] 輸出正規化。

    支援兩種 DB 格式：
      - list: [{"name": "...", "condition": "...", "amount": ...}, ...]
      - dict: {"夜間服務": {"condition": "...", "amount": ...}, ...}
    """
    if not modifiers:
        return []

    def _coerce_item(name: str, item) -> dict | None:
        if isinstance(item, dict):
            amount = item.get("amount")
            if amount is None:
                return None
            out: dict = {"name": name, "amount": _coerce_decimal(amount)}
            cond = item.get("condition")
            if cond:
                out["condition"] = str(cond)
            return out
        return None

    if isinstance(modifiers, list):
        out_list: list[dict] = []
        for entry in modifiers:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not name:
                continue
            mapped = _coerce_item(str(name), entry)
            if mapped:
                out_list.append(mapped)
        return out_list

    if isinstance(modifiers, dict):
        out_dict: list[dict] = []
        for name, entry in modifiers.items():
            mapped = _coerce_item(str(name), entry)
            if mapped:
                out_dict.append(mapped)
        return out_dict

    return []


def _normalize_surcharges_input(surcharges) -> list[dict]:
    """API PricingSurcharge[] 輸入 → DB modifiers jsonb（List[dict] 形式）。

    每筆需有 name + amount（decimal string 或 number）；condition 選填。
    """
    if surcharges is None:
        return []
    if not isinstance(surcharges, list):
        raise ApiError("VALIDATION_ERROR", "surcharges must be an array", 422)

    out: list[dict] = []
    for idx, item in enumerate(surcharges):
        if not isinstance(item, dict):
            raise ApiError(
                "VALIDATION_ERROR",
                f"surcharges[{idx}] must be an object",
                422,
            )
        name = item.get("name")
        amount = item.get("amount")
        if not name or not isinstance(name, str):
            raise ApiError(
                "VALIDATION_ERROR",
                f"surcharges[{idx}].name is required",
                422,
            )
        amt_f = _validate_decimal_str(amount, f"surcharges[{idx}].amount")
        entry: dict = {"name": name.strip()[:100], "amount": amt_f}
        cond = item.get("condition")
        if cond:
            entry["condition"] = str(cond).strip()[:200]
        out.append(entry)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Row → dict（saas.price_rule）
# ─────────────────────────────────────────────────────────────────────────────

_SELECT = (
    "id, tenant_id, brand, lock_type, difficulty, "
    "base_price, labor_cost, parts_cost, modifiers, "
    "is_active, created_at, updated_at"
)


def _row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _SELECT。"""
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "brand": row[2] or "",
        "lock_type": row[3] or "other",
        "difficulty": row[4],
        "base_price": _coerce_decimal(row[5]),
        "labor_cost": _coerce_decimal(row[6]),
        "parts_cost": _coerce_decimal(row[7]),
        "surcharges": _normalize_surcharges_output(row[8]),
        "is_active": bool(row[9]),
        "created_at": row[10].isoformat() if row[10] else None,
        "updated_at": row[11].isoformat() if row[11] else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Change request audit helper（ADR-0046）
# ─────────────────────────────────────────────────────────────────────────────


async def _write_change_request(
    *,
    tenant_id: str,
    payload_diff: dict,
    created_by: str,
    reason: str | None,
) -> str:
    """並寫一筆 saas.change_request（type_code='pricing_rule', state='effective'）。

    路徑 C 短期直生效：state='effective'（非 pending_approval / approved）。
    Phase II 收斂 M18 governance 後，state machine 會改走 approval workflow。

    created_by 對應 X-Initiator header（actor from auth），無 FK 強制。
    """
    cr_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO saas.change_request "
        "  (id, tenant_id, type_code, state, payload_diff, reason, created_by) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, %s::uuid)",
        (
            cr_id,
            tenant_id,
            "pricing_rule",
            "effective",
            json.dumps(payload_diff),
            reason,
            created_by,
        ),
    )
    return cr_id


# ─────────────────────────────────────────────────────────────────────────────
# list_pricing_rules_v2
# ─────────────────────────────────────────────────────────────────────────────


async def list_pricing_rules_v2(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    brand: str | None = None,
    lock_type: str | None = None,
    is_active: bool | None = None,
) -> dict:
    """cursor 分頁列出 saas.price_rule，tenant_id 直接過濾。

    預設只回傳 is_active=TRUE（未帶 is_active 參數時）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]

    # 預設過濾 is_active=TRUE；明確帶 False 才列出停用
    if is_active is None:
        where.append("is_active = TRUE")
    else:
        where.append("is_active = %s")
        args.append(is_active)

    if brand:
        where.append("LOWER(brand) = LOWER(%s)")
        args.append(brand)

    if lock_type:
        where.append("lock_type = %s")
        args.append(lock_type)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} FROM saas.price_rule "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY created_at DESC, id DESC "
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
        next_cursor = encode_cursor({"ts": last[10].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


# ─────────────────────────────────────────────────────────────────────────────
# get_pricing_rule_v2
# ─────────────────────────────────────────────────────────────────────────────


async def get_pricing_rule_v2(
    *,
    tenant_id: str,
    rule_id: str,
) -> dict:
    """取單筆 saas.price_rule；跨 tenant 或不存在 → 404 NOT_FOUND。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM saas.price_rule "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (rule_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Pricing rule {rule_id} not found", 404)
    return _row_to_dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# create_pricing_rule_v2
# ─────────────────────────────────────────────────────────────────────────────


async def create_pricing_rule_v2(
    *,
    tenant_id: str,
    brand: str,
    lock_type: str,
    difficulty: str | None = None,
    base_price,
    labor_cost=None,
    parts_cost=None,
    modifiers: list | None = None,
    reason: str | None = None,
    created_by: str,
) -> dict:
    """INSERT saas.price_rule + 並寫 saas.change_request（governance 審計）。

    created_by 對應 X-Initiator header（actor from auth）。
    change_request.payload_diff = {action:'create', after: rule}。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if not brand or not brand.strip():
        raise ApiError("VALIDATION_ERROR", "brand is required", 422)
    if not lock_type or not lock_type.strip():
        raise ApiError("VALIDATION_ERROR", "lock_type is required", 422)

    base_f = _validate_decimal_str(base_price, "base_price")
    labor_f = float(labor_cost) if labor_cost is not None else 0.0
    if labor_f < 0:
        raise ApiError("VALIDATION_ERROR", "labor_cost must be non-negative", 422)
    parts_f = float(parts_cost) if parts_cost is not None else 0.0
    if parts_f < 0:
        raise ApiError("VALIDATION_ERROR", "parts_cost must be non-negative", 422)

    modifiers_db = _normalize_surcharges_input(modifiers)

    cur = await db_module._conn.execute(
        f"INSERT INTO saas.price_rule "
        f"  (tenant_id, brand, lock_type, difficulty, base_price, "
        f"   labor_cost, parts_cost, modifiers, is_active) "
        f"VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb, TRUE) "
        f"RETURNING {_SELECT}",
        (
            tenant_id,
            brand.strip()[:200],
            lock_type.strip()[:200],
            difficulty,
            base_f,
            labor_f,
            parts_f,
            json.dumps(modifiers_db),
        ),
    )
    row = await cur.fetchone()
    rule = _row_to_dict(row)

    # 並寫 governance 審計軌跡
    await _write_change_request(
        tenant_id=tenant_id,
        payload_diff={"action": "create", "after": rule},
        created_by=created_by,
        reason=reason,
    )

    return rule


# ─────────────────────────────────────────────────────────────────────────────
# update_pricing_rule_v2
# ─────────────────────────────────────────────────────────────────────────────


async def update_pricing_rule_v2(
    *,
    tenant_id: str,
    rule_id: str,
    brand: str,
    lock_type: str,
    difficulty: str | None = None,
    base_price,
    labor_cost=None,
    parts_cost=None,
    modifiers: list | None = None,
    reason: str | None = None,
    created_by: str,
) -> dict:
    """全量 UPDATE saas.price_rule + 並寫 saas.change_request（governance 審計）。

    404 NOT_FOUND 若 rule_id 不屬於此 tenant。
    change_request.payload_diff = {action:'update', before: old_rule, after: new_rule}。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if not brand or not brand.strip():
        raise ApiError("VALIDATION_ERROR", "brand is required", 422)
    if not lock_type or not lock_type.strip():
        raise ApiError("VALIDATION_ERROR", "lock_type is required", 422)

    # 先讀舊資料（before snapshot for payload_diff）
    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM saas.price_rule "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (rule_id, tenant_id),
    )
    old_row = await cur.fetchone()
    if not old_row:
        raise ApiError("NOT_FOUND", f"Pricing rule {rule_id} not found", 404)
    old_rule = _row_to_dict(old_row)

    base_f = _validate_decimal_str(base_price, "base_price")
    labor_f = float(labor_cost) if labor_cost is not None else 0.0
    if labor_f < 0:
        raise ApiError("VALIDATION_ERROR", "labor_cost must be non-negative", 422)
    parts_f = float(parts_cost) if parts_cost is not None else 0.0
    if parts_f < 0:
        raise ApiError("VALIDATION_ERROR", "parts_cost must be non-negative", 422)

    modifiers_db = _normalize_surcharges_input(modifiers)

    cur = await db_module._conn.execute(
        f"UPDATE saas.price_rule SET "
        f"  brand = %s, lock_type = %s, difficulty = %s, "
        f"  base_price = %s, labor_cost = %s, parts_cost = %s, "
        f"  modifiers = %s::jsonb, updated_at = NOW() "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid "
        f"RETURNING {_SELECT}",
        (
            brand.strip()[:200],
            lock_type.strip()[:200],
            difficulty,
            base_f,
            labor_f,
            parts_f,
            json.dumps(modifiers_db),
            rule_id,
            tenant_id,
        ),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Pricing rule {rule_id} not found", 404)
    new_rule = _row_to_dict(row)

    # 並寫 governance 審計軌跡
    await _write_change_request(
        tenant_id=tenant_id,
        payload_diff={"action": "update", "before": old_rule, "after": new_rule},
        created_by=created_by,
        reason=reason,
    )

    return new_rule
