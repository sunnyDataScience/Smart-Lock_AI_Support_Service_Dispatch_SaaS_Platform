"""CR-0176：GDPR crypto-shredding 的 envelope 加密核心（純函式，無 DB）。

FR-API-16 / NFR-Priv-008：forget 的 T0 要「銷毀金鑰 → 資料即刻不可復原」。前提是
PII 以**可單獨銷毀的每主體金鑰（DEK）**加密。現有 pii_crypto / line_uid_crypto 都是
單一 master key——銷毀它會讓全部人不可讀，無法「只 shred 一個 data subject」。

本模組提供 envelope 加密的純密碼學層（不碰 registry/DB）：

    KEK（master，env GDPR_DEK_KEK，全系統一把）
      └─ wrap ─▶ DEK（per-subject，Fernet 隨機金鑰，wrapped 後存 registry）
                    └─ encrypt ─▶ 該 subject 的 PII 密文

「銷毀」發生在 registry 層（清掉 wrapped_dek）：wrapped 一旦不可得，DEK 無法還原，
該 subject 全部 PII 密文瞬間不可解——且**不影響任何其他 subject**（各有各的 DEK）。

金鑰載入沿用 CR-0173 line_uid_crypto 慣例：env + 具名 dev fallback + lru_cache。
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# 具名 dev fallback（非隨機——隨機會導致重啟後既有 wrapped DEK 無法解）。prod 必覆蓋。
_DEV_KEK = "cr0176-dev-insecure-gdpr-dek-kek-do-not-use-in-prod"


@lru_cache(maxsize=1)
def _kek() -> Fernet:
    """KEK（master key），加解 per-subject DEK。env GDPR_DEK_KEK 未設 → dev fallback。"""
    raw = os.environ.get("GDPR_DEK_KEK")
    if not raw:
        logger.warning(
            "GDPR_DEK_KEK 未設 → dev fallback（不安全）。prod 必設，否則換機/重啟後"
            "既有 wrapped DEK 無法解密＝全部加密 PII 不可讀（比明文更脆，見 CIA §10 R2）。"
        )
        raw = _DEV_KEK
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def generate_dek() -> bytes:
    """產生一把新的 per-subject DEK（Fernet 金鑰，urlsafe-b64 bytes）。"""
    return Fernet.generate_key()


def wrap_dek(dek_key: bytes) -> str:
    """用 KEK 加密 DEK 材料 → wrapped（ascii），存 registry.wrapped_dek。"""
    return _kek().encrypt(dek_key).decode("ascii")


def unwrap_dek(wrapped: str | None) -> bytes | None:
    """用 KEK 還原 DEK 材料。wrapped 為 None/空/毀損/KEK 不符 → None（不拋）。
    銷毀後 registry 的 wrapped_dek 已清空 → 此處回 None ＝ 無法解該 subject PII。"""
    if not wrapped:
        return None
    try:
        return _kek().decrypt(wrapped.encode("ascii"))
    except (InvalidToken, ValueError):
        logger.warning("wrapped DEK 還原失敗（KEK 不符或密文毀損）")
        return None


def encrypt_with_dek(dek_key: bytes, plaintext: str | None) -> str | None:
    """用 DEK 加密單一 PII 值。None/空 → None。Fernet 非確定性（同明文→不同密文）。"""
    if plaintext is None:
        return None
    plaintext = plaintext.strip() if isinstance(plaintext, str) else plaintext
    if plaintext == "":
        return None
    return Fernet(dek_key).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_with_dek(dek_key: bytes | None, ciphertext: str | None) -> str | None:
    """用 DEK 解密單一 PII 值。dek_key 為 None（已銷毀）或密文/金鑰不符 → None。"""
    if not dek_key or not ciphertext:
        return None
    try:
        return Fernet(dek_key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
