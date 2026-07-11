"""CR-0150:requote v+1 分層核可+item_diffs 收緊(ADR-027 Decision 3/16_API:397)。

delta=|v+1 總額 − v 總額|:≤2000 小編(OPS)執行送出即核可;>2000 僅
operations_manager/admin 可送(403 REQUOTE_SUPERVISOR_REQUIRED)。
非 requote(無 supersedes)不受分層影響。item_diffs 空陣列/缺省 → 422。
"""

from __future__ import annotations

import os
import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"
SEED_TECH = "77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01"


async def _mk_wo() -> tuple[str, str]:
    assert await db_module._ensure_conn()
    wid, pid = str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, brand, model, status) "
        "VALUES (%s::uuid, %s, 'Chatlock', 'A90', 'confirmed')", (pid, TID))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, technician_id, customer_address, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, 'in_progress', %s::uuid, '台北市測試路1號', %s::uuid)",
        (wid, pid, SEED_TECH, TID))
    return wid, pid


async def _mk_requote_pair(wid: str, pid: str, *, v1_total: float, v2_total: float) -> str:
    """建 v1(sent)+v2(draft,supersedes v1)報價對;回 v2 quote id。"""
    q1, q2 = str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO quote (id, tenant_id, problem_card_id, work_order_id, state, version, total_amount) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 'sent', 1, %s)",
        (q1, TID, pid, wid, v1_total))
    await db_module._conn.execute(
        "INSERT INTO quote (id, tenant_id, problem_card_id, work_order_id, state, version, "
        "total_amount, supersedes_quote_id) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 'draft', 2, %s, %s::uuid)",
        (q2, TID, pid, wid, v2_total, q1))
    return q2


async def _cleanup(wid: str, pid: str) -> None:
    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute("DELETE FROM quote WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM requote_requests WHERE work_order_id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id=%s::uuid", (wid,))
    await db_module._conn.execute("DELETE FROM quote WHERE problem_card_id=%s::uuid", (pid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (pid,))


# 註:router 層 :send 現行 RBAC=admin/operations_manager(CR-0130 收斂,比分層
# 更嚴)——「小編核可 501-2000」在 API 面暫不可行使;分層 gate 於 service 層
# 落地作縱深防禦(actor_role 直驗),若業主日後開放 customer_service 送修正單
# (RBAC 擴權屬另案裁決),gate 即時生效。API 面以 ops_manager 驗通過路徑。


@pytest.mark.asyncio
async def test_delta_over_2000_editor_403_supervisor_ok(
    client, secondary_admin_headers,
):
    """delta=2500:service 層小編角色 403;API 面 ops_manager 送成功。"""
    from core.errors import ApiError
    from services import quote_engine_service as qe

    wid, pid = await _mk_wo()
    try:
        q2 = await _mk_requote_pair(wid, pid, v1_total=3000, v2_total=5500)

        # service 層:小編角色(customer_service)觸發分層 403
        with pytest.raises(ApiError) as ei:
            await qe.transition(tenant_id=TID, quote_id=q2, action="send",
                                actor_role="customer_service")
        assert ei.value.error_code == "REQUOTE_SUPERVISOR_REQUIRED"
        assert ei.value.status_code == 403

        # legacy 呼叫端未帶 actor_role → fail-closed 同 403
        with pytest.raises(ApiError) as ei2:
            await qe.transition(tenant_id=TID, quote_id=q2, action="send")
        assert ei2.value.error_code == "REQUOTE_SUPERVISOR_REQUIRED"

        # API 面:主管(operations_manager)可送
        r = await client.post(
            f"/tenants/{TID}/quotes/{q2}:send",
            headers={**secondary_admin_headers, "Idempotency-Key": str(uuid.uuid4())})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["state"] == "sent"
    finally:
        await _cleanup(wid, pid)


@pytest.mark.asyncio
async def test_delta_within_editor_tier_cs_can_send():
    """delta=1500(501-2000 小編層):service 層 customer_service 執行送出即核可。"""
    from services import quote_engine_service as qe

    wid, pid = await _mk_wo()
    try:
        q2 = await _mk_requote_pair(wid, pid, v1_total=3000, v2_total=4500)
        out = await qe.transition(tenant_id=TID, quote_id=q2, action="send",
                                  actor_role="customer_service")
        assert out["state"] == "sent"
    finally:
        await _cleanup(wid, pid)


@pytest.mark.asyncio
async def test_non_requote_send_unaffected(client, secondary_admin_headers):
    """無 supersedes 串鏈的一般報價:分層核可不介入(既有行為不變)。"""
    wid, pid = await _mk_wo()
    try:
        q = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO quote (id, tenant_id, problem_card_id, work_order_id, state, version, total_amount) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 'draft', 1, 9000)",
            (q, TID, pid, wid))
        r = await client.post(
            f"/tenants/{TID}/quotes/{q}:send",
            headers={**secondary_admin_headers, "Idempotency-Key": str(uuid.uuid4())})
        assert r.status_code == 200, r.text
    finally:
        await _cleanup(wid, pid)


@pytest.mark.asyncio
async def test_item_diffs_required_non_empty(client, monkeypatch, technician_headers):
    """item_diffs 空陣列/缺省 → 422(internal 與 browser 兩入口)。"""
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")
    hdr = {"X-Internal-Token": "test-internal-token"}
    base = {"request_id": f"rq-{uuid.uuid4().hex[:8]}", "work_order_id": str(uuid.uuid4()),
            "technician_id": SEED_TECH, "reason": "scope_add"}

    r1 = await client.post("/internal/requote-requests",
                           json={**base, "item_diffs": []}, headers=hdr)
    assert r1.status_code == 422, r1.text
    r2 = await client.post("/internal/requote-requests", json=base, headers=hdr)
    assert r2.status_code == 422, r2.text

    r3 = await client.post(
        f"/tenants/{TID}/work-orders/{uuid.uuid4()}/requote-requests",
        json={"reason": "scope_add", "item_diffs": []}, headers=technician_headers)
    assert r3.status_code == 422, r3.text
