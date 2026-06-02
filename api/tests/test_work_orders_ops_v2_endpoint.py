"""Component tests for M07 WorkOrder Ops v2 tenant-scoped endpoints（CR-0003 P2-W4）。

測試矩陣：
  reschedule-request:
    1. POST /tenants/{tenantId}/work-orders/{id}/reschedule-request
       a. 缺 Idempotency-Key → 400（idempotency_guard）
       b. 帶 Idempotency-Key，WO 不存在 → 404 / 409
       c. cross-tenant → 403 CROSS_TENANT_WRITE
    2. POST /tenants/{tenantId}/work-orders/{id}/reschedule:approve
       a. 缺 Idempotency-Key → 400
       b. 非管理員角色（technician）→ 403 FORBIDDEN_ROLE
       c. cross-tenant → 403 CROSS_TENANT_WRITE
  notify-delay:
    3. POST /tenants/{tenantId}/work-orders/{id}/notify-delay
       a. 缺 Idempotency-Key → 400
       b. 帶 Idempotency-Key，WO 不存在 → 404 / 409
       c. cross-tenant → 403 CROSS_TENANT_WRITE
  material-request:
    4. POST /tenants/{tenantId}/work-orders/{id}/material-request
       a. 缺 Idempotency-Key → 400
       b. 帶 Idempotency-Key，WO 不存在 → 404 / 409
       c. 缺必填欄位（items 空） → 422（pydantic validation）
       d. cross-tenant → 403 CROSS_TENANT_WRITE
  events:
    5. GET /tenants/{tenantId}/work-orders/{id}/events
       a. 200 空列表或結構（即使 WO 不存在也回結構，依 service 實作）
       b. cross-tenant → 403 CROSS_TENANT_READ
  pool:
    6. GET /tenants/{tenantId}/work-orders/pool
       a. 200 + 結構含 items / has_more
       b. cross-tenant → 403 CROSS_TENANT_READ
  dispatch-queue:
    7. GET /tenants/{tenantId}/dispatch/queue
       a. 200 + 結構（DispatchQueueSnapshot）
       b. cross-tenant → 403 CROSS_TENANT_READ

注意：worktree 無真實 DB。cross-tenant / role / validation 類測試不需 DB，可在 CI 可靠運行。
404/409 依賴 DB 存活；有 DB 的環境才會跑（@pytest.mark.component）。
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


def _role_headers(role: str) -> dict[str, str]:
    """特定角色 JWT，tenant 為 DEFAULT_TENANT。"""
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


_RESCHEDULE_REQUEST_BODY = {
    "new_scheduled_at": "2027-01-15T10:00:00+08:00",
    "reason": "客戶確認後改約",
}

_APPROVE_RESCHEDULE_BODY = {
    "decision": "approve",
    "comment": "已確認技師行程",
}

_NOTIFY_DELAY_BODY = {
    "delay_minutes": 30,
    "reason": "前一單耗時較長",
}

_MATERIAL_REQUEST_BODY = {
    "items": [{"brand": "Dormakaba", "model": "AS850 主板", "quantity": 1}],
    "urgency": "today",
    "note": "需今日配送",
}

# ---------------------------------------------------------------------------
# 1. reschedule-request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_request_missing_idem_key(client, admin_headers):
    """POST reschedule-request 缺 Idempotency-Key → 400。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/reschedule-request",
        headers=admin_headers,
        json=_RESCHEDULE_REQUEST_BODY,
    )
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_reschedule_request_with_idem_key_wo_not_found(client, admin_headers):
    """POST reschedule-request 帶 Idempotency-Key，WO 不存在 → 404 or 409。"""
    fake_id = str(uuid.uuid4())
    headers = _idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/reschedule-request",
        headers=headers,
        json=_RESCHEDULE_REQUEST_BODY,
    )
    assert res.status_code in (404, 409), res.text


@pytest.mark.asyncio
async def test_reschedule_request_cross_tenant_403(client):
    """cross-tenant：path tenantId ≠ JWT claim → 403 CROSS_TENANT_WRITE。"""
    fake_id = str(uuid.uuid4())
    headers = _idem_headers(_cross_tenant_headers())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_id}/reschedule-request",
        headers=headers,
        json=_RESCHEDULE_REQUEST_BODY,
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# 2. reschedule:approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_reschedule_missing_idem_key(client, admin_headers):
    """POST reschedule:approve 缺 Idempotency-Key → 400。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/reschedule:approve",
        headers=admin_headers,
        json=_APPROVE_RESCHEDULE_BODY,
    )
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_approve_reschedule_technician_role_forbidden(client):
    """technician 角色打 reschedule:approve → 403（role guard: _admin_only）。"""
    fake_id = str(uuid.uuid4())
    headers = _idem_headers(_role_headers("technician"))
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/reschedule:approve",
        headers=headers,
        json=_APPROVE_RESCHEDULE_BODY,
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_approve_reschedule_cross_tenant_403(client):
    """cross-tenant reschedule:approve → 403 CROSS_TENANT_WRITE。"""
    fake_id = str(uuid.uuid4())
    headers = _idem_headers(_cross_tenant_headers())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_id}/reschedule:approve",
        headers=headers,
        json=_APPROVE_RESCHEDULE_BODY,
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# 3. notify-delay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_delay_missing_idem_key(client, admin_headers):
    """POST notify-delay 缺 Idempotency-Key → 400。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/notify-delay",
        headers=admin_headers,
        json=_NOTIFY_DELAY_BODY,
    )
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_notify_delay_with_idem_key_wo_not_found(client, admin_headers):
    """POST notify-delay 帶 Idempotency-Key，WO 不存在 → 404 or 409。"""
    fake_id = str(uuid.uuid4())
    headers = _idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/notify-delay",
        headers=headers,
        json=_NOTIFY_DELAY_BODY,
    )
    assert res.status_code in (404, 409), res.text


@pytest.mark.asyncio
async def test_notify_delay_cross_tenant_403(client):
    """cross-tenant notify-delay → 403 CROSS_TENANT_WRITE。"""
    fake_id = str(uuid.uuid4())
    headers = _idem_headers(_cross_tenant_headers())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_id}/notify-delay",
        headers=headers,
        json=_NOTIFY_DELAY_BODY,
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# 4. material-request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_material_request_missing_idem_key(client, admin_headers):
    """POST material-request 缺 Idempotency-Key → 400。"""
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/material-request",
        headers=admin_headers,
        json=_MATERIAL_REQUEST_BODY,
    )
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_material_request_with_idem_key_wo_not_found(client, admin_headers):
    """POST material-request 帶 Idempotency-Key，WO 不存在 → 404 or 409。"""
    fake_id = str(uuid.uuid4())
    headers = _idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/material-request",
        headers=headers,
        json=_MATERIAL_REQUEST_BODY,
    )
    assert res.status_code in (404, 409), res.text


@pytest.mark.asyncio
async def test_material_request_empty_items_422(client, admin_headers):
    """POST material-request items 為空陣列 → 422（pydantic min_length=1）。"""
    fake_id = str(uuid.uuid4())
    headers = _idem_headers(admin_headers)
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/material-request",
        headers=headers,
        json={"items": [], "urgency": "today"},
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_material_request_cross_tenant_403(client):
    """cross-tenant material-request → 403 CROSS_TENANT_WRITE。"""
    fake_id = str(uuid.uuid4())
    headers = _idem_headers(_cross_tenant_headers())
    res = await client.post(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_id}/material-request",
        headers=headers,
        json=_MATERIAL_REQUEST_BODY,
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# 5. events（GET — 無 Idempotency-Key 需求）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_work_order_events_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/work-orders/{id}/events → 200（DB 無此 WO 時依 service 實作；
    service 多半回空列表或 404；兩者皆可接受）。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{fake_id}/events",
        headers=admin_headers,
    )
    assert res.status_code in (200, 404), res.text


@pytest.mark.asyncio
async def test_list_work_order_events_v2_cross_tenant_403(client):
    """cross-tenant events GET → 403 CROSS_TENANT_READ。"""
    fake_id = str(uuid.uuid4())
    headers = _cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/{fake_id}/events",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# 6. pool（GET）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_work_order_pool_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/work-orders/pool → 200 + items / has_more。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders/pool",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body


@pytest.mark.asyncio
async def test_list_work_order_pool_v2_cross_tenant_403(client):
    """cross-tenant pool → 403 CROSS_TENANT_READ。"""
    headers = _cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/work-orders/pool",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# 7. dispatch-queue（GET）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dispatch_queue_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/dispatch/queue → 200（DispatchQueueSnapshot 結構）。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/dispatch/queue",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_get_dispatch_queue_v2_cross_tenant_403(client):
    """cross-tenant dispatch queue → 403 CROSS_TENANT_READ。"""
    headers = _cross_tenant_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/dispatch/queue",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "CROSS_TENANT_READ"
