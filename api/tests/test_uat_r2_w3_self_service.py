"""UAT R2 W3-5/W3-6 免 email 自助方案（component，真 DB）。

業主裁決（2026-07-18，SMTP 暫緩）：
  [B1] 品牌申請進度查詢 —— POST /platform/brand-applications:lookup（公開）
       email + application_id 雙精確匹配才回 {status, submitted_at, reviewed_at,
       review_notes}；不匹配一律 generic 404（防列舉）；review_notes 僅
       rejected 時回（核准備註不外洩）。
  [B2] 師傅補件連結 —— POST /platform/technicians/{id}:issue-upload-token
       （platform admin）補發一次性上傳 token，師傅憑 token 走既有公開上傳
       端點補傳文件；過期 token 拒絕。

單庫 fallback：brand_applications 以 Schema_platform.sql 冪等建表；
technician_* 表住主連線。每測試自清資料。
"""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio

import core.db as db_module
from services import brand_application_service
from services.media_service import MEDIA_ROOT

pytestmark = pytest.mark.component

LOOKUP = "/api/v1/platform/brand-applications:lookup"
REGISTER = "/api/v1/technicians/register"
UPLOAD = "/api/v1/technicians/registration-documents"
PLATFORM_TECH = "/api/v1/platform/technicians"

_SCHEMA = Path(__file__).resolve().parents[2] / "SQL" / "platform" / "Schema_platform.sql"

# 極小合法 PNG 檔頭（驗證面只看 magic bytes / content_type / 大小）
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"w3-selfservice-payload"


@pytest_asyncio.fixture(autouse=True)
async def _ensure_platform_schema():
    """套平台 schema（冪等）供 fallback 模式測試；並清 lookup 限流桶避免跨測試累積。"""
    assert await db_module._ensure_conn()
    await db_module._conn.execute(_SCHEMA.read_text(encoding="utf-8"))
    brand_application_service._lookup_rate_buckets.clear()
    yield
    brand_application_service._lookup_rate_buckets.clear()


# ── B1: 品牌申請進度查詢 ─────────────────────────────────────────────────────


async def _seed_application(
    *, status: str = "pending", review_notes: str | None = None,
    reviewed: bool = False,
) -> tuple[str, str]:
    """直接落一筆申請（繞過公開 submit 的 per-IP DB 限流），回 (id, email)。"""
    email = f"lookup-{uuid.uuid4().hex[:8]}@brand-example.com"
    cur = await db_module._conn.execute(
        "INSERT INTO brand_applications "
        "(application_type, company_name, contact_name, tax_id, phone, email, "
        " status, review_notes, reviewed_at) "
        "VALUES ('brand', '查詢測試公司', '王小明', '12345678', '0912345678', %s, "
        "        %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END) RETURNING id",
        (email, status, review_notes, reviewed),
    )
    app_id = str((await cur.fetchone())[0])
    return app_id, email


async def _cleanup_application(email: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM brand_applications WHERE email = %s", (email,))


@pytest.mark.asyncio
async def test_lookup_pending_returns_status(client):
    app_id, email = await _seed_application()
    try:
        res = await client.post(LOOKUP, json={"email": email, "application_id": app_id})
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["status"] == "pending"
        assert data["submitted_at"], "應回送出時間"
        assert data["reviewed_at"] is None
        assert data["review_notes"] is None
    finally:
        await _cleanup_application(email)


@pytest.mark.asyncio
async def test_lookup_rejected_returns_reason(client):
    """駁回案：申請人查得到駁回理由（review_notes）與審核時間。"""
    app_id, email = await _seed_application(
        status="rejected", review_notes="資料不全，請補統編登記文件", reviewed=True)
    try:
        res = await client.post(LOOKUP, json={"email": email, "application_id": app_id})
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["status"] == "rejected"
        assert data["review_notes"] == "資料不全，請補統編登記文件"
        assert data["reviewed_at"], "駁回案應回審核時間"
    finally:
        await _cleanup_application(email)


@pytest.mark.asyncio
async def test_lookup_approved_hides_review_notes(client):
    """核准案：回 approved 但 review_notes 不外洩（平台內部備註）。"""
    app_id, email = await _seed_application(
        status="approved", review_notes="內部備註：走 VIP 開站排程", reviewed=True)
    try:
        res = await client.post(LOOKUP, json={"email": email, "application_id": app_id})
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["status"] == "approved"
        assert data["review_notes"] is None, "核准備註不得外洩"
        assert data["reviewed_at"]
    finally:
        await _cleanup_application(email)


@pytest.mark.asyncio
async def test_lookup_mismatch_generic_404(client):
    """防列舉：email 對不上 id、id 不存在、id 非 uuid —— 一律 generic 404。"""
    app_id, email = await _seed_application()
    try:
        # email 錯（id 存在）→ 404
        res = await client.post(
            LOOKUP, json={"email": "other@brand-example.com", "application_id": app_id})
        assert res.status_code == 404, res.text
        # id 錯（email 存在）→ 404
        res = await client.post(
            LOOKUP, json={"email": email, "application_id": str(uuid.uuid4())})
        assert res.status_code == 404, res.text
        # id 非 uuid 格式 → 同樣 404（不洩露格式判斷面）
        res = await client.post(
            LOOKUP, json={"email": email, "application_id": "not-a-uuid"})
        assert res.status_code == 404, res.text
    finally:
        await _cleanup_application(email)


@pytest.mark.asyncio
async def test_lookup_rate_limited_429(client):
    """同 IP 超過視窗上限 → 429（in-memory 滑動視窗；桶由 fixture 前後清空）。"""
    app_id, email = await _seed_application()
    try:
        for _ in range(brand_application_service._LOOKUP_RATE_MAX):
            res = await client.post(
                LOOKUP, json={"email": email, "application_id": app_id})
            assert res.status_code == 200, res.text
        res = await client.post(LOOKUP, json={"email": email, "application_id": app_id})
        assert res.status_code == 429, res.text
    finally:
        await _cleanup_application(email)


# ── B2: 師傅補件連結（issue-upload-token）───────────────────────────────────


async def _register_technician(client) -> dict:
    """自助註冊一位測試師傅（pending_approval），回 register response data。"""
    suffix = uuid.uuid4().hex[:8]
    body = {
        "name": f"補件測試{suffix}",
        "phone": f"09{int(suffix, 16) % 100000000:08d}",
        "email": f"reissue-{suffix}@example.com",
        "password": "reissue-pw-123",
        "regions": ["台北市"],
        "terms_accepted": True,
    }
    resp = await client.post(
        REGISTER, json=body, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _cleanup_technician(tech_id: str) -> None:
    await db_module._ensure_conn()
    for sql in (
        "DELETE FROM technician_registration_document WHERE technician_id=%s::uuid",
        "DELETE FROM technician_upload_token WHERE technician_id=%s::uuid",
        "DELETE FROM technician_kyc WHERE technician_id=%s::uuid",
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id=%s::uuid",
        "DELETE FROM users WHERE id=(SELECT user_id FROM technicians WHERE id=%s::uuid)",
        "DELETE FROM technicians WHERE id=%s::uuid",
    ):
        await db_module._conn.execute(sql, (tech_id,))
    shutil.rmtree(MEDIA_ROOT / "kyc-registration" / tech_id, ignore_errors=True)


def _upload_kwargs(token: str, doc_type: str = "id_front") -> dict:
    return {
        "data": {"token": token, "doc_type": doc_type},
        "files": {"file": ("身分證正面.png", _PNG_BYTES, "image/png")},
    }


@pytest.mark.asyncio
async def test_issue_upload_token_rbac(client, admin_headers):
    fake = str(uuid.uuid4())
    res = await client.post(f"{PLATFORM_TECH}/{fake}:issue-upload-token")
    assert res.status_code == 401, "無 token → 401"
    res = await client.post(
        f"{PLATFORM_TECH}/{fake}:issue-upload-token", headers=admin_headers)
    assert res.status_code == 403, "品牌 admin 不可補發"


@pytest.mark.asyncio
async def test_issue_upload_token_then_upload_ok(client, platform_admin_headers):
    """補發 token → 憑新 token 走既有公開上傳端點成功（W3-5 補件閉環）。"""
    reg = await _register_technician(client)
    tech_id = reg["id"]
    try:
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:issue-upload-token",
            headers=platform_admin_headers)
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["token"], "應一次性回傳 token 明文"
        assert data["expires_at"]
        # 補發 token 與註冊 token 各自獨立
        assert data["token"] != reg["upload_token"]

        up = await client.post(UPLOAD, **_upload_kwargs(data["token"]))
        assert up.status_code == 201, up.text
        assert up.json()["data"]["doc_type"] == "id_front"
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
async def test_issue_upload_token_expired_rejected(client, platform_admin_headers):
    """補發後把 token 改為過期 → 上傳一律 403（單一錯誤碼，不洩原因）。"""
    reg = await _register_technician(client)
    tech_id = reg["id"]
    try:
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:issue-upload-token",
            headers=platform_admin_headers)
        assert res.status_code == 200, res.text
        token = res.json()["data"]["token"]

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_module._conn.execute(
            "UPDATE technician_upload_token SET expires_at = %s "
            "WHERE technician_id = %s::uuid",
            (past, tech_id),
        )
        up = await client.post(UPLOAD, **_upload_kwargs(token))
        assert up.status_code == 403, up.text
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
async def test_issue_upload_token_not_pending_409(client, platform_admin_headers):
    """師傅已離開 pending_approval（如已核准）→ 簽發面直接 409，不發死 token。"""
    reg = await _register_technician(client)
    tech_id = reg["id"]
    try:
        await db_module._conn.execute(
            "UPDATE technicians SET status = 'active' WHERE id = %s::uuid", (tech_id,))
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:issue-upload-token",
            headers=platform_admin_headers)
        assert res.status_code == 409, res.text
    finally:
        await _cleanup_technician(tech_id)


@pytest.mark.asyncio
async def test_issue_upload_token_nonexistent_404(client, platform_admin_headers):
    res = await client.post(
        f"{PLATFORM_TECH}/{uuid.uuid4()}:issue-upload-token",
        headers=platform_admin_headers)
    assert res.status_code == 404, res.text
