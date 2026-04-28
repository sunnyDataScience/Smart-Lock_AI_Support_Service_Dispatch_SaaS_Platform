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


async def is_jti_revoked(jti: str) -> bool:
    if not await _ensure_conn():
        return False
    cur = await db_module._conn.execute(
        "SELECT 1 FROM revoked_jti WHERE jti = %s::uuid",
        (jti,),
    )
    return await cur.fetchone() is not None


async def revoke_jti(jti: str, user_id: str, expires_at: datetime) -> None:
    if not await _ensure_conn():
        raise RuntimeError("DB unavailable")
    await db_module._conn.execute(
        "INSERT INTO revoked_jti (jti, user_id, expires_at) VALUES (%s::uuid, %s::uuid, %s) "
        "ON CONFLICT (jti) DO NOTHING",
        (jti, user_id, expires_at),
    )
