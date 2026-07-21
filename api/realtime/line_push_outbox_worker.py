"""LINE Flex push outbox worker — CR-0017 Stage 2 (HD-2 outbox+worker pattern)。

每 N 秒 poll line_push_outbox table 取 status='pending' AND next_attempt_at
<= NOW() 的 row，依 push_kind dispatch 到 api/templates/line_flex builder
產 messages，呼叫 LINE Messaging API push_message。

成功 → status='sent' + sent_at；
失敗 → attempts++ + next_attempt_at = NOW + backoff（exponential）；
超 max_attempts → status='dead'。

啟動：main.py lifespan 內 `worker.start()`；停止：`await worker.stop()`。
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.line_push_outbox_worker")

DEFAULT_INTERVAL = int(os.getenv("LINE_PUSH_WORKER_INTERVAL", "10"))  # seconds
BATCH_SIZE = int(os.getenv("LINE_PUSH_WORKER_BATCH", "20"))
# Exponential backoff seconds 對應 attempts=1..5：30s / 2min / 8min / 30min / 2hr
_BACKOFF_SECONDS_BY_ATTEMPT = [30, 120, 480, 1800, 7200]

# audit NFR-Perf-009：outbox 送達延遲取樣（enqueue created_at → sent 的 wall-clock 秒），
# 供 outbox_lag_p99_seconds SLO（p99 ≤ 30s）度量。in-process 滾動視窗；OPS 由
# get_outbox_lag_metrics() 讀出（可接 /metrics 或週期性日誌），不新增對外端點。
_LAG_SAMPLES: deque[float] = deque(maxlen=2000)


def record_outbox_lag_seconds(seconds: float) -> None:
    """記一筆送達延遲樣本（秒）。負值/None 忽略。"""
    if seconds is not None and seconds >= 0:
        _LAG_SAMPLES.append(float(seconds))


def _percentile(sorted_samples: list[float], p: float) -> float:
    n = len(sorted_samples)
    idx = min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))
    return sorted_samples[idx]


def get_outbox_lag_metrics() -> dict:
    """回 outbox 送達延遲指標：count / p50 / p99（秒）。無樣本 → 值為 None。"""
    samples = sorted(_LAG_SAMPLES)
    n = len(samples)
    if n == 0:
        return {"count": 0, "p50_seconds": None, "p99_seconds": None}
    return {
        "count": n,
        "p50_seconds": round(_percentile(samples, 50), 3),
        "p99_seconds": round(_percentile(samples, 99), 3),
    }

# CR-0172 HD-A=A：技師派工 push_kind 走 tech-portal 內部端點投遞（非客戶 LINE 直推）。
# worker 只多一個「投遞目標=HTTP 內部端點」分支，不碰技師權威庫 / 第二 channel token，
# 由端點沿用現行 notify_assignment（技師庫反查 + 平台官方號推播）。
_TECH_DISPATCH_ENDPOINT: dict[str, str] = {
    "tech_dispatch_assigned": "/api/v1/internal/technicians/notify-assign",
}


class LinePushOutboxWorker:
    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL) -> None:
        self._interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        logger.info(
            "LinePushOutboxWorker started (interval=%ds, batch=%d)",
            self._interval, BATCH_SIZE,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("LinePushOutboxWorker stopped")

    async def _run(self) -> None:
        # 啟動後等 5 秒避開 startup 競爭
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=5)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("line_push_outbox_worker"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                await self._poll_once()
            except Exception:  # noqa: BLE001
                logger.exception("LinePushOutboxWorker poll_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval,
                )
                return
            except asyncio.TimeoutError:
                continue

    async def _poll_once(self) -> None:
        """取一批 pending row → 逐一處理。"""
        if not await _ensure_conn():
            logger.warning("DB not available, skip outbox poll")
            return

        # SELECT FOR UPDATE SKIP LOCKED 防多 worker 競爭（雖然當前 single instance
        # in-process worker，但 future cluster deploy 也安全）。
        cur = await db_module._conn.execute(
            "SELECT id, tenant_id, push_kind, target_line_id, reference_id, "
            "       reference_table, payload, attempts, max_attempts, created_at "
            "FROM line_push_outbox "
            "WHERE status = 'pending' AND next_attempt_at <= NOW() "
            "ORDER BY next_attempt_at ASC "
            "LIMIT %s "
            "FOR UPDATE SKIP LOCKED",
            (BATCH_SIZE,),
        )
        rows = await cur.fetchall()
        if not rows:
            return

        for row in rows:
            await self._process_row(row)

    async def _process_row(self, row: tuple) -> None:
        outbox_id = str(row[0])
        tenant_id = str(row[1])
        push_kind = row[2]
        target_line_id = row[3]
        reference_id = str(row[4]) if row[4] else None
        reference_table = row[5]
        payload = row[6] if isinstance(row[6], dict) else {}
        attempts = int(row[7])
        max_attempts = int(row[8])
        created_at = row[9] if len(row) > 9 else None

        # CR-0172 HD-A=A：技師派工 kind 走 tech-portal 內部端點投遞（非客戶 LINE 直推），
        # 由端點沿用技師庫反查 + 平台官方號推播。與客戶側 users.line_user_id 反查分流。
        if push_kind in _TECH_DISPATCH_ENDPOINT:
            ok, err = await self._dispatch_to_tech(push_kind, payload)
            if ok:
                await self._mark_sent(outbox_id)
                self._record_lag(created_at)
                logger.info(
                    "outbox tech-dispatch ok: id=%s kind=%s ref=%s",
                    outbox_id, push_kind, reference_id,
                )
            else:
                await self._mark_failed(outbox_id, attempts, max_attempts, err or "")
                logger.warning(
                    "outbox tech-dispatch failed: id=%s kind=%s attempts=%d err=%s",
                    outbox_id, push_kind, attempts + 1, err,
                )
            return

        # 1. 取 LINE userId（target_line_id 優先；缺失則從 reference 反查）
        line_uid = target_line_id or await self._resolve_line_uid(
            reference_table, reference_id, tenant_id,
        )
        if not line_uid:
            await self._mark_failed(
                outbox_id, attempts, max_attempts,
                "cannot resolve LINE userId from reference",
            )
            return

        # 2. Render messages（Stage 2 placeholder，Stage 3 升 Flex）
        from templates.line_flex import build_messages
        messages = build_messages(push_kind, payload)
        if not messages:
            await self._mark_dead(outbox_id, f"unknown push_kind: {push_kind}")
            return

        # 3. Push to LINE（CR-0175 C：帶 x_line_retry_key=outbox_id，讓 LINE 對「同一
        #    row 的 crash-replay 重送」24h 內去重——閉合 R19 兩步非原子重送缺口）
        ok, err = await self._push_to_line(line_uid, messages, retry_key=outbox_id)
        if ok:
            await self._mark_sent(outbox_id)
            self._record_lag(created_at)
            logger.info(
                "outbox push ok: id=%s kind=%s line=%s ref=%s",
                outbox_id, push_kind, line_uid[:8], reference_id,
            )
        else:
            await self._mark_failed(outbox_id, attempts, max_attempts, err or "")
            logger.warning(
                "outbox push failed: id=%s kind=%s attempts=%d err=%s",
                outbox_id, push_kind, attempts + 1, err,
            )

    async def _resolve_line_uid(
        self,
        reference_table: str | None,
        reference_id: str | None,
        tenant_id: str,
    ) -> str | None:
        """從 reference 反查 LINE userId。

        支援的 reference_table 對應路徑：
          - 'saas.reschedule_proposal' / 'scope_changes' / 'work_orders'
            → 同樣走 work_orders.problem_card_id → problem_cards.conversation_id
            → conversations.user_id → users.line_user_id
        """
        if not reference_table or not reference_id:
            return None
        if not await _ensure_conn():
            return None
        try:
            if reference_table == "work_orders":
                # 注意：work_orders 無 tenant_id 欄，租戶過濾走 users.tenant_id
                # （與 work_order_service._WO_JOIN 一致）。CR-0028 修正原 wo.tenant_id bug。
                sql = (
                    "SELECT u.line_user_id "
                    "FROM work_orders wo "
                    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
                    "JOIN conversations c ON pc.conversation_id = c.id "
                    "JOIN users u ON c.user_id = u.id "
                    "WHERE wo.id = %s::uuid AND u.tenant_id = %s::uuid"
                )
            elif reference_table == "quote":
                # CR-0095：報價推 LINE。CR-0128 報價先行後 quote 可能尚未綁工單
                # （work_order_id=NULL 的 PC 階段報價），改走 quote.problem_card_id
                # 直連 problem_card → conversation → user.line_user_id
                # （對 WO 階段報價同樣成立——problem_card_id 恆有值）。
                sql = (
                    "SELECT u.line_user_id "
                    "FROM quote q "
                    "JOIN problem_cards pc ON q.problem_card_id = pc.id "
                    "JOIN conversations c ON pc.conversation_id = c.id "
                    "JOIN users u ON c.user_id = u.id "
                    "WHERE q.id = %s::uuid "
                    "AND (q.tenant_id = %s::uuid OR q.tenant_id IS NULL)"
                )
            elif reference_table == "scope_changes":
                # 同上：scope_changes 與 work_orders 皆無 tenant_id 欄，走 users.tenant_id。
                sql = (
                    "SELECT u.line_user_id "
                    "FROM scope_changes sc "
                    "JOIN work_orders wo ON sc.work_order_id = wo.id "
                    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
                    "JOIN conversations c ON pc.conversation_id = c.id "
                    "JOIN users u ON c.user_id = u.id "
                    "WHERE sc.id = %s::uuid AND u.tenant_id = %s::uuid"
                )
            elif reference_table == "saas.reschedule_proposal":
                sql = (
                    "SELECT u.line_user_id "
                    "FROM saas.reschedule_proposal rp "
                    "JOIN work_orders wo ON rp.work_order_id = wo.id "
                    "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
                    "JOIN conversations c ON pc.conversation_id = c.id "
                    "JOIN users u ON c.user_id = u.id "
                    "WHERE rp.id = %s::uuid AND rp.tenant_id = %s::uuid"
                )
            else:
                return None
            cur = await db_module._conn.execute(sql, (reference_id, tenant_id))
            row = await cur.fetchone()
            return row[0] if row else None
        except Exception:  # noqa: BLE001
            logger.exception(
                "resolve_line_uid failed table=%s id=%s",
                reference_table, reference_id,
            )
            return None

    async def _push_to_line(
        self, line_uid: str, messages: list[dict], retry_key: str | None = None,
    ) -> tuple[bool, str | None]:
        """呼叫 LINE Messaging API push_message。

        retry_key（CR-0175 C）：傳 outbox_id 當 x_line_retry_key，讓 LINE 對「同一 row
        的重送」24h 內去重（outbox_id 為 UUID，符合 X-Line-Retry-Key 格式要求）。

        Stage 2 placeholder messages 為 dict (TextMessage)；Stage 3 升 Flex
        後 builder 仍回 dict，SDK 端 PushMessageRequest 接受 dict 或 SDK obj。
        """
        access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        if not access_token:
            return False, "LINE_CHANNEL_ACCESS_TOKEN missing"
        try:
            from linebot.v3.messaging import (
                ApiException,
                AsyncApiClient,
                AsyncMessagingApi,
                Configuration,
                FlexContainer,
                FlexMessage,
                PushMessageRequest,
                TextMessage,
            )
            cfg = Configuration(access_token=access_token)
            # Stage 3：messages 含 text 與 flex 兩型 → 各自轉 SDK obj
            sdk_messages = []
            for m in messages:
                mtype = m.get("type")
                if mtype == "text":
                    sdk_messages.append(TextMessage(text=m["text"]))
                elif mtype == "flex":
                    sdk_messages.append(FlexMessage(
                        alt_text=m.get("altText", ""),
                        contents=FlexContainer.from_dict(m["contents"]),
                    ))
                else:
                    logger.warning("unknown message type: %s", mtype)
            if not sdk_messages:
                return False, "no valid messages in builder output"
            async with AsyncApiClient(cfg) as api_client:
                api = AsyncMessagingApi(api_client)
                req = PushMessageRequest(to=line_uid, messages=sdk_messages)
                if retry_key:
                    await api.push_message(req, x_line_retry_key=retry_key)
                else:
                    await api.push_message(req)
            return True, None
        except ApiException as exc:
            status = getattr(exc, "status", None)
            return False, f"ApiException status={status}"
        except Exception as exc:  # noqa: BLE001
            return False, f"{type(exc).__name__}: {exc}"

    async def _dispatch_to_tech(
        self, push_kind: str, payload: dict,
    ) -> tuple[bool, str | None]:
        """CR-0172 HD-A=A：技師派工推播經 outbox 投遞——POST 到 tech-portal 內部端點
        (X-Internal-Token)，由端點沿用現行技師庫反查 + 平台官方號推播（維持 service
        邊界，worker 不碰技師庫 / 第二 channel token）。

        env 未配置（TECH_API_BASE_URL / INTERNAL_API_TOKEN）→ (False, ...)，交由 outbox
        重試 / dead 機制處理（比客戶側同步 fail-soft 多了送達保證）。base/token 讀入
        .strip()（0719 C-5 尾端換行防護）。
        """
        base = (os.getenv("TECH_API_BASE_URL") or "").strip()
        token = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
        if not base or not token:
            return False, "TECH_API_BASE_URL/INTERNAL_API_TOKEN 未配置"
        path = _TECH_DISPATCH_ENDPOINT.get(push_kind)
        if not path:
            return False, f"no tech dispatch endpoint for kind: {push_kind}"
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base.rstrip('/')}{path}",
                    json=payload,
                    headers={"X-Internal-Token": token},
                ) as r:
                    if r.status == 200:
                        return True, None
                    body = (await r.text())[:200]
                    return False, f"tech notify status={r.status} body={body}"
        except Exception as exc:  # noqa: BLE001
            return False, f"{type(exc).__name__}: {exc}"

    def _record_lag(self, created_at) -> None:
        """送達成功時記錄 enqueue(created_at)→sent 的延遲（秒），for outbox_lag_p99 SLO。
        best-effort，任何解析失敗不影響送達主流程。"""
        if created_at is None:
            return
        try:
            now = datetime.now(timezone.utc)
            ca = created_at
            if getattr(ca, "tzinfo", None) is None:
                ca = ca.replace(tzinfo=timezone.utc)
            record_outbox_lag_seconds((now - ca).total_seconds())
        except Exception:  # noqa: BLE001
            pass

    async def _mark_sent(self, outbox_id: str) -> None:
        await db_module._conn.execute(
            "UPDATE line_push_outbox SET "
            "  status = 'sent', sent_at = NOW(), updated_at = NOW(), "
            "  attempts = attempts + 1 "
            "WHERE id = %s::uuid",
            (outbox_id,),
        )

    async def _mark_failed(
        self,
        outbox_id: str,
        current_attempts: int,
        max_attempts: int,
        err: str,
    ) -> None:
        new_attempts = current_attempts + 1
        if new_attempts >= max_attempts:
            await self._mark_dead(outbox_id, err)
            return
        # exponential backoff
        backoff_idx = min(new_attempts - 1, len(_BACKOFF_SECONDS_BY_ATTEMPT) - 1)
        backoff = _BACKOFF_SECONDS_BY_ATTEMPT[backoff_idx]
        next_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
        await db_module._conn.execute(
            "UPDATE line_push_outbox SET "
            "  attempts = %s, next_attempt_at = %s, last_error = %s, "
            "  updated_at = NOW() "
            "WHERE id = %s::uuid",
            (new_attempts, next_at.isoformat(), err[:500], outbox_id),
        )

    async def _mark_dead(self, outbox_id: str, err: str) -> None:
        await db_module._conn.execute(
            "UPDATE line_push_outbox SET "
            "  status = 'dead', last_error = %s, updated_at = NOW() "
            "WHERE id = %s::uuid",
            (err[:500], outbox_id),
        )


# Singleton — main.py lifespan 引用
worker = LinePushOutboxWorker()
