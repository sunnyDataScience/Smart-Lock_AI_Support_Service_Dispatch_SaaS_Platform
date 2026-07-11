"""CR-0161：報價先行卡階段加品項（work_order_id=NULL）不再 500，開單回填 lines。

Root cause：quote_line_items.work_order_id 曾 NOT NULL（037 work_order 層遺留），
CR-0128 報價先行的卡階段報價 work_order_id=NULL → add_line 寫入撞 NotNullViolation。
本測試驗證：①卡階段報價可正常加品項與計算總額；②開單
bind_quotes_to_work_order 把 quote 與其 line_items 的 work_order_id 一併回填。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import quote_engine_service as qe

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"


async def _mk_pc() -> str:
    assert await db_module._ensure_conn()
    pid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, brand, model, status) "
        "VALUES (%s::uuid, %s, 'Chatlock', 'A90', 'confirmed')", (pid, TID))
    return pid


async def _cleanup(pid: str, wid: str | None = None) -> None:
    await db_module._conn.execute(
        "DELETE FROM quote_line_items WHERE quote_id IN "
        "(SELECT id FROM quote WHERE problem_card_id = %s::uuid)", (pid,))
    await db_module._conn.execute("DELETE FROM quote WHERE problem_card_id = %s::uuid", (pid,))
    if wid:
        await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pid,))


@pytest.mark.asyncio
async def test_stage_quote_add_line_no_500():
    """卡階段報價（work_order_id=NULL）加品項成功，總額由品項計算。"""
    pid = await _mk_pc()
    try:
        q = await qe.create_quote(tenant_id=TID, problem_card_id=pid, created_by=None)
        assert q["work_order_id"] is None
        # 加一筆服務品項——原本此處 NotNullViolation 500
        out = await qe.add_line(
            tenant_id=TID, quote_id=q["id"], service_code="SVC-CAR-002", quantity=1)
        assert len(out["lines"]) == 1
        assert out["total_amount"] is not None and float(out["total_amount"]) > 0
    finally:
        await _cleanup(pid)


@pytest.mark.asyncio
async def test_bind_backfills_line_items_work_order_id():
    """開單 bind 把 quote 與其 line_items 的 work_order_id 一併回填。"""
    pid = await _mk_pc()
    wid = str(uuid.uuid4())
    try:
        q = await qe.create_quote(tenant_id=TID, problem_card_id=pid, created_by=None)
        await qe.add_line(tenant_id=TID, quote_id=q["id"], service_code="SVC-CAR-002", quantity=1)
        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, status, customer_address, tenant_id) "
            "VALUES (%s::uuid, %s::uuid, 'inquiring', '台北市測試路1號', %s::uuid)",
            (wid, pid, TID))

        n = await qe.bind_quotes_to_work_order(
            tenant_id=TID, problem_card_id=pid, work_order_id=wid)
        assert n == 1, "應回填 1 張卡階段報價"

        # quote 與 line_items 都應綁到工單
        qrow = await (await db_module._conn.execute(
            "SELECT work_order_id FROM quote WHERE id = %s::uuid", (q["id"],))).fetchone()
        assert str(qrow[0]) == wid
        lrow = await (await db_module._conn.execute(
            "SELECT count(*) FROM quote_line_items "
            "WHERE quote_id = %s::uuid AND work_order_id = %s::uuid", (q["id"], wid))).fetchone()
        assert lrow[0] == 1, "line_items.work_order_id 應回填"
    finally:
        await _cleanup(pid, wid)
