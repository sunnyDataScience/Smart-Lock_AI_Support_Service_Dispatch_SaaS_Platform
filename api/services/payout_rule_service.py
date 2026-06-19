"""CR-0037 師傅拆帳規則主檔 service（mock-first，仿 CR-0034 catalog）。

esales sheet 21 拆帳草稿（23 服務 × A/B/C 級別 + 夜間/急件加成率）查詢 + 純計算 helper。
base_payout 為內部敏感成本 → include_cost RBAC 遮蔽（同 catalog unit_price）。

NOT wired：reconciliation 拆帳重算（目前硬編 80% / ADR-0041）改查表 → Phase II
（需 work_orders 夜間/急件旗標 + 業主 Q-09 確認）。本 service 只提供查詢與純計算。
"""

from __future__ import annotations

from datetime import date

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError


def _dec(v) -> str | None:
    return None if v is None else f"{float(v):.2f}"


async def _conn():
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    return db_module._conn


def _row_to_dict(r: tuple, include_cost: bool) -> dict:
    out = {
        "rule_id": r[0], "service_code": r[1], "service_name": r[2], "level_id": r[3],
        "night_surcharge_pct": float(r[5]), "urgent_surcharge_pct": float(r[6]),
        "currency": r[7], "decision_status": r[9], "is_mock": bool(r[10]),
    }
    if include_cost:
        out["base_payout"] = _dec(r[4])  # 內部敏感：僅 admin/ops 可見
    return out


_SELECT = ("rule_id, service_code, service_name, level_id, base_payout, night_surcharge_pct, "
           "urgent_surcharge_pct, currency, effective_date, decision_status, is_mock")


async def list_rules(*, tenant_id: str | None, include_cost: bool,
                     service_code: str | None = None) -> list[dict]:
    """列拆帳規則；base_payout 依 include_cost RBAC 遮蔽。

    租戶隔離（仿 CR-0034 catalog）：回全域（tenant_id IS NULL，目前 seed 皆全域共享）
    + 該租戶自訂規則（未來）。靜態 WHERE + 參數化避免動態拼接。
    """
    conn = await _conn()
    rows = await (await conn.execute(
        f"SELECT {_SELECT} FROM technician_payout_rule "
        "WHERE (tenant_id IS NULL OR tenant_id = %s::uuid) "
        "  AND (%s::text IS NULL OR service_code = %s) "
        "ORDER BY service_code, level_id",
        (tenant_id, service_code, service_code))).fetchall()
    return [_row_to_dict(r, include_cost) for r in rows]


async def get_rule(*, tenant_id: str | None, service_code: str, level_id: str,
                   on_date: date | None = None, include_cost: bool = False) -> dict | None:
    """取單一 service×level 的生效拆帳規則（effective_date ≤ on_date 且未過期）。

    多版本時取最新生效（ORDER BY effective_date DESC NULLS LAST LIMIT 1）；無對應 → None。
    base_payout / base_payout_raw（內部成本）僅在 include_cost=True 才回（預設 False 防外洩）；
    Phase II reconciliation 重算內部呼叫時帶 include_cost=True。租戶隔離同 list_rules。
    """
    conn = await _conn()
    d = on_date or date.today()
    r = await (await conn.execute(
        f"SELECT {_SELECT} FROM technician_payout_rule "
        "WHERE (tenant_id IS NULL OR tenant_id = %s::uuid) "
        "  AND service_code = %s AND level_id = %s "
        "  AND (effective_date IS NULL OR effective_date <= %s) "
        "  AND (expiry_date IS NULL OR expiry_date > %s) "
        "ORDER BY effective_date DESC NULLS LAST LIMIT 1",
        (tenant_id, service_code, level_id, d, d))).fetchone()
    if not r:
        return None
    out = _row_to_dict(r, include_cost=include_cost)
    if include_cost:
        out["base_payout_raw"] = float(r[4])
    return out


def compute_payout(*, base_payout: float, night: bool = False, urgent: bool = False,
                   night_pct: float = 0.0, urgent_pct: float = 0.0) -> float:
    """純計算拆帳金額（CR-0037）：base × (1+夜間?) × (1+急件?)。

    純函式，不查 DB；reconciliation 重算接此（Phase II）。加成乘法疊加（與 base 一致幣別）。
    """
    amount = float(base_payout)
    if night:
        amount *= (1 + float(night_pct))
    if urgent:
        amount *= (1 + float(urgent_pct))
    return round(amount, 2)
