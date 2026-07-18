"""CR-0114:API_SURFACE=platform 部署塑形(平台方 console 精簡面)。

對齊 test_api_surface.py 的驗法:
1. 預設(all)完整掛載 —— platform 路由與品牌路由並存,零行為變化。
2. platform 面前綴判定只留 /api/v1/platform(+健康/文件),剔除品牌/技師/internal。
3. 對真實 app 路由表做模擬過濾,確認平台端點存活、其餘消失。
"""

from __future__ import annotations

import pytest

import main


@pytest.mark.unit
def test_default_surface_mounts_platform_routes():
    """預設 API_SURFACE=all:platform 路由掛載,品牌面不受影響。"""
    paths = {getattr(r, "path", "") for r in main.app.router.routes}
    assert "/api/v1/platform/auth/login" in paths
    assert "/api/v1/platform/auth/refresh" in paths
    assert "/api/v1/platform/auth/logout" in paths
    assert "/api/v1/platform/me" in paths
    # 品牌面仍完整
    assert "/api/v1/auth/login" in paths
    assert any(p.startswith("/tenants/{tenantId}/work-orders") for p in paths)


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/docs",
        "/openapi.json",
        "/api/v1/platform/auth/login",
        "/api/v1/platform/auth/refresh",
        "/api/v1/platform/auth/logout",
        "/api/v1/platform/me",
        # R2/R3 未來端點也天然被同一前綴涵蓋
        "/api/v1/platform/brand-applications",
        "/api/v1/platform/technicians/{technicianId}:onboard-approve",
    ],
)
def test_platform_surface_keeps_platform_endpoints(path):
    assert main._platform_surface_keep(path), f"平台面應保留 {path}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/login",
        "/api/v1/technicians/login",
        "/api/v1/vendors/login",  # register 已於 UAT R2 W3-2 移除，改列 login

        "/api/v1/dispatch/assign",
        "/api/v1/internal/conversations/ingest",
        "/api/v1/line/webhook",
        "/tenants/{tenantId}/work-orders",
        "/tenants/{tenantId}/technicians/{technicianId}:onboard-approve",
        "/realtime/pool/{tech_id}",
        "/realtime/dispatch-queue",
    ],
)
def test_platform_surface_drops_brand_and_tech_endpoints(path):
    assert not main._platform_surface_keep(path), f"平台面不應保留 {path}"


@pytest.mark.unit
def test_platform_surface_simulated_filter_on_real_routes():
    """對真實路由表模擬 platform 過濾:平台端點存活、品牌/技師端點消失。"""
    kept = {
        getattr(r, "path", "")
        for r in main.app.router.routes
        if main._platform_surface_keep(getattr(r, "path", ""))
    }
    assert "/health" in kept
    assert "/api/v1/platform/auth/login" in kept
    assert "/api/v1/platform/me" in kept
    assert not any(p.startswith("/api/v1/auth") for p in kept)
    assert not any(p.startswith("/api/v1/technicians") for p in kept)
    assert not any(p.startswith("/tenants/") for p in kept)
    assert not any(p.startswith("/realtime/") for p in kept)
    # 平台面是極小面:除健康/文件外只有 /api/v1/platform 前綴
    platform_routes = [p for p in kept if p.startswith("/api/v1/platform")]
    assert len(platform_routes) >= 4
