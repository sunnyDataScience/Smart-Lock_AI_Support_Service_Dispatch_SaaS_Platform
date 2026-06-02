"""Component tests — M15 Exceptions inbox/approve v2 tenant-scoped（CR-0003 P2）。

測試矩陣：
  1. GET /tenants/{tenantId}/exceptions:inbox → 200 tenant-scoped inbox（或 503/404 無 DB）
  2. POST /tenants/{tenantId}/exceptions/{id}:approve（decision=approve，Idempotency-Key）→ 200/404/503
  3. POST /tenants/{tenantId}/exceptions/{id}:approve（decision=reject，Idempotency-Key）→ 200/404/503
  4. cross-tenant GET guard → 403 CROSS_TENANT_READ
  5. cross-tenant POST guard → 403 CROSS_TENANT_WRITE

注意：無真實 DB 時 200 路徑會回 503（DB unavailable）或 404（not found）；
      測試重點在結構正確性與 cross-tenant 403 的 early-return，與 DB 無關。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.unit

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cross_tenant_headers(
    role: str = "admin",
    own_tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT claim 屬 own_tenant，但打 OTHER_TENANT path → cross-tenant guard 觸發。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=own_tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": own_tenant_id,
    }


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/exceptions:inbox
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_exceptions_inbox_200(client, admin_headers):
    """GET inbox → 200 有效回應（含 items key）；無 DB 時接受 503。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/exceptions:inbox",
        headers=admin_headers,
    )
    # 無 DB 時可能 503；重點：不應是 403 或 422
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "items" in body


@pytest.mark.asyncio
async def test_list_exceptions_inbox_cross_tenant_403(client):
    """cross-tenant GET：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/exceptions:inbox",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# POST /tenants/{tenantId}/exceptions/{exceptionId}:approve（decision=approve）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_exception_approve_decision(client, admin_headers):
    """POST :approve（decision=approve，Idempotency-Key）→ 200/404/503（不應是 403/422）。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/exceptions/{fake_id}:approve",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve", "note": "核准備註"},
    )
    # 無 DB 時：503（DB unavailable）或 404（schedule request not found）
    assert res.status_code in (200, 404, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert body.get("status") == "approved"


@pytest.mark.asyncio
async def test_approve_exception_reject_decision(client, admin_headers):
    """POST :approve（decision=reject，Idempotency-Key）→ 200/404/503（不應是 403/422）。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/exceptions/{fake_id}:approve",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "reject", "note": "拒絕原因"},
    )
    assert res.status_code in (200, 404, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert body.get("status") == "rejected"


# ---------------------------------------------------------------------------
# POST cross-tenant guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_exception_cross_tenant_403(client):
    """cross-tenant POST：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_WRITE。"""
    headers = _make_cross_tenant_headers()
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/exceptions/{fake_id}:approve",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"decision": "approve"},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"
