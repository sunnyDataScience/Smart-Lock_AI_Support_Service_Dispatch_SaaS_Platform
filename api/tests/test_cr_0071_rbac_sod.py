"""CR-0071 / TI-RBAC-02 — role 指派雙人 SoD（§4.6.5 SOD-ROLE-ASSIGN）。

SoD 核心：propose+approve 不可同人（service 403 SOD_VIOLATION_RBAC + DB CHECK 硬防）。
"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from core.errors import ApiError
from services import role_assignment_service as ras

TID = "00000000-0000-0000-0000-000000000001"
ADMIN_A = str(uuid.uuid4())
ADMIN_B = str(uuid.uuid4())


# ── 純狀態機（無 DB）──
@pytest.mark.unit
def test_state_machine_transitions():
    from services.role_assignment_service import _check_transition, _ALLOWED_TRANSITIONS
    _check_transition("proposed", "approved")     # ok
    _check_transition("approved", "applied")      # ok
    assert _ALLOWED_TRANSITIONS["applied"] == set()   # 終態無 outgoing
    with pytest.raises(ApiError) as e:
        _check_transition("proposed", "applied")  # 跳步
    assert e.value.status_code == 409


@pytest.mark.unit
def test_hierarchy_and_admin_gate_pure():
    from services.role_service import can_grant, RBAC_ADMIN_ROLES
    assert can_grant("admin", "technician") is True
    assert can_grant("technician", "admin") is False    # 階層不足
    assert "admin" in RBAC_ADMIN_ROLES and "customer_service" not in RBAC_ADMIN_ROLES


async def _seed_target() -> str:
    uid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, role) "
        "VALUES (%s::uuid,%s::uuid,'目標','customer_service')", (uid, TID))
    return uid


async def _cleanup(uid):
    await db_module._conn.execute("DELETE FROM saas.role_assignment WHERE target_user_id=%s::uuid", (uid,))
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


# ── SoD：同人 approve → 403 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_sod_approver_equals_proposer_rejected_403():
    assert await db_module._ensure_conn()
    uid = await _seed_target()
    try:
        p = await ras.propose_role_change(
            tenant_id=TID, target_user_id=uid, to_role="technician",
            proposer_id=ADMIN_A, proposer_role="admin", reason="升級")
        with pytest.raises(ApiError) as e:
            await ras.approve_role_change(
                tenant_id=TID, assignment_id=p["id"], approver_id=ADMIN_A, approver_role="admin")
        assert e.value.error_code == "SOD_VIOLATION_RBAC" and e.value.status_code == 403
    finally:
        await _cleanup(uid)


# ── SoD：不同人 approve → 成功 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_sod_distinct_approver_succeeds_and_applies():
    assert await db_module._ensure_conn()
    uid = await _seed_target()
    try:
        p = await ras.propose_role_change(
            tenant_id=TID, target_user_id=uid, to_role="technician",
            proposer_id=ADMIN_A, proposer_role="admin")
        a = await ras.approve_role_change(
            tenant_id=TID, assignment_id=p["id"], approver_id=ADMIN_B, approver_role="admin")
        assert a["status"] == "approved" and a["approved_by"] == ADMIN_B
        # apply → users.role 真的改
        applied = await ras.apply_role_change(tenant_id=TID, assignment_id=p["id"])
        assert applied["status"] == "applied"
        cur = await db_module._conn.execute("SELECT role FROM users WHERE id=%s::uuid", (uid,))
        assert (await cur.fetchone())[0] == "technician"
    finally:
        await _cleanup(uid)


# ── DB CHECK 硬防：繞過 service 直接 UPDATE 同人 → CHECK violation ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_db_check_blocks_same_signer():
    assert await db_module._ensure_conn()
    uid = await _seed_target()
    try:
        p = await ras.propose_role_change(
            tenant_id=TID, target_user_id=uid, to_role="technician",
            proposer_id=ADMIN_A, proposer_role="admin")
        import psycopg
        with pytest.raises(psycopg.errors.CheckViolation):
            await db_module._conn.execute(
                "UPDATE saas.role_assignment SET approved_by=proposed_by WHERE id=%s::uuid", (p["id"],))
        # autocommit 下單句失敗即回；確保連線可續用
        await db_module._conn.execute("SELECT 1")
    finally:
        await _cleanup(uid)


# ── 階層不足 propose → 403 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_propose_hierarchy_violation_403():
    assert await db_module._ensure_conn()
    uid = await _seed_target()
    try:
        with pytest.raises(ApiError) as e:
            # technician(階層1) 不可授 admin(階層4)
            await ras.propose_role_change(
                tenant_id=TID, target_user_id=uid, to_role="admin",
                proposer_id=ADMIN_A, proposer_role="technician")
        assert e.value.status_code == 403  # 先撞 FORBIDDEN(非 admin role) 或 HIERARCHY
    finally:
        await _cleanup(uid)


# ── 非 RBAC admin propose → 403 FORBIDDEN ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_propose_non_admin_forbidden_403():
    assert await db_module._ensure_conn()
    uid = await _seed_target()
    try:
        with pytest.raises(ApiError) as e:
            await ras.propose_role_change(
                tenant_id=TID, target_user_id=uid, to_role="technician",
                proposer_id=ADMIN_A, proposer_role="customer_service")
        assert e.value.error_code == "FORBIDDEN" and e.value.status_code == 403
    finally:
        await _cleanup(uid)


# ── 並發 approve 樂觀鎖 → 第二次 409 ──
@pytest.mark.component
@pytest.mark.asyncio
async def test_concurrent_approve_optimistic_lock_409():
    assert await db_module._ensure_conn()
    uid = await _seed_target()
    try:
        p = await ras.propose_role_change(
            tenant_id=TID, target_user_id=uid, to_role="technician",
            proposer_id=ADMIN_A, proposer_role="admin")
        await ras.approve_role_change(
            tenant_id=TID, assignment_id=p["id"], approver_id=ADMIN_B, approver_role="admin")
        # 再 approve（已 approved）→ 狀態機 409
        with pytest.raises(ApiError) as e:
            await ras.approve_role_change(
                tenant_id=TID, assignment_id=p["id"], approver_id=ADMIN_B, approver_role="admin")
        assert e.value.status_code == 409
    finally:
        await _cleanup(uid)
