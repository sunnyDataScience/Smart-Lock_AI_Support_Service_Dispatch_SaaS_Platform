"""CR-0036 Phase II 金流參數入 config 治理 + 訂金接發票 測試（component，需 migration 044）。

- M18 config seed 可讀（deposit_policy / dispatch_commission / monthly_close_schedule，is_mock）
- invoice.create_from_quote 從 deposit_policy config 算 deposit_required（rate / min / 上限 total）
- config 缺失 → _resolve_deposit fallback 常數（不破）
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import config_m18_service
from services import invoice_service
from services import quote_engine_service as qe
from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_finance_config_seeded(client):
    """sheet 24 三組金流參數已 seed 進 M18 config（global active，is_mock 自標）。"""
    assert await db_module._ensure_conn()
    dep = await config_m18_service.read_global_value(namespace="deposit_policy")
    assert dep and dep["rate"] == 0.3 and dep["min_twd"] == 1000 and dep["is_mock"] is True
    comm = await config_m18_service.read_global_value(namespace="dispatch_commission")
    assert comm and comm["rate"] == 0.08
    close = await config_m18_service.read_global_value(namespace="monthly_close_schedule")
    assert close and close["pay_workday"] == 10


@pytest.mark.asyncio
async def test_read_global_value_missing_returns_none(client):
    """不存在的 namespace → None（不丟 404，供 fallback）。"""
    assert await db_module._ensure_conn()
    assert await config_m18_service.read_global_value(namespace="nonexistent_ns_xyz") is None


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_resolve_deposit_from_config(client):
    """_resolve_deposit：max(amount×rate, min) 上限 total（config 或 fallback 同值 0.3/1000）。"""
    # 800：max(240, 1000)=1000，但上限 total 800 → 800（小額全收，min 路徑被 total 上限蓋）
    assert await invoice_service._resolve_deposit(800.0) == 800.0
    # 8000：max(2400, 1000)=2400（rate/min 取高 → rate 路徑）
    assert await invoice_service._resolve_deposit(8000.0) == 2400.0
    # 4000：max(1200, 1000)=1200
    assert await invoice_service._resolve_deposit(4000.0) == 1200.0
    # 守會計不變式：amount ≤ 0 → 0（不產生負/誤訂金）
    assert await invoice_service._resolve_deposit(0.0) == 0.0
    assert await invoice_service._resolve_deposit(-100.0) == 0.0


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


async def _accept_quote(woid: str, qty: int) -> dict:
    q = await qe.create_quote(tenant_id=DEFAULT_TENANT_ID, work_order_id=woid, created_by=ADMIN_USER_ID)
    await qe.add_line(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], service_code="SVC-RES-001", quantity=qty)
    await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], action="send", actor_id=ADMIN_USER_ID)
    await qe.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"], action="accept")
    return q


@pytest.mark.asyncio
async def test_invoice_deposit_computed_from_config(client):
    """開發票時 deposit_required 從 config 算並存 DB。"""
    assert await db_module._ensure_conn()
    # SVC-RES-001 客戶價 800 ×10 = 8000 → deposit max(2400,1000)=2400
    woid, ids = await _seed_wo()
    try:
        q = await _accept_quote(woid, qty=10)
        await invoice_service.create_from_quote(tenant_id=DEFAULT_TENANT_ID, quote_id=q["id"])
        row = await (await db_module._conn.execute(
            "SELECT amount, deposit_required FROM invoices WHERE work_order_id = %s::uuid", (woid,))).fetchone()
        assert float(row[0]) == 8000.0
        assert float(row[1]) == 2400.0  # max(8000×0.3, 1000)=2400（rate/min 取高）
    finally:
        await _cleanup(ids)
