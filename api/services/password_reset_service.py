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
from core.pii_crypto import mask_email_for_log
from core.config import load_config
from core.db import _ensure_conn
from core.errors import ApiError
from core.tech_mirror import mirror_rows
from services import email_provider

logger = logging.getLogger("api.password_reset_service")

_TOKEN_TTL_MINUTES = 30
_RATE_LIMIT_WINDOW_MINUTES = 15
_RATE_LIMIT_MAX = 3  # 同一帳號 15 分鐘內最多簽發 3 個 reset token


def _is_tech_surface() -> bool:
    """師傅面(:8002)的忘記密碼整條走技師權威庫(surface 分流,業主 2026-07-16 拍板)。

    背景:CR-0112 拆庫後技師 user 在權威庫,且品牌投影不含技師 email/password_hash
    (tech_mirror 最小化白名單)→ 在品牌庫查技師 email 永遠查無、安靜略過,
    技師忘記密碼整條失效(20260715 清單 16.5.4 銷案時 live 實證)。
    語意:在師傅站按忘記密碼=重設技師帳號;在品牌後台按=重設後台帳號,
    同 email 兩庫皆有時不會互相誤動。與 CR-0164 B 技師登入 lookup 修復同構。
    """
    return os.getenv("API_SURFACE", "all").strip().lower() == "tech"


async def _reset_conn():
    """依 surface 選庫:tech 面=技師權威庫(單庫 fallback 時自動退主庫),其餘=主庫。"""
    if _is_tech_surface():
        return await db_module.require_tech_conn()
    if not await _ensure_conn():
        return None
    return db_module._conn


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# 各站台的正式網址。這些值會**原封不動出現在寄給使用者的信裡**——localhost 在
# 收信人的裝置上永遠打不開，所以未設 env 時的 fallback 不能是 localhost
# （同 technician_line_service._DEFAULT_TECH_PORTAL_URL 的理由）。
# prod 由 scripts/deploy/api.sh 依 surface 烤入 PASSWORD_RESET_WEB_URL，一般吃不到本預設。
_DEFAULT_TECH_PORTAL_URL = "https://lock-tech-web-sjmxp23sqq-de.a.run.app"
_DEFAULT_BRAND_PORTAL_URL = "https://smart-lock-web-sjmxp23sqq-de.a.run.app"


def _reset_link(raw_token: str) -> str:
    """組重設頁連結。base 取 env PASSWORD_RESET_WEB_URL → 依 surface 預設站台。

    2026-07-30：原本 tech 面未設 env 時退 `http://localhost:3001`，而 prod 的
    lock-tech-api **確實沒設**這個 env → 技師在正式師傅站按「忘記密碼」收到的信裡
    是 localhost 連結。與 CR-0194 的 LINE 深連結同一類 bug：寄到使用者裝置上的
    連結不能是 localhost。
    """
    base = (os.getenv("PASSWORD_RESET_WEB_URL") or "").strip()
    if not base and _is_tech_surface():
        base = _DEFAULT_TECH_PORTAL_URL  # 技師的重設頁在師傅站
    if not base:
        # 品牌/平台面：優先取 CORS 白名單首位（本機開發會是 localhost:3000，正確），
        # 完全沒有設定時才退正式品牌站——同樣不退 localhost。
        origins = load_config().system.get("cors_origins") or []
        base = origins[0] if origins else _DEFAULT_BRAND_PORTAL_URL
    return f"{base.rstrip('/')}/reset-password?token={raw_token}"


async def request_reset(*, email: str, request_ip: str | None = None) -> None:
    """簽發 reset token 並寄信。永遠安靜返回（枚舉防護）。

    surface 分流:tech 面全走技師權威庫(users 查詢+token 表),其餘走主庫。
    """
    try:
        conn = await _reset_conn()
    except ApiError:
        conn = None
    if conn is None:
        # DB 不可用：仍不洩漏，但記 log（呼叫端照常回 200）
        logger.error("request_reset: DB unavailable, email=%s", mask_email_for_log(email))
        return

    # CR-0176 S5 前置（A1）：品牌庫雙謂詞（明文 OR bidx）；tech 面走技師權威庫
    # 無 bidx 欄（延伸範圍）維持明文等值。
    if _is_tech_surface():
        cur = await conn.execute(
            "SELECT id, is_active FROM users WHERE email = %s ORDER BY created_at LIMIT 1",
            (email,),
        )
    else:
        from core import user_pii_bidx

        cur = await conn.execute(
            "SELECT id, is_active FROM users "
            "WHERE (email = %s OR email_bidx = %s) ORDER BY created_at LIMIT 1",
            (email, user_pii_bidx.blind_index(email)),
        )
    row = await cur.fetchone()
    if not row:
        logger.info("request_reset: 無此帳號（安靜略過）email=%s", mask_email_for_log(email))
        return
    user_id, is_active = str(row[0]), row[1]
    if not is_active:
        logger.info("request_reset: 帳號停用（安靜略過）user_id=%s", user_id)
        return

    # rate limit：近 15 分鐘已簽發數
    window_start = datetime.now(timezone.utc) - timedelta(minutes=_RATE_LIMIT_WINDOW_MINUTES)
    cur = await conn.execute(
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

    await conn.execute(
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
    """以 token 設新密碼。token 無效 / 過期 / 已用 → 錯誤碼。

    surface 分流:tech 面 token 表與 users 同在技師權威庫(同庫語意,改完鏡射
    投影);其餘 surface 維持既有邏輯(token 在主庫;user 若為技師投影列則寫
    權威庫+鏡射——服務拆庫前遺留的品牌庫技師資料)。
    """
    conn = await _reset_conn()
    if conn is None:
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    token_hash = _hash_token(token)
    cur = await conn.execute(
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

    if _is_tech_surface():
        # tech 面:token 與 users 同在權威庫 —— 先改密、後燒 token(同庫但沿用
        # 保守順序);改完鏡射投影白名單欄位(不含 password_hash,冪等)。
        user_conn = conn
        mirror_after = db_module.tech_db_enabled()
    else:
        # CR-0112 方案 B:users 若為技師列須寫權威庫 + 鏡射;token 表留品牌庫。
        # 拆庫後兩句無法同交易 —— 順序「先改密、後燒 token」:改密失敗 token 未燒可
        # 重試;燒 token 失敗最壞情況是 token 於 TTL 內可再設一次密碼(可接受)。
        is_tech = False
        if db_module.tech_db_enabled():  # fallback 模式免探查(單庫行為不變)
            rcur = await conn.execute(
                "SELECT role FROM users WHERE id = %s::uuid LIMIT 1", (user_id,)
            )
            rrow = await rcur.fetchone()
            is_tech = bool(rrow) and rrow[0] == "technician"
        user_conn = await db_module.require_tech_conn() if is_tech else conn
        mirror_after = is_tech

    # A3：password_changed_at = NOW() → 撤銷該 user 此前所有 access/refresh token。
    await user_conn.execute(
        "UPDATE users SET password_hash = %s, password_changed_at = NOW(), updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_hash, user_id),
    )
    if mirror_after:
        await mirror_rows("users", [user_id])
    await conn.execute(
        "UPDATE password_reset_tokens SET used_at = NOW() WHERE id = %s::uuid",
        (token_id,),
    )
    logger.info("confirm_reset: 密碼已重設 user_id=%s", user_id)
