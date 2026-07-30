"""CR-0115 S-upload + S7:師傅 KYC 文件上傳(兩階段 token)與平台審核讀取。

§8-2 (a):註冊回一次性 upload token(48h/次數上限/明文不落庫)→ 憑 token
走公開端點上傳;師傅離開 pending_approval 即失效。
§8-3 (a):平台管理員看 KYC —— 預設遮罩、:reveal 取全值(寫稽核)、文件檢視;
品牌 admin 一律 403。

單庫 fallback:兩張新表(migration 090)住主連線。
"""

from __future__ import annotations

import shutil
import uuid

import pytest

import core.db as db_module
from services.media_service import MEDIA_ROOT

pytestmark = pytest.mark.component

REGISTER = "/api/v1/technicians/register"
UPLOAD = "/api/v1/technicians/registration-documents"
PLATFORM_TECH = "/api/v1/platform/technicians"

# 極小合法 PNG 檔頭(內容不需真的可渲染,驗證面只看 content_type/大小)
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"cr0115-test-payload"


async def _register(client, *, with_kyc: bool = True) -> dict:
    """自助註冊一位測試師傅;回 register response 的 data dict。"""
    suffix = uuid.uuid4().hex[:8]
    body = {
        "name": f"文件測試{suffix}",
        "phone": f"09{int(suffix, 16) % 100000000:08d}",
        "email": f"kyc-doc-{suffix}@example.com",
        "password": "kyc-doc-pw-123",
        "regions": ["台北市"],
        "years_experience": 5,
        "emergency_contact_name": "緊急聯絡人",
        "emergency_contact_phone": "0911222333",
        "terms_accepted": True,
    }
    if with_kyc:
        body["national_id"] = "A123456789"
        body["bank_code"] = "822"
        body["bank_account"] = "12345678901234"
    resp = await client.post(REGISTER, json=body, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _cleanup(tech_id: str) -> None:
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


def _upload_kwargs(token: str, doc_type: str = "id_front", data: bytes = _PNG_BYTES) -> dict:
    return {
        "data": {"token": token, "doc_type": doc_type},
        "files": {"file": ("身分證正面.png", data, "image/png")},
    }


@pytest.mark.asyncio
async def test_register_returns_upload_token(client):
    reg = await _register(client)
    try:
        assert reg["upload_token"], "註冊 response 應含兩階段上傳 token"
        assert reg["upload_token_expires_at"], "應含 token 到期時間"
        # 明文不落庫:DB 只有 SHA-256(64 hex),不等於 token 本身
        await db_module._ensure_conn()
        cur = await db_module._conn.execute(
            "SELECT token_hash FROM technician_upload_token WHERE technician_id=%s::uuid",
            (reg["id"],),
        )
        row = await cur.fetchone()
        assert row and len(row[0]) == 64 and row[0] != reg["upload_token"]
    finally:
        await _cleanup(reg["id"])


@pytest.mark.asyncio
async def test_upload_list_reveal_and_view(client, platform_admin_headers):
    """主流程:上傳 → 平台 KYC 審核資料(遮罩+文件)→ reveal 全值 → 讀檔。"""
    reg = await _register(client)
    try:
        res = await client.post(UPLOAD, **_upload_kwargs(reg["upload_token"]))
        assert res.status_code == 201, res.text
        doc = res.json()["data"]
        assert doc["doc_type"] == "id_front"

        # 平台審核資料:Tier 1 + 遮罩 KYC + 文件清單
        res = await client.get(
            f"{PLATFORM_TECH}/{reg['id']}/kyc", headers=platform_admin_headers
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["profile"]["years_experience"] == 5
        assert data["profile"]["terms_accepted_at"], "同意條款時間應存在"
        assert data["kyc"]["has_national_id"] is True
        assert data["kyc"]["national_id_last3"] == "789"
        assert data["kyc"]["bank_account_last4"] == "1234"
        # 預設回應絕不含明文全值
        assert "A123456789" not in res.text
        assert any(d["id"] == doc["id"] for d in data["documents"])

        # reveal:平台管理員取全值
        res = await client.post(
            f"{PLATFORM_TECH}/{reg['id']}/kyc:reveal", headers=platform_admin_headers
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["national_id"] == "A123456789"
        assert res.json()["data"]["bank_account"] == "12345678901234"

        # §8-3:每次揭露必須寫稽核(tech 域 lifecycle audit,非品牌庫 audit_events
        # —— 後者 actor FK 指品牌庫 users,平台管理員會 FK violation 被 fail-soft 吞)
        cur = await db_module._conn.execute(
            "SELECT actor_role FROM saas.technician_lifecycle_event "
            "WHERE technician_id=%s::uuid AND event_type='kyc_reveal'",
            (reg["id"],),
        )
        audit_rows = await cur.fetchall()
        assert len(audit_rows) == 1 and audit_rows[0][0] == "platform_admin"

        # 文件實體檢視
        res = await client.get(
            f"{PLATFORM_TECH}/{reg['id']}/documents/{doc['id']}",
            headers=platform_admin_headers,
        )
        assert res.status_code == 200
        assert res.content == _PNG_BYTES
        assert res.headers["content-type"].startswith("image/png")
    finally:
        await _cleanup(reg["id"])


@pytest.mark.asyncio
async def test_upload_idempotent_dedup(client):
    reg = await _register(client)
    try:
        r1 = await client.post(UPLOAD, **_upload_kwargs(reg["upload_token"]))
        r2 = await client.post(UPLOAD, **_upload_kwargs(reg["upload_token"]))
        assert r1.status_code == 201 and r2.status_code == 201
        assert r2.json()["data"].get("deduplicated") is True
        assert r1.json()["data"]["id"] == r2.json()["data"]["id"]
        await db_module._ensure_conn()
        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM technician_registration_document WHERE technician_id=%s::uuid",
            (reg["id"],),
        )
        assert (await cur.fetchone())[0] == 1, "同檔重傳不重複入庫"
    finally:
        await _cleanup(reg["id"])


@pytest.mark.asyncio
async def test_upload_rejects_invalid_inputs(client):
    reg = await _register(client, with_kyc=False)
    try:
        # 假 token → 403(單一錯誤碼不區分原因)
        res = await client.post(UPLOAD, **_upload_kwargs("x" * 43))
        assert res.status_code == 403

        # doc_type 不在白名單 → 422
        res = await client.post(
            UPLOAD, **_upload_kwargs(reg["upload_token"], doc_type="selfie")
        )
        assert res.status_code == 422

        # 檔案型別不在白名單 → 422
        res = await client.post(
            UPLOAD,
            data={"token": reg["upload_token"], "doc_type": "id_front"},
            files={"file": ("doc.txt", b"plain text", "text/plain")},
        )
        assert res.status_code == 422

        # HEIC 不再放行(瀏覽器無法預覽)→ 422
        res = await client.post(
            UPLOAD,
            data={"token": reg["upload_token"], "doc_type": "id_front"},
            files={"file": ("photo.heic", b"\x00" * 64, "image/heic")},
        )
        assert res.status_code == 422

        # 宣告 image/png 但內容非 PNG magic bytes → 422(擋偽造 Content-Type)
        res = await client.post(
            UPLOAD,
            data={"token": reg["upload_token"], "doc_type": "id_front"},
            files={"file": ("fake.png", b"not a real png", "image/png")},
        )
        assert res.status_code == 422

        # 超過 10 MiB → 422
        res = await client.post(
            UPLOAD,
            data={"token": reg["upload_token"], "doc_type": "id_front"},
            files={"file": ("big.png", _PNG_BYTES + b"\x00" * (10 * 1024 * 1024), "image/png")},
        )
        assert res.status_code == 422
    finally:
        await _cleanup(reg["id"])


@pytest.mark.asyncio
async def test_same_file_different_doc_types_both_stored(client, platform_admin_headers):
    """同一張檔案傳到不同槽位 = 不同文件宣告,dedup key 含 doc_type,兩者都入庫。"""
    reg = await _register(client, with_kyc=False)
    try:
        r1 = await client.post(UPLOAD, **_upload_kwargs(reg["upload_token"], doc_type="id_front"))
        r2 = await client.post(UPLOAD, **_upload_kwargs(reg["upload_token"], doc_type="id_back"))
        assert r1.status_code == 201 and r2.status_code == 201
        assert r2.json()["data"].get("deduplicated") is not True, "跨 doc_type 不應被去重吞掉"
        res = await client.get(
            f"{PLATFORM_TECH}/{reg['id']}/kyc", headers=platform_admin_headers
        )
        doc_types = {d["doc_type"] for d in res.json()["data"]["documents"]}
        assert {"id_front", "id_back"} <= doc_types
    finally:
        await _cleanup(reg["id"])


@pytest.mark.asyncio
async def test_upload_respects_quota_limit(client):
    """上傳額度上限:超過 max_uploads 後 → 403(原子扣額度,不可突破)。"""
    reg = await _register(client, with_kyc=False)
    try:
        await db_module._ensure_conn()
        # 把額度壓到 1(已上傳 0),先傳一份成功,第二份不同內容應 403
        await db_module._conn.execute(
            "UPDATE technician_upload_token SET max_uploads=1 WHERE technician_id=%s::uuid",
            (reg["id"],),
        )
        r1 = await client.post(UPLOAD, **_upload_kwargs(reg["upload_token"], data=_PNG_BYTES + b"a"))
        assert r1.status_code == 201, r1.text
        r2 = await client.post(UPLOAD, **_upload_kwargs(reg["upload_token"], data=_PNG_BYTES + b"b"))
        assert r2.status_code == 403, "超過額度應拒絕"
    finally:
        await _cleanup(reg["id"])


@pytest.mark.asyncio
async def test_upload_still_allowed_after_conditional_approval(
    client, platform_admin_headers
):
    """**CR-0195 改寫了本測試的契約**（原名 `test_upload_forbidden_after_decision`，
    原本斷言「核准後 token 即失效」）。

    原契約＝「核准前補件」語意。但核准端當時對文件零檢查，兩者相加就是業主實遇的
    死結：核准通過才發現沒傳身分證，補件卻已被封死。業主 2026-07-30 裁決條件式核准
    後，補件窗口延伸到 active——**手上原本那張 token 也應該還能用**，否則師傅得等
    管理員重新產連結，等於沒解決。
    """
    reg = await _register(client)
    try:
        res = await client.post(
            f"{PLATFORM_TECH}/{reg['id']}:onboard-approve",
            json={"notes": "test", "conditional": True,
                  "conditional_reason": "人力吃緊先放行，核准後補件"},
            headers=platform_admin_headers,
        )
        assert res.status_code == 200, res.text
        res = await client.post(UPLOAD, **_upload_kwargs(reg["upload_token"]))
        assert res.status_code == 201, f"條件式核准後仍應可補件：{res.text}"
    finally:
        await _cleanup(reg["id"])


@pytest.mark.asyncio
async def test_upload_forbidden_after_terminate(client, platform_admin_headers):
    """放寬只到 active——終態後 token 仍須立即失效（原測試的防護意圖保留在這裡）。

    注意消費閘是**每次上傳即時查現況 status**，所以不需要撤銷機制：
    簽發時可補、之後被終止，手上那張立刻失效。
    """
    reg = await _register(client)
    try:
        res = await client.post(
            f"{PLATFORM_TECH}/{reg['id']}:onboard-approve",
            json={"conditional": True, "conditional_reason": "人力吃緊先放行，後補件"},
            headers=platform_admin_headers,
        )
        assert res.status_code == 200, res.text
        res = await client.post(
            f"{PLATFORM_TECH}/{reg['id']}:terminate",
            json={"reason": "測試終止"}, headers=platform_admin_headers,
        )
        assert res.status_code == 200, res.text
        res = await client.post(UPLOAD, **_upload_kwargs(reg["upload_token"]))
        assert res.status_code == 403, "終態後不可再憑 token 上傳"
    finally:
        await _cleanup(reg["id"])


@pytest.mark.asyncio
async def test_kyc_endpoints_require_platform_admin(client, admin_headers):
    """§8-3:品牌 admin 不可讀 KYC/reveal/文件(403);無 token 401。"""
    reg = await _register(client)
    try:
        kyc_path = f"{PLATFORM_TECH}/{reg['id']}/kyc"
        assert (await client.get(kyc_path)).status_code == 401
        assert (await client.get(kyc_path, headers=admin_headers)).status_code == 403
        assert (
            await client.post(f"{kyc_path}:reveal", headers=admin_headers)
        ).status_code == 403
    finally:
        await _cleanup(reg["id"])


@pytest.mark.asyncio
async def test_kyc_review_without_kyc_row(client, platform_admin_headers):
    """未提供敏感 PII 的師傅:kyc=None、reveal 404,審核頁不炸。"""
    reg = await _register(client, with_kyc=False)
    try:
        res = await client.get(
            f"{PLATFORM_TECH}/{reg['id']}/kyc", headers=platform_admin_headers
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["kyc"] is None
        res = await client.post(
            f"{PLATFORM_TECH}/{reg['id']}/kyc:reveal", headers=platform_admin_headers
        )
        assert res.status_code == 404
    finally:
        await _cleanup(reg["id"])
