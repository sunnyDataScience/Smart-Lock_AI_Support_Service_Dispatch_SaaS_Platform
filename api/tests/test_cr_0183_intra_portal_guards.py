"""CR-0183（CR-0182 D4a follow-up）：同面內敏感 GET 端點角色守衛。

補洞前 brand-api 多個敏感 GET 僅 require_tenant（無角色守衛），品牌內低權限角色
（viewer/customer_service）可越權讀金流/PII/治理。本測試取各守衛層代表端點，驗證
低權限角色被擋（403 FORBIDDEN）、合法角色通過守衛（非 FORBIDDEN）。

角色檢查在 token claim 上、DB 查詢 fail-open 之後才判——403 路徑不依賴健康 DB。
"""

from __future__ import annotations

import pytest

from core.auth import create_token

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"


def _tok(role: str) -> str:
    t, _, _ = create_token(user_id="00000000-0000-0000-0000-0000000000aa",
                           role=role, tenant_id=TID, token_type="access")
    return t


def _hdr(role: str) -> dict:
    return {"Authorization": f"Bearer {_tok(role)}", "X-Tenant-ID": TID}


# (path, 應被擋的低權限角色, 應通過的合法角色)
CASES = [
    (f"/tenants/{TID}/refunds?limit=1", "customer_service", "reviewer"),          # 金流 REVIEW_ROLES（cs 不在）
    (f"/tenants/{TID}/vouchers?limit=1", "customer_service", "operations_manager"),  # 傳票 REVIEW_ROLES
    (f"/tenants/{TID}/settlements?limit=1", "dispatcher", "admin"),                # 結算 REVIEW_ROLES
    (f"/tenants/{TID}/customers?limit=1", "reviewer", "customer_service"),         # customers admin/ops/cs（reviewer 不在）
    (f"/tenants/{TID}/m18/configs", "operations_manager", "admin"),                # config 治理 admin-only
    (f"/tenants/{TID}/reports/kpi", "customer_service", "operations_manager"),     # 報表 OPS_ROLES
    (f"/tenants/{TID}/data-corrections", "customer_service", "operations_manager"),  # HD-4：ops 可讀、cs 擋（業主 0726）
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path,blocked_role,allowed_role", CASES)
async def test_low_priv_role_blocked(client, path, blocked_role, allowed_role):
    resp = await client.get(path, headers=_hdr(blocked_role))
    assert resp.status_code == 403, f"{path} 應擋 {blocked_role}，得 {resp.status_code}"
    assert resp.json().get("error_code") == "FORBIDDEN"


@pytest.mark.asyncio
@pytest.mark.parametrize("path,blocked_role,allowed_role", CASES)
async def test_legit_role_passes_guard(client, path, blocked_role, allowed_role):
    """合法角色通過角色守衛（後續 DB 行為不論；只確保非 FORBIDDEN 被誤擋）。"""
    resp = await client.get(path, headers=_hdr(allowed_role))
    assert resp.json().get("error_code") != "FORBIDDEN", \
        f"{path} 誤擋合法角色 {allowed_role}"


@pytest.mark.asyncio
async def test_technician_still_reads_workorder_pool(client):
    """Category B 回歸：工單池維持 require_tenant，技師（tech-api 合法讀者）不被 FORBIDDEN。"""
    resp = await client.get(f"/tenants/{TID}/work-orders/pool?limit=1", headers=_hdr("technician"))
    assert resp.json().get("error_code") != "FORBIDDEN"
