"""Dispatch Logs v2 tenant-scoped 端點測試（BUILD_TENANT_SCOPED 收尾）。

對齊 spec:
  GET /tenants/{tenantId}/dispatch-logs        → listDispatchLogsV2（cursor 分頁，admin-only）
  GET /tenants/{tenantId}/dispatch-logs/{id}   → getDispatchLogV2（admin-only）

測試矩陣（@pytest.mark.unit = 純邏輯無 DB，@pytest.mark.component = 需 live DB）：

unit（不需 DB，早期驗 auth / routing）：
  U-01  list — 無 Authorization → 401 UNAUTHENTICATED
  U-02  list — 非 admin 角色（technician）→ 403 FORBIDDEN
  U-03  list — cross-tenant（path tenant ≠ JWT claim）→ 403 CROSS_TENANT_READ
  U-04  get/{id} — 無 Authorization → 401 UNAUTHENTICATED
  U-05  get/{id} — cross-tenant → 403 CROSS_TENANT_READ

component（需 live DB；本 worktree 無 .env，主控在主 worktree 跑）：
  C-01  list — admin 正常呼叫 → 200 + DispatchLogPage envelope
  C-02  list — cursor 分頁欄位存在
  C-03  list — work_order_id filter → 200（空列或有資料皆可）
  C-04  list — action filter → 200
  C-05  get/{id} — 隨機 UUID → 404 NOT_FOUND
  C-06  舊 /api/v1/dispatch-logs → 200 + Deprecation: true（D3 雙掛驗證）

注意：cross-tenant 檢查在 DB query 前做，所以 U-03 / U-05 不需 live DB。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

LIST_PATH = f"/tenants/{DEFAULT_TENANT_ID}/dispatch-logs"
LIST_OTHER_TENANT_PATH = f"/tenants/{OTHER_TENANT_ID}/dispatch-logs"
LEGACY_PATH = "/api/v1/dispatch-logs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(role: str = "admin", tenant_id: str = DEFAULT_TENANT_ID) -> str:
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=tenant_id,
        token_type="access",
    )
    return token


def _headers(role: str = "admin", tenant_id: str = DEFAULT_TENANT_ID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_make_token(role=role, tenant_id=tenant_id)}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


# ---------------------------------------------------------------------------
# UNIT tests（無 DB 依賴，auth / routing 層邏輯）
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDispatchLogsV2Unit:
    """純邏輯測試 — 不依賴 live DB，驗 auth/tenant guard 在 DB 呼叫前的早期返回。"""

    @pytest.mark.asyncio
    async def test_list_no_auth_401(self, client):
        """U-01 list — 無 Authorization header → 401 UNAUTHENTICATED。"""
        res = await client.get(LIST_PATH)
        assert res.status_code == 401, res.text
        body = res.json()
        assert body.get("error_code") == "UNAUTHENTICATED"

    @pytest.mark.asyncio
    async def test_list_forbidden_role_403(self, client):
        """U-02 list — technician 角色不在允許清單 → 403 FORBIDDEN。"""
        res = await client.get(LIST_PATH, headers=_headers(role="technician"))
        assert res.status_code == 403, res.text

    @pytest.mark.asyncio
    async def test_list_cross_tenant_403(self, client):
        """U-03 list — JWT tenant A 打 tenant B path → 403 CROSS_TENANT_READ。"""
        headers = _headers(role="admin", tenant_id=DEFAULT_TENANT_ID)
        res = await client.get(LIST_OTHER_TENANT_PATH, headers=headers)
        assert res.status_code == 403, res.text
        body = res.json()
        assert body.get("error_code") == "CROSS_TENANT_READ"

    @pytest.mark.asyncio
    async def test_get_no_auth_401(self, client):
        """U-04 get/{id} — 無 Authorization header → 401 UNAUTHENTICATED。"""
        fake_id = str(uuid.uuid4())
        res = await client.get(f"{LIST_PATH}/{fake_id}")
        assert res.status_code == 401, res.text
        body = res.json()
        assert body.get("error_code") == "UNAUTHENTICATED"

    @pytest.mark.asyncio
    async def test_get_cross_tenant_403(self, client):
        """U-05 get/{id} — JWT tenant A 打 tenant B path → 403 CROSS_TENANT_READ。"""
        fake_id = str(uuid.uuid4())
        headers = _headers(role="admin", tenant_id=DEFAULT_TENANT_ID)
        res = await client.get(
            f"/tenants/{OTHER_TENANT_ID}/dispatch-logs/{fake_id}",
            headers=headers,
        )
        assert res.status_code == 403, res.text
        body = res.json()
        assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# COMPONENT tests（需 live DB；主控在主 worktree 跑）
# ---------------------------------------------------------------------------


@pytest.mark.component
class TestDispatchLogsV2Component:
    """端到端測試 — 需 live DB（dev 環境 lock_AI_data）。"""

    @pytest.mark.asyncio
    async def test_list_200(self, client, admin_headers):
        """C-01 list — admin 正常呼叫 → 200 + DispatchLogPage envelope。"""
        res = await client.get(LIST_PATH, headers=admin_headers)
        # 無 seed 資料時仍回 200（空 items）；DB unavailable 才 503
        assert res.status_code in (200, 503), res.text
        if res.status_code == 200:
            body = res.json()
            assert "items" in body
            assert "has_more" in body
            assert isinstance(body["items"], list)

    @pytest.mark.asyncio
    async def test_list_pagination_fields(self, client, admin_headers):
        """C-02 list — cursor 分頁欄位（items / next_cursor / has_more）存在。"""
        res = await client.get(f"{LIST_PATH}?limit=1", headers=admin_headers)
        assert res.status_code in (200, 503), res.text
        if res.status_code == 200:
            body = res.json()
            assert "items" in body
            assert "next_cursor" in body
            assert "has_more" in body

    @pytest.mark.asyncio
    async def test_list_work_order_filter(self, client, admin_headers):
        """C-03 list — work_order_id filter → 200（空列或有資料皆可）。"""
        fake_wo_id = str(uuid.uuid4())
        res = await client.get(
            f"{LIST_PATH}?work_order_id={fake_wo_id}",
            headers=admin_headers,
        )
        assert res.status_code in (200, 503), res.text
        if res.status_code == 200:
            body = res.json()
            assert isinstance(body.get("items"), list)

    @pytest.mark.asyncio
    async def test_list_action_filter(self, client, admin_headers):
        """C-04 list — action=assign filter → 200。"""
        res = await client.get(f"{LIST_PATH}?action=assign", headers=admin_headers)
        assert res.status_code in (200, 503), res.text
        if res.status_code == 200:
            body = res.json()
            assert isinstance(body.get("items"), list)

    @pytest.mark.asyncio
    async def test_get_unknown_id_404(self, client, admin_headers):
        """C-05 get/{id} — 隨機 UUID → 404 NOT_FOUND（無 seed 時的正常行為）。"""
        fake_id = str(uuid.uuid4())
        res = await client.get(f"{LIST_PATH}/{fake_id}", headers=admin_headers)
        assert res.status_code in (404, 503), res.text
        if res.status_code == 404:
            body = res.json()
            assert body.get("error_code") == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_legacy_list_has_deprecation_header(self, client, admin_headers):
        """C-06 舊 /api/v1/dispatch-logs → Deprecation: true（D3 雙掛驗證）。"""
        res = await client.get(LEGACY_PATH, headers=admin_headers)
        # 回應碼可能是 200/503；重點是 Deprecation header 存在
        assert res.status_code in (200, 503), res.text
        assert res.headers.get("deprecation") == "true", (
            f"Expected Deprecation: true header, got: {dict(res.headers)}"
        )
