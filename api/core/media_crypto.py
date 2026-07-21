"""FR-API-08：到府證據 media 位元組 envelope 加密（靜態加密）。

照片/簽名/PDF 原以明文 `write_bytes` 落盤（檔案系統/DBA 可直接讀）。此模組以 Fernet
對稱加密位元組，金鑰 env `MEDIA_ENC_KEY` + 具名 dev fallback（沿 CR-0173/pii_crypto 慣例）。

- **加密範圍**：僅儲存的位元組。`sha256` 完整性/去重雜湊仍算在**明文**上（不受加密影響）。
- **dual-read**：舊明文檔（非本金鑰 Fernet token）`decrypt` 失敗 → 回 None，呼叫端 fallback
  原位元組（過渡期零破壞，存量檔不需即時 re-encrypt；未來可補 backfill 腳本 re-encrypt）。

金鑰未設 → dev fallback + loud warning（僅本機/測試；**prod 必設**，否則換機/重啟後既有
密文檔無法解）。
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_DEV_KEY = "fr-api-08-dev-insecure-media-enc-key-do-not-use-in-prod"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    raw = os.environ.get("MEDIA_ENC_KEY")
    if not raw:
        logger.warning(
            "MEDIA_ENC_KEY 未設 → dev fallback（不安全）。prod 必設，否則換機/重啟後"
            "既有加密證據檔將無法解密。"
        )
        raw = _DEV_KEY
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_bytes(data: bytes) -> bytes:
    """加密證據位元組（落盤前）。"""
    return _fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes | None:
    """解密回明文位元組。非本金鑰 token（如舊明文檔/毀損）→ None（呼叫端 fallback 原位元組）。"""
    try:
        return _fernet().decrypt(data)
    except (InvalidToken, ValueError):
        return None
