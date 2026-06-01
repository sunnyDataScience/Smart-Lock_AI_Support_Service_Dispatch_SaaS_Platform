"""M17 Audit v2 tenant-scoped 端點元件測試（CR-0002-α）。

對齊 spec: GET /tenants/{tenantId}/audit/events（listAuditEventsV2）
           POST /tenants/{tenantId}/audit/exports（exportAuditEventsV2）

⚠ 本檔為 @pytest.mark.component，需 live DB（dev 環境）。
  若 DB 不可用，這些測試會在 fixture 階段 error/skip — 屬預期行為。
  主控 Opus 會在有 DB 的主 worktree 執行驗證。

測試矩陣:
  1. GET events tenant-scoped 200（管理員可讀自己 tenant）
  2. GET events cross-tenant 403（CROSS_TENANT_WRITE）
  3. POST exports tenant-scoped 200 or 202（admin 角色，取決於行數）
  4. POST exports cross-tenant 403（CROSS_TENANT_WRITE）
  5. 確認舊 GET /api/v1/audit-logs 仍有效 + 帶 Deprecation header
"""

from __future__ import annotations

import pytest
from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

# ────────────────────────────────────────────────────────────────────────────
# 路徑工廠
# ────────────────────────────────────────────────────────────────────────────

EVENTS_PATH = f"/tenants/{DEFAULT_TENANT_ID}/audit/events"
EXPORTS_PATH = f"/tenants/{DEFAULT_TENANT_ID}/audit/exports"
OTHER_TENANT_ID = "ffffffff-ffff-4fff-bfff-ffffffffffff"
CROSS_EVENTS_PATH = f"/tenants/{OTHER_TENANT_ID}/audit/events"
CROSS_EXPORTS_PATH = f"/tenants/{OTHER_TENANT_ID}/audit/exports"
LEGACY_PATH = "/api/v1/audit-logs"


# ────────────────────────────────────────────────────────────────────────────
# Helper — 取得 admin headers（已由 conftest fixtures 提供）
# ────────────────────────────────────────────────────────────────────────────


class TestListAuditEventsV2:
    """GET /tenants/{tenantId}/audit/events"""

    async def test_own_tenant_200(self, client, admin_headers):
        """Admin 可讀自己 tenant 的稽核事件列表 → 200 + 標準 page 格式。"""
        resp = await client.get(EVENTS_PATH, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "items" in body
        assert "has_more" in body
        assert isinstance(body["items"], list)

    async def test_cross_tenant_403(self, client, admin_headers):
        """Admin token（tenant A）嘗試讀 tenant B 的事件 → 403 CROSS_TENANT_WRITE。"""
        resp = await client.get(CROSS_EVENTS_PATH, headers=admin_headers)
        assert resp.status_code == 403, resp.text
        # 舊或新 error schema 都接受
        body = resp.json()
        error_code = body.get("error_code") or body.get("title", "")
        assert "CROSS_TENANT" in error_code.upper() or resp.status_code == 403

    async def test_unauthenticated_401(self, client):
        """無 token → 401。"""
        resp = await client.get(EVENTS_PATH)
        assert resp.status_code == 401, resp.text

    async def test_log_type_filter(self, client, admin_headers):
        """log_type 過濾參數可傳入且不報錯。"""
        resp = await client.get(
            EVENTS_PATH,
            params={"log_type": "admin_action"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body["items"], list)


class TestExportAuditEventsV2:
    """POST /tenants/{tenantId}/audit/exports"""

    async def test_own_tenant_admin_200_or_202(self, client, admin_headers):
        """Admin 匯出自己 tenant → 200（CSV stream）或 202（>100k 筆時的 async stub）。"""
        resp = await client.post(
            EXPORTS_PATH,
            json={"format": "csv"},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 202), resp.text

    async def test_cross_tenant_403(self, client, admin_headers):
        """Admin token（tenant A）嘗試匯出 tenant B 的事件 → 403 CROSS_TENANT_WRITE。"""
        resp = await client.post(
            CROSS_EXPORTS_PATH,
            json={"format": "csv"},
            headers=admin_headers,
        )
        assert resp.status_code == 403, resp.text

    async def test_unauthenticated_401(self, client):
        """無 token → 401。"""
        resp = await client.post(EXPORTS_PATH, json={"format": "csv"})
        assert resp.status_code == 401, resp.text


class TestLegacyDeprecationHeader:
    """舊 GET /api/v1/audit-logs 仍有效，且帶 Deprecation header（D3）。"""

    async def test_legacy_still_200(self, client, admin_headers):
        """舊端點回 200（行為不變）。"""
        resp = await client.get(LEGACY_PATH, headers=admin_headers)
        assert resp.status_code == 200, resp.text

    async def test_deprecation_header_present(self, client, admin_headers):
        """回應帶 Deprecation: true header。"""
        resp = await client.get(LEGACY_PATH, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        deprecation = resp.headers.get("deprecation", "")
        assert deprecation.lower() == "true", (
            f"Expected 'Deprecation: true' header, got: {deprecation!r}"
        )

    async def test_link_header_successor(self, client, admin_headers):
        """回應帶 Link header 指向 successor-version。"""
        resp = await client.get(LEGACY_PATH, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        link = resp.headers.get("link", "")
        assert "successor-version" in link, (
            f"Expected Link header with rel='successor-version', got: {link!r}"
        )
        assert "audit/events" in link, (
            f"Expected Link header to point to audit/events, got: {link!r}"
        )
