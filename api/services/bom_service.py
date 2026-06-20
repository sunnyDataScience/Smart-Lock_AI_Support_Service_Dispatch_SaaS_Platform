"""兩層 BOM service（CR-0078 / TI-FIN-BOM-03 / BR-M10-01/02 / Q079-Q087；Phase I mock）。

第一層 product_model（brand/model 主檔）→ 第二層 bom_line（子件 + material_owner +
cost_attribution + 退回期限）。Phase I 只做資料模型 + CRUD；Phase II 接 part-level
warranty 退回狀態機。enum 對齊 spec BR-M10-02 / Q087。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.bom_service")

# spec BR-M10-02：材料擁有者；Q087：材料費歸屬
_VALID_MATERIAL_OWNER = {"brand", "company", "locksmith", "customer"}
_VALID_COST_ATTRIBUTION = {"customer", "brand", "technician", "company"}


def _validate_material_owner(owner: str) -> None:
    if owner not in _VALID_MATERIAL_OWNER:
        raise ApiError("VALIDATION_ERROR",
                       f"material_owner must be one of {sorted(_VALID_MATERIAL_OWNER)}", 422)


def _validate_cost_attribution(attr: str) -> None:
    if attr not in _VALID_COST_ATTRIBUTION:
        raise ApiError("VALIDATION_ERROR",
                       f"cost_attribution must be one of {sorted(_VALID_COST_ATTRIBUTION)}", 422)


async def create_product_model(
    *, tenant_id: str, brand: str, model: str,
) -> dict:
    """建 BOM 第一層 brand/model 主檔。重複 (tenant,brand,model) → 409。"""
    if not (brand and brand.strip() and model and model.strip()):
        raise ApiError("VALIDATION_ERROR", "brand and model are required", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id FROM saas.product_model WHERE tenant_id=%s::uuid AND brand=%s AND model=%s",
        (tenant_id, brand, model))
    if await cur.fetchone():
        raise ApiError("STATE_CONFLICT", "product model already exists", 409)
    cur = await db_module._conn.execute(
        "INSERT INTO saas.product_model (tenant_id, brand, model) "
        "VALUES (%s::uuid, %s, %s) RETURNING id, brand, model, is_active",
        (tenant_id, brand, model))
    row = await cur.fetchone()
    return {"id": str(row[0]), "brand": row[1], "model": row[2], "is_active": row[3], "lines": []}


async def add_bom_line(
    *, tenant_id: str, product_model_id: str, material_ref: str,
    material_owner: str, cost_attribution: str, material_name: str | None = None,
    quantity: float = 1, return_deadline_days: int | None = None,
) -> dict:
    """建第二層子件。enum 驗證（422）；product_model 不存在 → 404。"""
    _validate_material_owner(material_owner)
    _validate_cost_attribution(cost_attribution)
    if not (material_ref and material_ref.strip()):
        raise ApiError("VALIDATION_ERROR", "material_ref is required", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    pcur = await db_module._conn.execute(
        "SELECT 1 FROM saas.product_model WHERE id=%s::uuid AND tenant_id=%s::uuid",
        (product_model_id, tenant_id))
    if not await pcur.fetchone():
        raise ApiError("NOT_FOUND", "product model not found", 404)
    cur = await db_module._conn.execute(
        "INSERT INTO saas.bom_line "
        "  (tenant_id, product_model_id, material_ref, material_name, quantity, "
        "   material_owner, cost_attribution, return_deadline_days) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s) "
        "RETURNING id, material_ref, material_name, quantity, material_owner, "
        "          cost_attribution, return_deadline_days",
        (tenant_id, product_model_id, material_ref, material_name, quantity,
         material_owner, cost_attribution, return_deadline_days))
    r = await cur.fetchone()
    return {"id": str(r[0]), "material_ref": r[1], "material_name": r[2],
            "quantity": float(r[3]), "material_owner": r[4], "cost_attribution": r[5],
            "return_deadline_days": r[6]}


async def list_bom(*, tenant_id: str, product_model_id: str) -> dict:
    """回兩層 BOM：第一層 model + 第二層 lines 陣列。tenant 過濾；空 BOM 回空陣列非錯誤。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    mcur = await db_module._conn.execute(
        "SELECT id, brand, model, is_active FROM saas.product_model "
        "WHERE id=%s::uuid AND tenant_id=%s::uuid", (product_model_id, tenant_id))
    m = await mcur.fetchone()
    if not m:
        raise ApiError("NOT_FOUND", "product model not found", 404)
    lcur = await db_module._conn.execute(
        "SELECT id, material_ref, material_name, quantity, material_owner, "
        "       cost_attribution, return_deadline_days "
        "FROM saas.bom_line WHERE product_model_id=%s::uuid AND tenant_id=%s::uuid "
        "ORDER BY created_at", (product_model_id, tenant_id))
    lines = [
        {"id": str(r[0]), "material_ref": r[1], "material_name": r[2], "quantity": float(r[3]),
         "material_owner": r[4], "cost_attribution": r[5], "return_deadline_days": r[6]}
        for r in await lcur.fetchall()
    ]
    return {"id": str(m[0]), "brand": m[1], "model": m[2], "is_active": m[3], "lines": lines}
