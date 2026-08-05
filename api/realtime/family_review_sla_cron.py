"""家族覆核 SLA 逾時升級 cron — CR-0166 R1（合約 4.4(d) / BR-SOP-002）。

家族覆核端點宣稱 reviewer SLA 24h，但逾時無任何升級機制。本 cron 每小時掃（interval=3600，見 :25；原註解寫「每日」與實作不符）
sop_drafts.reviewed_at（管理員初審通過時間）超過 24h、仍未有 family_reviews
紀錄的草稿 → 寫 audit event（sop.family_review_overdue）＋通知該租戶管理層。

去重（同一 draft 只升級一次、跨重啟安全）：以 audit_events 查重，不用 in-memory。
對齊 DisputeEscalationCron pattern：ensure_leader + startup delay + run_once 可手動觸發。

「累計 ≥3 件未審 → ChangeRequest 替補提名」（BR-SOP-002 後半）列 Phase II backlog。
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module
from core.observability import job_span
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.family_review_sla_cron")

DEFAULT_INTERVAL_S = int(os.getenv("FAMILY_REVIEW_SLA_CRON_INTERVAL", str(60 * 60)))  # 1h
DEFAULT_STARTUP_DELAY_S = int(os.getenv("FAMILY_REVIEW_SLA_CRON_STARTUP_DELAY", "60"))
SLA_HOURS = int(os.getenv("FAMILY_REVIEW_SLA_HOURS", "24"))
# 升級通知對象角色（CR-0166 §8-R1-3 裁決：tenant 內 admin + operations_manager）
_NOTIFY_ROLES = ("admin", "super_admin", "operations_manager")


class FamilyReviewSlaCron:
    def __init__(
        self,
        interval_seconds: int = DEFAULT_INTERVAL_S,
        startup_delay_s: int = DEFAULT_STARTUP_DELAY_S,
    ) -> None:
        self._interval = interval_seconds
        self._startup_delay = startup_delay_s
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        logger.info(
            "FamilyReviewSlaCron started (interval=%ds, sla=%dh)",
            self._interval, SLA_HOURS,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("FamilyReviewSlaCron stopped")

    async def _run(self) -> None:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=self._startup_delay)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            if not await _ensure_leader("family_review_sla_cron"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                n = await self.run_once()
                if n:
                    logger.info("family-review-sla tick: escalated %d overdue drafts", n)
            except Exception:  # noqa: BLE001
                logger.exception("family-review-sla run_once failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                return
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> int:
        """掃逾時未審草稿，逐筆升級（audit + 通知），回升級筆數。"""
        # CR-0209 TC-NFR-OBS-01：背景 job 此前全樹零 span
        with job_span("cron.family_review_sla"):
            if not await _ensure_conn():
                return 0
            cur = await db_module._conn.execute(
                "SELECT sd.id, sd.tenant_id, sd.title, sd.reviewed_at "
                "FROM sop_drafts sd "
                "WHERE LOWER(sd.status) = 'approved' "
                "  AND sd.reviewed_at IS NOT NULL "
                "  AND sd.reviewed_at < NOW() - (%s * INTERVAL '1 hour') "
                "  AND NOT EXISTS ("
                "    SELECT 1 FROM family_reviews fr WHERE fr.sop_draft_id = sd.id"
                "  ) "
                "  AND NOT EXISTS ("
                "    SELECT 1 FROM audit_events ae "
                "    WHERE ae.action = 'sop.family_review_overdue' "
                "      AND ae.target_id = sd.id"
                "  )",
                (SLA_HOURS,),
            )
            rows = await cur.fetchall()
            escalated = 0
            for draft_id, tenant_id, title, reviewed_at in rows:
                await self._escalate_one(str(draft_id), str(tenant_id), title or "", reviewed_at)
                escalated += 1
            return escalated

    async def _escalate_one(self, draft_id, tenant_id, title, reviewed_at) -> None:
        from services import audit_log_service

        awaiting_since = reviewed_at.isoformat() if reviewed_at else None
        # 1) append-only audit（去重錨點 target_id=draft_id）
        await audit_log_service.log_event(
            event_type="escalation",
            actor_id=None,
            actor_role="system",
            action="sop.family_review_overdue",
            target_type="sop_draft",
            target_id=draft_id,
            payload={
                "tenant_id": tenant_id,
                "title": title,
                "awaiting_since": awaiting_since,
                "sla_hours": SLA_HOURS,
                "policy": "BR-SOP-002 / 合約4.4(d)",
            },
        )
        # 2) 通知管理層（best-effort，不因通知失敗而漏記 audit）
        try:
            await self._notify_managers(tenant_id, draft_id, title)
        except Exception:  # noqa: BLE001
            logger.exception("family-review-sla notify failed (draft=%s)", draft_id)

    async def _notify_managers(self, tenant_id, draft_id, title) -> None:
        from services import notification_service

        cur = await db_module._conn.execute(
            "SELECT id FROM users "
            "WHERE tenant_id = %s::uuid AND role = ANY(%s) AND is_active = TRUE",
            (tenant_id, list(_NOTIFY_ROLES)),
        )
        rows = await cur.fetchall()
        for (uid,) in rows:
            await notification_service.push_notification(
                {
                    "target_type": "user",
                    "target_id": str(uid),
                    "kind": "family_review_overdue",
                    "title": "家族覆核逾時待處理",
                    "body": f"SOP 草稿「{title}」已逾 {SLA_HOURS} 小時未完成家族覆核，請儘速指派。",
                },
                tenant_id=str(tenant_id),
            )


# Singleton — main.py lifespan 引用
worker = FamilyReviewSlaCron()
