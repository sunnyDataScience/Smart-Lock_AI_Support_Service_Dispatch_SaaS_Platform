"""5 角色 RBAC 權限隔離矩陣（A3，會議 2026-06-10 Action #7 / 決議 #9）。

驗證授權層強制：
  - forbidden 角色 → 403（role guard 在處理 body 前就擋下）
  - authorized 角色 → 非 403（穿過 RBAC guard；後續可能因 body/資料 200/404/422，
    但「不是 403」即證明授權層放行）

測 5 個操作角色（conftest fixture）：
  admin / operations_manager / dispatcher / customer_service / technician

代表性守衛端點：
  - POST /api/v1/auth/admin-reset-password   → role_required("admin")
  - GET  /api/v1/technicians/me              → role_required("technician")
  - POST /tenants/{tid}/customers            → role_required("admin","operations_manager")
  - GET  /api/v1/admin/schedule-requests     → role_required("admin","operations_manager")
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.component

TENANT = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def role_headers(
    admin_headers,
    secondary_admin_headers,
    dispatcher_headers,
    customer_service_headers,
    technician_headers,
) -> dict[str, dict[str, str]]:
    """5 個操作角色的 headers（secondary_admin 是 operations_manager 角色）。"""
    return {
        "admin": admin_headers,
        "operations_manager": secondary_admin_headers,
        "dispatcher": dispatcher_headers,
        "customer_service": customer_service_headers,
        "technician": technician_headers,
    }


async def _assert_matrix(client, *, method, path, json, allowed, role_headers):
    """allowed = 可穿過授權層的角色集合；其餘角色應 403。"""
    for role, headers in role_headers.items():
        res = await client.request(method, path, headers=headers, json=json)
        if role in allowed:
            assert res.status_code != 403, (
                f"{role} 應可存取 {method} {path}，卻得 403：{res.text}"
            )
        else:
            assert res.status_code == 403, (
                f"{role} 應被擋（403），卻得 {res.status_code}：{path}"
            )


@pytest.mark.asyncio
async def test_admin_only_admin_reset_password(client, role_headers):
    """admin-reset-password 僅 admin 可用；用不存在 email 探測（admin→404,非 mutate）。"""
    await _assert_matrix(
        client,
        method="POST",
        path="/api/v1/auth/admin-reset-password",
        json={"email": "rbac-probe-nonexistent@example.com"},
        allowed={"admin"},
        role_headers=role_headers,
    )


@pytest.mark.asyncio
async def test_technician_only_my_profile(client, role_headers):
    """/technicians/me 僅 technician 可用；admin 等其他角色應 403。"""
    await _assert_matrix(
        client,
        method="GET",
        path="/api/v1/technicians/me",
        json=None,
        allowed={"technician"},
        role_headers=role_headers,
    )


@pytest.mark.asyncio
async def test_customer_writer_admin_or_ops(client, role_headers):
    """建立客戶（write）僅 admin / operations_manager；dispatcher / cs / technician 應 403。"""
    await _assert_matrix(
        client,
        method="POST",
        path=f"/tenants/{TENANT}/customers",
        json={},  # 空 body：授權角色會 422（非 403），未授權角色 403
        allowed={"admin", "operations_manager"},
        role_headers=role_headers,
    )


@pytest.mark.asyncio
async def test_admin_schedule_admin_or_ops(client, role_headers):
    """排程審批清單僅 admin / operations_manager。"""
    await _assert_matrix(
        client,
        method="GET",
        path="/api/v1/admin/schedule-requests",
        json=None,
        allowed={"admin", "operations_manager"},
        role_headers=role_headers,
    )
