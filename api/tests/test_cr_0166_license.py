"""CR-0166 R3：租戶 License / 模組開通 gate（ADR-002/ADR-018）。

單庫 fallback：tenant 住主連線；套 Schema_platform.sql + license migration 001。
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio

import core.db as db_module
from core.auth import hash_password
from core.errors import ApiError
from services import platform_tenant_service as svc

pytestmark = pytest.mark.component

BASE = "/api/v1/platform/tenants"
PLATFORM_LOGIN = "/api/v1/platform/auth/login"
PASSWORD = "platform-test-pw-123"

_SCHEMA = Path(__file__).resolve().parents[2] / "SQL" / "platform" / "Schema_platform.sql"
_MIGRATION = (Path(__file__).resolve().parents[2] / "SQL" / "platform" / "migrations"
              / "001-tenant-license-entitlements.sql")


@pytest_asyncio.fixture(autouse=True)
async def _platform_schema():
    assert await db_module._ensure_conn()
    await db_module._conn.execute(_SCHEMA.read_text(encoding="utf-8"))
    await db_module._conn.execute(_MIGRATION.read_text(encoding="utf-8"))
    await db_module._conn.execute("DELETE FROM tenant WHERE slug LIKE 'cr0166-%'")
    yield
    await db_module._conn.execute("DELETE FROM tenant WHERE slug LIKE 'cr0166-%'")


async def _seed_tenant(modules='["core"]', tier="standard", expires=None) -> str:
    tid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO tenant (id, slug, company_name, plan_tier, entitled_modules, license_expires_at) "
        "VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s)",
        (tid, f"cr0166-{tid[:8]}", "L測試品牌", tier, modules, expires))
    return tid


async def _platform_admin_token(client) -> str:
    email = f"pa-{uuid.uuid4().hex[:8]}@lock-ai-example.com"
    uid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, 'platform_admin', TRUE)",
        (uid, "00000000-0000-0000-0000-000000000001", "測試平台管理員", email,
         hash_password(PASSWORD)))
    res = await client.post(PLATFORM_LOGIN, json={"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


# ── service 層 entitlement ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_core_always_entitled():
    tid = await _seed_tenant()
    assert await svc.is_module_entitled(tid, "core") is True
    assert await svc.is_module_entitled(tid, "refinery") is False


@pytest.mark.asyncio
async def test_entitled_module_true():
    tid = await _seed_tenant(modules='["core","refinery"]')
    assert await svc.is_module_entitled(tid, "refinery") is True


@pytest.mark.asyncio
async def test_expired_license_blocks_module():
    tid = await _seed_tenant(modules='["core","refinery"]',
                             expires="2020-01-01T00:00:00+00:00")
    assert await svc.is_module_entitled(tid, "refinery") is False


@pytest.mark.asyncio
async def test_assert_module_entitled_raises():
    tid = await _seed_tenant()
    with pytest.raises(ApiError) as e:
        await svc.assert_module_entitled(tid, "refinery")
    assert e.value.error_code == "MODULE_NOT_ENTITLED"
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_unknown_tenant_fail_closed():
    assert await svc.is_module_entitled(str(uuid.uuid4()), "refinery") is False


# ── API endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_and_update_license_api(client):
    token = await _platform_admin_token(client)
    hdr = {"Authorization": f"Bearer {token}"}
    tid = await _seed_tenant()

    r = await client.get(f"{BASE}/{tid}/license", headers=hdr)
    assert r.status_code == 200
    assert r.json()["data"]["entitled_modules"] == ["core"]

    r2 = await client.put(f"{BASE}/{tid}/license", headers=hdr,
                          json={"plan_tier": "pro", "entitled_modules": ["refinery"]})
    assert r2.status_code == 200, r2.text
    d = r2.json()["data"]
    assert d["plan_tier"] == "pro"
    assert set(d["entitled_modules"]) == {"core", "refinery"}  # core 強制保留


@pytest.mark.asyncio
async def test_update_license_unknown_module_422(client):
    token = await _platform_admin_token(client)
    hdr = {"Authorization": f"Bearer {token}"}
    tid = await _seed_tenant()
    r = await client.put(f"{BASE}/{tid}/license", headers=hdr,
                         json={"entitled_modules": ["bogus_module"]})
    assert r.status_code == 422
    assert r.json()["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_license_requires_platform_admin(client, admin_headers):
    tid = await _seed_tenant()
    r = await client.get(f"{BASE}/{tid}/license", headers=admin_headers)
    assert r.status_code in (401, 403)  # 品牌 admin 非 platform_admin
