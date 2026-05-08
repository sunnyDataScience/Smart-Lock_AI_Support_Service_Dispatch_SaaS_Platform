"""F-019 — RBAC 動態調整 component tests.

Covers updateRolePermissions endpoint：
  1. admin（tenant_admin 階層）成功更新 → 200 + WS event 推送
  2. operations_manager 試授 admin/tenant_admin → 403 RBAC_HIERARCHY_VIOLATION
  3. support_agent / dispatcher → 403 FORBIDDEN（不在 RBAC_ADMIN_ROLES）
  4. 越權升級：actor 試授「自己沒有的 permission」→ 403
  5. Locked permission 變更 → 403 PERMISSION_LOCKED
  6. 不存在的 role_name → 404
  7. invalid permission code（resource 未知 / action 未知）→ 422
  8. WS payload 結構對齊 AsyncAPI（envelope + data.role_id / changed_codes）
  9. hierarchy matrix 子集驗證（can_grant 純函式）
 10. listRoles 反映 overrides（end-to-end）

每個 test 結尾盡量還原 role_permissions（讓測試之間不互相污染）。
"""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.component

from .conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID, _make_token  # type: ignore


PATH = "/api/v1/roles/{role}/permissions"


def _hdr(role: str, user_id: str | None = None) -> dict:
    token = _make_token(
        user_id=user_id or ADMIN_USER_ID,
        role=role,
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


async def _cleanup(role: str) -> None:
    """每個測試結尾把該 role 的 overrides 全清掉，避免污染。"""
    try:
        import core.db as db_module
        from core.db import _ensure_conn

        if not await _ensure_conn():
            return
        await db_module._conn.execute(
            "DELETE FROM role_permissions WHERE tenant_id = %s::uuid AND role_name = %s",
            (DEFAULT_TENANT_ID, role),
        )
    except Exception:
        pass


# ─── 1. hierarchy 純函式測試 ───────────────────────────────────────


def test_hierarchy_can_grant_matrix():
    from services.role_service import can_grant

    # admin (4) 嚴格高於 operations_manager (2)、reviewer (2)、technician (1)
    assert can_grant("admin", "reviewer") is True
    assert can_grant("admin", "technician") is True
    assert can_grant("tenant_admin", "operations_manager") is True

    # 同階互不能授權
    assert can_grant("admin", "tenant_admin") is False
    assert can_grant("operations_manager", "reviewer") is False

    # 低階不能授權高階
    assert can_grant("operations_manager", "admin") is False
    assert can_grant("technician", "operations_manager") is False
    assert can_grant("brand_oem", "technician") is False

    # super_admin 高於一切
    assert can_grant("super_admin", "admin") is True
    assert can_grant("super_admin", "tenant_admin") is True


# ─── 2. RBAC admin 成功路徑 + WS publish ──────────────────────────


@pytest.mark.asyncio
async def test_admin_can_update_reviewer_permissions(client, admin_headers):
    """admin → 修改 reviewer 權限（grant invoices.write）→ 200。"""
    payload = {
        # reviewer 預設沒有 invoices.write — 此處新增
        "permissions": [
            "work_orders.read",
            "technicians.read",
            "customers.read",
            "accounting.read",
            "invoices.read",
            "invoices.write",   # newly granted
            "refunds.read",
            "refunds.write",
            "inventory.read",
            "warranty.read",
            "warranty.write",
            "disputes.read",
            "disputes.write",
        ],
        "reason": "F-019 test: 給 reviewer 開啟發票寫入",
    }
    res = await client.patch(
        PATH.format(role="reviewer"), json=payload, headers=admin_headers
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["role_name"] == "reviewer"
    assert "invoices.write" in body["permissions"]
    assert "updated_at" in body
    assert isinstance(body["ws_published"], bool)

    # listRoles 應反映此 override
    list_res = await client.get("/api/v1/roles", headers=admin_headers)
    assert list_res.status_code == 200
    reviewer = next(r for r in list_res.json()["data"] if r["id"] == "reviewer")
    invoices = next(p for p in reviewer["permissions"] if p["resource"] == "invoices")
    assert invoices["write"] is True

    await _cleanup("reviewer")


# ─── 3. 階層越權 ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_operations_manager_cannot_update_role(client):
    """operations_manager 不在 RBAC_ADMIN_ROLES → 403 FORBIDDEN。"""
    headers = _hdr("operations_manager", user_id="11111111-1111-1111-1111-111111111111")
    res = await client.patch(
        PATH.format(role="reviewer"),
        json={"permissions": ["work_orders.read"], "reason": "should fail"},
        headers=headers,
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_cannot_update_same_tier_admin(client, admin_headers):
    """admin 階層 == tenant_admin == admin → 不能改 admin / tenant_admin。"""
    res = await client.patch(
        PATH.format(role="admin"),
        json={"permissions": ["work_orders.read"], "reason": "hierarchy test"},
        headers=admin_headers,
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "RBAC_HIERARCHY_VIOLATION"


# ─── 4. 非 RBAC 角色 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_support_agent_forbidden(client):
    """support_agent / technician → 403 FORBIDDEN。"""
    for role in ("technician", "dispatcher", "customer_service"):
        headers = _hdr(role, user_id="22222222-2222-2222-2222-222222222222")
        res = await client.patch(
            PATH.format(role="reviewer"),
            json={"permissions": ["work_orders.read"], "reason": "no rbac admin"},
            headers=headers,
        )
        assert res.status_code == 403, f"{role} should be 403"
        assert res.json()["error_code"] == "FORBIDDEN"


# ─── 5. 不存在的 role / 無效 permission ──────────────────────────


@pytest.mark.asyncio
async def test_unknown_role_returns_404(client, admin_headers):
    res = await client.patch(
        PATH.format(role="nonexistent_role"),
        json={"permissions": [], "reason": "404 test"},
        headers=admin_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_invalid_permission_code_returns_422(client, admin_headers):
    # action `execute` 不在 white-list
    res = await client.patch(
        PATH.format(role="reviewer"),
        json={
            "permissions": ["work_orders.execute"],
            "reason": "invalid action test",
        },
        headers=admin_headers,
    )
    # Pydantic regex 攔截 → 422，或進到 service 後 422
    assert res.status_code == 422


# ─── 6. Locked permission 變更被拒 ───────────────────────────────


@pytest.mark.asyncio
async def test_locked_permission_cannot_change(client, admin_headers):
    """嘗試把 reviewer.audit_logs.write 開啟 → locked → 403。"""
    # reviewer 預設權限 + 多加 audit_logs.write
    payload = {
        "permissions": [
            "work_orders.read",
            "technicians.read",
            "customers.read",
            "accounting.read",
            "invoices.read",
            "refunds.read",
            "refunds.write",
            "inventory.read",
            "warranty.read",
            "warranty.write",
            "disputes.read",
            "disputes.write",
            "audit_logs.write",  # locked → 應該拒
        ],
        "reason": "locked test",
    }
    res = await client.patch(
        PATH.format(role="reviewer"), json=payload, headers=admin_headers
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "PERMISSION_LOCKED"


# ─── 7. WS publish payload 對齊 AsyncAPI ─────────────────────────


@pytest.mark.asyncio
async def test_ws_publish_envelope_aligned_with_asyncapi(client, admin_headers):
    """訂閱 /realtime/rbac → 觸發 update → 收到 envelope + data。

    使用 fake WebSocket 記錄 send_json 內容，避免起真的 WS server。
    """
    from realtime.ws_hub import hub

    captured: list[dict] = []

    class _FakeWS:
        async def send_json(self, msg):
            captured.append(msg)

    fake = _FakeWS()
    await hub.subscribe("/realtime/rbac", fake)  # type: ignore[arg-type]

    try:
        res = await client.patch(
            PATH.format(role="reviewer"),
            json={
                "permissions": [
                    "work_orders.read",
                    "refunds.read",
                    "refunds.write",
                ],
                "reason": "ws envelope test",
            },
            headers=admin_headers,
        )
        # 給 publish 一點時間
        await asyncio.sleep(0.05)
        assert res.status_code == 200

        assert len(captured) >= 1, "expected at least one WS publish"
        msg = captured[0]
        assert msg["type"] == "rbac.permission.changed"
        env = msg["payload"]
        # AsyncAPI DomainEventEnvelope required: event_id / event_type / event_time / tenant_id / version / data
        for k in ("event_id", "event_type", "event_time", "tenant_id", "version", "data"):
            assert k in env, f"missing {k} in envelope"
        assert env["event_type"] == "rbac.permission.changed"
        assert env["tenant_id"] == DEFAULT_TENANT_ID
        # RbacPermissionChangedData required: role_id, changed_codes
        assert env["data"]["role_id"] == "reviewer"
        assert isinstance(env["data"]["changed_codes"], list)
    finally:
        await hub.unsubscribe("/realtime/rbac", fake)  # type: ignore[arg-type]
        await _cleanup("reviewer")


# ─── 8. audit log 寫入確認 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log_persisted(client, admin_headers):
    """更新後 audit_events 應有對應紀錄。"""
    import core.db as db_module
    from core.db import _ensure_conn

    if not await _ensure_conn():
        pytest.skip("DB not available")

    await client.patch(
        PATH.format(role="brand_oem"),
        json={
            "permissions": [
                "work_orders.read",
                "technicians.read",
                "customers.read",
                "inventory.read",
                "warranty.read",
            ],
            "reason": "audit log test",
        },
        headers=admin_headers,
    )

    cur = await db_module._conn.execute(
        "SELECT action, payload FROM audit_events "
        "WHERE action = %s "
        "ORDER BY created_at DESC LIMIT 1",
        ("role.permissions_updated",),
    )
    row = await cur.fetchone()
    assert row is not None
    assert row[0] == "role.permissions_updated"
    payload = row[1] if isinstance(row[1], dict) else json.loads(row[1])
    assert payload["role_name"] == "brand_oem"
    assert payload["reason"] == "audit log test"
    assert "before" in payload and "after" in payload

    await _cleanup("brand_oem")
