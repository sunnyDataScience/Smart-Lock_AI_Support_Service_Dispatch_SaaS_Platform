"""UAT 第一波修復（2026-07-11）：F7 requote 稽核 FK、F9 品牌授權 fail-closed、F5 報價冪等。

- F7：requote_service 稽核 actor_id 原傳 technicians.id → 撞 audit_events.actor_id
  FK(→users.id) → 稽核靜默漏記。修為傳 technicians.user_id。
- F9：手動派工 assign/reassign 原不驗品牌授權（fail-open）。修為 fail-closed，
  主管帶 override_reason 可突破。
- F5：quote 狀態機動作端點原未掛冪等 → 同 Idempotency-Key 重試回 409 非回放。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import quote_engine_service as qe
from services import requote_service
from services import work_order_service as wo_svc
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID
SEED_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01"
SEED_TECH_USER = "66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01"


async def _mk_wo(*, brand: str = "Chatlock", status: str = "in_progress",
                 technician_id: str | None = SEED_TECH) -> tuple[str, str, str]:
    """建 user→conversation→problem_card→work_order 完整鏈（_WO_JOIN 需 users）。

    回 (wo_id, pc_id, user_id)。
    """
    assert await db_module._ensure_conn()
    wid, pid = str(uuid.uuid4()), str(uuid.uuid4())
    uid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, line_user_id, display_name, role) "
        "VALUES (%s::uuid, %s::uuid, %s, 'UAT修復測試客', 'customer')",
        (uid, TID, f"Uuatfix{uuid.uuid4().hex[:20]}"))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')", (cid, uid, f"sess-{cid[:8]}"))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, conversation_id, brand, model, status) "
        "VALUES (%s::uuid, %s, %s::uuid, %s, 'A90', 'confirmed')", (pid, TID, cid, brand))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, technician_id, brand, model, "
        "customer_address, customer_name, problem_type, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, 'A90', '台北市測試路1號', '測試客', '維修', %s::uuid)",
        (wid, pid, status, technician_id, brand, TID))
    return wid, pid, uid


async def _cleanup(wid: str, pid: str, uid: str) -> None:
    await db_module._conn.execute("DELETE FROM audit_events WHERE target_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM requote_requests WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute(
        "DELETE FROM quote_line_items WHERE quote_id IN "
        "(SELECT id FROM quote WHERE work_order_id=%s::uuid OR problem_card_id=%s::uuid)", (wid, pid))
    await db_module._conn.execute("DELETE FROM quote WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM quote WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM dispatch_logs WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM work_order_events WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id=%s::uuid", (wid,))
    cur = await db_module._conn.execute(
        "SELECT conversation_id FROM problem_cards WHERE id=%s::uuid", (pid,))
    crow = await cur.fetchone()
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))
    if crow and crow[0]:
        await db_module._conn.execute("DELETE FROM conversations WHERE id=%s::uuid", (crow[0],))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


# ── F7：requote 稽核 actor_id 修正 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_requote_writes_audit_with_user_id():
    """requote 後 audit_events 應寫入（actor_id=technician.user_id，非 technicians.id）。"""
    wid, pid, uid = await _mk_wo()
    try:
        out, replayed = await requote_service.submit_requote(
            tenant_id=TID, request_id=f"rq-{uuid.uuid4().hex[:10]}", work_order_id=wid,
            technician_id=SEED_TECH, reason="scope_add",
            item_diffs=[{"item": "鎖芯", "qty": 1}], initiated_via="technician_command")
        assert out["created_quote_id"]
        row = await (await db_module._conn.execute(
            "SELECT actor_id, action FROM audit_events "
            "WHERE target_id=%s::uuid AND action='requote.command_received'", (wid,))).fetchone()
        assert row is not None, "requote 稽核事件應寫入（原 FK 違反被 fail-soft 吞）"
        assert str(row[0]) == SEED_TECH_USER, "actor_id 應為 technician.user_id 而非 technicians.id"
    finally:
        await _cleanup(wid, pid, uid)


# ── F9：品牌授權 fail-closed ─────────────────────────────────────────────────

async def _seed_accepted_quote(pid: str, wid: str) -> None:
    """滿足派工報價閘：落一筆 accepted 報價綁該工單。"""
    await db_module._conn.execute(
        "INSERT INTO quote (work_order_id, problem_card_id, state, tenant_id, version) "
        "VALUES (%s::uuid, %s::uuid, 'accepted', %s::uuid, 1)", (wid, pid, TID))


@pytest.mark.asyncio
async def test_assign_blocks_brand_unauthorized_tech():
    """品牌有授權名單但技師不在 → assign 403 TECHNICIAN_BRAND_NOT_AUTHORIZED。"""
    brand = "Yale"
    wid, pid, uid = await _mk_wo(brand=brand, status="created", technician_id=None)
    try:
        await _seed_accepted_quote(pid, wid)
        # 讓「別的技師」（seed 陳師傅）擁有 Yale 授權，但 SEED_TECH 沒有
        other = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02"
        await db_module._conn.execute(
            "INSERT INTO technician_brand_authorization (technician_id, brand, authorized) "
            "VALUES (%s::uuid, %s, TRUE)", (other, brand))
        with pytest.raises(ApiError) as exc:
            await wo_svc.assign_order(
                tenant_id=TID, wo_id=wid, technician_id=SEED_TECH,
                reason_code="manual", actor_role="dispatcher")
        assert exc.value.status_code == 403
        assert exc.value.error_code == "TECHNICIAN_BRAND_NOT_AUTHORIZED"
    finally:
        await db_module._conn.execute("DELETE FROM technician_brand_authorization WHERE brand=%s", (brand,))
        await _cleanup(wid, pid, uid)


@pytest.mark.asyncio
async def test_assign_allows_with_supervisor_override():
    """未授權技師 + 主管帶 override_reason → 放行（安全閥，稽核由 router 記）。"""
    brand = "Yale"
    wid, pid, uid = await _mk_wo(brand=brand, status="created", technician_id=None)
    try:
        await _seed_accepted_quote(pid, wid)
        other = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02"
        await db_module._conn.execute(
            "INSERT INTO technician_brand_authorization (technician_id, brand, authorized) "
            "VALUES (%s::uuid, %s, TRUE)", (other, brand))
        out = await wo_svc.assign_order(
            tenant_id=TID, wo_id=wid, technician_id=SEED_TECH,
            reason_code="manual", actor_role="admin",
            override_reason="急件安全閥：現場唯一可到技師")
        assert out["status"] in ("assigned", "inquiring") or out.get("technician_id")
    finally:
        await db_module._conn.execute("DELETE FROM technician_brand_authorization WHERE brand=%s", (brand,))
        await _cleanup(wid, pid, uid)


@pytest.mark.asyncio
async def test_assign_allows_when_brand_has_no_auth_data():
    """該品牌無任何授權資料 → 不阻擋（與候選過濾 None 語意一致，避免全斷）。"""
    brand = "UnknownBrandXYZ"
    wid, pid, uid = await _mk_wo(brand=brand, status="created", technician_id=None)
    try:
        await _seed_accepted_quote(pid, wid)
        out = await wo_svc.assign_order(
            tenant_id=TID, wo_id=wid, technician_id=SEED_TECH,
            reason_code="manual", actor_role="dispatcher")
        assert out.get("technician_id")
    finally:
        await _cleanup(wid, pid, uid)

# 註：F5（quote 狀態機冪等）已評估後緩修——修法需把 Idempotency-Key 變成 6 個
# transition 端點的強制契約（config idempotency.applies_to 含 POST），對低嚴重度
# 問題（狀態機本已擋重複執行、無副作用）不成比例，另立獨立變更審慎處理。
