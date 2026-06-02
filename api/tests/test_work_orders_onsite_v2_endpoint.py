"""Component tests for M07 work-orders onsite v2 tenant-scoped endpoints（CR-0003 P2）。

測試矩陣：
  1. POST /tenants/{tenantId}/work-orders/{woId}/onsite/arrival
       a. 缺 Idempotency-Key → 400（idempotency_guard）
       b. 帶 Idempotency-Key，WO 不存在 → 409 STATE_CONFLICT（SUBFLOW 狀態門）
          或 404 NOT_FOUND（DB 無此 WO）
       c. cross-tenant → 403 CROSS_TENANT_WRITE

  2. POST /tenants/{tenantId}/work-orders/{woId}/onsite/completion
       a. 缺 Idempotency-Key → 400（idempotency_guard）
       b. 帶 Idempotency-Key，WO 不存在 → 404 / 409（STATE_CONFLICT）
       c. 缺必填欄位（photo_evidence_ids 空） → 422（pydantic validation）
       d. cross-tenant → 403 CROSS_TENANT_WRITE

注意：worktree 無真實 DB。cross-tenant 403 在 guard 層 early-return，無需 DB，
可在 CI 環境可靠運行。404/409 依賴 DB 存活；有 DB 的環境才會跑（@pytest.mark.component）。
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


def _idem_headers(base: dict[str, str]) -> dict[str, str]:
    """在現有 headers 基礎上加新鮮 Idempotency-Key（POST 必須帶）。"""
    return {**base, "Idempotency-Key": str(uuid.uuid4())}


def _cross_tenant_headers(role: str = "admin") -> dict[str, str]:
    """JWT 屬於 DEFAULT_TENANT 但打 OTHER_TENANT path → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=DEFAULT_TENANT_ID,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


def _valid_arrival_body() -> dict:
    return {
        "arrived_at": "2026-06-02T10:00:00+08:00",
        "gps": {"lat": 25.0330, "lng": 121.5654, "accuracy_m": 5.0},
    }


def _valid_completion_body() -> dict:
    return {
        "signature_evidence_id": str(uuid.uuid4()),
        "photo_evidence_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
        "notes": "門鎖更換完成，測試開關 3 次正常。",
    }


# ===========================================================================
# POST /tenants/{tenantId}/work-orders/{woId}/onsite/arrival
# ===========================================================================


@pytest.mark.asyncio
async def test_onsite_arrival_v2_requires_idempotency_key(client, admin_headers):
    """缺 Idempotency-Key → 400（idempotency_guard 早於 DB 查詢）。"""
    fake_wo_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_wo_id}/onsite/arrival",
        headers=admin_headers,  # 無 Idempotency-Key
        json=_valid_arrival_body(),
    )
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_onsite_arrival_v2_unknown_wo(client, admin_headers):
    """帶 Idempotency-Key，WO 不存在 → 404 NOT_FOUND（DB 查無此工單）。"""
    fake_wo_id = str(uuid.uuid4())
    headers = _idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_wo_id}/onsite/arrival",
        headers=headers,
        json=_valid_arrival_body(),
    )
    # DB 查無此工單 → NOT_FOUND (404) 或 STATE_CONFLICT (409)
    assert res.status_code in (404, 409), res.text


@pytest.mark.asyncio
async def test_onsite_arrival_v2_cross_tenant_403(client):
    """cross-tenant write：path tenantId ≠ JWT claim → 403 CROSS_TENANT_WRITE（無需 DB）。"""
    headers = _idem_headers(_cross_tenant_headers())
    fake_wo_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_wo_id}/onsite/arrival",
        headers=headers,
        json=_valid_arrival_body(),
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"


@pytest.mark.asyncio
async def test_onsite_arrival_v2_missing_required_fields(client, admin_headers):
    """arrived_at 缺失 → 422 validation error（pydantic）。"""
    fake_wo_id = str(uuid.uuid4())
    headers = _idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_wo_id}/onsite/arrival",
        headers=headers,
        json={"gps": {"lat": 25.0, "lng": 121.5}},  # 缺 arrived_at
    )
    assert res.status_code == 422, res.text


# ===========================================================================
# POST /tenants/{tenantId}/work-orders/{woId}/onsite/completion
# ===========================================================================


@pytest.mark.asyncio
async def test_onsite_completion_v2_requires_idempotency_key(client, admin_headers):
    """缺 Idempotency-Key → 400（idempotency_guard 早於 DB 查詢）。"""
    fake_wo_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_wo_id}/onsite/completion",
        headers=admin_headers,  # 無 Idempotency-Key
        json=_valid_completion_body(),
    )
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_onsite_completion_v2_unknown_wo(client, admin_headers):
    """帶 Idempotency-Key，WO 不存在 → 404 NOT_FOUND 或 409 STATE_CONFLICT。"""
    fake_wo_id = str(uuid.uuid4())
    headers = _idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_wo_id}/onsite/completion",
        headers=headers,
        json=_valid_completion_body(),
    )
    assert res.status_code in (404, 409), res.text


@pytest.mark.asyncio
async def test_onsite_completion_v2_empty_photo_list_422(client, admin_headers):
    """photo_evidence_ids 空陣列（min_length=1）→ 422（pydantic validation）。"""
    fake_wo_id = str(uuid.uuid4())
    headers = _idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_wo_id}/onsite/completion",
        headers=headers,
        json={
            "signature_evidence_id": str(uuid.uuid4()),
            "photo_evidence_ids": [],  # 違反 minItems=1
        },
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_onsite_completion_v2_missing_signature_422(client, admin_headers):
    """signature_evidence_id 缺失 → 422（pydantic required field）。"""
    fake_wo_id = str(uuid.uuid4())
    headers = _idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_wo_id}/onsite/completion",
        headers=headers,
        json={"photo_evidence_ids": [str(uuid.uuid4())]},  # 缺 signature_evidence_id
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_onsite_completion_v2_cross_tenant_403(client):
    """cross-tenant write：path tenantId ≠ JWT claim → 403 CROSS_TENANT_WRITE（無需 DB）。"""
    headers = _idem_headers(_cross_tenant_headers())
    fake_wo_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_wo_id}/onsite/completion",
        headers=headers,
        json=_valid_completion_body(),
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_WRITE"
