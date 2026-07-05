"""平台方 console 帳號服務（CR-0114）。

platform_admin 是平台方（Lock AI)自用角色:
  - 帳號池住平台庫(require_platform_conn;未配置時 fallback 主連線)。
  - 不在任何品牌 gate 集合 → 品牌/平台 token 互不通用(deny-by-default);
    platform stack 另配獨立 API_JWT_SECRET_KEY 達成密碼學隔離。
  - token 的 tenant_id claim 帶全零 UUID(平台視角,非品牌租戶)。

lockout 語意對齊 auth_service A1(連續失敗鎖定,門檻讀 [auth] config),
但計數/鎖定寫平台庫。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError

import core.db as db_module
from core.auth import (
    create_token,
    decode_token,
    is_jti_revoked,
    load_user_security_state,
    revoke_jti,
    verify_password,
)
from core.config import load_config
from core.errors import ApiError

logger = logging.getLogger("api.platform_admin")

_ROLE = "platform_admin"
#: 平台視角的 tenant claim(非品牌租戶;全零與 demo 租戶 …0001 區隔)
PLATFORM_TENANT_ID = "00000000-0000-0000-0000-000000000000"
_LOCKED_MSG = "帳號因連續登入失敗已暫時鎖定，請稍後再試或聯絡管理員"


def _lockout_cfg() -> tuple[int, int]:
    cfg = load_config().auth
    return int(cfg.get("login_max_attempts", 5)), int(cfg.get("login_lockout_minutes", 15))


def _build_login_payload(*, user_id: str) -> dict:
    cfg = load_config().auth
    access_ttl = cfg.get("access_token_ttl_minutes", 60) * 60
    access_token, _, _ = create_token(
        user_id=user_id, role=_ROLE, tenant_id=PLATFORM_TENANT_ID, token_type="access"
    )
    refresh_token, _, _ = create_token(
        user_id=user_id, role=_ROLE, tenant_id=PLATFORM_TENANT_ID, token_type="refresh"
    )
    return {
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": access_ttl,
        },
        "message": "Login successful",
    }


async def _conn():
    try:
        return await db_module.require_platform_conn()
    except RuntimeError:
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)


async def login(email: str, password: str) -> dict:
    """平台管理員登入(email + password;鎖定/計數落平台庫)。"""
    conn = await _conn()
    cur = await conn.execute(
        "SELECT id, password_hash, is_active, locked_until "
        "FROM users WHERE email = %s AND role = %s LIMIT 1",
        (email, _ROLE),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("UNAUTHENTICATED", "Invalid email or password", 401)

    user_id, password_hash, is_active, locked_until = str(row[0]), row[1], row[2], row[3]
    if not is_active:
        raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
    if locked_until and locked_until > datetime.now(timezone.utc):
        raise ApiError("LOGIN_LOCKED", _LOCKED_MSG, 429)
    if not password_hash or not verify_password(password, password_hash):
        max_attempts, lockout_minutes = _lockout_cfg()
        await conn.execute(
            "UPDATE users SET "
            "  failed_login_attempts = CASE WHEN failed_login_attempts + 1 >= %s "
            "                               THEN 0 ELSE failed_login_attempts + 1 END, "
            "  locked_until = CASE WHEN failed_login_attempts + 1 >= %s "
            "                      THEN NOW() + make_interval(mins => %s) ELSE locked_until END "
            "WHERE id = %s::uuid",
            (max_attempts, max_attempts, lockout_minutes, user_id),
        )
        raise ApiError("UNAUTHENTICATED", "Invalid email or password", 401)

    await conn.execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = %s::uuid",
        (user_id,),
    )
    return _build_login_payload(user_id=user_id)


async def refresh(refresh_token: str) -> dict:
    """refresh token 換發(撤舊 jti、重查平台庫使用者狀態)。"""
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise ApiError("UNAUTHENTICATED", "Invalid refresh token", 401)

    if payload.get("type") != "refresh" or payload.get("role") != _ROLE:
        raise ApiError("UNAUTHENTICATED", "Token is not a platform refresh token", 401)

    jti = payload.get("jti")
    if jti and await is_jti_revoked(jti, _ROLE):
        raise ApiError("TOKEN_REVOKED", "Refresh token has been revoked", 401)

    state = await load_user_security_state(payload["sub"], _ROLE)
    if state is not None:
        if not state["is_active"]:
            raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
        pwd_changed = state["password_changed_at"]
        iat = payload.get("iat")
        if pwd_changed and iat is not None and int(iat) < int(pwd_changed.timestamp()):
            raise ApiError("TOKEN_STALE", "Refresh token invalidated by password change", 401)

    if jti:
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        await revoke_jti(jti, payload["sub"], exp_dt, _ROLE)

    return _build_login_payload(user_id=payload["sub"])


async def logout(*, access_jti: str, access_user_id: str, refresh_token: str | None) -> None:
    """登出:撤銷 access jti 與(如有)refresh jti,寫平台庫 revoked_jti。"""
    if access_jti and access_user_id:
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        await revoke_jti(access_jti, access_user_id, exp, _ROLE)

    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti and payload.get("type") == "refresh":
                exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                await revoke_jti(jti, payload["sub"], exp, _ROLE)
        except (JWTError, KeyError, ValueError, TypeError):
            pass  # refresh 解析失敗 → 只撤 access


async def me(user_id: str) -> dict:
    """回目前平台管理員 profile。"""
    conn = await _conn()
    cur = await conn.execute(
        "SELECT id, display_name, email, phone, created_at "
        "FROM users WHERE id = %s::uuid AND role = %s LIMIT 1",
        (user_id, _ROLE),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Platform admin not found", 404)
    return {
        "data": {
            "id": str(row[0]),
            "display_name": row[1],
            "email": row[2],
            "phone": row[3],
            "role": _ROLE,
            "created_at": row[4].isoformat() if row[4] else None,
        },
        "message": None,
    }
