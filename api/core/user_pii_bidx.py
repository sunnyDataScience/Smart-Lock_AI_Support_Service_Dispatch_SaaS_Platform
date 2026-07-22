"""CR-0176 S5 前置（業主 0722 裁決 A1）：users email/phone blind index。

S5 要 DROP email/phone 明文，但 login／EMAIL_TAKEN 去重／phone 去重是
**WHERE 等值查**——Fernet 密文非確定性查不了。比照 CR-0173（technician
line_user_id）前例：HMAC-SHA256 盲索引（**確定性**：同明文→同索引，不可逆），
金鑰 env `USER_PII_BIDX_KEY`。

語意鏡射現行明文等值（僅 strip，不做大小寫正規化——與既有
`WHERE email = %s` 行為一致，避免收斂輪引入比對語意漂移）。
金鑰未設 → 具名 dev fallback + loud warning（僅本機；**prod 必設**，
否則索引對不上＝login/去重失效）。
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

# 具名 dev fallback（非隨機——隨機會導致重啟後既有索引對不上）。prod 必覆蓋。
_DEV_BIDX_KEY = "cr0176-dev-insecure-userpii-bidx-key-do-not-use-in-prod"


@lru_cache(maxsize=1)
def _key() -> bytes:
    raw = os.environ.get("USER_PII_BIDX_KEY")
    if not raw:
        logger.warning(
            "USER_PII_BIDX_KEY 未設 → dev fallback（不安全）。prod 必設,"
            "否則 blind index 對不上(login/EMAIL_TAKEN/phone 去重失效)。"
        )
        raw = _DEV_BIDX_KEY
    return hashlib.sha256(raw.encode("utf-8")).digest()


def blind_index(value: str | None) -> str | None:
    """等值查用不可逆索引：HMAC-SHA256(key, value.strip()) hex。None/空 → None。"""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return hmac.new(_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()
