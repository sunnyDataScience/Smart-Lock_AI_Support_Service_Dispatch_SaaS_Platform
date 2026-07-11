"""CR-0162：卡階段報價 LINE 同意不再 404 —— resolve_customer_line_uid 走 problem_card 直連。

Root cause：CR-0128 報價先行的卡階段報價 work_order_id=NULL，
resolve_customer_line_uid 原經 work_orders 的 INNER JOIN 反查客人 LINE uid
→ 查無 → customer_respond_to_quote 回 404「quote not found」→ LINE 客人
點「同意報價」看到「報價或已失效」（業主 UAT 實測）。推播 worker
（line_push_outbox_worker）的 quote 路徑早在 CR-0128 改走 problem_card_id
直連（推得出去），本函式沒跟上（收不回來）。

本測試驗證：①卡階段報價（無工單）可反查 LINE uid 並完成同意；
②工單階段報價（已綁 WO）同路徑仍成立；③非本人 LINE uid 仍被 403 擋下。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import quote_engine_service as qe

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"


async def _mk_card_chain() -> tuple[str, str, str, str]:
    """建 user(line_user_id)→conversation→problem_card 完整鏈。

    回 (line_uid, user_id, conversation_id, problem_card_id)；
    line_uid 每次動態產生，避免撞前次失敗殘留的 unique constraint。
    """
    assert await db_module._ensure_conn()
    line_uid = f"Utest0162{uuid.uuid4().hex[:24]}"
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, line_user_id, display_name, role) "
        "VALUES (%s::uuid, %s::uuid, %s, 'CR-0162 測試客', 'customer')",
        (uid, TID, line_uid))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')", (cid, uid, f"sess-{cid[:8]}"))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, conversation_id, brand, model, status) "
        "VALUES (%s::uuid, %s, %s::uuid, 'Chatlock', 'A90', 'confirmed')",
        (pid, TID, cid))
    return line_uid, uid, cid, pid


async def _cleanup(uid: str, cid: str, pid: str, wid: str | None = None) -> None:
    await db_module._conn.execute(
        "DELETE FROM quote_line_items WHERE quote_id IN "
        "(SELECT id FROM quote WHERE problem_card_id = %s::uuid)", (pid,))
    await db_module._conn.execute("DELETE FROM quote WHERE problem_card_id = %s::uuid", (pid,))
    if wid:
        await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


async def _mk_sent_quote(pid: str) -> str:
    """建卡階段報價並推進到 sent（客人可回應的狀態）。"""
    q = await qe.create_quote(tenant_id=TID, problem_card_id=pid, created_by=None)
    await qe.add_line(tenant_id=TID, quote_id=q["id"], service_code="SVC-CAR-002", quantity=1)
    await qe.transition(tenant_id=TID, quote_id=q["id"], action="submit")
    await qe.transition(tenant_id=TID, quote_id=q["id"], action="approve")
    await qe.transition(tenant_id=TID, quote_id=q["id"], action="send")
    return q["id"]


@pytest.mark.asyncio
async def test_card_stage_quote_resolves_line_uid_and_accepts():
    """卡階段報價（work_order_id=NULL）：反查 LINE uid 成功、同意走通。"""
    line_uid, uid, cid, pid = await _mk_card_chain()
    try:
        qid = await _mk_sent_quote(pid)
        # 原 bug：此處回 None → customer_respond 404「報價或已失效」
        owner = await qe.resolve_customer_line_uid(tenant_id=TID, quote_id=qid)
        assert owner == line_uid
        out = await qe.customer_respond_to_quote(
            tenant_id=TID, quote_id=qid, line_user_id=line_uid, decision="accept")
        assert out["state"] == "accepted"
    finally:
        await _cleanup(uid, cid, pid)


@pytest.mark.asyncio
async def test_wo_stage_quote_still_resolves():
    """工單階段報價（已綁 WO）：problem_card 直連路徑同樣成立（迴歸保護）。"""
    line_uid, uid, cid, pid = await _mk_card_chain()
    wid = str(uuid.uuid4())
    try:
        qid = await _mk_sent_quote(pid)
        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, status, customer_address, tenant_id) "
            "VALUES (%s::uuid, %s::uuid, 'inquiring', '台北市測試路1號', %s::uuid)",
            (wid, pid, TID))
        await qe.bind_quotes_to_work_order(
            tenant_id=TID, problem_card_id=pid, work_order_id=wid)
        owner = await qe.resolve_customer_line_uid(tenant_id=TID, quote_id=qid)
        assert owner == line_uid
    finally:
        await _cleanup(uid, cid, pid, wid)


@pytest.mark.asyncio
async def test_wrong_line_user_still_403():
    """安全迴歸：非本人 LINE uid 回應仍被 403 擋下（防客戶 A 同意客戶 B 的報價）。"""
    _line_uid, uid, cid, pid = await _mk_card_chain()
    try:
        qid = await _mk_sent_quote(pid)
        with pytest.raises(ApiError) as exc:
            await qe.customer_respond_to_quote(
                tenant_id=TID, quote_id=qid, line_user_id="Uattacker0000", decision="accept")
        assert exc.value.status_code == 403
    finally:
        await _cleanup(uid, cid, pid)
