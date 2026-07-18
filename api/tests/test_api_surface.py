"""CR-0112:API_SURFACE 部署塑形(師傅端/派工方雙 stack 拆分)。

驗證三件事:
1. 預設(all)完整掛載 —— 既有部署零行為變化。
2. tech 面前綴判定保留技師 app 全部呼叫面、剔除派工/帳務/internal/LINE webhook。
3. 對真實 app 路由表做模擬過濾,確認技師端點存活、派工端點消失
   (不重載 main 模組 —— 過濾邏輯本身是純函式,直接驗證判定結果)。
"""

from __future__ import annotations

import pytest

import main


@pytest.mark.unit
def test_default_surface_mounts_everything():
    """預設 API_SURFACE=all:派工/帳務/internal 路由全部在。"""
    paths = {getattr(r, "path", "") for r in main.app.router.routes}
    assert any(p.startswith("/api/v1/dispatch") for p in paths)
    assert any(p.startswith("/tenants/{tenantId}/dispatch") for p in paths)
    assert any(p.startswith("/api/v1/internal") for p in paths)
    assert any(p.startswith("/api/v1/accounting/invoices") for p in paths)
    # 技師面同樣在
    assert "/api/v1/technicians/login" in paths
    assert any(p.startswith("/tenants/{tenantId}/work-orders") for p in paths)


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/request-password-reset",
        "/api/v1/technicians/login",
        "/api/v1/technicians/register",
        "/api/v1/technicians/me/availability",
        "/api/v1/work-orders/pool",
        "/api/v1/work-orders/{wo_id}/door-check",
        "/api/v1/problem-cards/{card_id}",
        "/api/v1/media/{media_id}",
        "/tenants/{tenantId}/work-orders/pool",
        "/tenants/{tenantId}/work-orders/{woId}/onsite/completion",
        "/tenants/{tenantId}/tech-statements",
        "/tenants/{tenantId}/media",
        "/realtime/pool/{tech_id}",
        "/realtime/work-orders/{wo_id}",
    ],
)
def test_tech_surface_keeps_technician_endpoints(path):
    assert main._tech_surface_keep(path), f"技師面應保留 {path}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/dispatch/assign",
        "/api/v1/vendors/register",
        "/api/v1/accounting/invoices",
        "/api/v1/internal/conversations/ingest",
        "/api/v1/line/webhook",
        "/api/v1/conversations",
        "/api/v1/customers",
        "/tenants/{tenantId}/dispatch/queue",
        "/tenants/{tenantId}/quote-catalog/{segment}",
        "/tenants/{tenantId}/technicians/{technicianId}:onboard-approve",
        "/realtime/dispatch-queue",
        "/realtime/sla-alerts",
        "/realtime/refunds",
    ],
)
def test_tech_surface_drops_dispatch_endpoints(path):
    assert not main._tech_surface_keep(path), f"技師面不應保留 {path}"


@pytest.mark.unit
def test_tech_surface_simulated_filter_on_real_routes():
    """對真實路由表模擬 tech 過濾:技師端點存活、派工端點消失、健康檢查在。"""
    kept = {
        getattr(r, "path", "")
        for r in main.app.router.routes
        if main._tech_surface_keep(getattr(r, "path", ""))
    }
    assert "/health" in kept
    assert "/api/v1/technicians/login" in kept
    assert any(p.startswith("/tenants/{tenantId}/work-orders") for p in kept)
    assert any(p.startswith("/tenants/{tenantId}/tech-statements") for p in kept)
    assert "/realtime/pool/{tech_id}" in kept
    assert not any(p.startswith("/api/v1/dispatch") for p in kept)
    # CR-0169 起 /api/v1/internal/technicians（品牌 api → LINE 推播）為技師面
    # 白名單例外；其餘 internal（ingest 等）仍須剔除。
    assert not any(
        p.startswith("/api/v1/internal")
        and not p.startswith("/api/v1/internal/technicians")
        for p in kept
    )
    assert any(p.startswith("/api/v1/internal/technicians") for p in kept)
    assert not any("/line/webhook" in p for p in kept)
    assert not any(p.startswith("/tenants/{tenantId}/dispatch") for p in kept)
    # 過濾是縮減不是清空:保留數量在合理範圍(> 20 條技師面路由)
    assert len(kept) > 20


# ── CR-0114 收斂:dispatch 面剔除過濾(品牌 API 不服務平台端點/師傅自助註冊)──


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/platform/auth/login",
        "/api/v1/platform/technicians/{technicianId}:onboard-approve",
        "/api/v1/platform/technicians/{technicianId}:suspend",
        "/api/v1/platform/brand-applications",
        "/api/v1/technicians/register",
        "/api/v1/technicians/registration-documents",  # CR-0115 孿生公開寫端點
    ],
)
def test_dispatch_surface_drops_platform_and_register(path):
    """品牌面剔除:平台 console 端點(平台 stack 自有 API)+ 師傅自助註冊
    (師傅註冊動線=tech 站;留在品牌 API 會產生品牌庫幽靈師傅)。"""
    assert not main._dispatch_surface_keep(path), f"品牌面不應保留 {path}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/api/v1/auth/login",
        "/api/v1/technicians/login",  # 只剔 register,登入照舊(3000/tech-login 沿用)
        "/api/v1/dispatch/assign",
        "/tenants/{tenantId}/technicians",
        "/tenants/{tenantId}/work-orders",
        "/api/v1/accounting/invoices",
    ],
)
def test_dispatch_surface_keeps_brand_endpoints(path):
    assert main._dispatch_surface_keep(path), f"品牌面應保留 {path}"


@pytest.mark.unit
def test_dispatch_surface_simulated_filter_on_real_routes():
    """對真實路由表模擬 dispatch 過濾:平台端點/師傅註冊消失,品牌面全數存活。"""
    kept = {
        getattr(r, "path", "")
        for r in main.app.router.routes
        if main._dispatch_surface_keep(getattr(r, "path", ""))
    }
    dropped = {
        getattr(r, "path", "") for r in main.app.router.routes
    } - kept
    assert not any(p.startswith("/api/v1/platform") for p in kept)
    assert "/api/v1/technicians/register" not in kept
    assert "/api/v1/technicians/registration-documents" not in kept  # CR-0115 孿生端點
    assert "/api/v1/technicians/login" in kept
    assert any(p.startswith("/api/v1/dispatch") for p in kept)
    assert any(p.startswith("/tenants/{tenantId}/technicians") for p in kept)
    # 剔除的每一條都屬兩類之一(平台前綴 or 師傅公開寫端點 register/registration-documents)
    assert all(
        p.startswith("/api/v1/platform") or p.startswith("/api/v1/technicians/regist")
        for p in dropped
    ), dropped
