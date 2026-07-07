"""CR-0116:平台維運監控 — 監控目標 registry CRUD + /health 並發探測。

單庫 fallback 模式:monitor_target 住主連線 → 以 Schema_platform.sql 冪等建表。
探測測試 monkeypatch `_probe_one` 避免真連網(CI/單庫環境無各 stack 服務)。

驗證:
  - registry CRUD(create 201 / list / update / delete)
  - RBAC:無 token 401、品牌 admin token 403
  - create 驗證 422(缺欄位 / url scheme 錯)
  - _map_status 純函式映射(200→up / 503→degraded / 其他→down)
  - probe 只回啟用目標、逐目標帶 status、路由 health 不被 {id} 吃掉
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio

import core.db as db_module
from core.auth import hash_password
from services import platform_monitor_service as svc

pytestmark = pytest.mark.component

BASE = "/api/v1/platform/monitor-targets"
PLATFORM_LOGIN = "/api/v1/platform/auth/login"
PASSWORD = "platform-test-pw-123"

_SCHEMA = Path(__file__).resolve().parents[2] / "SQL" / "platform" / "Schema_platform.sql"


@pytest_asyncio.fixture(autouse=True)
async def _ensure_platform_schema():
    """套平台 schema(冪等,含 monitor_target)+ 清空 registry 隔離每測試。"""
    assert await db_module._ensure_conn()
    await db_module._conn.execute(_SCHEMA.read_text(encoding="utf-8"))
    await db_module._conn.execute("DELETE FROM monitor_target")
    yield
    await db_module._conn.execute("DELETE FROM monitor_target")


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


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _target(**over) -> dict:
    return {"brand": "test-brand", "label": "API", "url": "http://svc:8080/health", **over}


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


# ── CRUD ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_crud_lifecycle(client):
    token, uid = await _platform_admin_token(client)
    try:
        # create → 201
        res = await client.post(BASE, json=_target(note="主派工"), headers=_hdr(token))
        assert res.status_code == 201, res.text
        tid = res.json()["data"]["id"]
        assert res.json()["data"]["enabled"] is True

        # list → 含剛建的
        res = await client.get(BASE, headers=_hdr(token))
        assert res.status_code == 200
        rows = res.json()["data"]
        assert any(r["id"] == tid for r in rows)

        # update → 改 label + 停用
        res = await client.patch(
            f"{BASE}/{tid}", json={"label": "派工 API v2", "enabled": False}, headers=_hdr(token))
        assert res.status_code == 200, res.text
        assert res.json()["data"]["label"] == "派工 API v2"
        assert res.json()["data"]["enabled"] is False

        # delete → 200,再 list 不含
        res = await client.delete(f"{BASE}/{tid}", headers=_hdr(token))
        assert res.status_code == 200
        res = await client.get(BASE, headers=_hdr(token))
        assert all(r["id"] != tid for r in res.json()["data"])
    finally:
        await _cleanup_user(uid)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "over",
    [{"brand": ""}, {"label": ""}, {"url": ""}, {"url": "ftp://x/health"}, {"url": "notaurl"}],
)
async def test_create_validation_422(client, over):
    token, uid = await _platform_admin_token(client)
    try:
        res = await client.post(BASE, json=_target(**over), headers=_hdr(token))
        assert res.status_code == 422, res.text
    finally:
        await _cleanup_user(uid)


@pytest.mark.asyncio
async def test_update_nonexistent_404(client):
    token, uid = await _platform_admin_token(client)
    try:
        res = await client.patch(
            f"{BASE}/{uuid.uuid4()}", json={"enabled": False}, headers=_hdr(token))
        assert res.status_code == 404
    finally:
        await _cleanup_user(uid)


# ── 探測 ─────────────────────────────────────────────────────────────────────

def test_map_status_pure():
    assert svc._map_status(200) == "up"
    assert svc._map_status(503) == "degraded"
    assert svc._map_status(500) == "down"
    assert svc._map_status(None) == "down"


@pytest.mark.asyncio
async def test_probe_returns_only_enabled_with_status(client, monkeypatch):
    """probe 只回啟用目標,逐目標帶 status;health 路由不被 {id} 吃掉。"""
    token, uid = await _platform_admin_token(client)
    try:
        r1 = await client.post(BASE, json=_target(brand="b1", label="API"), headers=_hdr(token))
        await client.post(
            BASE, json=_target(brand="b2", label="停用", enabled=False), headers=_hdr(token))
        up_id = r1.json()["data"]["id"]

        async def _fake_probe(session, target):
            return {**target, "status": "up", "http_code": 200, "latency_ms": 5, "error": None}

        monkeypatch.setattr(svc, "_probe_one", _fake_probe)

        res = await client.get(f"{BASE}/health", headers=_hdr(token))
        assert res.status_code == 200, res.text
        body = res.json()
        assert "checked_at" in body
        data = body["data"]
        assert len(data) == 1  # 只有啟用的 b1
        assert data[0]["id"] == up_id
        assert data[0]["status"] == "up"
    finally:
        await _cleanup_user(uid)
