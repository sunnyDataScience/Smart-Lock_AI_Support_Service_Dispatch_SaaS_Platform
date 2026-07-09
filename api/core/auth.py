"""JWT 簽發/驗證 + 密碼 hash。

- HS256，secret 從 env JWT_SECRET_KEY
- access token 1h、refresh token 30d
- claims：sub (user_id)、role、tenant_id、exp、iat、jti、token_type
- logout 寫 revoked_jti 表
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import load_config, require_env
from core.db import _ensure_conn
import core.db as db_module

logger = logging.getLogger("api.auth")

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def _cfg():
    return load_config().auth


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_ctx.verify(plain, hashed)
    except Exception:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_token(
    *,
    user_id: str,
    role: str,
    tenant_id: str,
    token_type: TokenType,
) -> tuple[str, str, datetime]:
    """簽出 JWT，回傳 (token_str, jti, expires_at)。"""
    cfg = _cfg()
    if token_type == "access":
        ttl = timedelta(minutes=cfg.get("access_token_ttl_minutes", 60))
    else:
        ttl = timedelta(days=cfg.get("refresh_token_ttl_days", 30))

    iat = _now()
    exp = iat + ttl
    jti = str(uuid.uuid4())

    payload = {
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
        "type": token_type,
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": jti,
    }
    secret = require_env(cfg.get("jwt_secret_env", "API_JWT_SECRET_KEY"))
    token = jwt.encode(payload, secret, algorithm=cfg.get("jwt_algorithm", "HS256"))
    return token, jti, exp


def decode_token(token: str) -> dict:
    cfg = _cfg()
    secret = require_env(cfg.get("jwt_secret_env", "API_JWT_SECRET_KEY"))
    try:
        return jwt.decode(token, secret, algorithms=[cfg.get("jwt_algorithm", "HS256")])
    except JWTError as e:
        logger.debug("JWT decode failed: %s", e)
        raise


async def _security_conn(role: str | None):
    """token 安全狀態/jti 的查詢連線路由（CR-0114）。

    platform_admin 的 users/revoked_jti 住平台庫（require_platform_conn；未配置
    平台庫時 fallback 主連線 → 行為同舊版）。其餘角色維持主連線。
    連不上回 None（呼叫端各自維持 fail-open / fail-closed 語意）。
    """
    if role == "platform_admin":
        try:
            return await db_module.require_platform_conn()
        except RuntimeError:
            return None
    if not await _ensure_conn():
        return None
    return db_module._conn


async def load_user_security_state(user_id: str, role: str | None = None) -> dict | None:
    """回 {is_active, password_changed_at} 供每請求 token 驗證重查（A2/A3）。

    **Fail-open 設計**（對齊 is_jti_revoked）：DB 不可用、user_id 非合法 uuid、或查無此
    使用者 → 回 None（呼叫端維持 claims-only 行為）。這是刻意的：
      - 既有大量元件測試用「未 seed 的假 user_id」（token 驗證只看 claims）→ 查無回 None 不破測試。
      - 真實「停權（is_active=False）」或「改密碼後（password_changed_at）」的既存帳號 → 撈得到 → 失效。
    role 供 CR-0114 路由：platform_admin 查平台庫，其餘查主連線。
    """
    conn = await _security_conn(role)
    if conn is None:
        return None
    try:
        uuid.UUID(str(user_id))
    except (ValueError, TypeError, AttributeError):
        return None
    cur = await conn.execute(
        "SELECT is_active, password_changed_at FROM users WHERE id = %s::uuid LIMIT 1",
        (user_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {"is_active": row[0], "password_changed_at": row[1]}


async def security_state_verifiable(role: str | None = None) -> bool:
    """安全狀態是否可驗（SA-05 / CR-0131）：能取得對應安全庫連線＝可查 revoked_jti
    與 users.is_active。DB 不可用 → False——關鍵金流/派工寫入端點（fail_closed=True
    白名單）此時拒絕請求（503），不退 claims-only；一般端點維持 fail-open（C-05 取捨）。
    """
    return (await _security_conn(role)) is not None


async def is_jti_revoked(jti: str, role: str | None = None) -> bool:
    conn = await _security_conn(role)
    if conn is None:
        return False
    cur = await conn.execute(
        "SELECT 1 FROM revoked_jti WHERE jti = %s::uuid",
        (jti,),
    )
    return await cur.fetchone() is not None


async def revoke_jti(jti: str, user_id: str, expires_at: datetime, role: str | None = None) -> None:
    conn = await _security_conn(role)
    if conn is None:
        raise RuntimeError("DB unavailable")
    await conn.execute(
        "INSERT INTO revoked_jti (jti, user_id, expires_at) VALUES (%s::uuid, %s::uuid, %s) "
        "ON CONFLICT (jti) DO NOTHING",
        (jti, user_id, expires_at),
    )
