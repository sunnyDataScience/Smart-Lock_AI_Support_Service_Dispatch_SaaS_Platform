"""CR-0095 — 初始報價 LINE 送單 + 客戶同意 + 同意才派工。

涵蓋：
  - 單元（無 DB）：quote_proposal Flex builder 含 q:a|/q:r| postback + URI fallback；
    PushKind / BUILDERS 已註冊 quote_proposal。
  - component（live DB）：派工 gate（無 accepted 報價 → 409 QUOTE_NOT_ACCEPTED；
    有 accepted → 通過；主管 override 繞過；非主管不可 override）；
    客戶經 LINE 回覆報價（擁有權不符 → 403；正確客戶 accept → accepted）。

業主裁決（CR-0095 §8）：D2 硬擋（一律需報價同意）+ 主管 override；D4 過期視同未同意。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import seed_accepted_quote

import core.db as db_module
from core.errors import ApiError
from services import quote_engine_service, work_order_service as svc

TID = "00000000-0000-0000-0000-000000000001"


# ── 單元：builder（無 DB）─────────────────────────────────────────────
def test_quote_proposal_builder_postback_and_fallback():
    from templates.line_flex import build_messages

    msgs = build_messages("quote_proposal", {
        "quote_id": "q-123",
        "work_order_id": "wo-456789",
        "items": [{"name": "電子鎖整鎖更換", "customer_price": "15000", "quantity": 1}],
        "total": "15000",
        "public_token": "tok-abc",
    })
    assert msgs and msgs[0]["type"] == "flex"
    blob = str(msgs[0])
    # 同意/拒絕走 postback（agent gateway 接 q:a|/q:r|）
    assert "q:a|q-123" in blob
    assert "q:r|q-123" in blob
    # 網頁 fallback（URI 開 /quotes/{token}）
    assert "/quotes/tok-abc" in blob
    # 只露對客價，總額顯示
    assert "15000" in blob


def test_quote_proposal_registered():
    from services.line_push_outbox_service import PushKind
    from templates.line_flex.builders import BUILDERS
    import typing

    assert "quote_proposal" in typing.get_args(PushKind)
    assert "quote_proposal" in BUILDERS


def test_build_messages_importable_from_package():
    # 回歸：worker 以 `from templates.line_flex import build_messages` 取用，
    # 先前未匯出 → ImportError 使所有 LINE 推送 render 失敗（CR-0095 修）。
    from templates.line_flex import build_messages
    assert callable(build_messages)


# ── component：seed helpers ──────────────────────────────────────────
async def _seed_chain(line_user_id: str | None) -> tuple[str, str, str]:
    """user(可帶 line_user_id)→conv→confirmed PC→WO。回 (wo_id, pid, uid)。"""
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role, line_user_id) "
        "VALUES (%s::uuid,%s::uuid,'客','0912345678','台北市信義區1號','line_user',%s)",
        (uid, TID, line_user_id))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')", (cid, uid, "sess-" + pid[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status, intent) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM','維修','normal','confirmed','repair')", (pid, cid))
    # CR-0128 報價先行 gate 前置：seed 過閘後即刪——本檔測試（assign gate 擋無報價單、
    # 報價版本從 1 起算）都需要「乾淨無報價的 WO」作起點。
    gate_qid = await seed_accepted_quote(pid, TID)
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
    wid = wo["id"]
    await db_module._conn.execute("DELETE FROM quote WHERE id=%s::uuid", (gate_qid,))
    # 過派工必填閘（CR-0026）：補地址 + problem_type
    await db_module._conn.execute(
        "UPDATE work_orders SET customer_address='台北市信義區1號', problem_type='鎖故障' "
        "WHERE id=%s::uuid", (wid,))
    return wid, pid, uid


async def _make_quote(wid: str, pid: str, state: str) -> str:
    """直接 INSERT 一筆報價（避開 catalog 依賴）。回 quote_id。"""
    qid = str(uuid.uuid4())
    expiry = datetime.now(timezone.utc) + timedelta(days=7)
    await db_module._conn.execute(
        "INSERT INTO quote (id, work_order_id, problem_card_id, state, total_amount, expiry_at, tenant_id) "
        "VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s::uuid)",
        (qid, wid, pid, state, 1500, expiry, TID))
    return qid


async def _cleanup(uid: str, pid: str) -> None:
    sub = "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)"
    await db_module._conn.execute(f"DELETE FROM invoices WHERE quote_id IN (SELECT id FROM quote WHERE work_order_id IN {sub})", (pid,))
    await db_module._conn.execute(f"DELETE FROM pricing_rule_snapshot WHERE quote_id IN (SELECT id FROM quote WHERE work_order_id IN {sub})", (pid,))
    await db_module._conn.execute(f"DELETE FROM quote_approval WHERE quote_id IN (SELECT id FROM quote WHERE work_order_id IN {sub})", (pid,))
    await db_module._conn.execute(f"DELETE FROM quote_line_items WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute(f"DELETE FROM quote WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute(f"DELETE FROM work_order_events WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute(f"DELETE FROM dispatch_logs WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE user_id=%s::uuid", (uid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


# ── component：派工 gate（D2 硬擋）────────────────────────────────────
@pytest.mark.component
@pytest.mark.asyncio
async def test_assign_blocked_without_accepted_quote():
    assert await db_module._ensure_conn()
    wid, pid, uid = await _seed_chain(None)
    try:
        with pytest.raises(ApiError) as e:
            await svc._assert_quote_accepted(wid, None, None)
        assert e.value.error_code == "QUOTE_NOT_ACCEPTED"
        assert e.value.status_code == 409
        # 有報價但僅 sent（未同意）→ 一樣擋
        await _make_quote(wid, pid, "sent")
        with pytest.raises(ApiError):
            await svc._assert_quote_accepted(wid, None, None)
    finally:
        await _cleanup(uid, pid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_assign_passes_with_accepted_quote():
    assert await db_module._ensure_conn()
    wid, pid, uid = await _seed_chain(None)
    try:
        await _make_quote(wid, pid, "accepted")
        # 不應 raise
        await svc._assert_quote_accepted(wid, None, None)
    finally:
        await _cleanup(uid, pid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_assign_gate_supervisor_override():
    assert await db_module._ensure_conn()
    wid, pid, uid = await _seed_chain(None)
    try:
        # 無 accepted 報價，但 admin 帶 override_reason → 放行
        await svc._assert_quote_accepted(wid, "admin", "客戶現場急修，欄位事後補")
        # 非主管角色不可 override → 仍擋
        with pytest.raises(ApiError):
            await svc._assert_quote_accepted(wid, "technician", "我想派")
        # admin 但空白 reason → 不算 override，仍擋
        with pytest.raises(ApiError):
            await svc._assert_quote_accepted(wid, "admin", "   ")
    finally:
        await _cleanup(uid, pid)


# ── component：客戶經 LINE 回覆報價（擁有權 + 狀態機）─────────────────
@pytest.mark.component
@pytest.mark.asyncio
async def test_list_quotes_and_wo_number():
    """CR-0095 UX：list_quotes + get_quote 帶友善公單號（TP），供報價 dashboard 免貼 UUID。"""
    assert await db_module._ensure_conn()
    wid, pid, uid = await _seed_chain(None)
    try:
        qid = await _make_quote(wid, pid, "draft")
        rows = await quote_engine_service.list_quotes(tenant_id=TID)
        mine = [r for r in rows if r["id"] == qid]
        assert mine, "新建報價應出現在列表"
        assert mine[0]["work_order_number"], "列表應帶公單號（TP-xxxxxx）"
        q = await quote_engine_service.get_quote(tenant_id=TID, quote_id=qid, include_cost=True)
        assert q.get("work_order_number"), "get_quote 應帶公單號供工作台顯示"
    finally:
        await _cleanup(uid, pid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_create_quote_version_increments_per_work_order():
    """CR-0095 UX2：同工單建多張報價時 version 遞增（Q1, Q2…），避免可讀編號撞號。

    回歸：create_quote 原未設 version，靠 DB default 恆為 1 → 第二張也叫 TP-xxxxxx-Q1。
    """
    assert await db_module._ensure_conn()
    wid, pid, uid = await _seed_chain(None)
    try:
        q1 = await quote_engine_service.create_quote(tenant_id=TID, work_order_id=wid)
        q2 = await quote_engine_service.create_quote(tenant_id=TID, work_order_id=wid)
        assert q1["version"] == 1
        assert q2["version"] == 2
        assert q1["quote_number"].endswith("-Q1"), q1["quote_number"]
        assert q2["quote_number"].endswith("-Q2"), q2["quote_number"]
    finally:
        await _cleanup(uid, pid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_quote_event_synced_to_conversation():
    """CR-0095：報價同意事件 → 對話管理系統訊息（quote→wo→pc→conversation）。"""
    assert await db_module._ensure_conn()
    wid, pid, uid = await _seed_chain(None)
    try:
        qid = await _make_quote(wid, pid, "sent")
        await quote_engine_service.transition(tenant_id=TID, quote_id=qid, action="accept")
        cur = await db_module._conn.execute(
            "SELECT count(*) FROM messages m "
            "JOIN problem_cards pc ON m.conversation_id = pc.conversation_id "
            "WHERE pc.id = %s::uuid AND m.role = 'system' AND m.content LIKE %s",
            (pid, "%同意報價單%"))
        assert int((await cur.fetchone())[0]) >= 1, "對話應出現『客戶已同意報價單』系統訊息"
        # 可讀編號 TP-xxxxxx-Q1 形式
        q = await quote_engine_service.get_quote(tenant_id=TID, quote_id=qid, include_cost=True)
        assert q.get("quote_number") and "-Q" in q["quote_number"]
    finally:
        await _cleanup(uid, pid)


@pytest.mark.component
@pytest.mark.asyncio
async def test_customer_respond_ownership_and_accept():
    assert await db_module._ensure_conn()
    owner_line = "U" + uuid.uuid4().hex[:24]
    wid, pid, uid = await _seed_chain(owner_line)
    try:
        qid = await _make_quote(wid, pid, "sent")
        # 非該報價客戶 → 403
        with pytest.raises(ApiError) as e:
            await quote_engine_service.customer_respond_to_quote(
                tenant_id=TID, quote_id=qid, line_user_id="U_other_user", decision="accept")
        assert e.value.status_code == 403
        # 正確客戶 accept → accepted
        res = await quote_engine_service.customer_respond_to_quote(
            tenant_id=TID, quote_id=qid, line_user_id=owner_line, decision="accept")
        assert res["state"] == "accepted"
        # accept 後該工單 gate 應放行
        await svc._assert_quote_accepted(wid, None, None)
    finally:
        await _cleanup(uid, pid)
