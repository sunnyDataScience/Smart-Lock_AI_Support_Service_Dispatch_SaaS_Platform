"""Component tests for M12 settlements v2 tenant-scoped endpoint（FR-0012 / CR-0003 P2）。

spec path: POST /tenants/{tenantId}/settlements/monthly → triggerMonthlySettlement

測試矩陣：
  TC-1: POST monthly 帶 Idempotency-Key → 501 NOT_IMPLEMENTED（Phase II stub 驗證）
  TC-2: cross-tenant guard → 403 CROSS_TENANT_WRITE
  TC-3: 無 auth → 401 UNAUTHENTICATED

注意：
  - @pytest.mark.component — 需 live DB（dev 環境）+ JWT service 正常。
  - 501 stub 不依賴 DB 資料，TC-1 在無 DB 環境也能跑（auth layer 需 JWT secret）。
  - cross-tenant guard 在 service 呼叫前觸發，無需 DB 資料。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _path(tenant_id: str = DEFAULT_TENANT_ID) -> str:
    return f"/tenants/{tenant_id}/settlements/monthly"


def _make_cross_tenant_headers(
    role: str = "admin",
    jwt_tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT 屬於 DEFAULT_TENANT 但打 OTHER_TENANT path → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=jwt_tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


# ---------------------------------------------------------------------------
# TC-1: POST monthly 帶 Idempotency-Key → 501 NOT_IMPLEMENTED（stub）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_monthly_settlement_501_stub(client, admin_headers):
    """POST /tenants/{tenantId}/settlements/monthly 帶 Idempotency-Key → 501 NOT_IMPLEMENTED。

    Phase II stub：服務層尚未實作，預期永遠回 501。
    """
    headers = dict(admin_headers)
    headers["Idempotency-Key"] = str(uuid.uuid4())

    res = await client.post(_path(), headers=headers)
    assert res.status_code == 501, f"Expected 501 stub, got {res.status_code}: {res.text}"

    body = res.json()
    assert body.get("error_code") == "NOT_IMPLEMENTED", (
        f"Expected error_code=NOT_IMPLEMENTED, got: {body}"
    )
    # RFC7807-friendly body 驗證
    assert body.get("status") == 501
    assert "detail" in body or "message" in body


# ---------------------------------------------------------------------------
# TC-2: cross-tenant guard → 403 CROSS_TENANT_WRITE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_monthly_settlement_cross_tenant_403(client):
    """JWT tenant != path tenantId → 403 CROSS_TENANT_WRITE（cross-tenant guard，ADR-0030）。"""
    headers = _make_cross_tenant_headers()
    headers["Idempotency-Key"] = str(uuid.uuid4())

    res = await client.post(
        _path(tenant_id=OTHER_TENANT_ID),
        headers=headers,
    )
    assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE", (
        f"Expected CROSS_TENANT_WRITE, got: {body}"
    )


# ---------------------------------------------------------------------------
# TC-3: 無 auth → 401 UNAUTHENTICATED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_monthly_settlement_no_auth_401(client):
    """無 Bearer token → 401 UNAUTHENTICATED（require_tenant guard）。"""
    res = await client.post(_path())
    assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.text}"
    body = res.json()
    assert body.get("error_code") == "UNAUTHENTICATED"
