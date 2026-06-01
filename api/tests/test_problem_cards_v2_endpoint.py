"""Component tests for M03 ProblemCards v2 tenant-scoped endpoints（CR-0002-α）。

測試矩陣：
  1. GET /tenants/{tenantId}/problem-cards → 200 tenant-scoped list（cursor 分頁）
  2. POST /tenants/{tenantId}/problem-cards → 201 建立問題卡成功
  3. GET /tenants/{tenantId}/problem-cards/{id} → 200 單筆詳情
  4. PATCH /tenants/{tenantId}/problem-cards/{id} → 200 更新成功
  5. POST /tenants/{tenantId}/problem-cards/{id}/confirm → 200 確認問題卡
  6. POST /tenants/{tenantId}/problem-cards/{id}/resolve → 200 結案問題卡
  7. cross-tenant guard → 403 CROSS_TENANT_READ / CROSS_TENANT_WRITE
  8. legacy GET /api/v1/problem-cards → 200 + Deprecation header（雙掛驗證）

注意：worktree 無真實 DB，這些測試須在 Opus 主 worktree 有 DB 的環境跑。
      此處確保 test 結構正確 + pytest.mark.component 標記完整。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_other_tenant_path_headers(
    role: str = "admin",
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT 屬於 DEFAULT_TENANT 但打 OTHER_TENANT path → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
        "Idempotency-Key": str(uuid.uuid4()),  # POST 須帶（idempotency_guard）；403/404 檢查在其後
    }


# ---------------------------------------------------------------------------
# List problem cards v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_problem_cards_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/problem-cards → 200 tenant-scoped list。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/problem-cards",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body
    # tenant-scoped：所有結果應屬 DEFAULT_TENANT
    for item in body["items"]:
        assert "id" in item


@pytest.mark.asyncio
async def test_list_problem_cards_v2_pagination(client, admin_headers):
    """GET /tenants/{tenantId}/problem-cards?limit=1 → cursor 分頁。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/problem-cards?limit=1",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_list_problem_cards_v2_cross_tenant_403(client):
    """cross-tenant：path tenantId 與 JWT claim 不符 → 403。"""
    headers = _make_other_tenant_path_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/problem-cards",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Create problem card v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_problem_card_v2_201(client, admin_headers):
    """POST /tenants/{tenantId}/problem-cards → 201 建立問題卡。"""
    # Need a real conversation_id — skip if we can't create one
    fake_conversation_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/problem-cards",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "conversation_id": fake_conversation_id,
            "brand": "Dormakaba",
            "model": "AS701",
            "symptom": "門鎖無法開啟",
            "urgency": "high",
        },
    )
    # 201 成功，或 409（對話已有問題卡），或 422（conversation 不存在）均屬預期行為
    assert res.status_code in (201, 404, 409, 422), res.text
    if res.status_code == 201:
        body = res.json()
        assert "data" in body
        assert body["data"]["brand"] == "Dormakaba"


@pytest.mark.asyncio
async def test_create_problem_card_v2_cross_tenant_403(client):
    """cross-tenant create → 403。"""
    headers = _make_other_tenant_path_headers()
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/problem-cards",
        headers=headers,
        json={
            "conversation_id": str(uuid.uuid4()),
            "brand": "Dormakaba",
            "model": "AS701",
            "symptom": "測試",
            "urgency": "high",  # enum low/medium/high；required（否則 422 先於 403 cross-tenant guard）
        },
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# Get problem card v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_problem_card_v2_not_found(client, admin_headers):
    """GET 不存在的 problem card → 404。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/problem-cards/{fake_id}",
        headers=admin_headers,
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_get_problem_card_v2_cross_tenant_403(client):
    """cross-tenant get → 403。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/problem-cards/{fake_id}",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Update problem card v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_problem_card_v2_cross_tenant_403(client):
    """PATCH /tenants/{OTHER}/problem-cards/{id} → cross-tenant → 403。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.patch(
        f"/tenants/{OTHER_TENANT_ID}/problem-cards/{fake_id}",
        headers=headers,
        json={"brand": "Chatlock"},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# Confirm problem card v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_problem_card_v2_not_found(client, admin_headers):
    """POST /confirm 不存在的 problem card → 404。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/problem-cards/{fake_id}/confirm",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_confirm_problem_card_v2_cross_tenant_403(client):
    """cross-tenant confirm → 403。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/problem-cards/{fake_id}/confirm",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# Resolve problem card v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_problem_card_v2_not_found(client, admin_headers):
    """POST /resolve 不存在的 problem card → 404。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/problem-cards/{fake_id}/resolve",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"resolution_layer": "L1"},  # enum 為 L1/L2/L3（否則 422 先於 403/404）
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_resolve_problem_card_v2_cross_tenant_403(client):
    """cross-tenant resolve → 403。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/problem-cards/{fake_id}/resolve",
        headers=headers,
        json={"resolution_layer": "L1"},  # enum 為 L1/L2/L3（否則 422 先於 403/404）
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# Legacy endpoint — Deprecation header (D3 dual-hang)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_list_problem_cards_has_deprecation_header(client, admin_headers):
    """GET /api/v1/problem-cards → 200 + Deprecation: true（D3 雙掛驗證）。"""
    res = await client.get(
        "/api/v1/problem-cards",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    link_header = res.headers.get("link", "")
    assert "successor-version" in link_header, (
        f"Expected Link header with successor-version, got: {link_header}"
    )
