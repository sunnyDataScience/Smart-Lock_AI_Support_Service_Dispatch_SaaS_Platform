"""CR-0034 報價主檔 service（service_catalog / material_catalog / surcharge_rule）。

讀取：seed 數值為 esales mock（is_mock=TRUE）；內部成本(internal_*)僅後台角色可讀。
CRUD（CR-0110，20260702 會議裁決簡化版）：一品牌一 DB → 單庫內 code 天然唯一，
不做 global+override / 複合鍵改造。業主 2026-07-03 裁決：三類目一次做、
軟刪（deleted_at）、租戶編輯後 is_mock=FALSE + decision_status='已確認'。
"""

from __future__ import annotations

from typing import Any

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

# 租戶自行維護後的確認狀態（CR-0110 §8-6 業主裁決）
_CONFIRMED_STATUS = "已確認"


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
        "FROM service_catalog WHERE (tenant_id IS NULL OR tenant_id = %s::uuid) AND deleted_at IS NULL "
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
        "FROM material_catalog WHERE (tenant_id IS NULL OR tenant_id = %s::uuid) AND deleted_at IS NULL "
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
        "FROM surcharge_rule WHERE (tenant_id IS NULL OR tenant_id = %s::uuid) AND deleted_at IS NULL "
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


# ─────────────────────────────────────────────────────────────────────────────
# CRUD（CR-0110 簡化版）— 通用機制:
#   - create:code 唯一(未刪列),重複 → 409 CODE_TAKEN;寫入 tenant_id +
#     is_mock=FALSE + decision_status='已確認'(§8-6:租戶自填的價即正式值)
#   - update:白名單欄位 partial update;任何編輯同樣翻 is_mock/decision_status
#   - delete:軟刪 SET deleted_at=NOW()(§8-5:可復原、報價明細價來源可稽核)
# ─────────────────────────────────────────────────────────────────────────────

_TABLE_SPEC: dict[str, dict[str, Any]] = {
    "service": {
        "table": "service_catalog",
        "code_col": "service_code",
        "required": ("service_name",),
        # 可寫欄位（code 由 create 專屬處理）
        "fields": (
            "category", "service_name", "service_type", "material_class", "unit",
            "needs_dispatch", "cross_zone", "internal_note",
            "internal_base_cost", "suggested_customer_price",
        ),
        "numeric": ("internal_base_cost", "suggested_customer_price"),
    },
    "material": {
        "table": "material_catalog",
        "code_col": "material_code",
        "required": ("material_name",),
        "fields": (
            "category", "material_name", "material_class", "unit", "spec_note",
            "needs_evidence", "internal_cost", "suggested_price",
        ),
        "numeric": ("internal_cost", "suggested_price"),
    },
    "surcharge": {
        "table": "surcharge_rule",
        "code_col": "rule_code",
        "required": ("rule_name",),
        "fields": (
            "rule_type", "rule_name", "condition_note", "unit", "amount",
            "value_text", "note",
        ),
        "numeric": ("amount",),
    },
}


def _validate_fields(kind: str, data: dict[str, Any], *, require_all: bool) -> dict[str, Any]:
    """白名單過濾 + 必填/數值驗證。回可寫入的欄位 dict。"""
    spec = _TABLE_SPEC[kind]
    out: dict[str, Any] = {}
    for f in spec["fields"]:
        if f not in data or data[f] is None:
            continue
        v = data[f]
        if f in spec["numeric"]:
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise ApiError("VALIDATION_ERROR", f"{f} 必須為數字", 422)
            if v < 0:
                raise ApiError("VALIDATION_ERROR", f"{f} 不可為負數", 422)
        elif isinstance(v, str):
            v = v.strip()
            if not v:
                continue
        out[f] = v
    if require_all:
        for f in spec["required"]:
            if not out.get(f):
                raise ApiError("VALIDATION_ERROR", f"{f} 為必填", 422)
    return out


async def _code_exists(kind: str, code: str) -> bool:
    spec = _TABLE_SPEC[kind]
    rows = await _q(
        f"SELECT 1 FROM {spec['table']} WHERE {spec['code_col']} = %s AND deleted_at IS NULL",
        (code,),
    )
    return bool(rows)


async def create_item(*, kind: str, tenant_id: str, code: str, data: dict[str, Any]) -> dict:
    """新增類目項。code 唯一（未刪列）；寫入即為租戶確認值（is_mock=FALSE）。"""
    spec = _TABLE_SPEC[kind]
    code = (code or "").strip()
    if not code or len(code) > 40:
        raise ApiError("VALIDATION_ERROR", "code 為必填且長度 ≤ 40", 422)
    fields = _validate_fields(kind, data, require_all=True)
    if await _code_exists(kind, code):
        raise ApiError("CODE_TAKEN", f"代碼 {code} 已存在", 409)

    # code 是物理 PK,軟刪列仍佔用 → 對已刪同 code 走「復活」(UPDATE 覆寫 +
    # 清 deleted_at),否則 INSERT 新列。兩者對呼叫端等價(201)。
    revived = await db_module._conn.execute(
        f"UPDATE {spec['table']} SET deleted_at = NULL, tenant_id = %s::uuid, "
        f"  is_mock = FALSE, decision_status = %s, updated_at = NOW(), "
        f"  {', '.join(f'{f} = %s' for f in fields)} "
        f"WHERE {spec['code_col']} = %s AND deleted_at IS NOT NULL "
        f"RETURNING {spec['code_col']}",
        (tenant_id, _CONFIRMED_STATUS, *fields.values(), code),
    )
    if await revived.fetchone():
        return {"code": code, "kind": kind}

    cols = [spec["code_col"], "tenant_id", "is_mock", "decision_status", *fields.keys()]
    vals = [code, tenant_id, False, _CONFIRMED_STATUS, *fields.values()]
    placeholders = ["%s", "%s::uuid", "%s", "%s", *["%s"] * len(fields)]
    await db_module._conn.execute(
        f"INSERT INTO {spec['table']} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})",
        tuple(vals),
    )
    return {"code": code, "kind": kind}


async def update_item(*, kind: str, tenant_id: str, code: str, data: dict[str, Any]) -> dict:
    """編輯類目項（partial）。任何編輯視為租戶確認 → is_mock=FALSE + 已確認。"""
    spec = _TABLE_SPEC[kind]
    fields = _validate_fields(kind, data, require_all=False)
    if not fields:
        raise ApiError("VALIDATION_ERROR", "沒有可更新的欄位", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    sets = [f"{f} = %s" for f in fields]
    sets += ["is_mock = FALSE", f"decision_status = '{_CONFIRMED_STATUS}'", "updated_at = NOW()"]
    cur = await db_module._conn.execute(
        f"UPDATE {spec['table']} SET {', '.join(sets)} "
        f"WHERE {spec['code_col']} = %s AND deleted_at IS NULL "
        f"  AND (tenant_id IS NULL OR tenant_id = %s::uuid) "
        f"RETURNING {spec['code_col']}",
        (*fields.values(), code, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", f"找不到代碼 {code}", 404)
    return {"code": code, "kind": kind}


async def delete_item(*, kind: str, tenant_id: str, code: str) -> dict:
    """軟刪類目項（deleted_at=NOW()；報價明細的價來源可追溯，可人工復原）。"""
    spec = _TABLE_SPEC[kind]
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        f"UPDATE {spec['table']} SET deleted_at = NOW(), updated_at = NOW() "
        f"WHERE {spec['code_col']} = %s AND deleted_at IS NULL "
        f"  AND (tenant_id IS NULL OR tenant_id = %s::uuid) "
        f"RETURNING {spec['code_col']}",
        (code, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", f"找不到代碼 {code}", 404)
    return {"code": code, "kind": kind}
