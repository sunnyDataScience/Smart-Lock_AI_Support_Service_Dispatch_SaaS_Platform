"""CR-0152:ADR-025 報價 AI 雙閘(server-side enforce,掛既有 quote_v2 :send)。

①actor_role=ai_agent → 403 AI_FORBIDDEN_FINAL_QUOTE(永不可送最終報價);
②保固案件(warranty_claims 關聯)僅人類 staff 可送——AI/未帶角色 fail-closed
403 AI_FORBIDDEN_WARRANTY_PROJECT;③人類 staff 送保固案件正常。
router RBAC(admin/ops_manager)為第一層,本 gate 為 service 層縱深防禦。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import quote_engine_service as qe

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"
SEED_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01"


async def _mk_quote(*, warranty: bool = False) -> tuple[str, str, str]:
    assert await db_module._ensure_conn()
    wid, pid, qid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, brand, model, status) "
        "VALUES (%s::uuid, %s, 'Chatlock', 'A90', 'confirmed')", (pid, TID))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, technician_id, customer_address, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, 'in_progress', %s::uuid, '台北市測試路1號', %s::uuid)",
        (wid, pid, SEED_TECH, TID))
    await db_module._conn.execute(
        "INSERT INTO quote (id, tenant_id, problem_card_id, work_order_id, state, version, total_amount) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 'draft', 1, 800)",
        (qid, TID, pid, wid))
    if warranty:
        # customer_id FK → users;借 seed admin(test@lock-ai.com)滿足 NOT NULL
        urow = await (await db_module._conn.execute(
            "SELECT id FROM users LIMIT 1")).fetchone()
        await db_module._conn.execute(
            "INSERT INTO warranty_claims (id, work_order_id, customer_id, device_brand, "
            "device_model, warranty_start_date, warranty_end_date, claim_date, "
            "is_within_warranty, warranty_start_mode, warranty_period_months, "
            "warranty_scope, warranty_inherit_from_site_group) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, 'Chatlock', 'A90', "
            "CURRENT_DATE - 30, CURRENT_DATE + 335, CURRENT_DATE, TRUE, "
            "'purchase_date', 12, 'device', FALSE)",
            (str(uuid.uuid4()), wid, urow[0]))
    return wid, pid, qid


async def _cleanup(wid: str, pid: str) -> None:
    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute("DELETE FROM warranty_claims WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM quote WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM quote WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))


@pytest.mark.asyncio
async def test_ai_agent_never_sends_final_quote():
    wid, pid, qid = await _mk_quote()
    try:
        with pytest.raises(ApiError) as ei:
            await qe.transition(tenant_id=TID, quote_id=qid, action="send",
                                actor_role="ai_agent")
        assert ei.value.error_code == "AI_FORBIDDEN_FINAL_QUOTE"
        assert ei.value.status_code == 403
    finally:
        await _cleanup(wid, pid)


@pytest.mark.asyncio
async def test_warranty_case_fail_closed_for_non_staff():
    wid, pid, qid = await _mk_quote(warranty=True)
    try:
        # 未帶角色(legacy/自動化路徑)→ fail-closed
        with pytest.raises(ApiError) as ei:
            await qe.transition(tenant_id=TID, quote_id=qid, action="send")
        assert ei.value.error_code == "AI_FORBIDDEN_WARRANTY_PROJECT"
        # ai_agent 在雙閘第一關就擋
        with pytest.raises(ApiError) as ei2:
            await qe.transition(tenant_id=TID, quote_id=qid, action="send",
                                actor_role="ai_agent")
        assert ei2.value.error_code == "AI_FORBIDDEN_FINAL_QUOTE"
    finally:
        await _cleanup(wid, pid)


@pytest.mark.asyncio
async def test_warranty_case_human_staff_can_send(client, secondary_admin_headers):
    wid, pid, qid = await _mk_quote(warranty=True)
    try:
        r = await client.post(f"/tenants/{TID}/quotes/{qid}:send",
                              headers=secondary_admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["state"] == "sent"
    finally:
        await _cleanup(wid, pid)
