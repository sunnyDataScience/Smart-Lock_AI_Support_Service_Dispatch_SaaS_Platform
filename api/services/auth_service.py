"""Auth 業務邏輯：登入、refresh、logout、技師註冊。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import core.db as db_module
from core.auth import (
    create_token,
    decode_token,
    hash_password,
    is_jti_revoked,
    revoke_jti,
    verify_password,
)
from core.config import load_config
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.auth_service")


async def _find_user_by_email(email: str, role_in: list[str]) -> dict | None:
    """依角色清單查使用者。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    placeholders = ",".join(["%s"] * len(role_in))
    cur = await db_module._conn.execute(
        f"SELECT id, email, password_hash, role, tenant_id, is_active "
        f"FROM users "
        f"WHERE email = %s AND role IN ({placeholders}) "
        f"LIMIT 1",
        (email, *role_in),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "email": row[1],
        "password_hash": row[2],
        "role": row[3],
        "tenant_id": str(row[4]) if row[4] else None,
        "is_active": row[5],
    }


def _build_login_payload(*, user_id: str, role: str, tenant_id: str) -> dict:
    cfg = load_config().auth
    access_ttl = cfg.get("access_token_ttl_minutes", 60) * 60
    access_token, _, _ = create_token(
        user_id=user_id, role=role, tenant_id=tenant_id, token_type="access"
    )
    refresh_token, _, _ = create_token(
        user_id=user_id, role=role, tenant_id=tenant_id, token_type="refresh"
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


async def login(email: str, password: str, *, allowed_roles: list[str]) -> dict:
    user = await _find_user_by_email(email, allowed_roles)
    if not user:
        raise ApiError("UNAUTHENTICATED", "Invalid email or password", 401)
    if not user["is_active"]:
        raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
    if not user["password_hash"] or not verify_password(password, user["password_hash"]):
        raise ApiError("UNAUTHENTICATED", "Invalid email or password", 401)

    return _build_login_payload(
        user_id=user["id"],
        role=user["role"],
        tenant_id=user["tenant_id"] or "00000000-0000-0000-0000-000000000001",
    )


async def refresh(refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise ApiError("UNAUTHENTICATED", "Invalid refresh token", 401)

    if payload.get("type") != "refresh":
        raise ApiError("UNAUTHENTICATED", "Token is not a refresh token", 401)

    jti = payload.get("jti")
    if jti and await is_jti_revoked(jti):
        raise ApiError("TOKEN_REVOKED", "Refresh token has been revoked", 401)

    # Rotate：撤銷舊 jti，發新對
    if jti:
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        await revoke_jti(jti, payload["sub"], exp_dt)

    return _build_login_payload(
        user_id=payload["sub"],
        role=payload.get("role", ""),
        tenant_id=payload.get("tenant_id", ""),
    )


async def logout(*, access_jti: str, access_user_id: str, access_exp_iso: str | None,
                 refresh_token: str | None) -> None:
    """登出：撤銷 access jti 與（如有）refresh jti。"""
    if access_jti and access_user_id:
        # access token 過期前內阻擋
        from datetime import timedelta
        # 若不知 exp，預設 1h 後過期清除
        try:
            exp = datetime.fromisoformat(access_exp_iso) if access_exp_iso else datetime.now(timezone.utc) + timedelta(hours=1)
        except Exception:
            exp = datetime.now(timezone.utc) + timedelta(hours=1)
        await revoke_jti(access_jti, access_user_id, exp)

    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti and payload.get("type") == "refresh":
                exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                await revoke_jti(jti, payload["sub"], exp)
        except Exception:
            # refresh decode 失敗就忽略（只撤 access）
            pass


async def register_technician(req: dict) -> dict:
    """建立 users(role='technician') + technicians 兩列。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    email = req["email"]
    name = req["name"]
    phone = req["phone"]
    password = req["password"]
    capabilities = req.get("capabilities") or []
    regions = req.get("regions") or []

    # 重複 email 檢查
    cur = await db_module._conn.execute(
        "SELECT 1 FROM users WHERE email = %s LIMIT 1", (email,)
    )
    if await cur.fetchone():
        raise ApiError("EMAIL_TAKEN", f"Email {email} is already registered", 409)

    user_id = str(uuid.uuid4())
    technician_id = str(uuid.uuid4())
    pw_hash = hash_password(password)
    tenant_id = "00000000-0000-0000-0000-000000000001"

    async with db_module._conn.transaction():
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, display_name, phone, email, password_hash, role, is_active) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, 'technician', TRUE)",
            (user_id, tenant_id, name, phone, email, pw_hash),
        )
        await db_module._conn.execute(
            "INSERT INTO technicians (id, tenant_id, user_id, name, phone, email, capabilities, service_regions, status) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb, 'pending_approval')",
            (technician_id, tenant_id, user_id, name, phone, email, json.dumps(capabilities), json.dumps(regions)),
        )

    return {
        "data": {
            "id": technician_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "name": name,
            "phone": phone,
            "email": email,
            "capabilities": capabilities,
            "regions": regions,
            "status": "pending_approval",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "message": "Technician registered, pending admin approval",
    }
