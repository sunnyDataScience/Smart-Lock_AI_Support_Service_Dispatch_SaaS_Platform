"""CR-0169 師傅 LINE 推播 — 平台官方號綁定 + 派單/池單通知。

業主 2026-07-17 裁決:HD-1=c(綁定碼先行)/HD-3=b(指派必推+池單可開關)/
HD-4=a(line_user_id 明文,UI 遮蔽)/HD-5=a(每單即推)。

設計:
- 綁定:師傅站產 6 位一次性碼(TTL 10 分鐘,hash 存技師權威庫)→ 師傅加平台
  官方號好友、在 LINE 輸入碼 → webhook 驗碼寫 technicians.line_user_id。
- 推播:平台 channel 憑證(PLATFORM_LINE_CHANNEL_ACCESS_TOKEN)env-gated——
  未配置=fail-soft no-op(網頁通知中心照舊為保底),不阻斷任何主流程。
- 內容最小化:區域+品牌型號+單號縮寫,不含客戶姓名/地址/電話(接單前
  隱私最小揭露;點深連結進站登入後才看得到)。
- 所有資料面走技師權威庫(require_tech_conn;單庫 fallback 自動退主庫)。
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import aiohttp

import core.db as db_module
from core.errors import ApiError

logger = logging.getLogger("api.technician_line_service")

_BIND_CODE_TTL_MINUTES = 10
_LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
_LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"


def _hash_code(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def platform_line_configured() -> bool:
    return bool(os.getenv("PLATFORM_LINE_CHANNEL_ACCESS_TOKEN"))


def tech_portal_base() -> str:
    """深連結 base(師傅站)。"""
    return (os.getenv("TECH_PORTAL_URL") or "http://localhost:3001").rstrip("/")


# ── 綁定碼 ────────────────────────────────────────────────────────────────────

async def issue_bind_code(*, technician_id: str) -> dict:
    """簽發一次性綁定碼(舊碼作廢;回明文碼供 UI 顯示,庫存 hash)。"""
    conn = await db_module.require_tech_conn()
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=_BIND_CODE_TTL_MINUTES)
    # 同技師舊碼一律作廢(標 used)——避免多碼並存被撿走
    await conn.execute(
        "UPDATE technician_line_bind_codes SET used_at = NOW() "
        "WHERE technician_id = %s::uuid AND used_at IS NULL",
        (technician_id,),
    )
    await conn.execute(
        "INSERT INTO technician_line_bind_codes (technician_id, code_hash, expires_at) "
        "VALUES (%s::uuid, %s, %s)",
        (technician_id, _hash_code(code), expires),
    )
    return {"code": code, "expires_at": expires.isoformat(),
            "ttl_minutes": _BIND_CODE_TTL_MINUTES}


async def bind_by_code(*, line_user_id: str, code: str) -> dict | None:
    """webhook 路徑:以綁定碼完成綁定。回 {technician_id, name} 或 None(碼無效)。"""
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT c.id, c.technician_id, t.name FROM technician_line_bind_codes c "
        "JOIN technicians t ON t.id = c.technician_id "
        "WHERE c.code_hash = %s AND c.used_at IS NULL AND c.expires_at > NOW() "
        "LIMIT 1",
        (_hash_code(code.strip()),),
    )
    row = await cur.fetchone()
    if not row:
        return None
    code_id, technician_id, name = str(row[0]), str(row[1]), row[2]
    await conn.execute(
        "UPDATE technicians SET line_user_id = %s WHERE id = %s::uuid",
        (line_user_id, technician_id),
    )
    await conn.execute(
        "UPDATE technician_line_bind_codes SET used_at = NOW() WHERE id = %s::uuid",
        (code_id,),
    )
    logger.info("LINE 綁定完成 technician=%s", technician_id[:8])
    return {"technician_id": technician_id, "name": name}


async def get_binding(*, technician_id: str) -> dict:
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT line_user_id, notify_pool_new FROM technicians WHERE id = %s::uuid",
        (technician_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "technician not found", 404)
    lid = row[0]
    # HD-4=a:明文存、UI 遮蔽——只回綁定狀態與尾碼,不回完整 userId
    return {
        "bound": bool(lid),
        "line_user_id_masked": (f"…{lid[-6:]}" if lid else None),
        "notify_pool_new": bool(row[1]),
        "platform_line_configured": platform_line_configured(),
    }


async def unbind(*, technician_id: str) -> None:
    conn = await db_module.require_tech_conn()
    await conn.execute(
        "UPDATE technicians SET line_user_id = NULL WHERE id = %s::uuid",
        (technician_id,),
    )


async def set_pool_notify(*, technician_id: str, enabled: bool) -> None:
    conn = await db_module.require_tech_conn()
    await conn.execute(
        "UPDATE technicians SET notify_pool_new = %s WHERE id = %s::uuid",
        (enabled, technician_id),
    )


# ── 平台 channel 推播(fail-soft) ────────────────────────────────────────────

async def _push(line_user_id: str, text: str) -> bool:
    """平台官方號 push。未配置憑證=no-op False;429/5xx 簡易 backoff 重試 2 次。"""
    token = os.getenv("PLATFORM_LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        logger.info("platform LINE 未配置(缺 PLATFORM_LINE_CHANNEL_ACCESS_TOKEN)→ 跳過推播")
        return False
    payload = {"to": line_user_id, "messages": [{"type": "text", "text": text[:4900]}]}
    headers = {"Authorization": f"Bearer {token}"}
    for attempt in range(3):
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(_LINE_PUSH_URL, json=payload, headers=headers) as r:
                    if r.status == 200:
                        return True
                    if r.status in (429, 500, 502, 503) and attempt < 2:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)
                        continue
                    body = (await r.text())[:200]
                    logger.warning("platform LINE push 失敗 status=%s body=%s", r.status, body)
                    return False
        except aiohttp.ClientError as exc:  # noqa: PERF203
            logger.warning("platform LINE push 連線錯誤(attempt %s):%s", attempt, exc)
    return False


async def reply_text(reply_token: str, text: str) -> bool:
    """webhook 回覆(綁定成功/失敗提示)。fail-soft。"""
    token = os.getenv("PLATFORM_LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        return False
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                _LINE_REPLY_URL,
                json={"replyToken": reply_token,
                      "messages": [{"type": "text", "text": text[:4900]}]},
                headers={"Authorization": f"Bearer {token}"},
            ) as r:
                return r.status == 200
    except aiohttp.ClientError:
        return False


def _wo_summary(wo: dict) -> str:
    """內容最小化摘要:區域+品牌型號+單號縮寫(絕不含客戶姓名/地址/電話)。"""
    parts = [p for p in (
        wo.get("district"),
        " ".join(x for x in (wo.get("brand"), wo.get("model")) if x),
    ) if p]
    label = "・".join(parts) if parts else "新工單"
    number = wo.get("document_number") or str(wo.get("id", ""))[:8]
    return f"{label}({number})"


async def notify_assignment(*, technician_id: str, wo: dict) -> bool:
    """派單指派推播(HD-3:指派必推)。"""
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT line_user_id FROM technicians WHERE id = %s::uuid", (technician_id,))
    row = await cur.fetchone()
    if not row or not row[0]:
        return False
    text = (
        f"🔧 新工單指派給你:{_wo_summary(wo)}\n"
        f"請開啟師傅站確認接單:{tech_portal_base()}/my-orders"
    )
    return await _push(row[0], text)


async def notify_pool_new(*, wo: dict) -> int:
    """搶單池新單廣播(HD-3=b 開關、HD-5=a 每單即推)。回實際推送數。"""
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT line_user_id FROM technicians "
        "WHERE line_user_id IS NOT NULL AND notify_pool_new = TRUE "
        "  AND status = 'active'",
    )
    rows = await cur.fetchall()
    if not rows:
        return 0
    text = (
        f"📢 搶單池有新工單:{_wo_summary(wo)}\n"
        f"先接先得:{tech_portal_base()}/pool"
    )
    sent = 0
    for (lid,) in rows:
        if await _push(lid, text):
            sent += 1
    return sent
