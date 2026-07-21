"""CR-0176：envelope 加密核心（core.dek_crypto）純函式測試。

證明：KEK wrap/unwrap、DEK 加解密、**per-DEK 隔離**（一把 DEK 的密文換另一把解不開）、
非確定性密文、銷毀（wrapped=None）→ 不可解。全程不碰 DB。
"""

from __future__ import annotations

from core import dek_crypto


def test_wrap_unwrap_roundtrip():
    dek = dek_crypto.generate_dek()
    wrapped = dek_crypto.wrap_dek(dek)
    assert isinstance(wrapped, str) and wrapped
    assert dek_crypto.unwrap_dek(wrapped) == dek


def test_encrypt_decrypt_roundtrip():
    dek = dek_crypto.generate_dek()
    ct = dek_crypto.encrypt_with_dek(dek, "王小明")
    assert ct and ct != "王小明"
    assert dek_crypto.decrypt_with_dek(dek, ct) == "王小明"


def test_per_dek_isolation():
    """一把 DEK 的密文，用另一把 DEK 解 → None（per-subject 隔離的密碼學基礎）。"""
    dek_a = dek_crypto.generate_dek()
    dek_b = dek_crypto.generate_dek()
    ct_a = dek_crypto.encrypt_with_dek(dek_a, "secretA")
    assert dek_crypto.decrypt_with_dek(dek_b, ct_a) is None   # 別人的 DEK 解不開
    assert dek_crypto.decrypt_with_dek(dek_a, ct_a) == "secretA"


def test_ciphertext_non_deterministic():
    dek = dek_crypto.generate_dek()
    assert dek_crypto.encrypt_with_dek(dek, "x") != dek_crypto.encrypt_with_dek(dek, "x")


def test_destroyed_wrapped_unrecoverable():
    """銷毀＝registry wrapped_dek 清為 None → unwrap None → 用 None 解密回 None。"""
    assert dek_crypto.unwrap_dek(None) is None
    assert dek_crypto.unwrap_dek("garbage-not-a-token") is None
    dek = dek_crypto.generate_dek()
    ct = dek_crypto.encrypt_with_dek(dek, "gone")
    assert dek_crypto.decrypt_with_dek(None, ct) is None      # DEK 已銷毀 → 不可讀


def test_empty_and_none_passthrough():
    dek = dek_crypto.generate_dek()
    assert dek_crypto.encrypt_with_dek(dek, None) is None
    assert dek_crypto.encrypt_with_dek(dek, "   ") is None
    assert dek_crypto.decrypt_with_dek(dek, None) is None
