"""CR-0176 S5 前置（業主 0722 A1）：email/phone blind index 單元測試——不碰 DB。

驗證：bidx 確定性/strip/None 語意、金鑰相依、encrypt_user_pii 併出 bidx 欄、
dual_write SQL 帶 bidx、模擬 lookup 等值命中。
"""

import pytest

from core import user_pii_bidx
from services import dek_service

from .test_cr_0176_s2_dual_rw import mem_registry  # noqa: F401 — 復用 in-memory registry


def test_bidx_deterministic_and_strip():
    a = user_pii_bidx.blind_index("a@b.tw")
    assert a == user_pii_bidx.blind_index("  a@b.tw  ")  # strip 後同值同索引
    assert a != user_pii_bidx.blind_index("A@b.tw")  # 不做大小寫正規化（鏡射明文等值）
    assert user_pii_bidx.blind_index(None) is None
    assert user_pii_bidx.blind_index("   ") is None
    assert len(a) == 64  # sha256 hex


def test_bidx_key_dependent(monkeypatch):
    base = user_pii_bidx.blind_index("0912345678")
    monkeypatch.setenv("USER_PII_BIDX_KEY", "another-key")
    user_pii_bidx._key.cache_clear()
    try:
        assert user_pii_bidx.blind_index("0912345678") != base
    finally:
        monkeypatch.delenv("USER_PII_BIDX_KEY")
        user_pii_bidx._key.cache_clear()


@pytest.mark.asyncio
async def test_encrypt_user_pii_emits_bidx(mem_registry):  # noqa: F811
    enc = await dek_service.encrypt_user_pii(
        "u-1", None, {"display_name": "王", "email": "a@b.tw", "phone": None}
    )
    # display_name 無 bidx；email 有值出索引；phone None → 索引 None
    assert "display_name_bidx" not in enc
    assert enc["email_bidx"] == user_pii_bidx.blind_index("a@b.tw")
    assert enc["phone_bidx"] is None


@pytest.mark.asyncio
async def test_lookup_equality_via_bidx(mem_registry):  # noqa: F811
    """模擬 login/去重：寫入時存的 bidx == 查詢時算的 bidx（等值可命中）。"""
    enc = await dek_service.encrypt_user_pii("u-2", None, {"email": "user@x.tw"})
    assert enc["email_bidx"] == user_pii_bidx.blind_index("user@x.tw")
    assert enc["email_bidx"] != user_pii_bidx.blind_index("other@x.tw")
