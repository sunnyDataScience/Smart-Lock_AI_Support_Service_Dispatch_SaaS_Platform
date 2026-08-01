"""客服手動接管對話（active → escalated）。業主 2026-08-01 卡住事故的自救手段。

**為什麼需要這支**：在此之前，全系統把 `conversations.status` 寫成 `escalated` 的地方
只有一處 —— AI 呼叫 transfer_to_human 之後由 `problem_card_service.escalation_to_draft_pc`
（:952）連帶翻的。也就是說 **AI 那條路一旦沒走成，客服在 UI 上零復原手段**。

而客服發訊框的開關是 `conv.status === "waiting_human"` 嚴格比對
（brand-portal `conversations/[id]/page.tsx`），狀態沒翻＝誰都回不了那位客人的 LINE，
對話也結不掉。業主 2026-08-01 就是這樣：AI 回了「幫您轉接給真人專員」，
DB 狀態卻仍是 `active`（prod 實測 escalated 79 / active 6，該對話是那 6 之一）。

本檔釘住狀態機兩個方向都補齊：
    active ──request-handover──▶ escalated ──resolve-handover──▶ active

以及三條負向：非 active 不得被翻、已接管重複呼叫要 409（而非靜默成功）、越權 403。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def _seed_conversation(status: str = "active") -> str:
    """建一筆屬於預設租戶的對話。conversations.user_id → users.tenant_id 決定歸屬。"""
    assert await db_module._ensure_conn(), "需要真實 DB 連線（scratch 庫）"
    conn = db_module._conn
    user_id, conv_id = str(uuid.uuid4()), str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO users (id, tenant_id, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, 'x', 'customer', TRUE) ON CONFLICT (id) DO NOTHING",
        (user_id, DEFAULT_TENANT_ID, f"handover-{user_id[:8]}@example.com"),
    )
    await conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status, channel) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, 'line') ON CONFLICT (id) DO NOTHING",
        (conv_id, user_id, f"sess-{conv_id[:8]}", status),
    )
    return conv_id


def _path(conv_id: str, action: str) -> str:
    return f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}/{action}"


async def _db_status(conv_id: str) -> str:
    cur = await db_module._conn.execute(
        "SELECT status FROM conversations WHERE id = %s::uuid", (conv_id,)
    )
    return (await cur.fetchone())[0]


async def test_customer_service_can_take_over_active_conversation(client, admin_headers):
    """核心：active 對話可被客服接管，DB 狀態確實翻成 escalated。"""
    conv_id = await _seed_conversation("active")
    r = await client.post(_path(conv_id, "request-handover"), headers=admin_headers)
    assert r.status_code == 200, r.text
    assert await _db_status(conv_id) == "escalated", "DB 沒翻＝客服還是回不了訊息"


async def test_round_trip_take_over_then_hand_back(client, admin_headers):
    """兩個方向要對稱：接管後能交還，交還後回到 active（AI 恢復接待）。"""
    conv_id = await _seed_conversation("active")
    assert (await client.post(_path(conv_id, "request-handover"), headers=admin_headers)).status_code == 200
    assert await _db_status(conv_id) == "escalated"
    assert (await client.post(_path(conv_id, "resolve-handover"), headers=admin_headers)).status_code == 200
    assert await _db_status(conv_id) == "active"


async def test_already_escalated_returns_409_not_silent_success(client, admin_headers):
    """已在接管中要 409 —— 呼叫端得能分辨「我翻的」與「本來就翻了」。"""
    conv_id = await _seed_conversation("escalated")
    r = await client.post(_path(conv_id, "request-handover"), headers=admin_headers)
    assert r.status_code == 409, r.text
    assert await _db_status(conv_id) == "escalated", "409 不得順手改狀態"


async def test_closed_conversation_cannot_be_escalated(client, admin_headers):
    """已結束的對話不得被翻回接管中（避免誤開已結案的案子）。"""
    conv_id = await _seed_conversation("closed")
    r = await client.post(_path(conv_id, "request-handover"), headers=admin_headers)
    assert r.status_code == 409, r.text
    assert await _db_status(conv_id) == "closed"


async def test_unknown_conversation_404(client, admin_headers):
    r = await client.post(_path(str(uuid.uuid4()), "request-handover"), headers=admin_headers)
    assert r.status_code == 404


async def test_technician_cannot_take_over(client, technician_headers):
    """越權：技師不是客服，不得接管對話（權限比照 resolve-handover）。"""
    conv_id = await _seed_conversation("active")
    r = await client.post(_path(conv_id, "request-handover"), headers=technician_headers)
    assert r.status_code == 403, r.text
    assert await _db_status(conv_id) == "active", "被拒絕就不該留下副作用"
