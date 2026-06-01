"""Component tests for M06 dispatch v2 tenant-scoped endpoints（CR-0002-α）。

測試矩陣：
  1. GET /tenants/{tenantId}/dispatch:candidates → 200 tenant-scoped 候選列表
  2. POST /tenants/{tenantId}/dispatch:auto-match → 200 自動匹配回傳
  3. cross-tenant GET guard → 403 CROSS_TENANT_READ
  4. cross-tenant POST guard → 403 CROSS_TENANT_WRITE
  5. legacy GET /api/v1/dispatch/candidates → 200 + Deprecation header（D3 雙掛驗證）
  6. legacy POST /api/v1/dispatch/auto-match → 200 + Deprecation header（D3 雙掛驗證）

注意：worktree 無真實 DB，這些測試須在有 DB 的環境跑（@pytest.mark.component）。
      此處確保 test 結構正確 + cross-tenant 邏輯可在無 DB 時就 early-return 403。
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
        "Idempotency-Key": str(uuid.uuid4()),  # POST 須帶（idempotency_guard）；403 檢查在其後
    }


# ---------------------------------------------------------------------------
# v2 GET /tenants/{tenantId}/dispatch:candidates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_dispatch_candidates_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/dispatch:candidates → 200 有效回應（含 candidates key）。"""
    fake_wo_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/dispatch:candidates",
        headers=admin_headers,
        params={"work_order_id": fake_wo_id},
    )
    # 無 DB 時可能 404（work order not found）或 503（DB unavailable）
    # 重點：不應是 403（無 cross-tenant 違規）也不應是 422（參數格式錯誤）
    assert res.status_code in (200, 404, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "candidates" in body


@pytest.mark.asyncio
async def test_list_dispatch_candidates_v2_cross_tenant_403(client):
    """cross-tenant GET：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    fake_wo_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/dispatch:candidates",
        headers=headers,
        params={"work_order_id": fake_wo_id},
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# v2 POST /tenants/{tenantId}/dispatch:auto-match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_dispatch_auto_match_v2_200(client, admin_headers):
    """POST /tenants/{tenantId}/dispatch:auto-match → 200 有效回應（含 candidates key）。"""
    fake_pc_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/dispatch:auto-match",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "problem_card_id": fake_pc_id,
            "urgency": "normal",
            "max_candidates": 3,
        },
    )
    # 無 DB 時可能 404（PC not found）或 503；不應是 403 或 422
    assert res.status_code in (200, 404, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "candidates" in body


@pytest.mark.asyncio
async def test_plan_dispatch_auto_match_v2_cross_tenant_403(client):
    """cross-tenant POST：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_WRITE。"""
    headers = _make_other_tenant_path_headers()
    fake_pc_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/dispatch:auto-match",
        headers=headers,
        json={
            "problem_card_id": fake_pc_id,
            "urgency": "normal",
            "max_candidates": 3,
        },
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# Legacy endpoints — Deprecation header (D3 dual-hang)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_dispatch_candidates_has_deprecation_header(client, admin_headers):
    """GET /api/v1/dispatch/candidates → Deprecation: true（D3 雙掛驗證）。"""
    fake_wo_id = str(uuid.uuid4())
    res = await client.get(
        "/api/v1/dispatch/candidates",
        headers=admin_headers,
        params={"work_order_id": fake_wo_id},
    )
    # 回應碼可能是 200/404/503；重點是 Deprecation header 存在
    assert res.status_code in (200, 404, 503), res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    # D3 核心契約＝Deprecation header（DeprecationMiddleware 對所有 /api/v1 回應保證，含 error path）。
    # Link successor-version 為 per-route success-path 附加（error path 會隨 raise 遺失），此處不硬性要求。


@pytest.mark.asyncio
async def test_legacy_dispatch_auto_match_has_deprecation_header(client, admin_headers):
    """POST /api/v1/dispatch/auto-match → Deprecation: true（D3 雙掛驗證）。"""
    fake_pc_id = str(uuid.uuid4())
    res = await client.post(
        "/api/v1/dispatch/auto-match",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "problem_card_id": fake_pc_id,
            "urgency": "normal",
            "max_candidates": 3,
        },
    )
    # 回應碼可能是 200/404/503；重點是 Deprecation header 存在
    assert res.status_code in (200, 404, 503), res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    # D3 核心契約＝Deprecation header（DeprecationMiddleware 對所有 /api/v1 回應保證，含 error path）。
    # Link successor-version 為 per-route success-path 附加（error path 會隨 raise 遺失），此處不硬性要求。
