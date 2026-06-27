"""Auth 業務邏輯：登入、refresh、logout、技師註冊。"""

from __future__ import annotations

import json
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone

from jose import JWTError

import core.db as db_module
from core.auth import (
    create_token,
    decode_token,
    hash_password,
    is_jti_revoked,
    load_user_security_state,
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
        f"SELECT id, email, password_hash, role, tenant_id, is_active, locked_until "
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
        "locked_until": row[6],
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


# ---------------------------------------------------------------------------
# A1 登入防爆破（Phase I 帳號安全）：連續失敗達 login_max_attempts 即鎖定
# login_lockout_minutes。門檻入 [auth] config 不寫死。僅對「既存帳號」生效
# （查無帳號無 row 可記，回 401 同枚舉防護；per-IP/global spray 防護列後續）。
# ---------------------------------------------------------------------------


def _lockout_cfg() -> tuple[int, int]:
    cfg = load_config().auth
    return int(cfg.get("login_max_attempts", 5)), int(cfg.get("login_lockout_minutes", 15))


def _is_locked(user: dict) -> bool:
    locked_until = user.get("locked_until")
    return bool(locked_until and locked_until > datetime.now(timezone.utc))


async def _register_login_failure(user_id: str) -> None:
    """登入失敗 +1；達上限則設 locked_until 並把計數歸零（CASE 用 UPDATE 前舊值）。"""
    max_attempts, lockout_minutes = _lockout_cfg()
    await db_module._conn.execute(
        "UPDATE users SET "
        "  failed_login_attempts = CASE WHEN failed_login_attempts + 1 >= %s "
        "                               THEN 0 ELSE failed_login_attempts + 1 END, "
        "  locked_until = CASE WHEN failed_login_attempts + 1 >= %s "
        "                      THEN NOW() + make_interval(mins => %s) ELSE locked_until END "
        "WHERE id = %s::uuid",
        (max_attempts, max_attempts, lockout_minutes, user_id),
    )


async def _reset_login_failures(user_id: str) -> None:
    """登入成功 → 計數歸零、解鎖。"""
    await db_module._conn.execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = %s::uuid",
        (user_id,),
    )


_LOCKED_MSG = "帳號因連續登入失敗已暫時鎖定，請稍後再試或聯絡管理員"


async def login(email: str, password: str, *, allowed_roles: list[str]) -> dict:
    user = await _find_user_by_email(email, allowed_roles)
    if not user:
        raise ApiError("UNAUTHENTICATED", "Invalid email or password", 401)
    if not user["is_active"]:
        raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
    if _is_locked(user):
        raise ApiError("LOGIN_LOCKED", _LOCKED_MSG, 429)
    if not user["password_hash"] or not verify_password(password, user["password_hash"]):
        await _register_login_failure(user["id"])
        raise ApiError("UNAUTHENTICATED", "Invalid email or password", 401)

    await _reset_login_failures(user["id"])
    return _build_login_payload(
        user_id=user["id"],
        role=user["role"],
        tenant_id=user["tenant_id"] or "00000000-0000-0000-0000-000000000001",
    )


# 台灣手機格式（與 TechnicianRegisterBody.phone 一致）。符合 → 視為手機查詢，否則當 email。
_TW_MOBILE_RE = re.compile(r"^09\d{8}$")


async def _find_users_by_phone(phone: str, role_in: list[str]) -> list[dict]:
    """依手機 + 角色查使用者。phone 無唯一約束 → 回全部相符以偵測歧義（CR-0099 §8.1）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    placeholders = ",".join(["%s"] * len(role_in))
    cur = await db_module._conn.execute(
        f"SELECT id, email, password_hash, role, tenant_id, is_active, locked_until "
        f"FROM users "
        f"WHERE phone = %s AND role IN ({placeholders})",
        (phone, *role_in),
    )
    rows = await cur.fetchall()
    return [
        {
            "id": str(r[0]),
            "email": r[1],
            "password_hash": r[2],
            "role": r[3],
            "tenant_id": str(r[4]) if r[4] else None,
            "is_active": r[5],
            "locked_until": r[6],
        }
        for r in rows
    ]


async def login_with_identifier(
    identifier: str, password: str, *, allowed_roles: list[str]
) -> dict:
    """以 identifier（台灣手機 09xxxxxxxx 或 Email）登入（CR-0099，技師專用）。

    解析規則：
      - 符合手機格式 → 查 phone；手機非唯一，多筆相符 → 409 AMBIGUOUS_IDENTIFIER，
        要求改用 Email（§8.1 業主裁決）。
      - 否則 → 走既有 email 查詢（不符 email 格式者自然查無 → 401）。
    密碼驗證、停用檢查、token 簽發與 login() 一致。
    """
    ident = (identifier or "").strip()
    if _TW_MOBILE_RE.match(ident):
        users = await _find_users_by_phone(ident, allowed_roles)
        if len(users) > 1:
            raise ApiError(
                "AMBIGUOUS_IDENTIFIER",
                "此手機號對應多個帳號，請改用 Email 登入",
                409,
            )
        user = users[0] if users else None
    else:
        user = await _find_user_by_email(ident, allowed_roles)

    if not user:
        raise ApiError("UNAUTHENTICATED", "Invalid credentials", 401)
    if not user["is_active"]:
        raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
    if _is_locked(user):
        raise ApiError("LOGIN_LOCKED", _LOCKED_MSG, 429)
    if not user["password_hash"] or not verify_password(password, user["password_hash"]):
        await _register_login_failure(user["id"])
        raise ApiError("UNAUTHENTICATED", "Invalid credentials", 401)

    await _reset_login_failures(user["id"])
    return _build_login_payload(
        user_id=user["id"],
        role=user["role"],
        tenant_id=user["tenant_id"] or "00000000-0000-0000-0000-000000000001",
    )


async def refresh(refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise ApiError("UNAUTHENTICATED", "Invalid refresh token", 401)

    if payload.get("type") != "refresh":
        raise ApiError("UNAUTHENTICATED", "Token is not a refresh token", 401)

    jti = payload.get("jti")
    if jti and await is_jti_revoked(jti):
        raise ApiError("TOKEN_REVOKED", "Refresh token has been revoked", 401)

    # A2/A3：refresh 也重查使用者狀態（停權即時失效 + 改密碼後撤 session），
    # 否則被停用/改密碼後仍能用舊 refresh 換新 access 達 30 天。fail-open（查無回 None）。
    state = await load_user_security_state(payload["sub"])
    if state is not None:
        if not state["is_active"]:
            raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
        pwd_changed = state["password_changed_at"]
        iat = payload.get("iat")
        if pwd_changed and iat is not None and int(iat) < int(pwd_changed.timestamp()):
            raise ApiError("TOKEN_STALE", "Refresh token invalidated by password change", 401)

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
        except (ValueError, TypeError):
            exp = datetime.now(timezone.utc) + timedelta(hours=1)
        await revoke_jti(access_jti, access_user_id, exp)

    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti and payload.get("type") == "refresh":
                exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                await revoke_jti(jti, payload["sub"], exp)
        except (JWTError, KeyError, ValueError, TypeError):
            # refresh decode / payload 缺欄位 / timestamp 解析失敗 → 忽略（只撤 access）
            pass


async def change_password(*, user_id: str, current_password: str, new_password: str) -> None:
    """變更密碼：驗證 current → 寫入新 hash。

    驗證規則：
      - current_password 必須與 DB hash 相符
      - new_password 不可與 current_password 完全相同
      - 帳戶 is_active=TRUE
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if current_password == new_password:
        raise ApiError("VALIDATION_ERROR", "New password must differ from current password", 422)

    cur = await db_module._conn.execute(
        "SELECT password_hash, is_active FROM users WHERE id = %s::uuid LIMIT 1",
        (user_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("UNAUTHENTICATED", "User not found", 401)

    pw_hash, is_active = row[0], row[1]
    if not is_active:
        raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
    if not pw_hash or not verify_password(current_password, pw_hash):
        raise ApiError("INVALID_CURRENT_PASSWORD", "Current password is incorrect", 401)

    new_hash = hash_password(new_password)
    # A3：password_changed_at = NOW() → 此前簽發的 access/refresh token 全部失效（撤既有 session）。
    await db_module._conn.execute(
        "UPDATE users SET password_hash = %s, password_changed_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_hash, user_id),
    )


async def admin_reset_password(*, email: str, tenant_id: str) -> str:
    """管理員代為重設：把同租戶指定 email 的密碼重設為隨機臨時密碼,回傳明文。

    機制原由 2026-06-10 會議 Action #7（免 email、admin 代重設）裁定。
    **2026-06-17 CR-0025 / ADR-0114 已上線自助 email 重設**（見
    password_reset_service.py），本端點**保留為後備**（離線/緊急 break-glass），
    非唯一路徑。

    admin 在後台重設後把臨時密碼轉達使用者,使用者登入後自行用 change_password 改回。

    規則：
      - 不驗 current_password（admin 權限由 router 的 role guard 把關）
      - 限同租戶（tenant_id 來自已認證 admin,防跨租戶重設）
      - 帳號需存在；停用帳號也可重設（由 admin 自行判斷是否同時啟用）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT id FROM users WHERE email = %s AND tenant_id = %s::uuid LIMIT 1",
        (email, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError(
            "USER_NOT_FOUND", f"No user with email {email} in this tenant", 404
        )

    # token_urlsafe(9) → 12 字元 url-safe 臨時密碼（>= 8,滿足 bcrypt 與前端規則）
    temp_password = secrets.token_urlsafe(9)
    new_hash = hash_password(temp_password)
    # A3：admin 重設亦撤該帳號既有 session（password_changed_at = NOW()）。
    await db_module._conn.execute(
        "UPDATE users SET password_hash = %s, password_changed_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_hash, row[0]),
    )
    return temp_password


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

    # 重複 email 檢查（CR-0090：依角色限定 — 同 email 可同時為技師與廠商，
    # 但同一角色內仍唯一。登入端點以 role 過濾故不衝突）
    cur = await db_module._conn.execute(
        "SELECT 1 FROM users WHERE email = %s AND role = 'technician' LIMIT 1",
        (email,),
    )
    if await cur.fetchone():
        raise ApiError(
            "EMAIL_TAKEN", f"Email {email} is already registered as a technician", 409
        )

    user_id = str(uuid.uuid4())
    technician_id = str(uuid.uuid4())
    pw_hash = hash_password(password)
    tenant_id = "00000000-0000-0000-0000-000000000001"

    async with db_module._conn.transaction():
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, tenant_type, display_name, phone, email, password_hash, role, is_active) "
            "VALUES (%s::uuid, %s::uuid, 'technician', %s, %s, %s, %s, 'technician', TRUE)",
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


# CR-0094 後台員工帳號可建立的角色（對齊 auth._ADMIN_WEB_ROLES 登入集 + admin）。
# technician/vendor 走各自 self-register；super_admin/tenant_admin 為特殊不在此開放。
_STAFF_ROLES = ("admin", "operations_manager", "dispatcher", "customer_service", "reviewer")


async def create_staff_user(req: dict, *, tenant_id: str) -> dict:
    """admin 建立後台員工帳號（users 列，role ∈ _STAFF_ROLES）。

    解業主「5 種角色只有 admin」—— 過去無任何建立非-admin 角色帳號的路徑。
    admin 建立的員工即時 active（不需 self-register 的 pending_approval）。
    email 角色限定去重（對齊 CR-0090：同 email 不同角色可並存）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    email = (req.get("email") or "").strip()
    name = (req.get("name") or "").strip()
    password = req.get("password") or ""
    role = (req.get("role") or "").strip()
    phone = (req.get("phone") or "").strip() or None

    if role not in _STAFF_ROLES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"role must be one of: {', '.join(_STAFF_ROLES)}",
            422,
        )
    if not name or not email:
        raise ApiError("VALIDATION_ERROR", "name and email are required", 422)
    if len(password) < 8:
        raise ApiError("VALIDATION_ERROR", "password must be at least 8 characters", 422)

    cur = await db_module._conn.execute(
        "SELECT 1 FROM users WHERE email = %s AND role = %s LIMIT 1", (email, role)
    )
    if await cur.fetchone():
        raise ApiError(
            "EMAIL_TAKEN", f"Email {email} is already registered as {role}", 409
        )

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(password)
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, tenant_type, display_name, phone, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, 'platform', %s, %s, %s, %s, %s, TRUE)",
        (user_id, tenant_id, name, phone, email, pw_hash, role),
    )
    return {
        "data": {
            "id": user_id,
            "tenant_id": tenant_id,
            "name": name,
            "email": email,
            "phone": phone,
            "role": role,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "message": "Staff account created",
    }


async def list_staff_users(*, tenant_id: str) -> dict:
    """列出後台員工帳號（供 admin 員工管理頁）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    placeholders = ", ".join(["%s"] * len(_STAFF_ROLES))
    cur = await db_module._conn.execute(
        "SELECT id, display_name, email, phone, role, is_active, created_at FROM users "
        f"WHERE tenant_id = %s::uuid AND role IN ({placeholders}) "
        "ORDER BY created_at DESC NULLS LAST",
        (tenant_id, *_STAFF_ROLES),
    )
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "name": r[1],
            "email": r[2],
            "phone": r[3],
            "role": r[4],
            "is_active": r[5],
            "created_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]
    return {"items": items}


_VENDOR_TYPES = {"brand", "locksmith", "distributor"}


async def register_vendor(req: dict) -> dict:
    """建立 users(role='vendor', tenant_type='requestor') + vendors 兩列（CR-0029 發案者）。

    鏡像 register_technician：email 全域去重、bcrypt hash、transaction、single-tenant 硬綁。
    vendor 不簽 token（待首次 login）；status=pending_approval 待管理員核准。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    email = req["email"]
    name = req["name"]
    phone = req["phone"]
    password = req["password"]
    vendor_type = req["vendor_type"]
    company_name = req.get("company_name")
    tax_id = req.get("tax_id")  # CR-0089 統一編號（B2B 開發票）
    address = req.get("address")

    if vendor_type not in _VENDOR_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"vendor_type must be one of {sorted(_VENDOR_TYPES)}",
            422,
        )

    # CR-0090：依角色限定（同 email 可同時為技師與廠商，但廠商角色內唯一）
    cur = await db_module._conn.execute(
        "SELECT 1 FROM users WHERE email = %s AND role = 'vendor' LIMIT 1",
        (email,),
    )
    if await cur.fetchone():
        raise ApiError(
            "EMAIL_TAKEN", f"Email {email} is already registered as a vendor", 409
        )

    user_id = str(uuid.uuid4())
    vendor_id = str(uuid.uuid4())
    pw_hash = hash_password(password)
    tenant_id = "00000000-0000-0000-0000-000000000001"

    async with db_module._conn.transaction():
        await db_module._conn.execute(
            "INSERT INTO users (id, tenant_id, tenant_type, display_name, phone, email, password_hash, role, is_active) "
            "VALUES (%s::uuid, %s::uuid, 'requestor', %s, %s, %s, %s, 'vendor', TRUE)",
            (user_id, tenant_id, name, phone, email, pw_hash),
        )
        await db_module._conn.execute(
            "INSERT INTO vendors (id, tenant_id, user_id, vendor_type, name, company_name, tax_id, phone, email, address, status) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, 'pending_approval')",
            (vendor_id, tenant_id, user_id, vendor_type, name, company_name, tax_id, phone, email, address),
        )

    return {
        "data": {
            "id": vendor_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "vendor_type": vendor_type,
            "name": name,
            "company_name": company_name,
            "tax_id": tax_id,
            "phone": phone,
            "email": email,
            "status": "pending_approval",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "message": "Vendor registered, pending admin approval",
    }
