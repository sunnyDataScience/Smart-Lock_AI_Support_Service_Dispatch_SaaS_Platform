"""CR-0130 RBAC 轉 enforce（WBS 1.1.1 / SA-01）。

- 死角色收斂：tenant_admin/super_admin token 不再放行任何守衛（後端對齊 SA-06 前端）
- 金流/派工/設定弱守衛寫入收斂：technician / vendor token → 403
- 技師動作端點顯式白名單：technician 不被 403 擋（可因業務狀態回 4xx，但非 FORBIDDEN）
- 矩陣/階層/RBAC_ADMIN 收斂 7 角色正典
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID, TECHNICIAN_USER_ID, _make_token

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID


def _headers(role: str, user_id: str | None = None) -> dict[str, str]:
    token = _make_token(user_id=user_id or str(uuid.uuid4()), role=role)
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": TID}


# 金流/派工/設定 寫入樣本（SA-01 驗收線：technician/vendor 寫 → 403）
_PROTECTED_WRITES = [
    ("POST", f"/tenants/{TID}/inventory/items", {"name": "x"}),                      # 金流：庫存
    ("POST", "/api/v1/pricing/calculate", {"category": "smart_lock"}),               # 金流：定價（技師零定價權 ADR-027）
    ("POST", "/api/v1/warranty-claims", {"work_order_id": str(uuid.uuid4())}),       # 金流：保固 claim
    ("POST", f"/tenants/{TID}/refunds:agent-initiate",
     {"work_order_id": str(uuid.uuid4()), "amount": "1", "reason": "x", "reason_code": "y"}),  # 金流：退款發起
    ("POST", f"/tenants/{TID}/scheduled-reports", {"report_type": "kpi"}),           # 設定：排程報表
    ("POST", f"/tenants/{TID}/gdpr/forget-requests/{uuid.uuid4()}:cancel", {}),      # 設定：GDPR
    ("POST", f"/api/v1/problem-cards/{uuid.uuid4()}/convert-to-work-order", {}),     # 派工：開單
    ("POST", f"/api/v1/work-orders/{uuid.uuid4()}/escalate",
     {"level": "operations_manager", "reason": "x"}),                                # 派工：升級（小編域）
]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["technician", "vendor"])
async def test_protected_writes_forbidden_for_field_roles(client, role):
    """SA-01 驗收線：technician / vendor token 寫金流/派工/設定 → 一律 403。"""
    headers = _headers(role)
    for method, path, body in _PROTECTED_WRITES:
        res = await client.request(method, path, json=body, headers=headers)
        assert res.status_code == 403, f"{role} {method} {path} → {res.status_code}（應 403）"
        assert res.json().get("error_code") == "FORBIDDEN"


@pytest.mark.asyncio
@pytest.mark.parametrize("dead_role", ["tenant_admin", "super_admin"])
async def test_dead_role_tokens_no_longer_full_access(client, dead_role):
    """死角色 token 不再全放行（後端對齊 SA-06；業主裁決 CR-0130 D1 全面移除）。"""
    headers = _headers(dead_role)
    res = await client.post(
        f"/tenants/{TID}/inventory/items", json={"name": "x"}, headers=headers)
    assert res.status_code == 403
    res = await client.post(
        f"/tenants/{TID}/scheduled-reports", json={"report_type": "kpi"}, headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_technician_actions_not_blocked_by_rbac(client):
    """技師動作端點（accept/complete/door-check…）不因 RBAC 擋技師——
    可因業務狀態回 404/409/422，但**不得是 403 FORBIDDEN**。"""
    headers = {"Authorization": f"Bearer {_make_token(user_id=TECHNICIAN_USER_ID, role='technician')}",
               "X-Tenant-ID": TID}
    missing = str(uuid.uuid4())
    for method, path in [
        ("POST", f"/api/v1/work-orders/{missing}/accept"),
        ("POST", f"/api/v1/work-orders/{missing}/door-check"),
        ("POST", f"/api/v1/work-orders/{missing}/material-request"),
        ("POST", f"/tenants/{TID}/work-orders/{missing}:accept"),
    ]:
        res = await client.request(method, path, json={}, headers=headers)
        assert res.status_code != 403, f"technician {path} 被 RBAC 誤鎖（{res.status_code}）"


def test_role_canon_consistency():
    """矩陣/階層/RBAC_ADMIN/角色組常數 收斂 7 角色正典（13_Security §3.1）。"""
    from core import deps
    from services import role_service as r

    canon = {"admin", "operations_manager", "reviewer", "customer_service",
             "dispatcher", "technician", "line_user"}
    assert set(r._MATRIX) == canon
    assert set(r._ROLE_META) == canon
    assert set(r.ROLE_HIERARCHY) == canon
    assert r.RBAC_ADMIN_ROLES == frozenset({"admin"})
    dead = {"tenant_admin", "super_admin"}
    for grp in (deps.FULL_ACCESS_ROLES, deps.OPS_ROLES, deps.DISPATCH_ROLES,
                deps.BACKOFFICE_ROLES, deps.REVIEW_ROLES, deps.TECH_ACTION_ROLES):
        assert not (dead & set(grp)), grp
    assert deps.TECH_ACTION_ROLES[-1] == "technician"


# ── R2（2026-07-09 續輪）：kb/sop/conversations/media 等 37 端點收斂 ──────────

_R2_PROTECTED_WRITES = [
    ("POST", "/api/v1/knowledge-base/cases", {"title": "x"}),                 # kb：客服域寫入
    ("POST", "/api/v1/knowledge-base/manuals/upload", {}),                    # kb：手冊管理（OPS）
    ("POST", "/api/v1/sop-drafts", {"title": "x"}),                           # sop 起草（後台）
    ("POST", f"/api/v1/sop-drafts/{uuid.uuid4()}/adopt", {}),                 # sop 採納（REVIEW）
    ("POST", "/api/v1/conversations", {"user_id": str(uuid.uuid4())}),        # 對話代開（後台）
    ("POST", f"/tenants/{TID}/conversations/{uuid.uuid4()}/messages", {"content": "x"}),
    ("PATCH", f"/api/v1/sentiment/alerts/{uuid.uuid4()}", {"status": "acknowledged"}),
    ("POST", f"/tenants/{TID}/rma-quality-findings", {"finding": "x"}),       # 品質記錄（OPS）
    ("POST", f"/tenants/{TID}/ai-governance/traces", {"trace": {}}),          # AI 治理（OPS）
    ("POST", "/api/v1/notifications/push", {"title": "x"}),                   # 手動推播（OPS）
]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["technician", "vendor"])
async def test_r2_writes_forbidden_for_field_roles(client, role):
    """R2 收斂：technician / vendor 寫 kb/sop/對話/情緒/品質/推播 → 403。"""
    headers = _headers(role)
    for method, path, body in _R2_PROTECTED_WRITES:
        res = await client.request(method, path, json=body, headers=headers)
        assert res.status_code == 403, f"{role} {method} {path} → {res.status_code}（應 403）"


@pytest.mark.asyncio
async def test_r2_technician_allowed_paths(client):
    """R2 白名單：技師傳媒體（完工照）與 SOP 回饋不被 RBAC 擋（可因 payload 4xx，非 403）。"""
    headers = {"Authorization": f"Bearer {_make_token(user_id=TECHNICIAN_USER_ID, role='technician')}",
               "X-Tenant-ID": TID}
    for method, path, body in [
        ("POST", "/api/v1/media", {}),                       # TECH_ACTION_ROLES
        ("POST", f"/tenants/{TID}/sop-feedback", {"sop_id": str(uuid.uuid4()), "helpful": True}),
    ]:
        res = await client.request(method, path, json=body, headers=headers)
        assert res.status_code != 403, f"technician {path} 被誤鎖（{res.status_code}）"


@pytest.mark.asyncio
async def test_r2_self_scoped_notifications_stay_open(client):
    """對帳定案：自身通知操作（mark-all-read）維持 require_tenant——技師也要能收/清自己的通知。"""
    headers = {"Authorization": f"Bearer {_make_token(user_id=TECHNICIAN_USER_ID, role='technician')}",
               "X-Tenant-ID": TID}
    res = await client.post("/api/v1/notifications/mark-all-read", json={}, headers=headers)
    assert res.status_code != 403, f"自身通知操作不應被 RBAC 擋（{res.status_code}）"
