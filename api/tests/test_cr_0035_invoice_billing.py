"""CR-0035 金流結算 — 報價 accepted → 應收發票 測試（component，真 DB；需 migration 042）。

- create_from_quote：accepted 報價 → 開立應收發票（amount/line_items 客戶價、無成本）
- 冪等：同工單重複呼叫回既有發票（work_order_id UNIQUE）
- 非 accepted 報價 → 409
- transition(accept) 自動開票（best-effort 連動）
"""

from __future__ import annotations

import re
import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import invoice_service
from services import quote_engine_service as qe
from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


async def _seed_wo() -> tuple[str, list]:
    uid = str(uuid.uuid4()); cid = str(uuid.uuid4()); pcid = str(uuid.uuid4()); woid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, role) VALUES (%s::uuid, %s::uuid, 'line_user')", (uid, DEFAULT_TENANT_ID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id) VALUES (%s::uuid, %s::uuid, %s)", (cid, uid, f"s-{uid[:8]}"))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, status) VALUES (%s::uuid, %s::uuid, 'confirmed')", (pcid, cid))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, customer_address) "
        "VALUES (%s::uuid, %s::uuid, 'created', '新北市板橋區文化路1號')", (woid, pcid))
    return woid, [woid, pcid, cid, uid]


async def _cleanup(ids: list) -> None:
    woid, pcid, cid, uid = ids
    await db_module._conn.execute("DELETE FROM invoices WHERE work_order_id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM quote WHERE work_order_id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pcid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


async def _accepted_quote(woid: str) -> dict:
    """建報價 → 加項（門檻內）→ send（draft→sent）→ accept（sent→accepted）。"""
    q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
    await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], service_code="SVC-RES-001")
    await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], action="send", actor_id=ADMIN_USER_ID)
    await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], action="accept")
    return q


@pytest.mark.asyncio
async def test_create_from_quote_billing(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await _accepted_quote(woid)
        # accept 已 best-effort 自動開票；create_from_quote 冪等回既有
        inv = await invoice_service.create_from_quote(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"])
        assert inv["status"] == "issued"
        assert inv["amount"] == "800.00"  # SVC-RES-001 客戶價 800
        assert inv["work_order_id"] == woid
        # invoice_number 須符 Invoice schema 規範 ^[A-Z]{2}\d{8}$（否則 v2 router 序列化炸）
        assert re.match(r"^[A-Z]{2}\d{8}$", inv["invoice_number"]), inv["invoice_number"]
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_create_from_quote_idempotent(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await _accepted_quote(woid)
        inv1 = await invoice_service.create_from_quote(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"])
        inv2 = await invoice_service.create_from_quote(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"])
        assert inv1["id"] == inv2["id"]  # work_order_id UNIQUE → 不重開
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_create_from_quote_requires_accepted(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
        await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], service_code="SVC-RES-001")
        await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], action="send", actor_id=ADMIN_USER_ID)
        # state=sent（非 accepted）→ 不可開票
        with pytest.raises(ApiError) as ei:
            await invoice_service.create_from_quote(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"])
        assert ei.value.status_code == 409
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_create_from_quote_empty_quote_422(client):
    """無 line items（total_amount NULL/0）的報價 → 不可開 0 元發票（422）。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
        # 不加任何 line → total_amount NULL；send（0 在門檻內）→ accept
        await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], action="send", actor_id=ADMIN_USER_ID)
        await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], action="accept")
        with pytest.raises(ApiError) as ei:
            await invoice_service.create_from_quote(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"])
        assert ei.value.status_code == 422
        # best-effort 開票也因 422 跳過 → 無發票
        row = await (await db_module._conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE work_order_id = %s::uuid", (woid,))).fetchone()
        assert row[0] == 0
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_invoice_no_cost_leak(client):
    """發票 line_items 只含客戶價，結構上無內部成本 unit_price。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        q = await _accepted_quote(woid)
        await invoice_service.create_from_quote(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"])
        # 直查 DB line_items 確認無 unit_price
        row = await (await db_module._conn.execute(
            "SELECT line_items::text, is_mock FROM invoices WHERE work_order_id = %s::uuid", (woid,))).fetchone()
        assert "unit_price" not in row[0]
        assert "customer_price" in row[0]
        assert row[1] is True  # 報價 mock → 發票 is_mock
    finally:
        await _cleanup(ids)
