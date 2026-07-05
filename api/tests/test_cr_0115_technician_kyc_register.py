"""CR-0115 師傅註冊 KYC 擴充測試（component，真 DB）。

驗證：
- 擴充註冊 → technicians 存 Tier 1 非敏感欄 + technician_kyc 存加密敏感 PII + 證照落表
- 敏感 PII（身分證/銀行帳戶）**密文入庫**（DB 內非明文）+ 末碼欄正確 + 可解回
- 敏感 PII 不隨 technicians 明文欄外洩（technicians 表無 national_id/bank_account 欄）
- 只送既有 6 欄 → 向後相容（無 technician_kyc 列、不報錯）
- pydantic 驗證：身分證/銀行帳號格式非法 → 422
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

import core.db as db_module
from core.pii_crypto import decrypt_pii
from routers.auth import TechnicianRegisterBody
from services import auth_service

pytestmark = pytest.mark.component


def _full_req(email: str) -> dict:
    return {
        "name": "測試師傅",
        "phone": "0912345678",
        "email": email,
        "password": "techpass123",
        "capabilities": ["Dormakaba", "Milre"],
        "regions": ["台北市", "新北市"],
        # Tier 1
        "years_experience": 8,
        "bio": "十年智慧鎖安裝經驗，擅長電子鎖故障排除。",
        "vehicle_type": "機車",
        "availability_note": "全職・平日假日皆可",
        "emergency_contact_name": "測試家屬",
        "emergency_contact_phone": "0987654321",
        "certifications": [
            {"cert_name": "室內配線技術士乙級", "brand": None},
        ],
        "terms_accepted": True,
        # Tier 2 敏感 PII
        "national_id": "A123456789",
        "birth_date": "1990-05-20",
        "address": "台北市信義區測試路 1 號",
        "bank_code": "822",
        "bank_account": "1234567890123",
        "tax_id": "12345678",
    }


async def _cleanup(email: str) -> None:
    # users ON DELETE CASCADE → technicians → technician_kyc / certification 一併刪
    await db_module._conn.execute("DELETE FROM users WHERE email = %s", (email,))


@pytest.mark.asyncio
async def test_register_stores_tier1_and_encrypted_kyc(client):
    assert await db_module._ensure_conn()
    email = f"kyc-{uuid.uuid4().hex[:8]}@example.com"
    try:
        res = await auth_service.register_technician(_full_req(email))
        tech_id = res["data"]["id"]
        assert res["data"]["status"] == "pending_approval"

        # Tier 1 非敏感欄存進 technicians
        cur = await db_module._conn.execute(
            "SELECT years_experience, bio, vehicle_type, availability_note, "
            "emergency_contact_name, emergency_contact_phone, terms_accepted_at "
            "FROM technicians WHERE id = %s::uuid",
            (tech_id,),
        )
        row = await cur.fetchone()
        assert row[0] == 8
        assert "智慧鎖" in row[1]
        assert row[2] == "機車"
        assert row[4] == "測試家屬"
        assert row[5] == "0987654321"
        assert row[6] is not None  # terms_accepted_at 已記

        # Tier 2 敏感 PII 存 technician_kyc，且為密文
        kcur = await db_module._conn.execute(
            "SELECT national_id_enc, national_id_last3, bank_account_enc, "
            "bank_account_last4, bank_code, birth_date, address, tax_id "
            "FROM technician_kyc WHERE technician_id = %s::uuid",
            (tech_id,),
        )
        krow = await kcur.fetchone()
        assert krow is not None
        # 密文 ≠ 明文
        assert krow[0] and krow[0] != "A123456789"
        assert krow[2] and krow[2] != "1234567890123"
        # 末碼正確
        assert krow[1] == "789"
        assert krow[3] == "0123"
        assert krow[4] == "822"
        assert str(krow[5]) == "1990-05-20"
        assert krow[7] == "12345678"
        # 可解回明文
        assert decrypt_pii(krow[0]) == "A123456789"
        assert decrypt_pii(krow[2]) == "1234567890123"

        # 證照落 technician_certification
        ccur = await db_module._conn.execute(
            "SELECT cert_name FROM technician_certification WHERE technician_id = %s::uuid",
            (tech_id,),
        )
        crow = await ccur.fetchone()
        assert crow[0] == "室內配線技術士乙級"
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_national_id_not_in_technicians_plaintext(client):
    """敏感 PII 不得以明文出現在 technicians 表（最小揭露 §8-1）。"""
    assert await db_module._ensure_conn()
    email = f"kyc-{uuid.uuid4().hex[:8]}@example.com"
    try:
        res = await auth_service.register_technician(_full_req(email))
        tech_id = res["data"]["id"]
        # technicians 表整列轉文字都不應含身分證明文
        cur = await db_module._conn.execute(
            "SELECT technicians::text FROM technicians WHERE id = %s::uuid", (tech_id,)
        )
        row = await cur.fetchone()
        assert "A123456789" not in row[0]
        assert "1234567890123" not in row[0]
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_register_basic_only_backward_compat(client):
    """只送既有 6 欄 → 不建 technician_kyc、不報錯（加性非破壞）。"""
    assert await db_module._ensure_conn()
    email = f"kyc-{uuid.uuid4().hex[:8]}@example.com"
    try:
        res = await auth_service.register_technician(
            {
                "name": "簡易師傅",
                "phone": "0911222333",
                "email": email,
                "password": "techpass123",
                "regions": ["桃園市"],
            }
        )
        tech_id = res["data"]["id"]
        kcur = await db_module._conn.execute(
            "SELECT 1 FROM technician_kyc WHERE technician_id = %s::uuid", (tech_id,)
        )
        assert await kcur.fetchone() is None
    finally:
        await _cleanup(email)


def test_body_rejects_bad_national_id():
    with pytest.raises(ValidationError):
        TechnicianRegisterBody(
            name="x", phone="0912345678", email="a@b.com",
            password="techpass123", national_id="BAD",
        )


def test_body_rejects_bad_bank_account():
    with pytest.raises(ValidationError):
        TechnicianRegisterBody(
            name="x", phone="0912345678", email="a@b.com",
            password="techpass123", bank_account="abc",
        )
