"""CR-0085 / TI-M03-14 — 營運主流程 E2E（非 AI 段，service 層全鏈，live DB）。

PC(confirmed) → WO → assign → accept → arrival → door-check → complete → confirm。
AI 進線段（LINE→AI→PC）需 live LLM，不在此（切 needs_external）。
"""
from __future__ import annotations
import uuid
import pytest

from tests.conftest import seed_accepted_quote
import core.db as db_module
from core.errors import ApiError
from services import work_order_service as svc

TID = "00000000-0000-0000-0000-000000000001"


async def _seed_confirmed_pc() -> tuple[str, str]:
    """user→conv→confirmed PC（含 brand/model/category 過派工必填閘）。回 (pc_id, uid)。"""
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,'客','0912345678','台北市信義區1號','line_user')", (uid, TID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')", (cid, uid, "sess-" + pid[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status, intent) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM','維修','normal','confirmed','repair')", (pid, cid))
    return pid, uid


async def _active_tech() -> str | None:
    cur = await db_module._conn.execute(
        "SELECT id FROM technicians WHERE tenant_id=%s::uuid AND status='active' LIMIT 1", (TID,))
    r = await cur.fetchone()
    return str(r[0]) if r else None


async def _cleanup(uid, pid):
    sub = "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)"
    await db_module._conn.execute(f"DELETE FROM digital_signatures WHERE document_id IN {sub}", (pid,))
    await db_module._conn.execute(f"DELETE FROM work_order_events WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute(f"DELETE FROM dispatch_logs WHERE work_order_id IN {sub}", (pid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


@pytest.mark.component
@pytest.mark.asyncio
async def test_full_ops_pipeline_happy_path():
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    tech = await _active_tech()
    if not tech:
        await _cleanup(uid, pid); pytest.skip("需要 active 技師")
    try:
        await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        wid = wo["id"]
        # 確保服務地址（結案地址閘 CR-0064）
        await db_module._conn.execute(
            "UPDATE work_orders SET customer_address='台北市信義區1號' WHERE id=%s::uuid", (wid,))
        # assign → accept（CR-0095 報價 gate 由 test_cr_0095 覆蓋；此 E2E 用主管 override 略過）
        await svc.assign_order(tenant_id=TID, wo_id=wid, technician_id=tech, reason_code="manual",
                               actor_role="admin", override_reason="E2E 略過報價同意 gate")
        await svc.accept_order(tenant_id=TID, wo_id=wid)
        # arrival → door-check（前置閘）
        await svc.record_arrival(tenant_id=TID, wo_id=wid, arrived_at="2026-06-20T10:00:00Z",
                                 gps={"lat": 25.03, "lng": 121.56})
        await svc.submit_door_check_v2(tenant_id=TID, wo_id=wid, checklist={"ok": True})
        # complete（admin override 跳證據閘）→ confirm
        await svc.complete_order(tenant_id=TID, wo_id=wid, summary="完工",
                                 is_override=True, override_reason="E2E 測試", actor_role="admin")
        out = await svc.confirm_order(tenant_id=TID, wo_id=wid, rating=5, feedback="滿意")
        cur = await db_module._conn.execute("SELECT status FROM work_orders WHERE id=%s::uuid", (wid,))
        assert (await cur.fetchone())[0] == "confirmed"   # 全鏈走到終局
    finally:
        await _cleanup(uid, pid)


# ── 狀態機 gate：accept 必須在 assign 後 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_accept_before_assign_409():
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    try:
        await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        with pytest.raises(ApiError) as e:
            await svc.accept_order(tenant_id=TID, wo_id=wo["id"])   # created 直接 accept
        assert e.value.status_code == 409
    finally:
        await _cleanup(uid, pid)


# ── door-check 必須在 arrival 後 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_doorcheck_requires_arrival_409():
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    tech = await _active_tech()
    if not tech:
        await _cleanup(uid, pid); pytest.skip("需要 active 技師")
    try:
        await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        await svc.assign_order(tenant_id=TID, wo_id=wo["id"], technician_id=tech, reason_code="manual",
                               actor_role="admin", override_reason="E2E 略過報價同意 gate")
        await svc.accept_order(tenant_id=TID, wo_id=wo["id"])
        with pytest.raises(ApiError) as e:
            await svc.submit_door_check_v2(tenant_id=TID, wo_id=wo["id"], checklist={"x": 1})
        assert e.value.status_code == 409      # 未 arrival → 前置閘擋
    finally:
        await _cleanup(uid, pid)


# ── confirm 只能從 completed ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_confirm_only_from_completed_409():
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    try:
        await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        with pytest.raises(ApiError) as e:
            await svc.confirm_order(tenant_id=TID, wo_id=wo["id"], rating=5)   # created 直接 confirm
        assert e.value.status_code == 409
    finally:
        await _cleanup(uid, pid)
