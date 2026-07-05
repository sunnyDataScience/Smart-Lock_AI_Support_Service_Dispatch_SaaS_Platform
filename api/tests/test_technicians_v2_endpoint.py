"""Component tests for M05 technicians v2 tenant-scoped endpoints（CR-0002-α）。

測試矩陣：
  1. GET /tenants/{tenantId}/technicians → 200 tenant-scoped list（cursor 分頁）
  2. GET /tenants/{tenantId}/technicians/{techId} → 200 或 404（不存在的 techId）
  3. cross-tenant guard → 403 CROSS_TENANT_READ
  4. PATCH /tenants/{tenantId}/technicians/{techId} → updateTechnicianV2（CR-0103 編輯基本資料）
  5. cross-tenant update → 403 CROSS_TENANT_WRITE
     （:suspend/:reactivate 改走 technician_lifecycle_v2，CR-0103 已移除本檔重複 501 stub）
  6. legacy GET /api/v1/technicians → 200 + Deprecation header（D3 雙掛驗證）
  7. legacy GET /api/v1/technicians/{id} → 200/404 + Deprecation header

注意：worktree 無真實 DB，component 測試須在有 DB 的環境跑。
      此處確保 test 結構正確 + pytest.mark.component 標記完整。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_other_tenant_path_headers(
    role: str = "admin",
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, str]:
    """JWT 屬於 DEFAULT_TENANT 但打 OTHER_TENANT path → cross-tenant guard。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=str(uuid.uuid4()),
        role=role,
        tenant_id=tenant_id,
        token_type="access",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": DEFAULT_TENANT_ID,
    }


# ---------------------------------------------------------------------------
# List technicians v2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_technicians_v2_200(client, admin_headers):
    """GET /tenants/{tenantId}/technicians → 200 tenant-scoped list。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "has_more" in body
    # tenant-scoped：所有結果應有 id 欄位
    for item in body["items"]:
        assert "id" in item


@pytest.mark.asyncio
async def test_list_technicians_v2_pagination(client, admin_headers):
    """GET /tenants/{tenantId}/technicians?limit=1 → cursor 分頁。"""
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians?limit=1",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_list_technicians_v2_cross_tenant_403(client):
    """cross-tenant：path tenantId 與 JWT claim 不符 → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/technicians",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


@pytest.mark.asyncio
async def test_technician_response_exposes_onboarding_status():
    """list/get 回應須帶 onboarding status（供前端核准按鈕/狀態徽章）。

    回歸：Technician schema 原無 status 欄 → Pydantic extra=ignore 丟掉，
    前端永遠看不出誰 pending_approval、無從顯示核准按鈕。
    """
    import core.db as db_module
    from services import technician_service

    assert await db_module._ensure_conn()
    techid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, name, phone, capabilities, service_regions, status) "
        "VALUES (%s::uuid, %s::uuid, '待核技師', '0912345678', '[]'::jsonb, '[]'::jsonb, 'pending_approval')",
        (techid, DEFAULT_TENANT_ID))
    try:
        page = await technician_service.list_technicians(
            tenant_id=DEFAULT_TENANT_ID, cursor=None, limit=100, status="pending_approval")
        mine = [t for t in page["items"] if t["id"] == techid]
        assert mine, "新建 pending 技師應出現在 status 過濾列表"
        assert mine[0]["status"] == "pending_approval"
        one = await technician_service.get_technician(
            tenant_id=DEFAULT_TENANT_ID, technician_id=techid)
        assert one["status"] == "pending_approval"
    finally:
        await db_module._conn.execute("DELETE FROM technicians WHERE id=%s::uuid", (techid,))


# ---------------------------------------------------------------------------
# Get technician v2 (detail)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_technician_v2_not_found(client, admin_headers):
    """GET 不存在的 technician → 404。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians/{fake_id}",
        headers=admin_headers,
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_get_technician_v2_cross_tenant_403(client):
    """cross-tenant get → 403 CROSS_TENANT_READ。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/tenants/{OTHER_TENANT_ID}/technicians/{fake_id}",
        headers=headers,
    )
    assert res.status_code == 403, res.text
    body = res.json()
    assert body.get("error_code") == "CROSS_TENANT_READ"


# ---------------------------------------------------------------------------
# Suspend technician v2 (stub — 501)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brand_suspend_endpoint_removed(client, admin_headers):
    """CR-0114 R3:品牌端 :suspend 已搬平台方 → 品牌路徑 405 Method Not Allowed。

    師傅生命週期審核改由 platform console（/api/v1/platform/technicians/{id}:suspend）
    負責;品牌端只保留唯讀 lifecycle-events。完整生命週期覆蓋見
    test_technician_login_status_gate.py（打平台端點）。
    """
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians/{fake_id}:suspend",
        headers=admin_headers,
    )
    assert res.status_code == 405, res.text


# 註：原 test_suspend_technician_v2_cross_tenant_403 已移除。suspend 由 501 stub 改為 FR-0044
# dual-sign 端點（需 X-Initiator + body）；FastAPI body 驗證先於 handler 內 cross-tenant guard，
# 故無 body 的 cross-tenant 請求得 422 而非 403。suspend 的 cross-tenant + 完整生命週期由
# test_technician_lifecycle.py 覆蓋，此處不重複維護 stale stub。


# ---------------------------------------------------------------------------
# Update technician v2 (CR-0103 admin 編輯基本資料)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_technician_v2_partial(client, admin_headers):
    """PATCH /tenants/{tenantId}/technicians/{techId} → 部分更新 name/phone/capabilities/regions；
    未帶的欄位（email）保留不變。"""
    import core.db as db_module

    assert await db_module._ensure_conn()
    techid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, name, phone, email, capabilities, service_regions, status) "
        "VALUES (%s::uuid, %s::uuid, '原名', '0911000000', 'old@x.com', "
        "'[\"Yale\"]'::jsonb, '[\"TPE\"]'::jsonb, 'active')",
        (techid, DEFAULT_TENANT_ID))
    try:
        res = await client.patch(
            f"/tenants/{DEFAULT_TENANT_ID}/technicians/{techid}",
            headers=admin_headers,
            json={
                "display_name": "新名字",
                "phone": "0922371211",
                "capabilities": ["Dormakaba", "Kaadas"],
                "coverage_areas": ["TPE", "NTC"],
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["name"] == "新名字"
        assert data["phone"] == "0922371211"
        # capabilities/regions/email 經 DB 確認（避免猜 response 欄名）
        cur = await db_module._conn.execute(
            "SELECT email, capabilities, service_regions FROM technicians WHERE id=%s::uuid",
            (techid,))
        email, caps, regions = await cur.fetchone()
        assert email == "old@x.com"  # 未帶 → 不變（部分更新）
        assert set(caps) == {"Dormakaba", "Kaadas"}
        assert set(regions) == {"TPE", "NTC"}
    finally:
        await db_module._conn.execute("DELETE FROM technicians WHERE id=%s::uuid", (techid,))


@pytest.mark.asyncio
async def test_update_technician_v2_not_found(client, admin_headers):
    """PATCH 不存在的 technician → 404。"""
    fake_id = str(uuid.uuid4())
    res = await client.patch(
        f"/tenants/{DEFAULT_TENANT_ID}/technicians/{fake_id}",
        headers=admin_headers,
        json={"display_name": "x"},
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_update_technician_v2_cross_tenant_403(client):
    """cross-tenant PATCH（帶 body 通過驗證後，handler guard 擋）→ 403 CROSS_TENANT_WRITE。"""
    headers = _make_other_tenant_path_headers()
    fake_id = str(uuid.uuid4())
    res = await client.patch(
        f"/tenants/{OTHER_TENANT_ID}/technicians/{fake_id}",
        headers=headers,
        json={"display_name": "x"},
    )
    assert res.status_code == 403, res.text
    assert res.json().get("error_code") == "CROSS_TENANT_WRITE"


# ---------------------------------------------------------------------------
# Legacy endpoints — Deprecation header (D3 dual-hang)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_list_technicians_has_deprecation_header(client, admin_headers):
    """GET /api/v1/technicians → 200 + Deprecation: true（D3 雙掛驗證）。"""
    res = await client.get(
        "/api/v1/technicians",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    # D3 核心契約＝Deprecation header（DeprecationMiddleware 對所有 /api/v1 回應保證，含 error path）。
    # Link successor-version 為 per-route success-path 附加，此處不硬性要求。


@pytest.mark.asyncio
async def test_legacy_get_technician_has_deprecation_header(client, admin_headers):
    """GET /api/v1/technicians/{id} → 404 + Deprecation: true（D3 雙掛驗證，即使 404 也帶 header）。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(
        f"/api/v1/technicians/{fake_id}",
        headers=admin_headers,
    )
    # 無論 404 或 200 都應帶 Deprecation header
    assert res.headers.get("deprecation") == "true", (
        f"Expected Deprecation: true header, got: {dict(res.headers)}"
    )
    # D3 核心契約＝Deprecation header（DeprecationMiddleware 對所有 /api/v1 回應保證，含 error path）。
    # Link successor-version 為 per-route success-path 附加（error path 會隨 raise 遺失），此處不硬性要求。
