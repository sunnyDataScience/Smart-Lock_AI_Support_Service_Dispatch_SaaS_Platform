"""CR-0163：報價先行下游斷鏈四修（多 agent 掃雷確認，CR-0160/0161/0162 同家族收尾）。

CR-0128 報價先行後，卡階段報價（work_order_id=NULL）讓四個仍假設
「報價恆有工單」的下游全滅：
  A. convert 開單從未補開延後的發票（transition accept 註解承諾、實作不存在）
     → 主路徑每張工單靜默漏開應收發票。
  B. work_orders.estimated_price 永不回填（CR-0117 回寫要求已綁單，
     主路徑 send/accept 都在開單前）→ 師傅預估收入恆 0。
  C. _resolve_conversation_id 經 work_orders INNER JOIN
     → send/accept/decline 事件從不寫入對話管理。
  D. sla_monitor quote_expiring 錨定 work_orders → 卡階段 sent 報價永不告警。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import quote_engine_service as qe
from services import work_order_service as wo_svc

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"


async def _mk_chain() -> tuple[str, str, str]:
    """user（含地址電話）→conversation→confirmed PC。回 (uid, cid, pid)。"""
    assert await db_module._ensure_conn()
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, line_user_id, display_name, phone, address, role) "
        "VALUES (%s::uuid, %s::uuid, %s, 'CR-0163 測試客', '0912000163', '台北市信義區163號', 'customer')",
        (uid, TID, f"Utest0163{uuid.uuid4().hex[:24]}"))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')", (cid, uid, f"sess-{cid[:8]}"))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, conversation_id, brand, model, "
        " category, urgency, status, intent) "
        "VALUES (%s::uuid, %s, %s::uuid, 'Chatlock', 'A90', '維修', 'normal', 'confirmed', 'repair')",
        (pid, TID, cid))
    return uid, cid, pid


async def _cleanup(uid: str, cid: str, pid: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM invoices WHERE work_order_id IN "
        "(SELECT id FROM work_orders WHERE problem_card_id = %s::uuid)", (pid,))
    await db_module._conn.execute(
        "DELETE FROM quote_line_items WHERE quote_id IN "
        "(SELECT id FROM quote WHERE problem_card_id = %s::uuid)", (pid,))
    await db_module._conn.execute("DELETE FROM quote WHERE problem_card_id = %s::uuid", (pid,))
    await db_module._conn.execute(
        "DELETE FROM work_order_events WHERE work_order_id IN "
        "(SELECT id FROM work_orders WHERE problem_card_id = %s::uuid)", (pid,))
    await db_module._conn.execute(
        "DELETE FROM work_orders WHERE problem_card_id = %s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM messages WHERE conversation_id = %s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


async def _mk_quote(pid: str, *, to_state: str) -> str:
    """卡階段報價走真實主路徑推進：draft→submit→approve→send（→accept）。"""
    q = await qe.create_quote(tenant_id=TID, problem_card_id=pid, created_by=None)
    await qe.add_line(tenant_id=TID, quote_id=q["id"], service_code="SVC-CAR-002", quantity=1)
    await qe.transition(tenant_id=TID, quote_id=q["id"], action="submit")
    await qe.transition(tenant_id=TID, quote_id=q["id"], action="approve")
    await qe.transition(tenant_id=TID, quote_id=q["id"], action="send")
    if to_state == "accepted":
        await qe.transition(tenant_id=TID, quote_id=q["id"], action="accept")
    return q["id"]


@pytest.mark.asyncio
async def test_convert_backfills_invoice_and_estimated_price():
    """A+B：卡階段 accept（發票延後）→ convert 開單 → 發票補開 + estimated_price 回填。"""
    uid, cid, pid = await _mk_chain()
    try:
        qid = await _mk_quote(pid, to_state="accepted")
        # 卡階段 accept 不開票（延後）——前置確認
        pre = await (await db_module._conn.execute(
            "SELECT count(*) FROM invoices WHERE quote_id = %s::uuid", (qid,))).fetchone()
        assert pre[0] == 0, "卡階段 accept 應延後開票"

        wo, created = await wo_svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        assert created is True

        # A：convert 後發票已補開（原 bug：承諾補開但從未實作 → 0 筆）
        inv = await (await db_module._conn.execute(
            "SELECT total FROM invoices WHERE work_order_id = %s::uuid", (wo["id"],))).fetchone()
        assert inv is not None, "convert 後應補開延後的應收發票"

        # B：estimated_price 已回填為 accepted 報價總額（原 bug：恆 NULL → 師傅預估收入 0）
        row = await (await db_module._conn.execute(
            "SELECT wo.estimated_price, q.total_amount FROM work_orders wo "
            "JOIN quote q ON q.id = %s::uuid WHERE wo.id = %s::uuid",
            (qid, wo["id"]))).fetchone()
        assert row[0] is not None, "estimated_price 應回填"
        assert float(row[0]) == float(row[1]), "estimated_price 應等於 accepted 報價總額"
    finally:
        await _cleanup(uid, cid, pid)


@pytest.mark.asyncio
async def test_card_stage_quote_events_reach_conversation():
    """C：卡階段報價 send 事件寫入對話（原 bug：工單 JOIN 查無 conv → 靜默略過）。"""
    uid, cid, pid = await _mk_chain()
    try:
        qid = await _mk_quote(pid, to_state="sent")
        assert await qe._resolve_conversation_id(qid) == cid
        msg = await (await db_module._conn.execute(
            "SELECT count(*) FROM messages WHERE conversation_id = %s::uuid AND role = 'system'",
            (cid,))).fetchone()
        assert msg[0] >= 1, "send 後對話應有報價系統訊息"
    finally:
        await _cleanup(uid, cid, pid)


@pytest.mark.asyncio
async def test_sla_quote_expiring_covers_card_stage():
    """D：卡階段 sent 報價逾時進入 quote_expiring 掃描（原 bug：錨定工單永不觸發）。"""
    from realtime.sla_monitor import SLAMonitor

    uid, cid, pid = await _mk_chain()
    try:
        qid = await _mk_quote(pid, to_state="sent")
        # 回溯送出時間超過閾值（預設 1440 分鐘）
        await db_module._conn.execute(
            "UPDATE quote SET updated_at = NOW() - INTERVAL '2 days' WHERE id = %s::uuid", (qid,))
        mon = SLAMonitor()
        await mon._scan_once()
        assert ("quote_expiring", qid) in mon._alerted, "卡階段 sent 報價應進入逾時告警"
    finally:
        await _cleanup(uid, cid, pid)
