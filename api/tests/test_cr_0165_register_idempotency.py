"""CR-0165 F12：公開註冊端點冪等 fallback 公共命名空間（UAT wave1）。

原缺口：idempotency_guard 缺 X-Tenant-ID header 時靜默 return None（不 lookup、
不落庫、不回放）——公開無登入端點（技師/廠商註冊）client 本來就無從得知 tenant，
curl/外部整合方只帶 Idempotency-Key 完全不去重。修後 opt-in fallback zero-UUID
公共命名空間（僅兩個公開註冊端點），並順修非 UUID header 500 → 400。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

REGISTER = "/api/v1/technicians/register"
PUBLIC_NS = "00000000-0000-0000-0000-000000000000"


def _register_body(suffix: str | None = None) -> dict:
    suffix = suffix or uuid.uuid4().hex[:8]
    return {
        "name": f"冪等測試{suffix}",
        "phone": f"09{int(suffix, 16) % 100000000:08d}",
        "email": f"cr0165-idem-{suffix}@example.com",
        "password": "cr0165-idem-pw-123",
        "regions": ["台北市"],
        "years_experience": 3,
        "emergency_contact_name": "緊急聯絡人",
        "emergency_contact_phone": "0911222333",
        "terms_accepted": True,
    }


async def _cleanup(tech_id: str | None, idem_key: str | None = None) -> None:
    await db_module._ensure_conn()
    if tech_id:
        for sql in (
            "DELETE FROM technician_registration_document WHERE technician_id=%s::uuid",
            "DELETE FROM technician_upload_token WHERE technician_id=%s::uuid",
            "DELETE FROM technician_kyc WHERE technician_id=%s::uuid",
            "DELETE FROM saas.technician_lifecycle_event WHERE technician_id=%s::uuid",
            "DELETE FROM users WHERE id=(SELECT user_id FROM technicians WHERE id=%s::uuid)",
            "DELETE FROM technicians WHERE id=%s::uuid",
        ):
            await db_module._conn.execute(sql, (tech_id,))
    if idem_key:
        await db_module._conn.execute(
            "DELETE FROM idempotency_keys WHERE key=%s", (idem_key,)
        )


@pytest.mark.asyncio
async def test_register_replay_without_tenant_header(client):
    """同 key 同 body 重送（不帶 X-Tenant-ID）→ 回放 201 同 id，token 清洗為 null。"""
    key = str(uuid.uuid4())
    body = _register_body()
    tech_id = None
    try:
        r1 = await client.post(REGISTER, json=body, headers={"Idempotency-Key": key})
        assert r1.status_code == 201, r1.text
        data1 = r1.json()["data"]
        tech_id = data1["id"]
        assert data1["upload_token"]  # 首個回應含真 token

        r2 = await client.post(REGISTER, json=body, headers={"Idempotency-Key": key})
        assert r2.status_code == 201, r2.text
        data2 = r2.json()["data"]
        assert data2["id"] == tech_id  # 回放同一位，不重複建帳號
        assert data2["upload_token"] is None  # CR-0115 §8-2a 清洗語意：token 只發一次

        # 落庫在公共命名空間（原缺口＝根本不落庫）
        await db_module._ensure_conn()
        cur = await db_module._conn.execute(
            "SELECT tenant_id::text FROM idempotency_keys WHERE key=%s", (key,)
        )
        row = await cur.fetchone()
        assert row and row[0] == PUBLIC_NS
    finally:
        await _cleanup(tech_id, key)


@pytest.mark.asyncio
async def test_register_same_key_different_body_409(client):
    """同 key 異 body → 409 IDEMPOTENCY_KEY_MISMATCH（不再靜默重複建帳號）。"""
    key = str(uuid.uuid4())
    tech_id = None
    try:
        r1 = await client.post(
            REGISTER, json=_register_body(), headers={"Idempotency-Key": key}
        )
        assert r1.status_code == 201, r1.text
        tech_id = r1.json()["data"]["id"]

        r2 = await client.post(
            REGISTER, json=_register_body(), headers={"Idempotency-Key": key}
        )
        assert r2.status_code == 409
        assert r2.json()["error_code"] == "IDEMPOTENCY_KEY_MISMATCH"
    finally:
        await _cleanup(tech_id, key)


@pytest.mark.asyncio
async def test_register_missing_key_400(client):
    """缺 Idempotency-Key → 400（applies_to 含 POST 的既有強制策略，行為不變）。"""
    res = await client.post(REGISTER, json=_register_body())
    assert res.status_code == 400
    assert res.json()["error_code"] == "MISSING_IDEMPOTENCY_KEY"


@pytest.mark.asyncio
async def test_register_malformed_tenant_header_400(client):
    """非 UUID 的 X-Tenant-ID → 400（原為 psycopg cast 錯誤 500）。"""
    res = await client.post(
        REGISTER,
        json=_register_body(),
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Tenant-ID": "not-a-uuid"},
    )
    assert res.status_code == 400
    assert res.json()["error_code"] == "VALIDATION_ERROR"
