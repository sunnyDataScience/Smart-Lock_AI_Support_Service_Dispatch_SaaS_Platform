"""自助忘記密碼 — 一次性 reset token 流程。CR-0025 / ADR-0114。

request_reset：
  - 依 email 查使用者（跨角色：admin / 技師等皆可）
  - 簽高熵明文 token（只回給寄信用），DB 只存 SHA-256 雜湊
  - TTL 30 分鐘、單次用；per-user rate limit（近 15 分鐘上限）
  - **帳號枚舉防護**：不論帳號是否存在、是否送達，一律安靜返回（呼叫端回 200）

confirm_reset：
  - 以雜湊查未過期 / 未用 token → 改 users.password_hash → 標 token used
  - token 無效 / 過期 / 已用 → 明確錯誤碼（前端可提示重新申請）

安全強化（Phase I 帳號安全 A3，2026-06-28）：confirm 後設 `users.password_changed_at = NOW()`，
get_current_user / refresh 於 token 驗證時比對 `iat < password_changed_at` → 失效，
達成「改密碼即全域撤銷該 user 既有 access/refresh session」。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.auth import hash_password
from core.config import load_config
from core.db import _ensure_conn
from core.errors import ApiError
from core.tech_mirror import mirror_rows
from services import email_provider

logger = logging.getLogger("api.password_reset_service")

_TOKEN_TTL_MINUTES = 30
_RATE_LIMIT_WINDOW_MINUTES = 15
_RATE_LIMIT_MAX = 3  # 同一帳號 15 分鐘內最多簽發 3 個 reset token


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _reset_link(raw_token: str) -> str:
    """組重設頁連結。base 取 env PASSWORD_RESET_WEB_URL → cors_origins[0] → localhost。"""
    base = (os.getenv("PASSWORD_RESET_WEB_URL") or "").strip()
    if not base:
        origins = load_config().system.get("cors_origins") or ["http://localhost:3000"]
        base = origins[0] if origins else "http://localhost:3000"
    return f"{base.rstrip('/')}/reset-password?token={raw_token}"


async def request_reset(*, email: str, request_ip: str | None = None) -> None:
    """簽發 reset token 並寄信。永遠安靜返回（枚舉防護）。"""
    if not await _ensure_conn():
        # DB 不可用：仍不洩漏，但記 log（呼叫端照常回 200）
        logger.error("request_reset: DB unavailable, email=%s", email)
        return

    cur = await db_module._conn.execute(
        "SELECT id, is_active FROM users WHERE email = %s ORDER BY created_at LIMIT 1",
        (email,),
    )
    row = await cur.fetchone()
    if not row:
        logger.info("request_reset: 無此帳號（安靜略過）email=%s", email)
        return
    user_id, is_active = str(row[0]), row[1]
    if not is_active:
        logger.info("request_reset: 帳號停用（安靜略過）user_id=%s", user_id)
        return

    # rate limit：近 15 分鐘已簽發數
    window_start = datetime.now(timezone.utc) - timedelta(minutes=_RATE_LIMIT_WINDOW_MINUTES)
    cur = await db_module._conn.execute(
        "SELECT COUNT(*) FROM password_reset_tokens WHERE user_id = %s::uuid AND created_at > %s",
        (user_id, window_start),
    )
    recent = (await cur.fetchone())[0]
    if recent >= _RATE_LIMIT_MAX:
        logger.warning("request_reset: rate-limit 命中（安靜略過）user_id=%s recent=%s", user_id, recent)
        return

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_TOKEN_TTL_MINUTES)

    await db_module._conn.execute(
        "INSERT INTO password_reset_tokens (user_id, token_hash, channel, expires_at, requested_ip) "
        "VALUES (%s::uuid, %s, 'email', %s, %s)",
        (user_id, token_hash, expires_at, request_ip),
    )

    link = _reset_link(raw_token)
    subject = "【智慧鎖客服系統】密碼重設"
    body = (
        "您好，\n\n"
        "我們收到您的密碼重設要求。請於 30 分鐘內點擊以下連結設定新密碼：\n\n"
        f"{link}\n\n"
        "若非您本人操作，請忽略此信，您的密碼不會變更。\n\n"
        "— 智慧鎖客服系統"
    )
    # smtplib 阻塞 → 丟到 thread；未配置 SMTP 時 send_email 回 False（fail-safe）
    sent = await asyncio.to_thread(email_provider.send_email, to=email, subject=subject, body_text=body)
    if not sent:
        logger.warning("request_reset: token 已建但信未送達（SMTP 未配置或失敗）user_id=%s", user_id)


async def confirm_reset(*, token: str, new_password: str) -> None:
    """以 token 設新密碼。token 無效 / 過期 / 已用 → 錯誤碼。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    token_hash = _hash_token(token)
    cur = await db_module._conn.execute(
        "SELECT id, user_id, expires_at, used_at FROM password_reset_tokens "
        "WHERE token_hash = %s LIMIT 1",
        (token_hash,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("RESET_TOKEN_INVALID", "Reset token is invalid", 400)

    token_id, user_id, expires_at, used_at = row[0], str(row[1]), row[2], row[3]
    if used_at is not None:
        raise ApiError("RESET_TOKEN_INVALID", "Reset token has already been used", 400)
    if expires_at <= datetime.now(timezone.utc):
        raise ApiError("RESET_TOKEN_EXPIRED", "Reset token has expired", 400)

    new_hash = hash_password(new_password)

    # CR-0112 方案 B:users 若為技師列須寫權威庫 + 鏡射;token 表留品牌庫。
    # 拆庫後兩句無法同交易 —— 順序「先改密、後燒 token」:改密失敗 token 未燒可
    # 重試;燒 token 失敗最壞情況是 token 於 TTL 內可再設一次密碼(可接受)。
    is_tech = False
    if db_module.tech_db_enabled():  # fallback 模式免探查(單庫行為不變)
        rcur = await db_module._conn.execute(
            "SELECT role FROM users WHERE id = %s::uuid LIMIT 1", (user_id,)
        )
        rrow = await rcur.fetchone()
        is_tech = bool(rrow) and rrow[0] == "technician"

    conn = await db_module.require_tech_conn() if is_tech else db_module._conn
    # A3：password_changed_at = NOW() → 撤銷該 user 此前所有 access/refresh token。
    await conn.execute(
        "UPDATE users SET password_hash = %s, password_changed_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_hash, user_id),
    )
    if is_tech:
        await mirror_rows("users", [user_id])
    await db_module._conn.execute(
        "UPDATE password_reset_tokens SET used_at = NOW() WHERE id = %s::uuid",
        (token_id,),
    )
    logger.info("confirm_reset: 密碼已重設 user_id=%s", user_id)
