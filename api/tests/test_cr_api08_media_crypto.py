"""FR-API-08：media 位元組 envelope 加密（core.media_crypto）純函式測試。

證明：encrypt/decrypt round-trip、密文≠明文、dual-read（舊明文檔 decrypt→None 供 fallback）。
不碰 DB / 檔案系統。
"""

from __future__ import annotations

from core import media_crypto

_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"binary-evidence-bytes" * 20 + b"\xff\xd9"


def test_encrypt_decrypt_roundtrip():
    ct = media_crypto.encrypt_bytes(_FAKE_JPEG)
    assert ct != _FAKE_JPEG              # 密文異於明文
    assert media_crypto.decrypt_bytes(ct) == _FAKE_JPEG


def test_dual_read_plaintext_returns_none():
    # 舊明文檔（非本金鑰 Fernet token）→ decrypt 回 None，呼叫端 `or data` fallback
    assert media_crypto.decrypt_bytes(_FAKE_JPEG) is None
    assert media_crypto.decrypt_bytes(b"not-a-fernet-token") is None


def test_ciphertext_non_deterministic():
    assert media_crypto.encrypt_bytes(_FAKE_JPEG) != media_crypto.encrypt_bytes(_FAKE_JPEG)


def test_dual_read_or_fallback_pattern():
    # 模擬 get_media 的 dual-read：加密檔 → 解出明文；明文檔 → 回原位元組
    enc = media_crypto.encrypt_bytes(_FAKE_JPEG)
    assert (media_crypto.decrypt_bytes(enc) or enc) == _FAKE_JPEG
    legacy = _FAKE_JPEG
    assert (media_crypto.decrypt_bytes(legacy) or legacy) == _FAKE_JPEG
