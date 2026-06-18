"""CR-0034 報價主檔讀取 service（service_catalog / material_catalog / surcharge_rule）。

數值為 esales mock（is_mock=TRUE，決議 5）；內部成本(internal_*)僅後台角色可讀。
正式價待業主回 esales Q-01~Q-12 後從 mock 轉正式（另 workflow）。
"""

from __future__ import annotations

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError


def _dec(v) -> str | None:
    return None if v is None else f"{float(v):.2f}"


async def _q(sql: str, args: tuple):
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(sql, args)
    return await cur.fetchall()


async def list_services(*, tenant_id: str, include_cost: bool) -> list[dict]:
    rows = await _q(
        "SELECT service_code, category, service_name, service_type, material_class, unit, "
        "       needs_dispatch, cross_zone, internal_base_cost, suggested_customer_price, "
        "       decision_status, is_mock "
        "FROM service_catalog WHERE tenant_id IS NULL OR tenant_id = %s::uuid "
        "ORDER BY service_code",
        (tenant_id,),
    )
    out = []
    for r in rows:
        item = {
            "service_code": r[0], "category": r[1], "service_name": r[2],
            "service_type": r[3], "material_class": r[4], "unit": r[5],
            "needs_dispatch": r[6], "cross_zone": r[7],
            "suggested_customer_price": _dec(r[9]),
            "decision_status": r[10], "is_mock": bool(r[11]),
        }
        if include_cost:
            item["internal_base_cost"] = _dec(r[8])
        out.append(item)
    return out


async def list_materials(*, tenant_id: str, include_cost: bool) -> list[dict]:
    rows = await _q(
        "SELECT material_code, category, material_name, material_class, unit, spec_note, "
        "       needs_evidence, internal_cost, suggested_price, decision_status, is_mock "
        "FROM material_catalog WHERE tenant_id IS NULL OR tenant_id = %s::uuid "
        "ORDER BY material_code",
        (tenant_id,),
    )
    out = []
    for r in rows:
        item = {
            "material_code": r[0], "category": r[1], "material_name": r[2],
            "material_class": r[3], "unit": r[4], "spec_note": r[5],
            "needs_evidence": bool(r[6]) if r[6] is not None else None,
            "suggested_price": _dec(r[8]),
            "decision_status": r[9], "is_mock": bool(r[10]),
        }
        if include_cost:
            item["internal_cost"] = _dec(r[7])
        out.append(item)
    return out


async def list_surcharges(*, tenant_id: str) -> list[dict]:
    rows = await _q(
        "SELECT rule_code, rule_type, rule_name, condition_note, unit, amount, value_text, "
        "       decision_status, note, is_mock "
        "FROM surcharge_rule WHERE tenant_id IS NULL OR tenant_id = %s::uuid "
        "ORDER BY rule_code",
        (tenant_id,),
    )
    return [{
        "rule_code": r[0], "rule_type": r[1], "rule_name": r[2], "condition_note": r[3],
        "unit": r[4], "amount": _dec(r[5]), "value_text": r[6],
        "decision_status": r[7], "note": r[8], "is_mock": bool(r[9]),
    } for r in rows]


async def get_catalog(*, tenant_id: str, include_cost: bool) -> dict:
    return {
        "services": await list_services(tenant_id=tenant_id, include_cost=include_cost),
        "materials": await list_materials(tenant_id=tenant_id, include_cost=include_cost),
        "surcharges": await list_surcharges(tenant_id=tenant_id),
        "cost_visible": include_cost,
        "note": "數值為 esales mock（is_mock）；正式價待業主回 esales Q-01~Q-12",
    }
