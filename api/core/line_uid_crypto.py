"""CR-0173：technician line_user_id 欄位級加密 + blind index。

業主 2026-07-20 裁決推翻 CR-0169 HD-4=a（明文儲存）——HD-G=有合規驅動、crypto 方案
選 A（複用 pii_crypto 的 app 層 Fernet 模式，非另造 KMS）。

- encrypt / decrypt：Fernet（app 層對稱、**非確定性**，同明文→不同密文）。可攜、金鑰
  app 端集中管控，DBA 直接讀庫拿不到明文。金鑰 env `LINE_UID_ENC_KEY`。
- blind_index：HMAC-SHA256（金鑰 env `LINE_UID_BIDX_KEY`）→ hex。**確定性**（同明文→
  同索引），供「換綁去重」等值查——因 Fernet 密文非確定性無法 `WHERE line_user_id=%s`。

金鑰未設 → 具名 dev fallback + loud warning（僅本機/測試；**prod 必設**，否則換機/
重啟後既有密文無法解、blind index 對不上）。沿用 pii_crypto 的 SHA-256 正規化慣例。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# 具名 dev fallback（非隨機——隨機會導致重啟後既有密文/索引對不上）。prod 必覆蓋。
_DEV_ENC_KEY = "cr0173-dev-insecure-lineuid-enc-key-do-not-use-in-prod"
_DEV_BIDX_KEY = "cr0173-dev-insecure-lineuid-bidx-key-do-not-use-in-prod"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    raw = os.environ.get("LINE_UID_ENC_KEY")
    if not raw:
        logger.warning(
            "LINE_UID_ENC_KEY 未設 → dev fallback（不安全）。prod 必設,"
            "否則換機/重啟後既有 line_user_id 密文將無法解密。"
        )
        raw = _DEV_ENC_KEY
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


@lru_cache(maxsize=1)
def _bidx_key() -> bytes:
    raw = os.environ.get("LINE_UID_BIDX_KEY")
    if not raw:
        logger.warning(
            "LINE_UID_BIDX_KEY 未設 → dev fallback（不安全）。prod 必設,"
            "否則 blind index 對不上(換綁去重失效)。"
        )
        raw = _DEV_BIDX_KEY
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt(line_uid: str | None) -> str | None:
    """加密 line_user_id;None/空 → None。"""
    if line_uid is None:
        return None
    line_uid = line_uid.strip()
    if not line_uid:
        return None
    return _fernet().encrypt(line_uid.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str | None) -> str | None:
    """解密回 line_user_id;None → None;密文毀損/金鑰不符 → None（不拋,避免推播鏈整掛）。"""
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("line_user_id 密文解密失敗(金鑰不符或密文毀損)")
        return None


def blind_index(line_uid: str | None) -> str | None:
    """等值查用不可逆索引:HMAC-SHA256(bidx_key, uid) hex。同明文→同索引。None/空 → None。"""
    if line_uid is None:
        return None
    line_uid = line_uid.strip()
    if not line_uid:
        return None
    return hmac.new(_bidx_key(), line_uid.encode("utf-8"), hashlib.sha256).hexdigest()
