"""CR-0092 RBAC 硬化 — 代表性 HIGH 端點角色隔離。

驗證敏感寫入端點補上 role_required 後：
- technician token → 403 FORBIDDEN（role_required 為 dependency，在 body 驗證前先擋下）
- admin token → 非 403（通過角色守衛；後續可能因 body/資料 422/404，但不是 403）

斷言用「technician=403 且 admin!=403」隔離角色檢查本身，不受各端點 body schema 影響。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

T = DEFAULT_TENANT_ID
_WID = str(uuid.uuid4())

# (method, path, body) — 跨 category 代表性 HIGH 端點
CASES = [
    ("post", f"/tenants/{T}/brand-b2b-statements:generate", {}),                 # accounting
    ("post", f"/tenants/{T}/dispatcher-commissions:generate", {}),              # accounting
    ("post", f"/tenants/{T}/quotes/{_WID}:approve", {}),                        # pricing (quote approve)
    ("post", f"/api/v1/dispatch/auto-match", {}),                               # dispatch
    ("post", f"/api/v1/data-corrections/{_WID}/approve", {}),                   # data-correction
]


def _hdr(headers: dict) -> dict:
    return {**headers}


@pytest.mark.parametrize("method,path,body", CASES)
async def test_technician_forbidden(client, technician_headers, method, path, body):
    resp = await getattr(client, method)(path, json=body, headers=technician_headers)
    assert resp.status_code == 403, f"{path} 應擋 technician，得 {resp.status_code}: {resp.text[:200]}"


@pytest.mark.parametrize("method,path,body", CASES)
async def test_admin_passes_role_guard(client, admin_headers, method, path, body):
    # admin 通過角色守衛；可能因 body/資料因素 4xx，但不應是 403（角色被擋）
    resp = await getattr(client, method)(path, json=body, headers=admin_headers)
    assert resp.status_code != 403, f"{path} 不應擋 admin，得 403: {resp.text[:200]}"
