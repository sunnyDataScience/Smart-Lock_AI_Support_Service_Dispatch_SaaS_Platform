"""Component tests for Conversations v2 tenant-scoped endpoints（CR-0003 P2-W2 / FR-0018）。

測試矩陣：
  1. GET /tenants/{tenantId}/conversations → 200 tenant-scoped list（cursor 分頁）
  2. GET /tenants/{tenantId}/conversations?status=active → 200 status 篩選
  3. POST /tenants/{tenantId}/conversations → 201 建立對話（Idempotency-Key）
  4. POST /tenants/{tenantId}/conversations（重複 session_id）→ 200 冪等
  5. GET /tenants/{tenantId}/conversations/{id} → 200 詳情
  6. GET /tenants/{tenantId}/conversations/{id} (not found) → 404
  7. GET /tenants/{tenantId}/conversations/{id}/messages → 200 訊息列表
  8. POST /tenants/{tenantId}/conversations/{id}/messages → 201（Idempotency-Key）
  9. cross-tenant guard → 403 CROSS_TENANT_READ / CROSS_TENANT_WRITE
 10. 未認證 → 401

注意：worktree 無真實 DB，component mark 測試在主 worktree 含 DB 的環境跑。
      此處確保 test 結構正確 + pytest.mark.component 標記完整。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import ADMIN_USER_ID, CUSTOMER_SERVICE_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_other_tenant_path_headers(
    role: str = "admin",
    token_tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT 屬於 DEFAULT_TENANT 但打 OTHER_TENANT path → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=token_tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


def _make_cs_headers() -> dict[str, str]:
    """customer_service 角色 headers（用於 sendChatMessage 測試）。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=CUSTOMER_SERVICE_USER_ID,
        role="customer_service",
        tenant_id=DEFAULT_TENANT_ID,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


# ---------------------------------------------------------------------------
# 1. GET /tenants/{tenantId}/conversations → 200 list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_conversations_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/conversations → 200 tenant-scoped list。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body
    assert isinstance(body["items"], list)


# ---------------------------------------------------------------------------
# 2. GET with status filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_conversations_v2_status_filter_200(client, admin_headers):
    """GET /tenants/{tenantId}/conversations?status=active → 200。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations?status=active",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body


# ---------------------------------------------------------------------------
# 3. POST /tenants/{tenantId}/conversations → 201 (Idempotency-Key)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_conversation_v2_201(client, admin_headers):
    """POST /tenants/{tenantId}/conversations → 201 建立對話（Idempotency-Key）。"""
    unique_session = f"test-session-{uuid.uuid4().hex}"
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations",
        headers={
            **admin_headers,
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "line_user_id": f"U{uuid.uuid4().hex[:32]}",
            "session_id": unique_session,
            "display_name": f"Test User {uuid.uuid4().hex[:6]}",
            "channel": "line",
        },
    )
    assert res.status_code in (200, 201), res.text
    body = res.json()
    assert "data" in body
    data = body["data"]
    assert "id" in data
    assert data["status"] in ("active", "waiting_human", "closed")


# ---------------------------------------------------------------------------
# 4. POST same session_id → 200 idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_conversation_v2_idempotent_200(client, admin_headers):
    """POST 相同 session_id 兩次 → 第二次 200（冪等）。"""
    shared_session = f"idem-session-{uuid.uuid4().hex}"
    line_user_id = f"U{uuid.uuid4().hex[:32]}"

    # 第一次建立
    res1 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "line_user_id": line_user_id,
            "session_id": shared_session,
            "display_name": "Idempotent User",
            "channel": "line",
        },
    )
    assert res1.status_code in (200, 201), res1.text

    # 第二次相同 session_id → 200（業務冪等）
    res2 = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "line_user_id": line_user_id,
            "session_id": shared_session,
            "display_name": "Idempotent User",
            "channel": "line",
        },
    )
    assert res2.status_code == 200, res2.text
    body2 = res2.json()
    assert "data" in body2


# ---------------------------------------------------------------------------
# 5. GET /tenants/{tenantId}/conversations/{id} → 200 detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_conversation_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/conversations/{id} → 200（先建立再取得）。"""
    # 先建立一個 conversation
    unique_session = f"get-test-{uuid.uuid4().hex}"
    create_res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "line_user_id": f"U{uuid.uuid4().hex[:32]}",
            "session_id": unique_session,
            "display_name": "Get Test User",
            "channel": "line",
        },
    )
    assert create_res.status_code in (200, 201), create_res.text
    conv_id = create_res.json()["data"]["id"]

    # 取得詳情
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "data" in body
    assert body["data"]["id"] == conv_id


# ---------------------------------------------------------------------------
# 6. GET conversation not found → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_conversation_v2_not_found_404(client, admin_headers):
    """GET 不存在的 conversation → 404。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{fake_id}",
        headers=admin_headers,
    )
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# 7. GET /tenants/{tenantId}/conversations/{id}/messages → 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_conversation_messages_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/conversations/{id}/messages → 200 訊息列表。"""
    # 先建立一個 conversation
    unique_session = f"msg-list-{uuid.uuid4().hex}"
    create_res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "line_user_id": f"U{uuid.uuid4().hex[:32]}",
            "session_id": unique_session,
            "display_name": "Message List User",
            "channel": "line",
        },
    )
    assert create_res.status_code in (200, 201), create_res.text
    conv_id = create_res.json()["data"]["id"]

    # 取得訊息列表（新建對話應為空列表）
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}/messages",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body
    assert isinstance(body["items"], list)


# ---------------------------------------------------------------------------
# 8. POST /tenants/{tenantId}/conversations/{id}/messages → 201
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_chat_message_v2_requires_escalated(client, admin_headers):
    """POST .../messages → 409 對話未升級（新建對話為 active，非 waiting_human）。"""
    unique_session = f"send-msg-{uuid.uuid4().hex}"
    create_res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "line_user_id": f"U{uuid.uuid4().hex[:32]}",
            "session_id": unique_session,
            "display_name": "Send Msg User",
            "channel": "line",
        },
    )
    assert create_res.status_code in (200, 201), create_res.text
    conv_id = create_res.json()["data"]["id"]

    # 新建對話狀態為 active，非 waiting_human → 409
    cs_headers = _make_cs_headers()
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{conv_id}/messages",
        headers={**cs_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"content": "Hello from agent"},
    )
    assert res.status_code == 409, res.text


# ---------------------------------------------------------------------------
# 9. cross-tenant guard → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_conversations_v2_cross_tenant_403(client):
    """cross-tenant：JWT claim tenant ≠ path tenantId → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers(token_tenant_id=DEFAULT_TENANT_ID)
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/conversations",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


@pytest.mark.asyncio
async def test_get_conversation_v2_cross_tenant_403(client):
    """cross-tenant getConversation → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers(token_tenant_id=DEFAULT_TENANT_ID)
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/conversations/{fake_id}",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


@pytest.mark.asyncio
async def test_list_messages_v2_cross_tenant_403(client):
    """cross-tenant listConversationMessages → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers(token_tenant_id=DEFAULT_TENANT_ID)
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/conversations/{fake_id}/messages",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


@pytest.mark.asyncio
async def test_create_conversation_v2_cross_tenant_403(client):
    """cross-tenant createConversation → 403 CROSS_TENANT_WRITE。"""
    headers = _make_other_tenant_path_headers(token_tenant_id=DEFAULT_TENANT_ID)
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/conversations",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "line_user_id": f"U{uuid.uuid4().hex[:32]}",
            "session_id": f"cross-tenant-{uuid.uuid4().hex}",
            "channel": "line",
        },
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


@pytest.mark.asyncio
async def test_send_message_v2_cross_tenant_403(client):
    """cross-tenant sendChatMessage → 403 CROSS_TENANT_WRITE。"""
    headers = _make_other_tenant_path_headers(token_tenant_id=DEFAULT_TENANT_ID)
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/conversations/{fake_id}/messages",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"content": "Should fail"},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# 10. 未認證 → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_conversations_v2_unauthenticated_401(client):
    """無 Authorization header → 401。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations",
    )
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_get_conversation_v2_unauthenticated_401(client):
    """GET conversation 無 Authorization header → 401。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/conversations/{fake_id}",
    )
    assert res.status_code == 401, res.text
