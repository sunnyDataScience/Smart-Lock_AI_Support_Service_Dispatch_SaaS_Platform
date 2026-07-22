"""品牌員工帳號申請服務(CR-0114 R5)。

裁決 4:品牌員工自助申請 → 品牌 Admin 審核並指派角色(裁決 5:UAT 版 7 角色之
5 員工角色)。資料住品牌庫(該品牌自己的員工池,非師傅/平台域)。
不預建 users 列;核准時才 INSERT users(欄位對齊 auth_service.create_staff_user:
tenant_type='platform',但 password 用申請時已 hash 的值,不二次 hash)。
"""

from __future__ import annotations

import logging
import uuid

import core.db as db_module
from core.auth import hash_password
from core.errors import ApiError
from services.auth_service import _STAFF_ROLES, _find_user_by_email

logger = logging.getLogger("api.staff_application")


def _row_to_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "name": row[2],
        "email": row[3],
        "phone": row[4],
        "status": row[5],
        "assigned_role": row[6],
        "review_notes": row[7],
        "reviewed_at": row[8].isoformat() if row[8] else None,
        "created_at": row[9].isoformat() if row[9] else None,
    }


_SELECT_COLS = (
    "id, tenant_id, name, email, phone, status, assigned_role, "
    "review_notes, reviewed_at, created_at"
)


async def submit(
    *, tenant_id: str, name: str, email: str, phone: str | None, password: str,
) -> dict:
    """公開申請(品牌登入頁員工申請 tab)。不建 users,只寫申請列。

    防濫用:pending (tenant,email) 唯一索引 + email 去重(登入頁暴露面小,
    需知品牌網址才能到達)。
    """
    if not await db_module._ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    conn = db_module._conn

    # 去重:pending 申請 ∪ users 已存在同 email 的員工角色(避免重複申請已在職者)
    cur = await conn.execute(
        "SELECT 1 FROM staff_applications "
        "WHERE tenant_id = %s::uuid AND email = %s AND status = 'pending' LIMIT 1",
        (tenant_id, email),
    )
    if await cur.fetchone():
        raise ApiError("APPLICATION_EXISTS", "此 Email 已有待審核的申請", 409)
    existing = await _find_user_by_email(email, list(_STAFF_ROLES))
    if existing:
        raise ApiError("EMAIL_TAKEN", "此 Email 已是員工帳號,請直接登入或聯絡管理員", 409)

    app_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO staff_applications (id, tenant_id, name, email, phone, password_hash) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)",
        (app_id, tenant_id, name.strip(), email.strip(), (phone or "").strip() or None,
         hash_password(password)),
    )
    logger.info("staff_application 新申請 id=%s tenant=%s email=%s", app_id, tenant_id, email)
    return {
        "data": {"id": app_id, "status": "pending"},
        "message": "申請已送出,待品牌管理員審核並指派角色",
    }


async def list_applications(*, tenant_id: str, status: str | None = None) -> dict:
    if not await db_module._ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    conn = db_module._conn
    if status:
        cur = await conn.execute(
            f"SELECT {_SELECT_COLS} FROM staff_applications "
            "WHERE tenant_id = %s::uuid AND status = %s ORDER BY created_at DESC",
            (tenant_id, status),
        )
    else:
        cur = await conn.execute(
            f"SELECT {_SELECT_COLS} FROM staff_applications "
            "WHERE tenant_id = %s::uuid ORDER BY created_at DESC",
            (tenant_id,),
        )
    rows = await cur.fetchall()
    return {"data": [_row_to_dict(r) for r in rows], "message": None}


async def approve(*, tenant_id: str, app_id: str, reviewer_id: str, role: str) -> dict:
    """核准:指派角色(∈ _STAFF_ROLES,UAT 正典)→ transaction 內建 users + 翻狀態。

    users INSERT 欄位對齊 auth_service.create_staff_user(tenant_type='platform');
    password 直接用申請時已 hash 的 password_hash(不二次 hash)。
    """
    if role not in _STAFF_ROLES:
        raise ApiError("VALIDATION_ERROR", f"role 必須是 {_STAFF_ROLES} 之一", 422)
    if not await db_module._ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    conn = db_module._conn

    # 取申請(必須 pending 且同租戶)
    cur = await conn.execute(
        "SELECT name, email, phone, password_hash FROM staff_applications "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND status = 'pending'",
        (app_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        await _raise_not_pending(conn, tenant_id, app_id)
    name, email, phone, password_hash = row

    # email 角色限定去重(核准當下再查一次,避免競態;對齊 CR-0090)
    existing = await _find_user_by_email(email, [role])
    if existing:
        raise ApiError("EMAIL_TAKEN", f"Email {email} 已是 {role} 帳號", 409)

    new_user_id = str(uuid.uuid4())
    # CR-0176 S2：PII dual-write（enc 與明文同句 INSERT，交易內原子）
    from services import dek_service

    enc = await dek_service.encrypt_user_pii(
        new_user_id, tenant_id, {"display_name": name, "email": email, "phone": phone}
    )
    async with conn.transaction():
        await conn.execute(
            "INSERT INTO users (id, tenant_id, tenant_type, display_name, phone, email, "
            "password_hash, role, is_active, display_name_enc, email_enc, phone_enc, "
            "email_bidx, phone_bidx) "
            "VALUES (%s::uuid, %s::uuid, 'platform', %s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s)",
            (new_user_id, tenant_id, name, phone, email, password_hash, role,
             enc["display_name_enc"], enc["email_enc"], enc["phone_enc"],
             enc["email_bidx"], enc["phone_bidx"]),
        )
        await conn.execute(
            "UPDATE staff_applications SET status='approved', assigned_role=%s, "
            "created_user_id=%s::uuid, reviewed_by=%s::uuid, reviewed_at=NOW() "
            "WHERE id=%s::uuid",
            (role, new_user_id, reviewer_id, app_id),
        )
    logger.info("staff_application 核准 id=%s → user=%s role=%s", app_id, new_user_id, role)
    return {
        "data": {"id": app_id, "status": "approved", "assigned_role": role,
                 "created_user_id": new_user_id},
        "message": f"已核准並建立 {role} 帳號",
    }


async def reject(*, tenant_id: str, app_id: str, reviewer_id: str, reason: str) -> dict:
    if not reason or len(reason.strip()) < 3:
        raise ApiError("VALIDATION_ERROR", "拒絕原因至少 3 個字", 422)
    if not await db_module._ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    conn = db_module._conn
    cur = await conn.execute(
        "UPDATE staff_applications SET status='rejected', review_notes=%s, "
        "reviewed_by=%s::uuid, reviewed_at=NOW() "
        "WHERE id=%s::uuid AND tenant_id=%s::uuid AND status='pending' "
        f"RETURNING {_SELECT_COLS}",
        (reason.strip(), reviewer_id, app_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        await _raise_not_pending(conn, tenant_id, app_id)
    logger.info("staff_application 拒絕 id=%s by=%s", app_id, reviewer_id)
    return {"data": _row_to_dict(row), "message": "已拒絕"}


async def _raise_not_pending(conn, tenant_id: str, app_id: str) -> None:
    cur = await conn.execute(
        "SELECT status FROM staff_applications WHERE id=%s::uuid AND tenant_id=%s::uuid",
        (app_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Application not found", 404)
    raise ApiError("STATE_CONFLICT", f"Application is {row[0]}, not pending", 409)
