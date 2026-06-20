"""CR-0078 / TI-FIN-BOM-03 — 兩層 BOM + material owner + 材料費歸屬 + 退回期限（Phase I）。"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import bom_service as bom

TID = "00000000-0000-0000-0000-000000000001"
OTHER_TID = "00000000-0000-0000-0000-000000000002"


# ── enum 純函式 ──
@pytest.mark.unit
def test_validate_material_owner():
    from services.bom_service import _validate_material_owner
    for ok in ("brand", "company", "locksmith", "customer"):
        _validate_material_owner(ok)
    with pytest.raises(ApiError) as e:
        _validate_material_owner("platform")    # ADR-0052 值不在 spec BR-M10-02
    assert e.value.status_code == 422


@pytest.mark.unit
def test_validate_cost_attribution():
    from services.bom_service import _validate_cost_attribution
    for ok in ("customer", "brand", "technician", "company"):
        _validate_cost_attribution(ok)
    with pytest.raises(ApiError) as e:
        _validate_cost_attribution("unknown")
    assert e.value.status_code == 422


async def _cleanup(model_id):
    await db_module._conn.execute("DELETE FROM saas.bom_line WHERE product_model_id=%s::uuid", (model_id,))
    await db_module._conn.execute("DELETE FROM saas.product_model WHERE id=%s::uuid", (model_id,))


# ── 兩層 BOM happy + 每料件獨立歸屬 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_create_two_layer_bom_and_per_material_attribution():
    assert await db_module._ensure_conn()
    brand, model = "Yale", "YDM-" + uuid.uuid4().hex[:6]
    pm = await bom.create_product_model(tenant_id=TID, brand=brand, model=model)
    try:
        await bom.add_bom_line(tenant_id=TID, product_model_id=pm["id"], material_ref="LOCK-BODY",
                               material_owner="brand", cost_attribution="customer", quantity=1)
        await bom.add_bom_line(tenant_id=TID, product_model_id=pm["id"], material_ref="BATTERY",
                               material_owner="company", cost_attribution="brand", quantity=4)
        out = await bom.list_bom(tenant_id=TID, product_model_id=pm["id"])
        assert len(out["lines"]) == 2                       # 兩層：1 model + 2 lines
        attrs = {l["material_ref"]: l["cost_attribution"] for l in out["lines"]}
        assert attrs["LOCK-BODY"] == "customer" and attrs["BATTERY"] == "brand"   # 每料件獨立歸屬
        # 重複 model → 409
        with pytest.raises(ApiError) as e:
            await bom.create_product_model(tenant_id=TID, brand=brand, model=model)
        assert e.value.status_code == 409
    finally:
        await _cleanup(pm["id"])


# ── 非法 owner → 422，DB 無殘留 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_bom_line_invalid_owner_422():
    assert await db_module._ensure_conn()
    pm = await bom.create_product_model(tenant_id=TID, brand="X", model="Y-" + uuid.uuid4().hex[:6])
    try:
        with pytest.raises(ApiError) as e:
            await bom.add_bom_line(tenant_id=TID, product_model_id=pm["id"], material_ref="M",
                                   material_owner="platform", cost_attribution="customer")
        assert e.value.status_code == 422
        out = await bom.list_bom(tenant_id=TID, product_model_id=pm["id"])
        assert out["lines"] == []        # 驗證失敗無殘留
    finally:
        await _cleanup(pm["id"])


# ── Phase I：return_deadline_days 不帶 → NULL allowed ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_return_deadline_null_allowed():
    assert await db_module._ensure_conn()
    pm = await bom.create_product_model(tenant_id=TID, brand="X", model="Z-" + uuid.uuid4().hex[:6])
    try:
        line = await bom.add_bom_line(tenant_id=TID, product_model_id=pm["id"], material_ref="M",
                                      material_owner="locksmith", cost_attribution="technician")
        assert line["return_deadline_days"] is None
    finally:
        await _cleanup(pm["id"])


# ── tenant 隔離 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_bom_tenant_isolation():
    assert await db_module._ensure_conn()
    pm = await bom.create_product_model(tenant_id=TID, brand="Iso", model="M-" + uuid.uuid4().hex[:6])
    try:
        with pytest.raises(ApiError) as e:
            await bom.list_bom(tenant_id=OTHER_TID, product_model_id=pm["id"])
        assert e.value.status_code == 404      # 他 tenant 看不到
    finally:
        await _cleanup(pm["id"])
