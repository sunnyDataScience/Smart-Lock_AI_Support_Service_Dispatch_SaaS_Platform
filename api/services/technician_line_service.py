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
import time
from collections import deque
from datetime import datetime, timedelta, timezone

import aiohttp

import core.db as db_module
from core.errors import ApiError

logger = logging.getLogger("api.technician_line_service")

_BIND_CODE_TTL_MINUTES = 10
_LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
_LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# 綁定碼枚舉防護:per-source(line_user_id)嘗試限流(in-memory,單實例;多 replica
# 失準同 CR-0114 已知取捨)。webhook 已驗簽 fail-closed,此為第二層縱深——擋單一 LINE
# 帳號在 TTL 內暴力猜碼搶綁(6 位碼空間 10^6)。
_BIND_ATTEMPT_WINDOW_SEC = 10 * 60
_BIND_ATTEMPT_MAX = 5
_BIND_ATTEMPT_MAX_SOURCES = 10_000  # 記憶體邊界:超過即清掃全過期 bucket
_bind_attempts: dict[str, deque[float]] = {}


def _bind_attempt_ok(line_user_id: str) -> bool:
    """per-source 綁定碼嘗試限流:同一 line_user_id 於 window 內超過上限 → False
    (擋暴力枚舉搶綁)。成功綁定後由呼叫端清空該 bucket。無 source 不擋。

    記憶體邊界:成功綁定 pop 該 source;從未回來的 source 之 bucket 由 (a) 該 source
    再次呼叫時的過期修剪、(b) dict 超過 _BIND_ATTEMPT_MAX_SOURCES 時的全表清掃 兩者
    收斂,避免長壽命行程 unbounded 成長。單實例;多 replica 失準同 CR-0114 已知取捨。"""
    if not line_user_id:
        return True
    now = time.monotonic()
    if len(_bind_attempts) > _BIND_ATTEMPT_MAX_SOURCES:
        # 清掃:移除 timestamp 全過期(含空)的 source,回收記憶體
        for src in [s for s, b in _bind_attempts.items()
                    if not b or now - b[-1] > _BIND_ATTEMPT_WINDOW_SEC]:
            del _bind_attempts[src]
    bucket = _bind_attempts.setdefault(line_user_id, deque())
    while bucket and now - bucket[0] > _BIND_ATTEMPT_WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= _BIND_ATTEMPT_MAX:
        return False
    bucket.append(now)
    return True


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
    if not _bind_attempt_ok(line_user_id):
        logger.warning("LINE 綁定碼嘗試過於頻繁,暫拒枚舉 source=%s", (line_user_id or "")[:8])
        return None
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
    # 換綁唯一性:同一 line_user_id 若已綁其他技師,先自動解除舊綁並記審計
    # (對齊客服側 line_binding_service.consume_link_token 的換綁邏輯,避免兩技師
    #  共用同一 LINE userId 導致派工推播推錯人)。純 SQL,不動 schema。
    # 註:三段 UPDATE 同 conn 但非單一交易;並發下同一 uid 對兩技師的有效碼被同時
    #   消費仍有窄殘留視窗(best-effort 縱深,非強一致);根治需 DB 層 UNIQUE 約束(defer)。
    dup_cur = await conn.execute(
        "UPDATE technicians SET line_user_id = NULL "
        "WHERE line_user_id = %s AND id <> %s::uuid "
        "RETURNING id",
        (line_user_id, technician_id),
    )
    for old in await dup_cur.fetchall():
        logger.warning(
            "LINE 換綁:line_user_id 原綁 technician=%s 已自動解除,改綁 technician=%s",
            str(old[0])[:8], technician_id[:8],
        )
    await conn.execute(
        "UPDATE technicians SET line_user_id = %s WHERE id = %s::uuid",
        (line_user_id, technician_id),
    )
    await conn.execute(
        "UPDATE technician_line_bind_codes SET used_at = NOW() WHERE id = %s::uuid",
        (code_id,),
    )
    _bind_attempts.pop(line_user_id, None)  # 綁定成功清空該 source 的嘗試計數
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
        logger.warning("platform LINE 未配置(缺 PLATFORM_LINE_CHANNEL_ACCESS_TOKEN)→ 跳過推播")
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
        logger.warning("platform LINE reply 未配置(缺 PLATFORM_LINE_CHANNEL_ACCESS_TOKEN)→ 綁定確認訊息未送出")
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
                if r.status != 200:
                    body = await r.text()
                    logger.warning("platform LINE reply 失敗 status=%s body=%s", r.status, body)
                    return False
                return True
    except aiohttp.ClientError as exc:
        logger.warning("platform LINE reply 連線錯誤:%s", exc)
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
