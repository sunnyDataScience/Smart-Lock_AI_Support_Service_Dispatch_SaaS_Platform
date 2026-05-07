"""Public anonymous token service — Q3=C / Q9=B 共用機制（SKELETON）。

LINE 推播短連結 → Web 匿名頁面 → 此模組驗證 token →
顯示工單狀態（Q3=C）或 Scope Change 提案（Q9=B）。

## Q3=C/Q9=B Implementation TODO

實作此模組時請補齊：
  1. HMAC-SHA256 簽章：`hmac(secret, f"{subject_id}|{purpose}|{exp}|{nonce}")`
  2. Token 結構：`base64url(payload).base64url(signature)`
     - payload = {sub, purpose, exp, nonce, tenant_id}
     - purpose ∈ {"work_order_status", "scope_change"}
  3. TTL：work order 預設 30 天；scope change 與 proposal expires_at 對齊
  4. 撤銷清單：Redis SET，key=`revoked:tokens`，member=token_hash(sha256)
  5. Rate limit：依 token + IP，60 req/min（Redis sliding window）
  6. PII 遮罩工具（mask_phone / mask_name）建議放這裡，由 router 呼叫
  7. Audit log：寫 token_hash + IP + UA，**禁止**寫完整 token / customer email

風險控制：
  - secret 從 GCP Secret Manager 讀（PUBLIC_TOKEN_HMAC_SECRET），輪替策略 90 天
  - 簽章演算法升級時保留 v1/v2 雙驗，一個版本灰度後再下架
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

TokenPurpose = Literal["work_order_status", "scope_change"]


@dataclass(frozen=True)
class TokenPayload:
    """簽章後的 token 解碼結果。"""

    subject_id: str  # work_order_id 或 scope_change_proposal_id
    purpose: TokenPurpose
    expires_at: datetime
    tenant_id: str | None = None


class TokenInvalidError(Exception):
    """Token 簽章驗證失敗 / 解碼失敗 → 對外回 404。"""


class TokenExpiredError(Exception):
    """Token 已過期或被撤銷 → 對外回 404 / 410。"""


def generate_token(
    subject_id: str,
    *,
    purpose: TokenPurpose,
    ttl_days: int = 30,
    tenant_id: str | None = None,
) -> str:
    """產生簽章 token（SKELETON — 回傳 placeholder 字串）。

    Q3=C/Q9=B Implementation TODO:
        實作 HMAC-SHA256 簽章 + base64url 編碼，回 `payload.sig` 雙段格式。
        現階段僅回傳可辨識的 placeholder，方便前端串接 mock。
    """
    # TODO Q3=C/Q9=B impl: HMAC-SHA256 signed UUID + expiry + revocation list
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    return (
        f"stub-{purpose}-{subject_id[:8]}-"
        f"{int(expires_at.timestamp())}-PLACEHOLDER"
    )


def verify_token(token: str) -> TokenPayload:
    """驗證 token（SKELETON — 回傳 placeholder TokenPayload）。

    Q3=C/Q9=B Implementation TODO:
        - 拆 `payload.sig` → base64url decode → HMAC verify
        - 檢查 expires_at < now → raise TokenExpiredError
        - 查 Redis 撤銷清單 → raise TokenExpiredError
        - 簽章不符 → raise TokenInvalidError
    """
    # TODO Q3=C/Q9=B impl: HMAC verify + revocation check
    if not token or len(token) < 16:
        raise TokenInvalidError("token too short")
    return TokenPayload(
        subject_id="00000000-0000-0000-0000-000000000000",
        purpose="work_order_status",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        tenant_id=None,
    )


def mask_technician_name(full_name: str | None) -> str | None:
    """技師姓名遮罩：僅露姓氏 + 「師傅」（例：「陳大文」→「陳師傅」）。

    Q3=C/Q9=B Implementation TODO:
        - 處理英文姓名（取首字 + Master）
        - 處理複姓（歐陽 / 司馬 / 諸葛）
    """
    # TODO Q3=C/Q9=B impl: 完整命名規則
    if not full_name:
        return None
    return f"{full_name[0]}師傅"


def mask_phone(phone: str | None) -> str | None:
    """電話遮罩：保留末四碼（例：「0912345678」→「****5678」）。"""
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 4:
        return "****"
    return f"****{digits[-4:]}"
