"""list_orders keyword 搜尋納入 document_number（公單號 TP-000001 可搜）。

報價頁工單選擇器（WorkOrderPicker）讓使用者用公單號 / 客戶名找工單，免貼 UUID；
後端 list_orders 的 keyword 須一併比對 document_number。
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import seed_accepted_quote

import core.db as db_module
from services import work_order_service as svc

TID = "00000000-0000-0000-0000-000000000001"


async def _seed_confirmed_pc() -> tuple[str, str]:
    """user（台北地址→TP）→conv→confirmed PC。回 (pc_id, uid)。"""
    await db_module._ensure_conn()  # 確保 live 連線（不靠測試執行順序殘留）
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,'公單號測試客','0912000111','台北市信義區99號','line_user')",
        (uid, TID),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')",
        (cid, uid, "sess-" + pid[:12]),
    )
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status, intent) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM','維修','normal','confirmed','repair')",
        (pid, cid),
    )
    return pid, uid


async def _cleanup(uid: str, pid: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM work_order_events WHERE work_order_id IN "
        "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)",
        (pid,),
    )
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_orders_keyword_matches_document_number():
    """用公單號（完整＋前綴片段）當 keyword 應搜到該工單。"""
    pid, uid = await _seed_confirmed_pc()
    try:
        await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        doc_no = wo["document_number"]
        assert doc_no, "工單建立應自動發公單號"

        page = await svc.list_orders(tenant_id=TID, cursor=None, limit=50, keyword=doc_no)
        assert wo["id"] in [w["id"] for w in page["items"]], f"用完整公單號 {doc_no} 應搜到工單"

        page_partial = await svc.list_orders(tenant_id=TID, cursor=None, limit=50, keyword=doc_no[:5])
        assert wo["id"] in [w["id"] for w in page_partial["items"]], "用公單號前綴片段也應命中"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_list_orders_keyword_still_matches_customer_name():
    """回歸：加 document_number 後，keyword 仍能用客戶名搜（不破壞既有行為）。"""
    pid, uid = await _seed_confirmed_pc()
    try:
        await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        page = await svc.list_orders(tenant_id=TID, cursor=None, limit=50, keyword="公單號測試客")
        assert wo["id"] in [w["id"] for w in page["items"]], "客戶名搜尋應仍有效"
    finally:
        await _cleanup(uid, pid)
