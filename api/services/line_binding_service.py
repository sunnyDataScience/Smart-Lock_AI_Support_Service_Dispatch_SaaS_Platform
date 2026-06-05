"""LINE Binding Service — CR-0013 HD-03=b 主動綁定。

範圍：
  - generate_link_token(user_id, tenant_id): 產 24h TTL 一次性 token，給
    web/track UI；用 SHA-256 hash 存 line_binding.link_token_hash
  - consume_link_token(token, line_user_id): rich menu「綁定」postback
    收到 line_user_id 後，透過 token 反查 user → 建 active binding
  - get_active_binding(tenant_id, line_user_id): 查 active row
  - resolve_user_by_line_uid(line_user_id): 給 LINE webhook 查進度入口用
    （含 active binding fallback users.line_user_id）
  - unbind(tenant_id, line_user_id): 軟解綁
  - record_auto_binding(tenant_id, user_id, line_user_id): wo 建立流程
    自動關聯時呼叫（補審計 row）

設計決策：
  - HD-03=(b) — 主動 binding 為主，但保留 auto 路徑（既有 users.line_user_id
    自動關聯不破壞），auto 路徑也寫 binding row 給審計
  - HD-04=(a) 24h token TTL — 與 FR-0022 §1.2 A2 一致
  - token plain 不存 DB（hash 防外洩）；service 簽 + 驗 + ttl
  - 同 tenant + line_user_id active 唯一（partial unique index）；
    解綁後可重綁
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.line_binding_service")

TOKEN_TTL_HOURS = 24  # HD-04=(a)


# ============================================================
# Token helpers
# ============================================================

def _hash_token(token: str) -> str:
    """SHA-256 hash + hex；不可逆，防 DB 外洩反推。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    """產 32 byte URL-safe token（同 public_token 風格）。"""
    return secrets.token_urlsafe(32)


# ============================================================
# Generate / Consume link token (主動 binding 主流程)
# ============================================================

async def generate_link_token(
    *, tenant_id: str, user_id: str,
) -> dict:
    """產 24h TTL 一次性 binding token。

    用途：客戶在 web/track 看 wo 詳情頁，按「綁定 LINE 接收通知」鈕，
    後端產 token → 客戶掃 QR code 或點 LINE link → rich menu「綁定」
    postback 帶 token + line_user_id 進 consume_link_token。

    寫一筆 line_binding row 處於 unbound_at=NOW pending 狀態（line_user_id
    為 placeholder），consume 時 UPDATE。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    token = _new_token()
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)

    # 寫 placeholder row 等 consume；line_user_id 用 'pending:<token_hash[:16]>'
    # 防 unique index 衝突（active partial index WHERE unbound_at IS NULL，
    # placeholder 仍 active 但 line_user_id 是唯一占位，consume 時 UPDATE 真實值）
    placeholder_uid = f"pending:{token_hash[:16]}"
    await db_module._conn.execute(
        "INSERT INTO saas.line_binding "
        "  (tenant_id, user_id, line_user_id, bind_method, link_token_hash, "
        "   unbound_at) "
        "VALUES (%s::uuid, %s::uuid, %s, 'manual', %s, NULL)",
        (tenant_id, user_id, placeholder_uid, token_hash),
    )

    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "ttl_hours": TOKEN_TTL_HOURS,
    }


async def consume_link_token(
    *, token: str, line_user_id: str,
) -> dict:
    """LINE postback 帶 token + line_user_id 進來 → 完成 binding。

    流程：
      1. SHA-256(token) 反查 link_token_hash
      2. 檢查 row 狀態（未過期 / 未被消費）
      3. UPDATE line_user_id = 真實值 + clear link_token_hash + bound_at=NOW
      4. 同 tenant 內若已有別的 active binding 該 row 自動標 unbound_at
         (避免 partial unique index 衝突)

    Raises:
        ApiError(404): token 不存在
        ApiError(410): token 過期或已消費
        ApiError(409): 該 line_user_id 已綁別 user
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    token_hash = _hash_token(token)
    cur = await db_module._conn.execute(
        "SELECT id, tenant_id, user_id, line_user_id, created_at "
        "FROM saas.line_binding "
        "WHERE link_token_hash = %s AND unbound_at IS NULL",
        (token_hash,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "binding token not found", 404)

    binding_id, tenant_id, user_id, current_uid, created_at = row

    # 過期檢查（created_at + 24h）
    if created_at and (
        datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc)
        > timedelta(hours=TOKEN_TTL_HOURS)
    ):
        # 軟標過期防重用
        await db_module._conn.execute(
            "UPDATE saas.line_binding SET unbound_at = NOW(), updated_at = NOW() "
            "WHERE id = %s::uuid",
            (str(binding_id),),
        )
        raise ApiError("GONE", "binding token expired (24h TTL)", 410)

    # 已被 consume 過？placeholder uid 不以 'pending:' 開頭代表已 consume
    if not str(current_uid).startswith("pending:"):
        raise ApiError("CONFLICT", "binding token already consumed", 409)

    # 解綁同 tenant 內已存的 active binding（同一 line_user_id 換綁）
    await db_module._conn.execute(
        "UPDATE saas.line_binding SET unbound_at = NOW(), updated_at = NOW() "
        "WHERE tenant_id = %s::uuid AND line_user_id = %s "
        "  AND unbound_at IS NULL AND id <> %s::uuid",
        (str(tenant_id), line_user_id, str(binding_id)),
    )

    # UPDATE 主 row：寫真實 line_user_id + clear token
    upd = await db_module._conn.execute(
        "UPDATE saas.line_binding SET "
        "  line_user_id = %s, link_token_hash = NULL, "
        "  bound_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid AND unbound_at IS NULL "
        "RETURNING id, tenant_id, user_id, line_user_id, bind_method, bound_at",
        (line_user_id, str(binding_id)),
    )
    updated = await upd.fetchone()
    if not updated:
        raise ApiError("CONFLICT", "concurrent consume race", 409)

    return {
        "binding_id": str(updated[0]),
        "tenant_id": str(updated[1]),
        "user_id": str(updated[2]),
        "line_user_id": updated[3],
        "bind_method": updated[4],
        "bound_at": updated[5].isoformat() if updated[5] else None,
    }


# ============================================================
# Read
# ============================================================

async def get_active_binding(
    *, tenant_id: str, line_user_id: str,
) -> dict | None:
    """取 active binding；無回 None（caller 自行 404 或 fallback）。"""
    if not await _ensure_conn():
        return None
    cur = await db_module._conn.execute(
        "SELECT id, user_id, line_user_id, bind_method, bound_at "
        "FROM saas.line_binding "
        "WHERE tenant_id = %s::uuid AND line_user_id = %s "
        "  AND unbound_at IS NULL",
        (tenant_id, line_user_id),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {
        "binding_id": str(row[0]),
        "user_id": str(row[1]),
        "line_user_id": row[2],
        "bind_method": row[3],
        "bound_at": row[4].isoformat() if row[4] else None,
    }


async def resolve_user_by_line_uid(
    *, tenant_id: str, line_user_id: str,
) -> str | None:
    """LINE webhook 查進度入口：line_user_id → user_id。

    優先順序：
      1. saas.line_binding active (manual 主動綁) → user_id
      2. fallback users.line_user_id (legacy auto 路徑)
    """
    if not await _ensure_conn():
        return None

    # 1. 查 line_binding active
    binding = await get_active_binding(
        tenant_id=tenant_id, line_user_id=line_user_id,
    )
    if binding:
        return binding["user_id"]

    # 2. fallback users.line_user_id（legacy）
    cur = await db_module._conn.execute(
        "SELECT id FROM users WHERE line_user_id = %s LIMIT 1",
        (line_user_id,),
    )
    row = await cur.fetchone()
    return str(row[0]) if row else None


# ============================================================
# Auto binding 補審計（wo 建立流程呼）
# ============================================================

async def record_auto_binding(
    *, tenant_id: str, user_id: str, line_user_id: str,
) -> str | None:
    """wo 建立時 customers.line_user_id 自動關聯 → 補審計 row。

    若同 tenant+line_uid 已有 active binding（含 manual）不重複寫；
    回傳 binding_id 或 None。
    """
    if not await _ensure_conn():
        return None

    existing = await get_active_binding(
        tenant_id=tenant_id, line_user_id=line_user_id,
    )
    if existing:
        return existing["binding_id"]

    cur = await db_module._conn.execute(
        "INSERT INTO saas.line_binding "
        "  (tenant_id, user_id, line_user_id, bind_method) "
        "VALUES (%s::uuid, %s::uuid, %s, 'auto') "
        "RETURNING id",
        (tenant_id, user_id, line_user_id),
    )
    row = await cur.fetchone()
    return str(row[0]) if row else None


# ============================================================
# Unbind
# ============================================================

async def unbind(*, tenant_id: str, line_user_id: str) -> dict:
    """軟解綁 active binding（unbound_at=NOW）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    upd = await db_module._conn.execute(
        "UPDATE saas.line_binding SET "
        "  unbound_at = NOW(), updated_at = NOW() "
        "WHERE tenant_id = %s::uuid AND line_user_id = %s "
        "  AND unbound_at IS NULL "
        "RETURNING id, user_id",
        (tenant_id, line_user_id),
    )
    row = await upd.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "no active binding to unbind", 404)
    return {"binding_id": str(row[0]), "user_id": str(row[1])}
