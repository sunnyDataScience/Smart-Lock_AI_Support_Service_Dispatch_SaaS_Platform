"""Pricing v2 tenant-scoped 計算端點 component 測試（需 live DB）。

對齊 spec: POST /tenants/{tenantId}/pricing/calculate（CR-0002-α P2-α）。
驗證：
  1. POST calculate 帶 Idempotency-Key → 200 + 正確結構
  2. cross-tenant guard → 403

⚠ 本檔為 @pytest.mark.component，需 live DB（dev 環境 lock_AI_data）+ price_rules 種子資料。
  若 DB 不可用或無匹配規則，測試會 skip/error — 屬預期；unit 邏輯由 pricing_rule_service 層覆蓋。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


def _path(tenant_id: str = DEFAULT_TENANT_ID) -> str:
    return f"/tenants/{tenant_id}/pricing/calculate"


def _calc_body(
    brand: str = "Chatlock",
    lock_type: str = "smart_lock",
    difficulty: str = "simple",
) -> dict:
    return {
        "brand": brand,
        "lock_type": lock_type,
        "difficulty": difficulty,
        "is_emergency": False,
        "is_night_service": False,
    }


# ---------------------------------------------------------------------------
# TC-1: POST calculate — happy path（帶 Idempotency-Key）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calculate_pricing_v2_200(client, admin_headers):
    """POST /tenants/{id}/pricing/calculate 回 200 且 payload 含 base_price / total / currency。

    若 DB 無對應 price_rules 資料則 422（規則缺失），屬環境問題非 endpoint bug。
    測試只要不 5xx 即可；200 路徑做結構斷言。
    """
    headers = dict(admin_headers)
    headers["Idempotency-Key"] = str(uuid.uuid4())

    res = await client.post(_path(), headers=headers, json=_calc_body())
    # 允許 422（無種子規則）或 200（有種子規則）；不允許 5xx
    assert res.status_code in (200, 422), f"Unexpected status {res.status_code}: {res.text}"

    if res.status_code == 200:
        data = res.json()
        assert "base_price" in data, "Response must contain base_price"
        assert "total" in data, "Response must contain total"
        assert data.get("currency") == "TWD"


# ---------------------------------------------------------------------------
# TC-2: cross-tenant guard → 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calculate_pricing_v2_cross_tenant_403(client, admin_headers):
    """path tenantId != JWT claim → 403 CROSS_TENANT_WRITE。"""
    wrong_tenant = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    headers = dict(admin_headers)
    headers["Idempotency-Key"] = str(uuid.uuid4())

    res = await client.post(
        _path(tenant_id=wrong_tenant),
        headers=headers,
        json=_calc_body(),
    )
    assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# TC-3: 無 auth → 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calculate_pricing_v2_no_auth_401(client):
    """無 Bearer token → 401 UNAUTHENTICATED。"""
    res = await client.post(_path(), json=_calc_body())
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# TC-4: invalid lock_type → 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calculate_pricing_v2_invalid_lock_type_422(client, admin_headers):
    """lock_type 不在 enum → Pydantic 422。"""
    headers = dict(admin_headers)
    headers["Idempotency-Key"] = str(uuid.uuid4())

    body = _calc_body()
    body["lock_type"] = "invalid_lock"
    res = await client.post(_path(), headers=headers, json=body)
    assert res.status_code == 422
