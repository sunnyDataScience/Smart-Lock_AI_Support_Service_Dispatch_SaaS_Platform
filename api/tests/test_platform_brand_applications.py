"""CR-0114 R2:品牌申請(landing 公開表單 → platform console 審核)。

單庫 fallback 模式:brand_applications 住主連線 → 以 Schema_platform.sql
冪等建表(IF NOT EXISTS;users/revoked_jti 已存在會跳過)。每測試自清資料。
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio

import core.db as db_module
from core.auth import hash_password

pytestmark = pytest.mark.component

BASE = "/api/v1/platform/brand-applications"
PLATFORM_LOGIN = "/api/v1/platform/auth/login"
PASSWORD = "platform-test-pw-123"

_SCHEMA = Path(__file__).resolve().parents[2] / "SQL" / "platform" / "Schema_platform.sql"


@pytest_asyncio.fixture(autouse=True)
async def _ensure_platform_schema():
    """套平台 schema(冪等)供 fallback 模式測試。"""
    assert await db_module._ensure_conn()
    await db_module._conn.execute(_SCHEMA.read_text(encoding="utf-8"))
    yield


def _payload(**over) -> dict:
    return {
        "application_type": "brand",
        "company_name": "測試鎖業股份有限公司",
        "contact_name": "王小明",
        "tax_id": "12345678",
        "phone": "0912345678",
        "email": f"apply-{uuid.uuid4().hex[:8]}@brand-example.com",
        "address": "台北市測試路 1 號",
        "notes": "想導入派工平台",
        **over,
    }


async def _cleanup_by_email(email: str) -> None:
    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute(
        "DELETE FROM brand_applications WHERE email = %s", (email,))


async def _platform_admin_token(client) -> tuple[str, str]:
    """seed 平台管理員並登入,回 (token, user_id);呼叫端負責清 user。"""
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


# ── 公開申請 ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_application_public_201(client):
    body = _payload()
    try:
        res = await client.post(BASE, json=body)
        assert res.status_code == 201, res.text
        data = res.json()["data"]
        assert data["status"] == "pending"
        assert data["id"]
    finally:
        await _cleanup_by_email(body["email"])


@pytest.mark.asyncio
async def test_submit_with_enriched_fields_stored_and_listed(client):
    """業界補充欄位（website/coverage/scale/brands/referral）送出後入庫、審核 list 可見。"""
    body = _payload(
        website="https://test-lock.example.com",
        coverage_regions="台北市、新北市、桃園市",
        store_count=5,
        expected_monthly_orders="200-500",
        main_brands="Yale、Dormakaba",
        referral_source="Google 搜尋",
    )
    token, admin_id = await _platform_admin_token(client)
    try:
        res = await client.post(BASE, json=body)
        assert res.status_code == 201, res.text
        # 平台審核 list 應回傳補充欄位
        lst = await client.get(
            BASE, params={"status": "pending"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert lst.status_code == 200, lst.text
        row = next(r for r in lst.json()["data"] if r["email"] == body["email"])
        assert row["website"] == "https://test-lock.example.com"
        assert row["coverage_regions"] == "台北市、新北市、桃園市"
        assert row["store_count"] == 5
        assert row["expected_monthly_orders"] == "200-500"
        assert row["main_brands"] == "Yale、Dormakaba"
        assert row["referral_source"] == "Google 搜尋"
    finally:
        await _cleanup_by_email(body["email"])
        await _cleanup_user(admin_id)


@pytest.mark.asyncio
async def test_submit_duplicate_pending_email_409(client):
    body = _payload()
    try:
        res = await client.post(BASE, json=body)
        assert res.status_code == 201, res.text
        res = await client.post(BASE, json={**body, "company_name": "另一家公司"})
        assert res.status_code == 409, res.text
        assert "待審核" in res.json().get("message", "")
    finally:
        await _cleanup_by_email(body["email"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [("tax_id", "1234"), ("phone", "12345678"), ("application_type", "other"), ("email", "not-an-email")],
)
async def test_submit_validation_422(client, field, value):
    res = await client.post(BASE, json=_payload(**{field: value}))
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_submit_rate_limited_429(client):
    """同 IP 一小時內第 6 件 → 429(先探出 transport 的 client IP 再灌 5 件)。"""
    probe = _payload()
    seeded_emails = [probe["email"]]
    try:
        res = await client.post(BASE, json=probe)
        assert res.status_code == 201, res.text
        cur = await db_module._conn.execute(
            "SELECT submitted_ip FROM brand_applications WHERE email = %s", (probe["email"],))
        ip = (await cur.fetchone())[0]
        assert ip, "transport 應帶 client IP"

        for _ in range(4):
            e = f"rl-{uuid.uuid4().hex[:8]}@brand-example.com"
            seeded_emails.append(e)
            await db_module._conn.execute(
                "INSERT INTO brand_applications "
                "(application_type, company_name, contact_name, tax_id, phone, email, submitted_ip) "
                "VALUES ('brand', 'RL 測試', 'RL', '12345678', '0912345678', %s, %s)",
                (e, ip),
            )

        overflow = _payload()
        seeded_emails.append(overflow["email"])
        res = await client.post(BASE, json=overflow)
        assert res.status_code == 429, res.text
    finally:
        for e in seeded_emails:
            await _cleanup_by_email(e)


# ── 審核(platform_admin 限定)────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_requires_platform_admin(client, admin_token):
    res = await client.get(BASE)
    assert res.status_code == 401
    res = await client.get(BASE, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 403, "品牌 admin token 不可讀平台申請列表"


@pytest.mark.asyncio
async def test_approve_returns_onboarding_guide(client):
    body = _payload()
    token, admin_id = await _platform_admin_token(client)
    try:
        res = await client.post(BASE, json=body)
        app_id = res.json()["data"]["id"]

        res = await client.get(
            f"{BASE}?status=pending", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert any(a["id"] == app_id for a in res.json()["data"])

        res = await client.post(
            f"{BASE}/{app_id}:approve",
            json={"slug": "test-brand"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["status"] == "approved"
        assert data["slug"] == "test-brand"
        guide = data["onboarding_guide"]
        assert "brands/test-brand.env" in guide
        assert "web/brand-portal/docker-compose.yml" in guide
        assert body["contact_name"] in guide

        # 已核准再核准 → 409
        res = await client.post(
            f"{BASE}/{app_id}:approve", json={},
            headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 409, res.text
    finally:
        await _cleanup_by_email(body["email"])
        await _cleanup_user(admin_id)


@pytest.mark.asyncio
async def test_approve_bad_slug_422(client):
    body = _payload()
    token, admin_id = await _platform_admin_token(client)
    try:
        res = await client.post(BASE, json=body)
        app_id = res.json()["data"]["id"]
        res = await client.post(
            f"{BASE}/{app_id}:approve",
            json={"slug": "Bad Slug!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422, res.text
    finally:
        await _cleanup_by_email(body["email"])
        await _cleanup_user(admin_id)


@pytest.mark.asyncio
async def test_reject_with_reason(client):
    body = _payload()
    token, admin_id = await _platform_admin_token(client)
    try:
        res = await client.post(BASE, json=body)
        app_id = res.json()["data"]["id"]

        res = await client.post(
            f"{BASE}/{app_id}:reject",
            json={"reason": "資料不全，請補統編登記文件"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "rejected"

        # 拒絕後同 email 可再申請(部分唯一索引只鎖 pending)
        res = await client.post(BASE, json=body)
        assert res.status_code == 201, res.text
    finally:
        await _cleanup_by_email(body["email"])
        await _cleanup_user(admin_id)


@pytest.mark.asyncio
async def test_approve_nonexistent_404(client):
    token, admin_id = await _platform_admin_token(client)
    try:
        res = await client.post(
            f"{BASE}/{uuid.uuid4()}:approve", json={},
            headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404, res.text
    finally:
        await _cleanup_user(admin_id)
