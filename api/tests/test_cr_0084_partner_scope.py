"""CR-0084 / TI-PORTAL-01 — Partner Portal scope 隔離（修 vendor 看全品牌假綠）。"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import partner_scope_service as pss

TID = "00000000-0000-0000-0000-000000000001"
PARTNER_A = str(uuid.uuid4())
PARTNER_B = str(uuid.uuid4())


# ── 純函式 resolver ──
@pytest.mark.unit
def test_brand_sees_only_own():
    # vendor 綁 A，requested=None → 強制 A（不可全 tenant）
    assert pss.resolve_partner_scope(role="vendor", bound_partner_id=PARTNER_A,
                                     requested_partner_id=None) == PARTNER_A


@pytest.mark.unit
def test_cross_partner_read_blocked():
    with pytest.raises(ApiError) as e:
        pss.resolve_partner_scope(role="vendor", bound_partner_id=PARTNER_A,
                                  requested_partner_id=PARTNER_B)
    assert e.value.error_code == "CROSS_PARTNER_READ" and e.value.status_code == 403


@pytest.mark.unit
def test_unbound_vendor_denied_fail_closed():
    with pytest.raises(ApiError) as e:
        pss.resolve_partner_scope(role="vendor", bound_partner_id=None, requested_partner_id=None)
    assert e.value.error_code == "PARTNER_NOT_BOUND" and e.value.status_code == 403


@pytest.mark.unit
def test_admin_bypass():
    # admin requested=None → None（看全部）；requested=B → B
    assert pss.resolve_partner_scope(role="admin", bound_partner_id=None,
                                     requested_partner_id=None) is None
    assert pss.resolve_partner_scope(role="admin", bound_partner_id=None,
                                     requested_partner_id=PARTNER_B) == PARTNER_B


# ── component：vendor binding lookup + list 過濾 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_vendor_binding_and_scoped_list_excludes_other_partner():
    assert await db_module._ensure_conn()
    from services import brand_b2b_statement_service as b2b
    vid, uid = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, display_name, role) "
            "VALUES (%s::uuid, %s::uuid, '品牌使用者', 'brand_oem')", (uid, TID))
        # vendor 綁 PARTNER_A
        await db_module._conn.execute(
            "INSERT INTO vendors (id, user_id, vendor_type, name, phone, email, address, "
            "  status, tenant_id, brand_partner_id) "
            "VALUES (%s::uuid, %s::uuid, 'brand_oem', '品牌A', '0900000000', 'a@x.com', '台北', "
            "  'approved', %s::uuid, %s::uuid)",
            (vid, uid, TID, PARTNER_A))
        bound = await pss.get_vendor_brand_partner_id(user_id=uid)
        assert bound == PARTNER_A
        # 建兩 partner 的 statement（A / B 同 tenant）
        await b2b.generate_statement(tenant_id=TID, brand_partner_id=PARTNER_A, brand_name="A",
                                     period_year=2099, period_month=1, direction="NET")
        await b2b.generate_statement(tenant_id=TID, brand_partner_id=PARTNER_B, brand_name="B",
                                     period_year=2099, period_month=1, direction="NET")
        # 以 resolve 出的 scope（A）list → 只見 A
        scope = pss.resolve_partner_scope(role="vendor", bound_partner_id=bound, requested_partner_id=None)
        out = await b2b.list_statements(tenant_id=TID, brand_partner_id=scope)
        partners = {i["brand_partner_id"] for i in (out.get("items") or [])}
        assert PARTNER_A in partners and PARTNER_B not in partners
    finally:
        await db_module._conn.execute(
            "DELETE FROM saas.brand_b2b_statement WHERE brand_partner_id IN (%s::uuid,%s::uuid)",
            (PARTNER_A, PARTNER_B))
        await db_module._conn.execute("DELETE FROM vendors WHERE id=%s::uuid", (vid,))
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))
