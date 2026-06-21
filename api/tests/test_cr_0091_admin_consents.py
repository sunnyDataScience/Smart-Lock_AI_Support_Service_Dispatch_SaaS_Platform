"""CR-0091 派工單模組 4：後台唯讀取得工單三段免責同意狀態。

GET /tenants/{tid}/work-orders/{id}/consents
- admin / dispatcher / customer_service → 200（後台角色，複用 consent_service.get_consents）
- technician → 403（不在 _DISPATCH_ALLOWED_ROLES；驗證 role_required 守衛）
- 無 token → 401
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

_SAMPLE = {
    "text_version": "blueprint-draft-2026-06",
    "consents": [
        {"consent_type": "new_installation", "title": "新機安裝同意", "body": "...", "accepted": True, "accepted_at": "2026-06-21T00:00:00+00:00"},
        {"consent_type": "lock_destruction", "title": "破壞鎖施工免責", "body": "...", "accepted": False, "accepted_at": None},
        {"consent_type": "personal_data", "title": "個人資料保護法", "body": "...", "accepted": False, "accepted_at": None},
    ],
}


def _url() -> str:
    return f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{uuid.uuid4()}/consents"


async def test_admin_can_read_consents(client, admin_headers):
    with patch("services.consent_service.get_consents", new_callable=AsyncMock, return_value=_SAMPLE):
        resp = await client.get(_url(), headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["text_version"] == "blueprint-draft-2026-06"
    assert len(body["consents"]) == 3


async def test_dispatcher_can_read_consents(client, dispatcher_headers):
    with patch("services.consent_service.get_consents", new_callable=AsyncMock, return_value=_SAMPLE):
        resp = await client.get(_url(), headers=dispatcher_headers)
    assert resp.status_code == 200, resp.text


async def test_customer_service_can_read_consents(client, customer_service_headers):
    with patch("services.consent_service.get_consents", new_callable=AsyncMock, return_value=_SAMPLE):
        resp = await client.get(_url(), headers=customer_service_headers)
    assert resp.status_code == 200, resp.text


async def test_technician_forbidden(client, technician_headers):
    # technician 不在 _DISPATCH_ALLOWED_ROLES → role_required 擋下（不應到達 service）
    with patch("services.consent_service.get_consents", new_callable=AsyncMock, return_value=_SAMPLE) as svc:
        resp = await client.get(_url(), headers=technician_headers)
    assert resp.status_code == 403, resp.text
    svc.assert_not_called()


async def test_unauthenticated_401(client):
    resp = await client.get(_url(), headers={"X-Tenant-ID": DEFAULT_TENANT_ID})
    assert resp.status_code == 401, resp.text
