"""Pricing Rules 業務邏輯。

範圍：
  - listPricingRules（cursor + limit + brand 篩選）
  - createPricingRule（POST，產生新計價規則）
  - updatePricingRule（PUT，修改 base_price / surcharges；其餘欄位 immutable）

不含：calculatePricing（依賴 LockType + difficulty 推算結果價格的線上引擎）。

OpenAPI PricingRule schema：
    id, brand, lock_type (LockType), difficulty (DifficultyLevel),
    base_price (decimal str), surcharges (PricingSurcharge[]), created_at, updated_at

DB ↔ API 對齊：
  - price_rules.brand / lock_type → 直通（seed 寫入時即用 OpenAPI enum 值，故無需 mapping）
  - price_rules.difficulty (easy/medium/hard) ↔ API enum (simple/moderate/complex)
  - price_rules.base_price (FLOAT) ↔ API base_price: decimal string with 2 decimals
  - price_rules.modifiers (JSONB array) ↔ API surcharges (PricingSurcharge[])
  - price_rules.is_active = FALSE → 過濾不回傳
  - price_rules.labor_cost (NOT NULL) → API 沒對應欄位，create 時預設 0.0；update 不動

租戶隔離：price_rules.tenant_id（Schema_api_phase1.sql 補上）。
"""

from __future__ import annotations

import json
import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.pricing_rule_service")


_DB_DIFFICULTY_TO_API = {
    "easy": "simple",
    "medium": "moderate",
    "hard": "complex",
}

_API_DIFFICULTY_TO_DB = {v: k for k, v in _DB_DIFFICULTY_TO_API.items()}

_VALID_LOCK_TYPES = {"digital_deadbolt", "smart_lock", "padlock", "other"}


def _coerce_decimal(amount) -> str:
    if amount is None:
        return "0.00"
    return f"{float(amount):.2f}"


def _normalize_surcharges(modifiers) -> list[dict]:
    """modifiers JSONB → list of PricingSurcharge dicts.

    支援兩種輸入格式：
      - list: [{"name": "...", "condition": "...", "amount": ...}, ...]
      - dict: {"夜間服務": {"condition": "...", "amount": ...}, ...}
    輸出統一為 PricingSurcharge schema：{name, condition?, amount}
    """
    if not modifiers:
        return []

    def _coerce_item(name: str, item) -> dict | None:
        if isinstance(item, dict):
            amount = item.get("amount")
            if amount is None:
                return None
            out = {"name": name, "amount": _coerce_decimal(amount)}
            cond = item.get("condition")
            if cond:
                out["condition"] = str(cond)
            return out
        return None

    if isinstance(modifiers, list):
        out: list[dict] = []
        for entry in modifiers:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not name:
                continue
            mapped = _coerce_item(str(name), entry)
            if mapped:
                out.append(mapped)
        return out

    if isinstance(modifiers, dict):
        out = []
        for name, entry in modifiers.items():
            mapped = _coerce_item(str(name), entry)
            if mapped:
                out.append(mapped)
        return out

    return []


def _row_to_dict(row: tuple) -> dict:
    """row 順序：
    id, brand, lock_type, difficulty, base_price, modifiers, created_at, updated_at
    """
    difficulty = row[3]
    api_difficulty = _DB_DIFFICULTY_TO_API.get(difficulty, difficulty)
    return {
        "id": str(row[0]),
        "brand": row[1] or "",
        "lock_type": row[2] or "other",
        "difficulty": api_difficulty,
        "base_price": _coerce_decimal(row[4]),
        "surcharges": _normalize_surcharges(row[5]),
        "created_at": row[6].isoformat() if row[6] else None,
        "updated_at": row[7].isoformat() if row[7] else None,
    }


_SELECT = (
    "id, brand, lock_type, difficulty, base_price, modifiers, "
    "created_at, updated_at"
)


async def list_pricing_rules(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    brand: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid", "is_active = TRUE"]
    args: list = [tenant_id]

    if brand:
        where.append("LOWER(brand) = LOWER(%s)")
        args.append(brand)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT} FROM price_rules "
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
        next_cursor = encode_cursor({"ts": last[6].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


def _validate_decimal_str(value, field: str) -> float:
    """API 輸入 decimal string → DB FLOAT，過程中驗證格式。"""
    if value is None:
        raise ApiError("VALIDATION_ERROR", f"{field} is required", 422)
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ApiError(
            "VALIDATION_ERROR",
            f"{field} must be a decimal string (e.g. '1200.00')",
            422,
        )
    if f < 0:
        raise ApiError("VALIDATION_ERROR", f"{field} must be non-negative", 422)
    return f


def _normalize_surcharges_input(surcharges) -> list[dict]:
    """API PricingSurcharge[] → DB modifiers JSONB（List[dict] 形式）。

    輸入每筆需有 name + amount(decimal string)；condition 選填。
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


async def create_pricing_rule(
    *,
    tenant_id: str,
    brand: str,
    lock_type: str,
    difficulty: str,
    base_price: str,
    surcharges: list | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if not brand or not brand.strip():
        raise ApiError("VALIDATION_ERROR", "brand is required", 422)
    if lock_type not in _VALID_LOCK_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"Invalid lock_type: {lock_type}",
            422,
        )
    if difficulty not in _API_DIFFICULTY_TO_DB:
        raise ApiError(
            "VALIDATION_ERROR",
            f"Invalid difficulty: {difficulty}",
            422,
        )

    base_f = _validate_decimal_str(base_price, "base_price")
    modifiers = _normalize_surcharges_input(surcharges)
    db_difficulty = _API_DIFFICULTY_TO_DB[difficulty]

    cur = await db_module._conn.execute(
        f"INSERT INTO price_rules "
        f"  (tenant_id, brand, lock_type, difficulty, base_price, "
        f"   labor_cost, modifiers, is_active) "
        f"VALUES (%s::uuid, %s, %s, %s, %s, %s, %s::jsonb, TRUE) "
        f"RETURNING {_SELECT}",
        (
            tenant_id,
            brand.strip()[:100],
            lock_type,
            db_difficulty,
            base_f,
            0.0,
            json.dumps(modifiers),
        ),
    )
    row = await cur.fetchone()
    return _row_to_dict(row)


async def update_pricing_rule(
    *,
    tenant_id: str,
    rule_id: str,
    base_price: str | None = None,
    surcharges: list | None = None,
) -> dict:
    """更新 base_price / surcharges。brand/lock_type/difficulty immutable。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT id FROM price_rules "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND is_active = TRUE",
        (rule_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", f"Pricing rule {rule_id} not found", 404)

    sets: list[str] = []
    args: list = []

    if base_price is not None:
        sets.append("base_price = %s")
        args.append(_validate_decimal_str(base_price, "base_price"))

    if surcharges is not None:
        modifiers = _normalize_surcharges_input(surcharges)
        sets.append("modifiers = %s::jsonb")
        args.append(json.dumps(modifiers))

    if not sets:
        raise ApiError(
            "VALIDATION_ERROR",
            "At least one of base_price or surcharges must be provided",
            422,
        )

    sets.append("updated_at = NOW()")
    args.extend([rule_id, tenant_id])

    cur = await db_module._conn.execute(
        f"UPDATE price_rules SET {', '.join(sets)} "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid "
        f"RETURNING {_SELECT}",
        tuple(args),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", f"Pricing rule {rule_id} not found", 404)
    return _row_to_dict(row)
