"""CR-0131 fail-closed 白名單＋API_SURFACE 剔除清單（WBS 1.1.3 / SA-03 / SA-05）。

- SA-05：安全狀態不可驗（DB 離線 → revoked_jti/is_active 查核失能）時，
  關鍵金流/派工寫入（fail_closed=True 白名單 20 端點）拒絕 503；
  一般端點維持 C-05 fail-open（claims-only）取捨。
- SA-03：API_SURFACE=tech/platform 為白名單前綴過濾（fail-closed by construction）；
  剔除清單測試鎖定敏感路由絕不出現在精簡面；保留面下的派工端點仍由 RBAC 擋技師。
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID


def _walk(dep, acc):
    for d in dep.dependencies:
        if d.call is not None:
            acc.append(d.call)
        _walk(d, acc)


def _guard_info(route):
    """回 (roles, fail_closed)——自 role_required closure 抽取。"""
    calls = []
    _walk(route.dependant, calls)
    roles, fc = set(), False
    for c in calls:
        if "role_required" in getattr(c, "__qualname__", "") and c.__closure__:
            for cell in c.__closure__:
                v = cell.cell_contents
                if isinstance(v, tuple) and all(isinstance(x, str) for x in v):
                    roles |= set(v)
                if v is True:
                    fc = True
    return roles, fc


# ── SA-05：fail-closed 白名單 ────────────────────────────────────────────────

# 金流終局動作＋派工指派（發起/撤回類維持 fail-open 可用性——設計取捨記 CR-0131）
_FAIL_CLOSED_CANON = {
    ("POST", "/api/v1/refunds"),
    ("POST", "/api/v1/refunds/{id}/decision"),
    ("POST", "/tenants/{tenantId}/refunds/{refundId}/decision"),
    ("POST", "/tenants/{tenantId}/refunds:agent-initiate"),
    ("POST", "/tenants/{tenantId}/disputes/{disputeId}:review"),
    ("POST", "/tenants/{tenantId}/disputes/{disputeId}:co-sign"),
    ("POST", "/tenants/{tenantId}/accounting/invoices:from-quote"),
    ("POST", "/tenants/{tenantId}/tech-statements/{statementId}:approve"),
    ("POST", "/tenants/{tenantId}/tech-statements/{statementId}:mark-paid"),
    ("POST", "/tenants/{tenantId}/dispatcher-commissions/{statementId}:approve"),
    ("POST", "/tenants/{tenantId}/dispatcher-commissions/{statementId}:mark-paid"),
    ("POST", "/tenants/{tenantId}/brand-b2b-statements/{statementId}:approve"),
    ("POST", "/tenants/{tenantId}/brand-b2b-statements/{statementId}:mark-paid"),
    ("POST", "/api/v1/dispatch/assign"),
    ("POST", "/api/v1/dispatch/auto-match"),
    ("POST", "/tenants/{tenantId}/dispatch:plan"),
    ("POST", "/tenants/{tenantId}/dispatch:auto-match"),
    ("POST", "/api/v1/work-orders/{id}/assign"),
    ("POST", "/tenants/{tenantId}/work-orders/{id}:assign"),
    ("POST", "/tenants/{tenantId}/work-orders/{id}:reassign"),
}


def _load_app():
    import main as api_main
    return api_main.app


def test_fail_closed_whitelist_canon():
    """白名單正典對帳：runtime 反射 fail_closed=True 的端點集 == 文件化清單（防漂移）。"""
    from fastapi.routing import APIRoute

    app = _load_app()
    flagged = set()
    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue
        _, fc = _guard_info(r)
        if fc:
            for m in r.methods - {"HEAD", "OPTIONS"}:
                flagged.add((m, r.path))
    assert flagged == _FAIL_CLOSED_CANON, (
        f"多出：{flagged - _FAIL_CLOSED_CANON}；缺少：{_FAIL_CLOSED_CANON - flagged}"
    )


@pytest.mark.asyncio
async def test_fail_closed_rejects_when_state_unverifiable(client, admin_headers, monkeypatch):
    """安全狀態不可驗 → 白名單端點 503 SECURITY_STATE_UNAVAILABLE；一般寫入維持 fail-open。"""
    import core.auth as core_auth

    async def _no_conn(role=None):
        return None

    monkeypatch.setattr(core_auth, "_security_conn", _no_conn)

    # 白名單（派工指派）→ 503
    res = await client.post(
        f"/api/v1/work-orders/{uuid.uuid4()}/assign",
        json={"technician_id": str(uuid.uuid4()), "reason_code": "manual"},
        headers=admin_headers,
    )
    assert res.status_code == 503, res.text
    assert res.json().get("error_code") == "SECURITY_STATE_UNAVAILABLE"

    # 白名單（金流核准）→ 503
    res = await client.post(
        f"/tenants/{TID}/tech-statements/{uuid.uuid4()}:approve",
        json={}, headers=admin_headers,
    )
    assert res.status_code == 503

    # 非白名單寫入（問題卡建立）→ 維持 fail-open（claims-only），走到業務層非 503
    res = await client.post(
        "/api/v1/problem-cards",
        json={"conversation_id": str(uuid.uuid4()), "brand": "Yale", "model": "X",
              "symptom": "測試", "category": "維修", "urgency": "medium"},
        headers=admin_headers,
    )
    assert res.status_code != 503, f"一般端點不應 fail-closed（{res.status_code}）"


@pytest.mark.asyncio
async def test_fail_closed_normal_path_unaffected(client, admin_headers):
    """DB 正常時白名單端點照常走到業務層（404/422 等，非 503）。"""
    res = await client.post(
        f"/api/v1/work-orders/{uuid.uuid4()}/assign",
        json={"technician_id": str(uuid.uuid4()), "reason_code": "manual"},
        headers=admin_headers,
    )
    assert res.status_code != 503


# ── SA-03：API_SURFACE 剔除清單 ──────────────────────────────────────────────

# tech 精簡面絕不可出現的路由前綴（金流/派工計畫/治理/平台/後台管理）
_TECH_EXCLUDED_PREFIXES = (
    "/api/v1/accounting", "/api/v1/refunds", "/api/v1/dispatch", "/api/v1/roles",
    "/api/v1/staff", "/api/v1/platform", "/api/v1/pricing", "/api/v1/notifications",
    "/api/v1/knowledge-base", "/api/v1/sop-drafts", "/api/v1/conversations",
    "/api/v1/customers", "/api/v1/sentiment",
    "/tenants/{tenantId}/accounting", "/tenants/{tenantId}/refunds",
    "/tenants/{tenantId}/disputes", "/tenants/{tenantId}/dispatch",
    "/tenants/{tenantId}/inventory", "/tenants/{tenantId}/quotes",
    "/tenants/{tenantId}/roles", "/tenants/{tenantId}/staff-applications",
    "/tenants/{tenantId}/conversations", "/tenants/{tenantId}/notifications",
    "/tenants/{tenantId}/scheduled-reports", "/tenants/{tenantId}/gdpr",
    "/tenants/{tenantId}/m18", "/tenants/{tenantId}/brand-b2b-statements",
    "/tenants/{tenantId}/dispatcher-commissions",
    "/vouchers", "/sops", "/kb",
)


def test_tech_surface_exclusion_list():
    """tech 面白名單過濾：全 app 敏感路由一條都不得保留（fail-closed by construction）。"""
    from main import _tech_surface_keep

    app = _load_app()
    leaked = []
    for r in app.routes:
        p = getattr(r, "path", "")
        if any(p.startswith(x) for x in _TECH_EXCLUDED_PREFIXES) and _tech_surface_keep(p):
            leaked.append(p)
    assert not leaked, f"tech 面外洩路由：{leaked}"
    # 技師必要面必須保留（防過濾過頭）
    for kept in ("/api/v1/technicians/login", "/api/v1/work-orders/{id}/accept",
                 "/tenants/{tenantId}/media", "/tenants/{tenantId}/tech-statements"):
        assert _tech_surface_keep(kept), f"技師必要路由被誤剔：{kept}"


def test_platform_surface_exclusion_list():
    """platform 面只保留 platform v1/v2（＋infra）；其餘一律剔除。"""
    from main import _platform_surface_keep

    app = _load_app()
    infra = ("/health", "/docs", "/openapi.json", "/redoc")
    leaked = [
        getattr(r, "path", "") for r in app.routes
        if _platform_surface_keep(getattr(r, "path", ""))
        and not getattr(r, "path", "").startswith(
            ("/api/v1/platform", "/api/v2/platform") + infra
        )
    ]
    assert not leaked, f"platform 面外洩路由：{leaked}"


def test_tech_surface_kept_dispatch_still_rbac_guarded():
    """保留前綴下的派工端點（assign 在 /work-orders 前綴內）仍由 RBAC 擋技師——
    surface 是部署塑形，安全靠每端點守衛（C-11）。"""
    from fastapi.routing import APIRoute
    from main import _tech_surface_keep

    app = _load_app()
    checked = 0
    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue
        p = r.path
        if _tech_surface_keep(p) and (":assign" in p or p.endswith("/assign") or ":reassign" in p):
            roles, _ = _guard_info(r)
            assert roles and "technician" not in roles, f"{p} 技師不應可派工（roles={roles}）"
            checked += 1
    assert checked >= 3, "應至少涵蓋 v1 assign + v2 assign/reassign"
