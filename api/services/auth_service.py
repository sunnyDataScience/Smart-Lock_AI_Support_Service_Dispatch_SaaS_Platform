"""Auth 業務邏輯：登入、refresh、logout、技師註冊。"""

from __future__ import annotations

import json
import logging
import math
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
from core.tech_mirror import mirror_rows
from core.errors import ApiError
from core.pii_crypto import encrypt_pii, last_n

logger = logging.getLogger("api.auth_service")


async def _login_lookup_conn(role_in: list[str]):
    """CR-0164 B：技師登入 lookup（email/phone→password_hash 驗證）改讀權威庫。

    品牌投影已不含技師 email/password_hash（tech_mirror 最小化白名單）→ 技師專用
    登入（role_in==['technician']）須查權威庫。其餘角色（admin/vendor 等）維持主庫。
    登入端點的 allowed_roles 不混用技師與其他角色（auth.py:130/143/372），故路由無歧義。
    """
    if role_in == ["technician"]:
        return await db_module.require_tech_conn()
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    return db_module._conn


async def _find_user_by_email(email: str, role_in: list[str]) -> dict | None:
    """依角色清單查使用者。"""
    conn = await _login_lookup_conn(role_in)

    placeholders = ",".join(["%s"] * len(role_in))
    cur = await conn.execute(
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


async def _users_write_conn(role: str | None):
    """users 表寫入路由（CR-0112 方案 B）：技師列權威庫、其餘主庫。

    技師寫入後呼叫端須 `mirror_rows("users", [user_id])` 同步品牌投影。
    單庫 fallback 時兩者為同一連線、mirror 為 no-op。
    """
    if role == "technician":
        return await db_module.require_tech_conn()
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    return db_module._conn


async def _register_login_failure(user_id: str, role: str | None = None) -> int:
    """登入失敗 +1；達上限則設 locked_until 並把計數歸零（CASE 用 UPDATE 前舊值）。

    回傳剩餘鎖定分鐘數（0 = 本次未觸發鎖定）。UAT-0718 W4-6（已釘契約）：
    觸發鎖定的那一次也回 403 ACCOUNT_LOCKED——呼叫端據回傳值決定回應。
    """
    max_attempts, lockout_minutes = _lockout_cfg()
    conn = await _users_write_conn(role)
    cur = await conn.execute(
        "UPDATE users SET "
        "  failed_login_attempts = CASE WHEN failed_login_attempts + 1 >= %s "
        "                               THEN 0 ELSE failed_login_attempts + 1 END, "
        "  locked_until = CASE WHEN failed_login_attempts + 1 >= %s "
        "                      THEN NOW() + make_interval(mins => %s) ELSE locked_until END "
        "WHERE id = %s::uuid "
        "RETURNING locked_until",
        (max_attempts, max_attempts, lockout_minutes, user_id),
    )
    row = await cur.fetchone()
    if role == "technician":
        await mirror_rows("users", [user_id])
    locked_until = row[0] if row else None
    if locked_until and locked_until > datetime.now(timezone.utc):
        return _remaining_lock_minutes(locked_until)
    return 0


async def _reset_login_failures(user_id: str, role: str | None = None) -> None:
    """登入成功 → 計數歸零、解鎖。"""
    conn = await _users_write_conn(role)
    await conn.execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = %s::uuid",
        (user_id,),
    )
    if role == "technician":
        await mirror_rows("users", [user_id])


# UAT-0718 W4-6（已釘契約）：登入撞鎖定（含鎖定期輸入正確密碼）→ 403
# ACCOUNT_LOCKED 含剩餘分鐘；觸發鎖定的那一次也回這個。鎖定前（1-4 次）
# 維持通用「帳號或密碼錯誤」——刻意不洩剩餘次數（枚舉/爆破安全取捨）。


def _remaining_lock_minutes(locked_until: datetime) -> int:
    """剩餘鎖定分鐘（無條件進位；至少 1 分鐘，避免顯示「0 分鐘後再試」）。"""
    delta = (locked_until - datetime.now(timezone.utc)).total_seconds()
    return max(1, math.ceil(delta / 60))


def _locked_error(minutes: int) -> ApiError:
    return ApiError("ACCOUNT_LOCKED", f"帳號已鎖定，請於 {minutes} 分鐘後再試", 403)


_GENERIC_LOGIN_FAIL = "帳號或密碼錯誤"


async def login(email: str, password: str, *, allowed_roles: list[str]) -> dict:
    user = await _find_user_by_email(email, allowed_roles)
    if not user:
        raise ApiError("UNAUTHENTICATED", _GENERIC_LOGIN_FAIL, 401)
    if not user["is_active"]:
        raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
    if _is_locked(user):
        raise _locked_error(_remaining_lock_minutes(user["locked_until"]))
    if not user["password_hash"] or not verify_password(password, user["password_hash"]):
        locked_minutes = await _register_login_failure(user["id"], user["role"])
        if locked_minutes:
            raise _locked_error(locked_minutes)
        raise ApiError("UNAUTHENTICATED", _GENERIC_LOGIN_FAIL, 401)

    await _reset_login_failures(user["id"], user["role"])
    return _build_login_payload(
        user_id=user["id"],
        role=user["role"],
        tenant_id=user["tenant_id"] or "00000000-0000-0000-0000-000000000001",
    )


# 台灣手機格式（與 TechnicianRegisterBody.phone 一致）。符合 → 視為手機查詢，否則當 email。
_TW_MOBILE_RE = re.compile(r"^09\d{8}$")


async def _find_users_by_phone(phone: str, role_in: list[str]) -> list[dict]:
    """依手機 + 角色查使用者。phone 無唯一約束 → 回全部相符以偵測歧義（CR-0099 §8.1）。"""
    # CR-0164 B：技師手機登入亦查權威庫（投影已無 phone/password_hash）
    conn = await _login_lookup_conn(role_in)

    placeholders = ",".join(["%s"] * len(role_in))
    cur = await conn.execute(
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
        raise ApiError("UNAUTHENTICATED", _GENERIC_LOGIN_FAIL, 401)
    if not user["is_active"]:
        if user.get("role") == "technician":
            code, msg = await _technician_disabled_reason(user["id"])
            raise ApiError(code, msg, 403)
        raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
    if _is_locked(user):
        raise _locked_error(_remaining_lock_minutes(user["locked_until"]))
    if not user["password_hash"] or not verify_password(password, user["password_hash"]):
        locked_minutes = await _register_login_failure(user["id"], user["role"])
        if locked_minutes:
            raise _locked_error(locked_minutes)
        raise ApiError("UNAUTHENTICATED", _GENERIC_LOGIN_FAIL, 401)

    await _reset_login_failures(user["id"], user["role"])
    return _build_login_payload(
        user_id=user["id"],
        role=user["role"],
        tenant_id=user["tenant_id"] or "00000000-0000-0000-0000-000000000001",
    )


async def _technician_disabled_reason(user_id: str) -> tuple[str, str]:
    """被停用技師帳號的精確拒登原因（依 technicians.status 區分訊息）。

    UAT-0718 W4-3：改讀**權威庫** technicians.status（require_tech_conn，同
    CR-0164 登入 lookup 路由）——原讀品牌投影，登入擋在權威庫、原因讀投影，
    兩源分岔時停權帳號被誤報「待核准」（張冠李戴）。兩源合一後不再分岔。

    查無 technicians 列 / 讀取失敗 → fail-open 回一般 ACCOUNT_DISABLED
    （不洩漏內部狀態；此處僅決定訊息文案，登入本體已被 is_active 擋下）。
    """
    try:
        conn = await db_module.require_tech_conn()
        cur = await conn.execute(
            "SELECT status FROM technicians WHERE user_id = %s::uuid",
            (user_id,),
        )
        row = await cur.fetchone()
    except Exception:  # noqa: BLE001 — 文案降級不影響拒登結果
        logger.warning("查詢技師停用原因失敗（回一般 ACCOUNT_DISABLED）", exc_info=True)
        row = None
    status = row[0] if row else None
    if status == "pending_approval":
        return "ACCOUNT_PENDING_APPROVAL", "帳號待核准，請等候平台審核通過後再登入"
    if status == "suspended":
        return "ACCOUNT_SUSPENDED", "帳號已停權，請聯繫平台管理員"
    return "ACCOUNT_DISABLED", "Account is disabled"


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
    # UAT-0718 R2：帶 role 讓 technician 於雙庫模式路由到權威庫（fail-closed）。
    state = await load_user_security_state(payload["sub"], payload.get("role"))
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
        "SELECT password_hash, is_active, role FROM users WHERE id = %s::uuid LIMIT 1",
        (user_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("UNAUTHENTICATED", "User not found", 401)

    pw_hash, is_active, role = row[0], row[1], row[2]
    if not is_active:
        raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
    if not pw_hash or not verify_password(current_password, pw_hash):
        raise ApiError("INVALID_CURRENT_PASSWORD", "Current password is incorrect", 401)

    new_hash = hash_password(new_password)
    # A3：password_changed_at = NOW() → 此前簽發的 access/refresh token 全部失效（撤既有 session）。
    conn = await _users_write_conn(role)
    await conn.execute(
        "UPDATE users SET password_hash = %s, password_changed_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_hash, user_id),
    )
    if role == "technician":
        await mirror_rows("users", [user_id])


async def get_profile(*, user_id: str) -> dict:
    """回傳目前登入者的個人資料（自助個人資料頁用）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, display_name, email, phone, role, tenant_id "
        "FROM users WHERE id = %s::uuid LIMIT 1",
        (user_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "User not found", 404)
    return {
        "id": str(row[0]),
        "display_name": row[1],
        "email": row[2],
        "phone": row[3],
        "role": row[4],
        "tenant_id": str(row[5]) if row[5] else None,
    }


async def update_profile(
    *, user_id: str, display_name: str | None, phone: str | None
) -> dict:
    """更新目前登入者自己的 display_name / phone（僅本人可改；只更新有帶入的欄位）。

    - display_name：去頭尾空白後 1–100 字（None＝不改）。
    - phone：去頭尾空白（None＝不改；空字串＝清空）。
    欄位名為固定字面（非使用者輸入），值皆參數化，無注入風險。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sets: list[str] = []
    params: list = []
    if display_name is not None:
        dn = display_name.strip()
        if not dn or len(dn) > 100:
            raise ApiError("VALIDATION_ERROR", "display_name 須為 1–100 字", 422)
        sets.append("display_name = %s")
        params.append(dn)
    if phone is not None:
        ph = phone.strip()
        if len(ph) > 50:
            raise ApiError("VALIDATION_ERROR", "phone 過長（上限 50 字）", 422)
        sets.append("phone = %s")
        params.append(ph or None)
    if not sets:
        return await get_profile(user_id=user_id)

    params.append(user_id)
    profile = await get_profile(user_id=user_id)  # 先取 role 供寫入路由（不存在即 404）
    conn = await _users_write_conn(profile["role"])
    await conn.execute(
        f"UPDATE users SET {', '.join(sets)}, updated_at = NOW() WHERE id = %s::uuid",
        tuple(params),
    )
    if profile["role"] == "technician":
        await mirror_rows("users", [user_id])
    return await get_profile(user_id=user_id)


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
        "SELECT id, role FROM users WHERE email = %s AND tenant_id = %s::uuid LIMIT 1",
        (email, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError(
            "USER_NOT_FOUND", f"No user with email {email} in this tenant", 404
        )

    # CR-0114 收斂：師傅帳號憑證屬平台方職權（師傅身分庫全平台唯一），品牌 admin
    # 不可重設/接管師傅登入憑證。師傅走自助 forgot-password；平台方代重設為後續輪。
    if row[1] == "technician":
        raise ApiError(
            "FORBIDDEN_TECHNICIAN_ACCOUNT",
            "師傅帳號密碼由平台方管理，品牌後台不可重設（師傅可自助走忘記密碼）",
            403,
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

    # CR-0115 Tier 1 非敏感欄位（全選填；最小必填在新表單層強制）
    years_experience = req.get("years_experience")
    bio = req.get("bio")
    vehicle_type = req.get("vehicle_type")
    availability_note = req.get("availability_note")
    emergency_contact_name = req.get("emergency_contact_name")
    emergency_contact_phone = req.get("emergency_contact_phone")
    certifications = req.get("certifications") or []
    terms_accepted = bool(req.get("terms_accepted"))

    # CR-0115 Tier 2 敏感 PII（§8-1：加密存獨立 technician_kyc 表、不鏡射品牌庫）
    national_id = (req.get("national_id") or "").strip() or None
    birth_date = req.get("birth_date")
    address = req.get("address")
    bank_code = req.get("bank_code")
    bank_account = (req.get("bank_account") or "").strip() or None
    tax_id = req.get("tax_id")
    has_kyc = any(
        v is not None
        for v in (national_id, birth_date, address, bank_code, bank_account, tax_id)
    )

    # CR-0112 方案 B：技師身分寫入落權威庫（fallback 時即主庫），完成後鏡射投影。
    conn = await db_module.require_tech_conn()

    # 重複 email 檢查（CR-0090：依角色限定 — 同 email 可同時為技師與廠商，
    # 但同一角色內仍唯一。登入端點以 role 過濾故不衝突）
    cur = await conn.execute(
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

    terms_accepted_at = datetime.now(timezone.utc) if terms_accepted else None

    async with conn.transaction():
        # is_active=FALSE：待核准前不可登入（BR-M07-01 上線審核 gate；
        # onboard-approve 時由 technician_lifecycle_service 同步翻 TRUE）
        await conn.execute(
            "INSERT INTO users (id, tenant_id, tenant_type, display_name, phone, email, password_hash, role, is_active) "
            "VALUES (%s::uuid, %s::uuid, 'technician', %s, %s, %s, %s, 'technician', FALSE)",
            (user_id, tenant_id, name, phone, email, pw_hash),
        )
        # CR-0115：technicians 加 Tier 1 非敏感欄位（全 nullable）
        await conn.execute(
            "INSERT INTO technicians (id, tenant_id, user_id, name, phone, email, "
            "capabilities, service_regions, status, years_experience, bio, vehicle_type, "
            "availability_note, emergency_contact_name, emergency_contact_phone, terms_accepted_at) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb, "
            "'pending_approval', %s, %s, %s, %s, %s, %s, %s)",
            (
                technician_id, tenant_id, user_id, name, phone, email,
                json.dumps(capabilities), json.dumps(regions),
                years_experience, bio, vehicle_type, availability_note,
                emergency_contact_name, emergency_contact_phone, terms_accepted_at,
            ),
        )
        # CR-0115 Tier 2：敏感 PII 加密後存獨立 technician_kyc 表（§8-1）
        if has_kyc:
            await conn.execute(
                "INSERT INTO technician_kyc (technician_id, tenant_id, national_id_enc, "
                "national_id_last3, bank_code, bank_account_enc, bank_account_last4, "
                "birth_date, address, tax_id) "
                "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    technician_id, tenant_id,
                    encrypt_pii(national_id), last_n(national_id, 3),
                    bank_code, encrypt_pii(bank_account), last_n(bank_account, 4),
                    birth_date or None, address, tax_id,
                ),
            )
        # CR-0115 Tier 1：自填證照落既有 technician_certification 表
        cert_ids: list[str] = []
        for cert in certifications:
            ccur = await conn.execute(
                "INSERT INTO technician_certification (tenant_id, technician_id, cert_name, "
                "brand, obtained_at, expires_at, is_mock) "
                "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, FALSE) "
                "RETURNING id",
                (
                    tenant_id, technician_id, cert["cert_name"], cert.get("brand"),
                    cert.get("obtained_at") or None, cert.get("expires_at") or None,
                ),
            )
            crow = await ccur.fetchone()
            if crow:
                cert_ids.append(str(crow[0]))

    # 投影鏡射（順序 users → technicians，投影側 FK technicians→users）
    # 注意：technician_kyc 敏感 PII **不鏡射**到品牌庫（§8-1 最小揭露）。
    await mirror_rows("users", [user_id])
    await mirror_rows("technicians", [technician_id])
    # UAT-0718 W3-3：自填證照同步鏡射品牌庫投影（表在 tech_mirror 白名單）——
    # 原本只落權威庫，平台/品牌審核頁「技能認證矩陣」讀投影恆空，審核者看不到證照。
    if cert_ids:
        await mirror_rows("technician_certification", cert_ids)

    # CR-0115 §8-2a：簽發兩階段文件上傳 token（Tier 3；明文僅出現在本 response，
    # 落庫只存 SHA-256）。fail-soft：migration 090 未套的異質部署註冊仍成功、僅少 token。
    upload_token: dict | None = None
    try:
        from services import technician_kyc_service

        upload_token = await technician_kyc_service.issue_upload_token(
            conn, technician_id=technician_id
        )
    except Exception:  # noqa: BLE001 — fail-soft:token 簽發失敗不擋註冊
        logger.warning(
            "文件上傳 token 簽發失敗（migration 090 未套？）；註冊仍成功", exc_info=True
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
            "upload_token": upload_token["token"] if upload_token else None,
            "upload_token_expires_at": (
                upload_token["expires_at"] if upload_token else None
            ),
        },
        "message": "Technician registered, pending admin approval",
    }


# 租戶 Admin 可開通集合（13_Security §3.1；業主裁決 2026-07-07 收斂 4 值，SA-06）。
# dispatcher 為**保留角色**暫不開通——存量帳號仍可登入（_ADMIN_WEB_ROLES 保留），
# 派工職能由 admin / operations_manager 承擔 + 自動派工（BR-PC-02）；重啟走 ChangeRequest。
# technician/vendor 走各自 self-register；super_admin/tenant_admin 為死角色不在此開放。
_STAFF_ROLES = ("admin", "operations_manager", "customer_service", "reviewer")


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
_VENDOR_INITIAL_STATUSES = {"active", "pending_approval"}


async def register_vendor(req: dict, *, initial_status: str = "active") -> dict:
    """建立 users(role='vendor', tenant_type='requestor') + vendors 兩列（CR-0029 發案者）。

    UAT R2 W3-2（2026-07-18 業主裁決）：公開自助註冊路徑已移除，本函式改為
    **平台代建復用核心**（platform_vendor_service.create_vendor 唯一呼叫者），
    預設 initial_status='active' 建立即啟用（不走待審核流）。

    鏡像 register_technician：email 角色內去重、bcrypt hash、transaction、
    single-tenant 硬綁。vendor 不簽 token（待首次 login）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    email = req["email"]
    name = req["name"]
    phone = req["phone"]
    password = req["password"]
    vendor_type = req.get("vendor_type") or "brand"
    company_name = req.get("company_name")
    tax_id = req.get("tax_id")  # CR-0089 統一編號（B2B 開發票）
    address = req.get("address")

    if vendor_type not in _VENDOR_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"vendor_type must be one of {sorted(_VENDOR_TYPES)}",
            422,
        )
    if initial_status not in _VENDOR_INITIAL_STATUSES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"initial_status must be one of {sorted(_VENDOR_INITIAL_STATUSES)}",
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
        # 代建（active）視同即刻核准 → 記 approved_at；approved_by 留 NULL
        # （FK 指品牌 users，平台管理員不在其中 —— 同平台核准時代的既有慣例）。
        await db_module._conn.execute(
            "INSERT INTO vendors (id, tenant_id, user_id, vendor_type, name, company_name, tax_id, phone, email, address, status, approved_at) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, "
            "        CASE WHEN %s = 'active' THEN NOW() ELSE NULL END)",
            (vendor_id, tenant_id, user_id, vendor_type, name, company_name,
             tax_id, phone, email, address, initial_status, initial_status),
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
            "status": initial_status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "message": (
            "廠商帳號已建立並啟用"
            if initial_status == "active"
            else "廠商已註冊，待管理員核准"
        ),
    }
