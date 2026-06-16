"""CR-0024 Phase 1 — 對話 handover 生命週期測試。

涵蓋：
- POST resolve-handover：escalated → active（happy path）
- resolve-handover 非 escalated → 409
- resolve-handover RBAC：technician → 403
- resolve-handover cross-tenant → 403
- internal handover-state GET：escalated 對話回 escalated=true、查無對話回 false
- WO 結案連動：完成關聯工單 → 對話 escalated → active

注意：需真實 DB（component mark），在主 worktree 含 DB 環境跑。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"
_INTERNAL_TOKEN = "test-internal-token-cr0024"


async def _make_escalated_conv() -> tuple[str, str]:
    """經 escalation_to_draft_pc 建一個 escalated 對話，回 (conv_id, session_id)。"""
    from services import problem_card_service

    uid = f"Uho-{uuid.uuid4().hex[:10]}"
    session_id = f"{DEFAULT_TENANT_ID}:{uid}"
    result = await problem_card_service.escalation_to_draft_pc(
        tenant_id=DEFAULT_TENANT_ID,
        line_user_id=uid,
        session_id=session_id,
        reason="客人要求真人協助 Yale 鎖故障",
        is_explicit=True,
        facts_snapshot={"user_input_excerpt": "我的 Yale 鎖打不開"},
    )
    return result["conversation_id"], session_id


# --------------------------- resolve-handover ---------------------------


@pytest.mark.asyncio
async def test_resolve_handover_escalated_to_active(client, customer_service_headers):
    conv_id, _ = await _make_escalated_conv()
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}/resolve-handover",
        headers=customer_service_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "active"


@pytest.mark.asyncio
async def test_resolve_handover_not_escalated_409(client, customer_service_headers):
    """已 active 的對話再結束接管 → 409（沒有接管可結束）。"""
    conv_id, _ = await _make_escalated_conv()
    # 先交還一次 → active
    r1 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}/resolve-handover",
        headers=customer_service_headers,
    )
    assert r1.status_code == 200
    # 再交還 → 409
    r2 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}/resolve-handover",
        headers=customer_service_headers,
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["error_code"] == "CONVERSATION_NOT_ESCALATED"


@pytest.mark.asyncio
async def test_resolve_handover_rbac_403(client, technician_headers):
    conv_id, _ = await _make_escalated_conv()
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}/resolve-handover",
        headers=technician_headers,
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_resolve_handover_cross_tenant_403(client, customer_service_headers):
    conv_id, _ = await _make_escalated_conv()
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/conversations/{conv_id}/resolve-handover",
        headers=customer_service_headers,
    )
    assert res.status_code == 403, res.text


# --------------------------- internal handover-state ---------------------------


@pytest.mark.asyncio
async def test_handover_state_escalated_true(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", _INTERNAL_TOKEN)
    _, session_id = await _make_escalated_conv()
    res = await client.get(
        "/api/v1/internal/conversations/handover-state",
        params={"tenant_id": DEFAULT_TENANT_ID, "session_id": session_id},
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["escalated"] is True
    assert data["reason"]  # 取得草擬卡症狀摘要


@pytest.mark.asyncio
async def test_handover_state_unknown_conv_false(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", _INTERNAL_TOKEN)
    res = await client.get(
        "/api/v1/internal/conversations/handover-state",
        params={
            "tenant_id": DEFAULT_TENANT_ID,
            "session_id": f"{DEFAULT_TENANT_ID}:Unknown-{uuid.uuid4().hex[:8]}",
        },
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["escalated"] is False


@pytest.mark.asyncio
async def test_handover_state_after_resolve_false(client, customer_service_headers, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", _INTERNAL_TOKEN)
    conv_id, session_id = await _make_escalated_conv()
    await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}/resolve-handover",
        headers=customer_service_headers,
    )
    res = await client.get(
        "/api/v1/internal/conversations/handover-state",
        params={"tenant_id": DEFAULT_TENANT_ID, "session_id": session_id},
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert res.json()["data"]["escalated"] is False


# --------------------------- WO 結案連動 ---------------------------


@pytest.mark.asyncio
async def test_wo_completion_unescalates_linked_conversation(client):
    """完成關聯工單 → 連動把對話 escalated → active（D2-b，fail-soft helper）。"""
    import core.db as db_module
    from services import conversation_service, work_order_service

    conv_id, _ = await _make_escalated_conv()
    # 取該對話的草擬問題卡 id
    cur = await db_module._conn.execute(
        "SELECT id FROM problem_cards WHERE conversation_id = %s::uuid LIMIT 1",
        (conv_id,),
    )
    pc_id = str((await cur.fetchone())[0])
    # 插一張關聯工單（最小欄位）
    ins = await db_module._conn.execute(
        "INSERT INTO work_orders (problem_card_id, status) "
        "VALUES (%s::uuid, 'in_progress') RETURNING id",
        (pc_id,),
    )
    wo_id = str((await ins.fetchone())[0])

    await work_order_service._unescalate_linked_conversation(
        tenant_id=DEFAULT_TENANT_ID, wo_id=wo_id
    )

    conv = await conversation_service.get_conversation(
        tenant_id=DEFAULT_TENANT_ID, conv_id=conv_id
    )
    assert conv["status"] == "active", conv
