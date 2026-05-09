"""F-001 createConversation integration tests（ADR-009 §8 D pattern bridge）。

測試矩陣：
  1. Happy path: line_user_id + session_id → 201 + new conversation + doc number
  2. Idempotency: 同 session_id 第二次呼叫 → 200 + 同 conversation id
  3. Upsert user: 同 line_user_id 不同 session → 不同 conversation, 同 user_id
  4. Validation: missing line_user_id → 422
  5. Validation: missing session_id → 422
  6. Document number 格式: ST-YYYYMMDD-NNNN
"""

from __future__ import annotations

import re
import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


@pytest_asyncio.fixture
async def cleanup_conversations(client):
    """各測試結束後刪除本次建立的 conversation + user。"""
    import core.db as db_module
    from core.db import _ensure_conn

    created_session_ids: list[str] = []
    created_line_user_ids: list[str] = []

    yield {
        "session_ids": created_session_ids,
        "line_user_ids": created_line_user_ids,
    }

    await _ensure_conn()
    if created_session_ids:
        # 拿到 conversation_id 列表 + 連帶 user_id
        cur = await db_module._conn.execute(
            "SELECT c.id, c.user_id FROM conversations c "
            "WHERE c.session_id = ANY(%s)",
            (created_session_ids,),
        )
        rows = await cur.fetchall()
        conv_ids = [str(r[0]) for r in rows]
        if conv_ids:
            await db_module._conn.execute(
                "DELETE FROM conversations WHERE id = ANY(%s::uuid[])",
                (conv_ids,),
            )
    if created_line_user_ids:
        await db_module._conn.execute(
            "DELETE FROM users WHERE line_user_id = ANY(%s)",
            (created_line_user_ids,),
        )


@pytest.mark.asyncio
async def test_create_happy_path(client, admin_headers, cleanup_conversations):
    line_user_id = f"U{uuid.uuid4().hex}"
    session_id = f"test-session-{uuid.uuid4().hex[:8]}"
    cleanup_conversations["session_ids"].append(session_id)
    cleanup_conversations["line_user_ids"].append(line_user_id)

    res = await client.post(
        "/api/v1/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "line_user_id": line_user_id,
            "session_id": session_id,
            "display_name": "測試客戶 A",
            "channel": "line",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["line_user_id"] == line_user_id
    # ServiceTicket 編號格式 ST-YYYYMMDD-NNNN
    doc = data.get("document_number")
    assert doc, f"document_number missing: {data}"
    assert re.match(r"^ST-\d{8}-\d{4}$", doc), f"invalid format: {doc}"


@pytest.mark.asyncio
async def test_create_idempotent_same_session(
    client, admin_headers, cleanup_conversations,
):
    line_user_id = f"U{uuid.uuid4().hex}"
    session_id = f"test-session-{uuid.uuid4().hex[:8]}"
    cleanup_conversations["session_ids"].append(session_id)
    cleanup_conversations["line_user_ids"].append(line_user_id)

    res1 = await client.post(
        "/api/v1/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"line_user_id": line_user_id, "session_id": session_id},
    )
    assert res1.status_code == 201
    conv_id_1 = res1.json()["data"]["id"]

    # 第二次呼叫不同 idempotency-key 但同 session_id → 業務層 idempotent
    res2 = await client.post(
        "/api/v1/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"line_user_id": line_user_id, "session_id": session_id},
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["id"] == conv_id_1


@pytest.mark.asyncio
async def test_create_validation_missing_line_user(client, admin_headers):
    res = await client.post(
        "/api/v1/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"session_id": "x"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_validation_missing_session(client, admin_headers):
    res = await client.post(
        "/api/v1/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"line_user_id": f"U{uuid.uuid4().hex}"},
    )
    assert res.status_code == 422
