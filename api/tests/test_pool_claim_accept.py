"""搶單 claim + 派工資格檢查（BR-M07-01 / FR-0005 A9）。

修復背景（2026-07-02 師傅端測試）：
  1. pool 列出 created 單但 _ACCEPT_FROM={"assigned"} → 技師搶 created 單必 409，
     且 accept 不寫 technician_id → 搶單語意根本未實作。
  2. accept 不驗 technicians.status → 停權/待核准技師仍可接單，違反 BR-M07-01
     「阻擋派工」（active 文件、阻擋 Coding=是）。
  3. pool 對技師列出「派給他人」的 assigned 單 → 點了必 409 的假搶單。

測試策略：自建 user + technician + WO 全鏈（不依賴 seed 固定 ID），結束清理。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import seed_accepted_quote

import core.db as db_module
from core.errors import ApiError
from services import work_order_service as svc

TID = "00000000-0000-0000-0000-000000000001"


async def _seed_tech(status: str = "active") -> tuple[str, str]:
    """建立 user(role=technician) + technicians 列。回 (user_id, tech_id)。"""
    uid, tech_id = str(uuid.uuid4()), str(uuid.uuid4())
    suffix = uid[:8]
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, email, display_name, phone, role, is_active) "
        "VALUES (%s::uuid,%s::uuid,%s,'搶單測試技師','0912111222','technician',true)",
        (uid, TID, f"pool-claim-{suffix}@example.com"),
    )
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status, online_state) "
        "VALUES (%s::uuid,%s::uuid,%s::uuid,'搶單測試技師','0912111222',%s,'available')",
        (tech_id, TID, uid, status),
    )
    return uid, tech_id


async def _seed_wo(status: str, technician_id: str | None = None) -> tuple[str, str, str]:
    """user→conv→pc→wo 全鏈。回 (wo_id, uid, pid)。"""
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,'客','0912000000','台北市信義區1號','line_user')",
        (uid, TID),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')",
        (cid, uid, "sess-" + pid[:12]),
    )
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM','維修','normal','confirmed')",
        (pid, cid),
    )
    await seed_accepted_quote(pid, TID)  # CR-0128 報價先行 gate 前置
    wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
    await db_module._conn.execute(
        "UPDATE work_orders SET status=%s, technician_id=%s WHERE id=%s::uuid",
        (status, technician_id, wo["id"]),
    )
    return wo["id"], uid, pid


async def _cleanup_wo(uid: str, pid: str) -> None:
    sub = "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)"
    await db_module._conn.execute(
        f"DELETE FROM work_order_events WHERE work_order_id IN {sub}", (pid,)
    )
    await db_module._conn.execute(
        f"DELETE FROM dispatch_logs WHERE work_order_id IN {sub}", (pid,)
    )
    await db_module._conn.execute(
        "DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,)
    )
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


async def _cleanup_tech(uid: str, tech_id: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id=%s::uuid", (tech_id,)
    )
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


# ── 搶單 claim ────────────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_tech_claims_created_wo_sets_technician_id():
    assert await db_module._ensure_conn()
    t_uid, tech_id = await _seed_tech("active")
    wid, uid, pid = await _seed_wo("created", None)
    try:
        out = await svc.accept_order(
            tenant_id=TID, wo_id=wid, actor_user_id=t_uid, actor_role="technician"
        )
        assert out["status"] == "accepted"
        cur = await db_module._conn.execute(
            "SELECT status, technician_id, accepted_at FROM work_orders WHERE id=%s::uuid",
            (wid,),
        )
        row = await cur.fetchone()
        assert row[0] == "accepted"
        assert str(row[1]) == tech_id  # claim 寫入搶單技師
        assert row[2] is not None
    finally:
        await _cleanup_wo(uid, pid)
        await _cleanup_tech(t_uid, tech_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_tech_accept_assigned_to_other_409():
    assert await db_module._ensure_conn()
    t_uid, tech_id = await _seed_tech("active")
    other_uid, other_tech = await _seed_tech("active")
    wid, uid, pid = await _seed_wo("assigned", other_tech)
    try:
        with pytest.raises(ApiError) as e:
            await svc.accept_order(
                tenant_id=TID, wo_id=wid, actor_user_id=t_uid, actor_role="technician"
            )
        assert e.value.status_code == 409  # FR-0005 A9 已派他人
        # technician_id 未被覆寫
        cur = await db_module._conn.execute(
            "SELECT status, technician_id FROM work_orders WHERE id=%s::uuid", (wid,)
        )
        row = await cur.fetchone()
        assert row[0] == "assigned" and str(row[1]) == other_tech
    finally:
        await _cleanup_wo(uid, pid)
        await _cleanup_tech(t_uid, tech_id)
        await _cleanup_tech(other_uid, other_tech)


@pytest.mark.component
@pytest.mark.asyncio
async def test_tech_accept_assigned_to_self_200():
    assert await db_module._ensure_conn()
    t_uid, tech_id = await _seed_tech("active")
    wid, uid, pid = await _seed_wo("assigned", tech_id)
    try:
        out = await svc.accept_order(
            tenant_id=TID, wo_id=wid, actor_user_id=t_uid, actor_role="technician"
        )
        assert out["status"] == "accepted"
    finally:
        await _cleanup_wo(uid, pid)
        await _cleanup_tech(t_uid, tech_id)


@pytest.mark.component
@pytest.mark.asyncio
@pytest.mark.parametrize("tech_status", ["suspended", "pending_approval", "terminated"])
async def test_non_active_tech_accept_403(tech_status):
    assert await db_module._ensure_conn()
    t_uid, tech_id = await _seed_tech(tech_status)
    wid, uid, pid = await _seed_wo("created", None)
    try:
        with pytest.raises(ApiError) as e:
            await svc.accept_order(
                tenant_id=TID, wo_id=wid, actor_user_id=t_uid, actor_role="technician"
            )
        assert e.value.status_code == 403
        assert e.value.error_code == "TECHNICIAN_NOT_DISPATCHABLE"
    finally:
        await _cleanup_wo(uid, pid)
        await _cleanup_tech(t_uid, tech_id)


# ── 後台代操作行為不變 ────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_admin_accept_assigned_unchanged():
    assert await db_module._ensure_conn()
    t_uid, tech_id = await _seed_tech("active")
    wid, uid, pid = await _seed_wo("assigned", tech_id)
    try:
        out = await svc.accept_order(tenant_id=TID, wo_id=wid)  # 無 actor（舊呼叫相容）
        assert out["status"] == "accepted"
    finally:
        await _cleanup_wo(uid, pid)
        await _cleanup_tech(t_uid, tech_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_admin_accept_created_still_409():
    assert await db_module._ensure_conn()
    wid, uid, pid = await _seed_wo("created", None)
    try:
        with pytest.raises(ApiError) as e:
            await svc.accept_order(
                tenant_id=TID, wo_id=wid, actor_user_id=str(uuid.uuid4()),
                actor_role="admin",
            )
        assert e.value.status_code == 409  # created 需 assign 或技師搶單
    finally:
        await _cleanup_wo(uid, pid)


# ── pool 技師視角過濾 ─────────────────────────────────────────


@pytest.mark.component
@pytest.mark.asyncio
async def test_pool_tech_view_filters_assigned_to_others():
    assert await db_module._ensure_conn()
    t_uid, tech_id = await _seed_tech("active")
    other_uid, other_tech = await _seed_tech("active")
    w_created, u1, p1 = await _seed_wo("created", None)
    w_mine, u2, p2 = await _seed_wo("assigned", tech_id)
    w_other, u3, p3 = await _seed_wo("assigned", other_tech)
    try:
        page = await svc.list_work_order_pool(
            tenant_id=TID, actor_user_id=t_uid, actor_role="technician"
        )
        ids = {w["id"] for w in page["items"]}
        assert w_created in ids
        assert w_mine in ids
        assert w_other not in ids  # 派給他人的單不出現在技師 pool

        # admin 視角全列
        page_admin = await svc.list_work_order_pool(tenant_id=TID)
        ids_admin = {w["id"] for w in page_admin["items"]}
        assert {w_created, w_mine, w_other} <= ids_admin
    finally:
        await _cleanup_wo(u1, p1)
        await _cleanup_wo(u2, p2)
        await _cleanup_wo(u3, p3)
        await _cleanup_tech(t_uid, tech_id)
        await _cleanup_tech(other_uid, other_tech)
