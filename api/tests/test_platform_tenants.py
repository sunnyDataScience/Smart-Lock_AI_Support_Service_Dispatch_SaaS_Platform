"""CR-0118:平台 console 租戶管理 — 已開站租戶 registry 檢視 + 生命週期。

單庫 fallback:tenant 住主連線 → 以 Schema_platform.sql 冪等建表。

驗證:
  - RBAC:無 token 401、品牌 admin token 403
  - 核准品牌申請連動:approve → 自動登錄租戶(response 帶 tenant_id、清單可見)
  - 生命週期:suspend(active→suspended,寫 status_changed_by)、reactivate、
    重複 suspend 409、不存在 404
  - 查詢:詳情、?status= 過濾
  - create_from_application idempotent(同 slug 只一列)
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio

import core.db as db_module
from core.auth import hash_password
from services import platform_tenant_service as svc

pytestmark = pytest.mark.component

BASE = "/api/v1/platform/tenants"
BRAND_APPS = "/api/v1/platform/brand-applications"
PLATFORM_LOGIN = "/api/v1/platform/auth/login"
PASSWORD = "platform-test-pw-123"
_MARK = "CR0118測試品牌"  # company_name 標記,fixture 據此清 brand_applications

_SCHEMA = Path(__file__).resolve().parents[2] / "SQL" / "platform" / "Schema_platform.sql"


@pytest_asyncio.fixture(autouse=True)
async def _ensure_platform_schema():
    """套平台 schema(冪等,含 tenant)+ 清 registry 隔離每測試。"""
    assert await db_module._ensure_conn()
    await db_module._conn.execute(_SCHEMA.read_text(encoding="utf-8"))
    # tenant.application_id FK → 先清 tenant 再清標記 application(ON DELETE SET NULL 亦可任序)
    await db_module._conn.execute("DELETE FROM tenant")
    await db_module._conn.execute("DELETE FROM brand_applications WHERE company_name = %s", (_MARK,))
    yield
    await db_module._conn.execute("DELETE FROM tenant")
    await db_module._conn.execute("DELETE FROM brand_applications WHERE company_name = %s", (_MARK,))


async def _platform_admin_token(client) -> tuple[str, str]:
    email = f"pa-{uuid.uuid4().hex[:8]}@lock-ai-example.com"
    user_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, 'platform_admin', TRUE)",
        (user_id, "00000000-0000-0000-0000-000000000001", "測試平台管理員", email,
         hash_password(PASSWORD)),
    )
    res = await client.post(PLATFORM_LOGIN, json={"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"], user_id


async def _cleanup_user(user_id: str) -> None:
    await db_module._conn.execute("DELETE FROM revoked_jti WHERE user_id = %s::uuid", (user_id,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (user_id,))


async def _insert_tenant(slug: str, status: str = "active") -> str:
    tid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO tenant (id, slug, company_name, contact_name, contact_email, contact_phone, status) "
        "VALUES (%s::uuid, %s, %s, %s, %s, %s, %s)",
        (tid, slug, _MARK, "王小明", "owner@example.com", "0912345678", status),
    )
    return tid


async def _insert_pending_application() -> str:
    app_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO brand_applications "
        "(id, application_type, company_name, contact_name, tax_id, phone, email, status) "
        "VALUES (%s::uuid, 'brand', %s, %s, %s, %s, %s, 'pending')",
        (app_id, _MARK, "王小明", "12345678", "0912345678",
         f"app-{uuid.uuid4().hex[:8]}@example.com"),
    )
    return app_id


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── RBAC ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_requires_token_401(client):
    res = await client.get(BASE)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_brand_admin_forbidden_403(client, admin_token):
    """品牌 admin token 打平台端點 → 403(非 platform_admin)。"""
    res = await client.get(BASE, headers=_hdr(admin_token))
    assert res.status_code == 403


# ── 核准品牌申請連動 ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approve_brand_application_creates_tenant(client):
    """核准品牌申請 → 自動登錄租戶;response 帶 tenant_id、清單可見。"""
    token, uid = await _platform_admin_token(client)
    app_id = await _insert_pending_application()
    try:
        slug = f"acme-{uuid.uuid4().hex[:6]}"
        res = await client.post(
            f"{BRAND_APPS}/{app_id}:approve", json={"slug": slug}, headers=_hdr(token))
        assert res.status_code == 200, res.text
        tenant_id = res.json()["data"]["tenant_id"]
        assert tenant_id is not None

        # 清單可見,且欄位來自申請
        res = await client.get(BASE, headers=_hdr(token))
        assert res.status_code == 200
        rows = res.json()["data"]
        row = next((r for r in rows if r["id"] == tenant_id), None)
        assert row is not None
        assert row["slug"] == slug
        assert row["status"] == "active"
        assert row["application_id"] == app_id
    finally:
        # 清理順序:tenant → brand_application(reviewed_by FK 無 SET NULL)→ user
        await db_module._conn.execute("DELETE FROM tenant WHERE application_id = %s::uuid", (app_id,))
        await db_module._conn.execute("DELETE FROM brand_applications WHERE id = %s::uuid", (app_id,))
        await _cleanup_user(uid)


@pytest.mark.asyncio
async def test_create_from_application_idempotent(client):
    """同 slug 重複登錄只一列(ON CONFLICT DO NOTHING),回既有 id。"""
    app_id = await _insert_pending_application()
    slug = f"dup-{uuid.uuid4().hex[:6]}"
    app = {"slug": slug, "company_name": _MARK, "contact_name": "王小明",
           "email": "a@b.com", "phone": "0912345678", "id": app_id}
    id1 = await svc.create_from_application(app)
    id2 = await svc.create_from_application(app)
    assert id1 is not None and id1 == id2
    cur = await db_module._conn.execute("SELECT COUNT(*) FROM tenant WHERE slug = %s", (slug,))
    assert (await cur.fetchone())[0] == 1


# ── 查詢 ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_tenant_detail(client):
    token, uid = await _platform_admin_token(client)
    try:
        tid = await _insert_tenant(f"detail-{uuid.uuid4().hex[:6]}")
        res = await client.get(f"{BASE}/{tid}", headers=_hdr(token))
        assert res.status_code == 200, res.text
        assert res.json()["data"]["id"] == tid
    finally:
        await _cleanup_user(uid)


@pytest.mark.asyncio
async def test_get_nonexistent_404(client):
    token, uid = await _platform_admin_token(client)
    try:
        res = await client.get(f"{BASE}/{uuid.uuid4()}", headers=_hdr(token))
        assert res.status_code == 404
    finally:
        await _cleanup_user(uid)


@pytest.mark.asyncio
async def test_list_filter_by_status(client):
    token, uid = await _platform_admin_token(client)
    try:
        active_id = await _insert_tenant(f"act-{uuid.uuid4().hex[:6]}", status="active")
        susp_id = await _insert_tenant(f"sus-{uuid.uuid4().hex[:6]}", status="suspended")
        res = await client.get(f"{BASE}?status=suspended", headers=_hdr(token))
        assert res.status_code == 200
        ids = {r["id"] for r in res.json()["data"]}
        assert susp_id in ids
        assert active_id not in ids
    finally:
        await _cleanup_user(uid)


# ── 生命週期 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_suspend_then_reactivate(client):
    token, uid = await _platform_admin_token(client)
    try:
        tid = await _insert_tenant(f"life-{uuid.uuid4().hex[:6]}", status="active")

        res = await client.post(f"{BASE}/{tid}:suspend", headers=_hdr(token))
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["status"] == "suspended"
        assert data["status_changed_by"] == uid
        assert data["status_changed_at"] is not None

        res = await client.post(f"{BASE}/{tid}:reactivate", headers=_hdr(token))
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "active"
    finally:
        await _cleanup_user(uid)


@pytest.mark.asyncio
async def test_suspend_already_suspended_409(client):
    token, uid = await _platform_admin_token(client)
    try:
        tid = await _insert_tenant(f"conf-{uuid.uuid4().hex[:6]}", status="suspended")
        res = await client.post(f"{BASE}/{tid}:suspend", headers=_hdr(token))
        assert res.status_code == 409, res.text
    finally:
        await _cleanup_user(uid)


@pytest.mark.asyncio
async def test_suspend_nonexistent_404(client):
    token, uid = await _platform_admin_token(client)
    try:
        res = await client.post(f"{BASE}/{uuid.uuid4()}:suspend", headers=_hdr(token))
        assert res.status_code == 404
    finally:
        await _cleanup_user(uid)
