"""CR-0027 成本拆項 + 客戶版電子工單測試（component，真 DB）。

驗證：
- add_line_item → 重算 work_orders.customer_final_amount
- list_line_items：include_cost=True 含 unit_price；False 不含（RBAC 成本遮蔽）
- render_document：回傳 %PDF bytes；customer view 結構上不含 unit_price（成本不外洩）
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import quote_service, work_order_document_service
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


async def _seed_work_order() -> tuple[str, list[str]]:
    """seed user→conversation→confirmed PC→work_order，回 (wo_id, cleanup_ids)。"""
    uid = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    pcid = str(uuid.uuid4())
    woid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, role) VALUES (%s::uuid, %s::uuid, 'line_user')",
        (uid, DEFAULT_TENANT_ID),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id) VALUES (%s::uuid, %s::uuid, %s)",
        (cid, uid, f"sess-{uid[:8]}"),
    )
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, status, brand, model, category) "
        "VALUES (%s::uuid, %s::uuid, 'confirmed', 'Yale', 'YDM-4109', '電池')",
        (pcid, cid),
    )
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, customer_name, customer_address, "
        "  brand, model, problem_type, service_category) "
        "VALUES (%s::uuid, %s::uuid, 'created', '王小明', '新北市板橋區文化路1號', "
        "  'Yale', 'YDM-4109', '電池故障', 'repair')",
        (woid, pcid),
    )
    return woid, [woid, pcid, cid, uid]


async def _cleanup(ids: list[str]) -> None:
    woid, pcid, cid, uid = ids
    await db_module._conn.execute("DELETE FROM quote_line_items WHERE work_order_id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pcid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


@pytest.mark.asyncio
async def test_add_line_item_recomputes_final_and_rbac_mask(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_work_order()
    try:
        await quote_service.add_line_item(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=woid,
            item_name="主機板", category="material",
            unit_price=1000, quantity=1, customer_price=800, is_mock=True,
        )
        await quote_service.add_line_item(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=woid,
            item_name="工資", category="labor",
            unit_price=500, quantity=2, customer_price=600, is_mock=True,
        )
        # 對外總額 = 800*1 + 600*2 = 2000
        admin_view = await quote_service.list_line_items(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, include_cost=True)
        assert admin_view["customer_final_amount"] == "2000.00"
        assert admin_view["cost_visible"] is True
        assert all("unit_price" in it for it in admin_view["items"])

        # 客戶/非後台角色：不含 unit_price
        cust_view = await quote_service.list_line_items(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, include_cost=False)
        assert cust_view["cost_visible"] is False
        assert all("unit_price" not in it for it in cust_view["items"])
        assert all("customer_price" in it for it in cust_view["items"])
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_render_document_pdf_no_cost_leak(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_work_order()
    try:
        await quote_service.add_line_item(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=woid,
            item_name="主機板", category="material",
            unit_price=1000, quantity=1, customer_price=800, is_mock=True,
        )
        # customer view 結構上不含 unit_price
        view = await work_order_document_service._fetch_customer_view(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=woid)
        for it in view["items"]:
            assert "unit_price" not in it
            assert set(it.keys()) == {"name", "qty", "price"}

        pdf = await work_order_document_service.render_document(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=woid)
        assert isinstance(pdf, bytes) and pdf[:4] == b"%PDF"
        assert len(pdf) > 800
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_quote_cross_tenant_404(client):
    """別的 tenant 不能讀/寫本 tenant 的 work_order line items。"""
    from core.errors import ApiError
    assert await db_module._ensure_conn()
    woid, ids = await _seed_work_order()
    other = "00000000-0000-0000-0000-000000000099"
    try:
        with pytest.raises(ApiError) as ei:
            await quote_service.list_line_items(
                tenant_id=other, work_order_id=woid, include_cost=True)
        assert ei.value.status_code == 404
    finally:
        await _cleanup(ids)
