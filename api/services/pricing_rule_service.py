"""Pricing Rules 業務邏輯（Phase 1.14 read-only）。

範圍：listPricingRules（cursor + limit + brand 篩選）。
不含：createPricingRule / updatePricingRule / calculatePricing 等寫入路徑。

OpenAPI PricingRule schema：
    id, brand, lock_type (LockType), difficulty (DifficultyLevel),
    base_price (decimal str), surcharges (PricingSurcharge[]), created_at, updated_at

DB ↔ API 對齊：
  - price_rules.brand / lock_type → 直通（seed 寫入時即用 OpenAPI enum 值，故無需 mapping）
  - price_rules.difficulty (easy/medium/hard) → API enum (simple/moderate/complex)
  - price_rules.base_price (FLOAT) → API base_price: decimal string with 2 decimals
  - price_rules.modifiers (JSONB array) → API surcharges (PricingSurcharge[])
  - price_rules.is_active = FALSE → 過濾不回傳

租戶隔離：price_rules.tenant_id（Schema_api_phase1.sql 補上）。
"""

from __future__ import annotations

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
