"""Public anonymous token service — Q3=C / Q9=B 共用機制（HMAC 真實版）。

LINE 推播短連結 → Web 匿名頁面 → 此模組驗證 token →
顯示工單狀態（Q3=C）或 Scope Change 提案（Q9=B）。

## 設計

Token 格式：``base64url(payload_json) . base64url(signature)``

payload 結構：
    {
      "sub": "<subject_id>",          # work_order_id 或 scope_change_proposal_id
      "purpose": "work_order_status" | "scope_change",
      "exp": 1714999999,               # 過期 unix timestamp (UTC)
      "nonce": "<8 url-safe bytes>",  # 防重播；同 subject 多 token 隔離
      "tenant_id": "<uuid>"           # 多租戶隔離
    }

signature = HMAC-SHA256(secret, payload_json_bytes) → 32 bytes → base64url

驗證流程：
    1. 拆 ``payload.sig`` → base64url decode
    2. HMAC verify（``hmac.compare_digest`` 防 timing attack）
    3. 檢查 ``exp < now`` → ``TokenExpiredError``
    4. 檢查撤銷清單（in-memory set, key=sha256(token)）
    5. router 層比對 ``purpose`` 是否與 endpoint 預期相符（不符 → 404）

風險控制：
    - secret 從環境變數 ``PUBLIC_TOKEN_HMAC_SECRET`` 讀；未設定時 dev 預設值
    - secret 輪替策略：90 天，輪替時保留 v1/v2 雙驗，灰度後下架
    - PII 遮罩工具（mask_phone / mask_technician_name）由 router 呼叫
    - audit log（token_hash + IP + UA）由 router/service 寫，**禁止**寫完整 token

TODO（未實作）：
    - rate limit：依 token + IP，60 req/min（Redis sliding window）
    - 撤銷清單：from in-memory set → Redis SET (revoked:tokens)
    - secret 從 GCP Secret Manager 讀取（生產環境）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

logger = logging.getLogger("api.public_token")

TokenPurpose = Literal["work_order_status", "scope_change", "quote_view"]

# secret 來源：env var → 生產由 GCP Secret Manager 注入
_SECRET_ENV = "PUBLIC_TOKEN_HMAC_SECRET"

# 2026-08-02 資安掃描：原本這裡是 `_DEV_SECRET = "dev-secret-do-not-use-in-prod"`，
# 且 `_get_secret()` 在 env 未設時**靜默** fallback 到它。那等於任何讀得到本檔的人
# 都能簽發合法的消費者 token——而這些 token 保護的不只是唯讀端點，還包括
# `POST /consumer/quotes/{token}`（代客戶接受報價）與
# `POST /consumer/scope-changes/{token}`（代客戶核可加價）等金額決策。
# payload 是明文 base64，偽造只需要知道工單 UUID。
#
# 改為 process 啟動時隨機產生，並記 CRITICAL。刻意**不**做成啟動失敗：
# 若 prod 目前確實漏設，fail-fast 會直接變成 outage；隨機 secret 則只讓既有的
# 公開連結失效（那些連結若真是用已知 secret 簽的，本來就該失效），
# 服務仍可服務其他流量，而 log 會大聲叫。
#
# ⚠️ 這個 fallback 的行為依賴**單 instance** 部署（`scripts/deploy/api.sh` 目前
# MIN_INSTANCES=MAX_INSTANCES=1）：單 instance 下的表現是「每次重啟後既有連結
# 一致失效」，可預期也好排查。若日後調高 max-instances，每個 instance 會各自
# 持有不同金鑰，症狀會變成**間歇性**失效（同一條連結時好時壞），那比一致失效
# 難 debug 得多。屆時必須先把這個 secret 真的設進環境，不能再靠 fallback。
_EPHEMERAL_SECRET = secrets.token_urlsafe(48)
_secret_warning_emitted = False

# in-memory 撤銷清單（TODO: 換 Redis）
_revoked_token_hashes: set[str] = set()


@dataclass(frozen=True)
class TokenPayload:
    """簽章後的 token 解碼結果。"""

    subject_id: str  # work_order_id 或 scope_change_proposal_id
    purpose: TokenPurpose
    expires_at: datetime
    tenant_id: str | None = None
    nonce: str | None = None


class TokenInvalidError(Exception):
    """Token 簽章驗證失敗 / 解碼失敗 → 對外回 404。"""


class TokenExpiredError(Exception):
    """Token 已過期或被撤銷 → 對外回 404 / 410。"""


# =============================================================================
# Internal helpers
# =============================================================================

def _get_secret() -> bytes:
    """取簽章金鑰。env 未設時用**本次 process 隨機產生**的金鑰，不是固定常數。

    隨機金鑰的後果是「重啟後既有公開連結全失效」——這是刻意的：
    寧可連結失效被使用者回報，也不要用一個寫在原始碼裡、人人可簽的金鑰。
    """
    secret = os.getenv(_SECRET_ENV)
    if secret:
        return secret.encode("utf-8")

    global _secret_warning_emitted
    if not _secret_warning_emitted:
        _secret_warning_emitted = True
        logger.critical(
            "%s 未設定！已改用本次 process 隨機金鑰——所有既有公開連結將失效，"
            "且服務重啟後再次失效。請在部署環境注入此 secret（GCP Secret Manager）。",
            _SECRET_ENV,
        )
    return _EPHEMERAL_SECRET.encode("utf-8")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(payload_bytes: bytes) -> bytes:
    return hmac.new(_get_secret(), payload_bytes, hashlib.sha256).digest()


def _token_hash(token: str) -> str:
    """Token 雜湊（供 audit log / 撤銷清單使用，不洩露原 token）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# =============================================================================
# Public API
# =============================================================================

def generate_token(
    subject_id: str,
    *,
    purpose: TokenPurpose,
    ttl_days: int = 30,
    tenant_id: str | None = None,
) -> str:
    """產生簽章 token。

    Args:
        subject_id: work_order_id 或 scope_change_proposal_id
        purpose: ``work_order_status`` (Q3=C) | ``scope_change`` (Q9=B)
        ttl_days: 過期天數；work order 預設 30，scope change 由呼叫端帶 7
        tenant_id: 多租戶隔離

    Returns:
        ``payload_b64.signature_b64`` 格式字串
    """
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    payload = {
        "sub": subject_id,
        "purpose": purpose,
        "exp": int(expires_at.timestamp()),
        "nonce": secrets.token_urlsafe(8),
        "tenant_id": tenant_id,
    }
    payload_bytes = json.dumps(
        payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    sig = _sign(payload_bytes)
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(sig)}"


def verify_token(token: str) -> TokenPayload:
    """驗證 token 並回傳 payload。

    Raises:
        TokenInvalidError: 格式錯誤 / 簽章不符
        TokenExpiredError: 過期或已撤銷
    """
    if not token or "." not in token:
        raise TokenInvalidError("token format invalid")

    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_b64)
        sig_bytes = _b64url_decode(sig_b64)
    except (ValueError, base64.binascii.Error) as exc:
        raise TokenInvalidError(f"token decode failed: {exc}") from None

    expected_sig = _sign(payload_bytes)
    if not hmac.compare_digest(expected_sig, sig_bytes):
        raise TokenInvalidError("signature mismatch")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TokenInvalidError(f"payload not valid json: {exc}") from None

    sub = payload.get("sub")
    purpose = payload.get("purpose")
    exp = payload.get("exp")
    if not sub or purpose not in {"work_order_status", "scope_change", "quote_view"} or not exp:
        raise TokenInvalidError("payload missing required fields")

    expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise TokenExpiredError("token expired")

    if is_revoked(_token_hash(token)):
        raise TokenExpiredError("token revoked")

    return TokenPayload(
        subject_id=str(sub),
        purpose=purpose,  # type: ignore[arg-type]
        expires_at=expires_at,
        tenant_id=payload.get("tenant_id"),
        nonce=payload.get("nonce"),
    )


def is_revoked(token_hash: str) -> bool:
    """檢查 token hash 是否在撤銷清單中。

    TODO: 改為 Redis ``SISMEMBER revoked:tokens <hash>``。
    """
    return token_hash in _revoked_token_hashes


def revoke_token(token: str) -> None:
    """將 token 加入撤銷清單（用於：客戶申訴後撤銷、scope_change 已決議）。

    TODO: 改為 Redis ``SADD revoked:tokens <hash>`` + 設過期時間 = token TTL。
    """
    _revoked_token_hashes.add(_token_hash(token))


def token_hash_for_audit(token: str) -> str:
    """供 audit log 使用的 token 雜湊（永遠不要寫完整 token）。"""
    return _token_hash(token)


# =============================================================================
# PII masking utilities
# =============================================================================

def mask_phone(phone: str | None) -> str | None:
    """電話遮罩：保留末四碼（例：「0912345678」→「****5678」）。"""
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 4:
        return "****"
    return f"****{digits[-4:]}"


def mask_technician_name(full_name: str | None) -> str | None:
    """技師姓名遮罩：僅露姓氏 + 「師傅」（例：「陳大文」→「陳師傅」）。

    複姓暫不處理（TODO：歐陽 / 司馬 / 諸葛）；英文名 fallback 用首字 + Master。
    """
    if not full_name:
        return None
    name = full_name.strip()
    if not name:
        return None
    first = name[0]
    if first.isascii() and first.isalpha():
        return f"{first}. Master"
    return f"{first}師傅"


def mask_customer_name(full_name: str | None) -> str | None:
    """客戶姓名遮罩：保留姓氏 + 性別中性「先生/小姐」改為「客戶」。

    例：「王小明」→「王客戶」；無資料 → None。
    """
    if not full_name:
        return None
    name = full_name.strip()
    if not name:
        return None
    return f"{name[0]}客戶"
