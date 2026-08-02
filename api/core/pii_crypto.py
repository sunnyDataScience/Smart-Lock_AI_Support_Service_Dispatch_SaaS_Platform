"""PII 加密工具（CR-0115 §8-1）—— 師傅 KYC 敏感欄位 app 層對稱加密。

決策依據（CR-0115 §8-1）：身分證字號、銀行帳戶等敏感 PII 存獨立 `technician_kyc`
表 + **欄位加密** + 讀取遮罩、不鏡射品牌庫。

為什麼 app 層 Fernet 而非 pgcrypto：
- 可攜（不綁 DB extension / 特定 SQL 方言）；tech-db 拆分後仍一致。
- 密文進出皆為 str，psycopg 直接存 text 欄，無需 bytea 處理。
- 金鑰在 app 端集中管控，DBA 直接讀庫也拿不到明文。

金鑰來源：env `KYC_ENCRYPTION_KEY`（任意字串，內部 SHA-256 正規化為 32-byte
Fernet 金鑰）。未設 → 用具名 dev fallback + loud warning（僅供本機/測試；
**正式環境必須設定**，否則換機/重啟後既有密文無法解）。

遮罩策略（讀取端）：預設只回末 N 碼（如身分證末 3、帳號末 4），全值僅授權
角色（平台管理員，§8-3）呼叫 decrypt 取得。
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# 未設金鑰時的 dev fallback：具名常數而非隨機（隨機會導致重啟後既有密文解不開）。
# 正式環境必須以 KYC_ENCRYPTION_KEY 覆蓋。
_DEV_FALLBACK_KEY = "cr0115-dev-insecure-kyc-key-do-not-use-in-prod"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    raw = os.environ.get("KYC_ENCRYPTION_KEY")
    if not raw:
        logger.warning(
            "KYC_ENCRYPTION_KEY 未設定 —— 使用 dev fallback 金鑰（不安全）。"
            "正式環境務必設定，否則敏感 PII 密文在換機/重啟後將無法解密。"
        )
        raw = _DEV_FALLBACK_KEY
    # 任意字串 → SHA-256（32 byte）→ urlsafe base64 → 合法 Fernet 金鑰。
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_pii(plaintext: str | None) -> str | None:
    """加密敏感明文；None / 空字串 → None（欄位可空）。"""
    if plaintext is None:
        return None
    plaintext = plaintext.strip()
    if not plaintext:
        return None
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_pii(ciphertext: str | None) -> str | None:
    """解密回明文；None → None；密文毀損/金鑰不符 → None（不拋例外，避免整頁掛）。"""
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("PII 密文解密失敗（金鑰不符或密文毀損）")
        return None


def last_n(value: str | None, n: int) -> str | None:
    """取末 N 碼供遮罩顯示（如身分證末 3、帳號末 4）；不足 N 碼回全長。"""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    return value[-n:]


def mask_tail(value: str | None, visible: int) -> str | None:
    """遮罩：保留末 `visible` 碼、前面以 • 遮蔽（如 A123456789 → •••••••789）。

    給「已知全值、要在 UI 遮罩顯示」情境；只有末碼時直接顯示末碼用 last_n。
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) <= visible:
        return value
    return "•" * (len(value) - visible) + value[-visible:]


def mask_email_for_log(value: str | None) -> str:
    """log 專用的 email 遮蔽：保留首字元與網域（a***@example.com）。

    **與 mask_tail 的差別**：mask_tail 是給「UI 顯示已知全值」用的；本函式是給
    **log／稽核輸出**用的，目標是「夠讓營運把同一個人的多筆 log 對起來，但單看
    log 還原不出完整地址」。

    2026-08-02（TC-COMPLIANCE-03）：探針實跑打 request-password-reset 後掃容器 log，
    直接掃到完整 email 明文。log 會被集中收集、保存期常比業務資料長、
    存取控制也比 DB 鬆——PII 落進 log 等於繞過了所有資料面的保護。

    None／空字串 → "(none)"；沒有 @ 的字串一律只留首字元（不假設格式）。
    """
    if not value or not value.strip():
        return "(none)"
    value = value.strip()
    if "@" not in value:
        return value[0] + "***"
    local, _, domain = value.partition("@")
    head = local[0] if local else ""
    return f"{head}***@{domain}"
