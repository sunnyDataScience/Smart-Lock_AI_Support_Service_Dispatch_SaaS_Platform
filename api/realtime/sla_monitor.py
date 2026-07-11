"""SLA 引擎 — 四類 service-level 告警背景偵測。

對應 docs/02-design/specs/asyncapi.yaml /realtime/sla-alerts。

五類 alert_type（原 spec 四類 + CR-0129 audit_overdue）：
  - quote_expiring     : 工單已 quoted（estimated_price 已設）但客戶長時間未確認
                          MVP 代理：work_orders.status='created' AND
                          estimated_price IS NOT NULL AND created > X 分
  - dispatch_delay     : 派工逾時 — work_orders.status IN ('created','assigned')
                          AND created_at < NOW() - X 分
  - response_overdue   : 客戶等待回覆超時 — conversations.status='active'
                          AND 最後一則訊息 role='user' AND created_at < NOW() - X 分
  - arrival_overdue    : F-016 紅色警報 — 技師逾 2hr 未到場
                          work_orders.status='assigned' AND scheduled_at IS NOT NULL
                          AND scheduled_at < NOW() - X 分 AND started_at IS NULL
                          升 Ops Manager + dashboard 紅燈（PM Q5=B Soft SLA）

設計：
  - asyncio loop 定期掃（預設 60s，最小 30s）
  - in-memory _alerted dict[(alert_type, target_id)] 防止重複告警；
    狀態恢復後（解除條件不再成立）從 set 移除，下次再觸發
  - 環境變數：
    SLA_MONITOR_INTERVAL_SECONDS（預設 60）
    SLA_QUOTE_EXPIRING_MINUTES（預設 1440 = 24 小時）
    SLA_DISPATCH_DELAY_MINUTES（預設 30）
    SLA_RESPONSE_OVERDUE_MINUTES（預設 30）
    SLA_ARRIVAL_OVERDUE_MINUTES（預設 120 = 2 小時，F-016）
  - audit_overdue       : 急件補審逾 4h 窗未完成（CR-0129/15_SDS §4.5；due 存 quote.audit_due_at，
                          窗長由完工時依 M18 config 寫入，本監測不再另設閾值 env）

PM Q5=B 拍板（Soft SLA）：
  - arrival_overdue 觸發後僅做 dashboard 紅燈 + Ops Manager 通知 + audit log
  - 嚴禁串接賠償 / 自動退款 / 抵用券發放 / 沖銷 邏輯
  - 後續若需引入 Hard SLA 必須通過獨立 PM 決策

對齊現有 InventoryMonitor 模式（v1.28.0）。
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.sla_monitor")

DEFAULT_INTERVAL = max(30, int(os.environ.get("SLA_MONITOR_INTERVAL_SECONDS", "60")))
QUOTE_EXPIRING_MINUTES = int(os.environ.get("SLA_QUOTE_EXPIRING_MINUTES", "1440"))
DISPATCH_DELAY_MINUTES = int(os.environ.get("SLA_DISPATCH_DELAY_MINUTES", "30"))
RESPONSE_OVERDUE_MINUTES = int(os.environ.get("SLA_RESPONSE_OVERDUE_MINUTES", "30"))
ARRIVAL_OVERDUE_MINUTES = int(os.environ.get("SLA_ARRIVAL_OVERDUE_MINUTES", "120"))


class SLAMonitor:
    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL) -> None:
        self._interval = interval_seconds
        # 用 (alert_type, target_id) 當 key
        self._alerted: set[tuple[str, str]] = set()
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        logger.info(
            "SLAMonitor started (interval=%ds, quote=%dm, dispatch=%dm, response=%dm, arrival=%dm)",
            self._interval,
            QUOTE_EXPIRING_MINUTES,
            DISPATCH_DELAY_MINUTES,
            RESPONSE_OVERDUE_MINUTES,
            ARRIVAL_OVERDUE_MINUTES,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("SLAMonitor stopped")

    async def _run(self) -> None:
        # 啟動後等 5 秒再首次掃，避免與 startup 競爭
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=5)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("sla_monitor"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                await self._scan_once()
            except Exception:  # noqa: BLE001
                logger.exception("SLAMonitor scan_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval
                )
                return
            except asyncio.TimeoutError:
                continue

    async def _scan_once(self) -> None:
        if not await _ensure_conn():
            logger.warning("DB not available, skip SLA scan")
            return

        active_keys: set[tuple[str, str]] = set()
        new_alerts: list[dict] = []

        # ─── quote_expiring ───────────────────────────────────────────
        # CR-0117：計時基準=「報價送出」（quote.state='sent' 的 updated_at ≈ 送出時刻）。
        # CR-0163：錨定從 work_orders 改 quote 本身（與 audit_overdue 同型）——
        # CR-0128 報價先行主路徑上 sent 報價尚無工單（accept 後才 convert 綁定），
        # 原 INNER JOIN work_orders 讓本告警對卡階段報價永不觸發（二度死邏輯）。
        # target_id=quote.id（前端深連結 /admin/quotes?open=）；急件補審報價
        # （audit_due_at 非空）由 audit_overdue 專責，排除以免雙告警。
        cur = await db_module._conn.execute(
            "SELECT q.id, q.work_order_id "
            "FROM quote q "
            "LEFT JOIN work_orders wo ON wo.id = q.work_order_id "
            "WHERE q.state = 'sent' "
            "  AND q.total_amount IS NOT NULL "
            "  AND q.audit_due_at IS NULL "
            "  AND (q.work_order_id IS NULL OR wo.status = 'created') "
            "  AND q.updated_at < NOW() - (INTERVAL '1 minute' * %s)",
            (QUOTE_EXPIRING_MINUTES,),
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            key = ("quote_expiring", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "quote_expiring",
                        "target_id": target_id,
                        "threshold_minutes": QUOTE_EXPIRING_MINUTES,
                        # 額外 context：已綁單者前端可另連工單
                        "work_order_id": str(r[1]) if r[1] else None,
                    }
                )

        # ─── dispatch_delay ───────────────────────────────────────────
        cur = await db_module._conn.execute(
            "SELECT id, status "
            "FROM work_orders "
            "WHERE status IN ('created', 'assigned') "
            "  AND created_at < NOW() - (INTERVAL '1 minute' * %s)",
            (DISPATCH_DELAY_MINUTES,),
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            key = ("dispatch_delay", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "dispatch_delay",
                        "target_id": target_id,
                        "threshold_minutes": DISPATCH_DELAY_MINUTES,
                    }
                )

        # ─── response_overdue ─────────────────────────────────────────
        # 抓 active 對話中、最後一則為 user 訊息且超過閾值
        cur = await db_module._conn.execute(
            "SELECT c.id "
            "FROM conversations c "
            "WHERE c.status = 'active' "
            "  AND EXISTS ( "
            "    SELECT 1 FROM messages m "
            "    WHERE m.conversation_id = c.id "
            "    ORDER BY m.created_at DESC LIMIT 1 "
            "  ) "
            "  AND ( "
            "    SELECT m.role FROM messages m "
            "    WHERE m.conversation_id = c.id "
            "    ORDER BY m.created_at DESC LIMIT 1 "
            "  ) = 'user' "
            "  AND ( "
            "    SELECT m.created_at FROM messages m "
            "    WHERE m.conversation_id = c.id "
            "    ORDER BY m.created_at DESC LIMIT 1 "
            "  ) < NOW() - (INTERVAL '1 minute' * %s)",
            (RESPONSE_OVERDUE_MINUTES,),
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            key = ("response_overdue", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "response_overdue",
                        "target_id": target_id,
                        "threshold_minutes": RESPONSE_OVERDUE_MINUTES,
                    }
                )

        # ─── arrival_overdue（F-016 SLA 紅色警報，2hr 到場破線）──────────
        # 條件：技師已派 (status='assigned') + 排程時間已超過閾值 + 仍未開工
        # 注意：scheduled_at 為計畫到場時間；started_at 為實際到場 / 開工時間。
        # 完成 (status='completed','confirmed','cancelled') 不再警示。
        cur = await db_module._conn.execute(
            "SELECT id, technician_id "
            "FROM work_orders "
            "WHERE status = 'assigned' "
            "  AND scheduled_at IS NOT NULL "
            "  AND started_at IS NULL "
            "  AND scheduled_at < NOW() - (INTERVAL '1 minute' * %s)",
            (ARRIVAL_OVERDUE_MINUTES,),
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            tech_id = str(r[1]) if r[1] else None
            key = ("arrival_overdue", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "arrival_overdue",
                        "target_id": target_id,
                        "threshold_minutes": ARRIVAL_OVERDUE_MINUTES,
                        "severity": "red",
                        "escalated_to": "ops_manager",
                        # 額外 context（非 spec 必填，但前端有用）
                        "technician_id": tech_id,
                    }
                )

        # ─── audit_overdue（CR-0129 急件補審逾時，15_SDS §4.5 步驟5）────────
        # 條件：急件補審報價（audit_due_at 非空）逾窗未達 accepted（佔位或已送客戶皆算）。
        # 告警升主管；同租戶最近 3 件急件補審**全數逾時** → 自動開 ChangeRequest（BR-WO-04）。
        cur = await db_module._conn.execute(
            "SELECT q.id, q.work_order_id, q.tenant_id, q.audit_due_at "
            "FROM quote q "
            "WHERE q.audit_due_at IS NOT NULL "
            "  AND q.audit_due_at < NOW() "
            "  AND q.state IN ('retrospective_audit_only', 'sent')",
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            key = ("audit_overdue", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "audit_overdue",
                        "target_id": target_id,
                        "severity": "red",
                        "escalated_to": "ops_manager",
                        # 額外 context
                        "work_order_id": str(r[1]) if r[1] else None,
                        "tenant_id": str(r[2]) if r[2] else None,
                        "audit_due_at": r[3].isoformat() if r[3] else None,
                    }
                )

        # 從 _alerted 移除已恢復（不再符合條件）的告警
        recovered = self._alerted - active_keys
        if recovered:
            logger.info("SLA recovered: %d alerts cleared", len(recovered))
        self._alerted = active_keys

        if not new_alerts:
            return

        try:
            from realtime.ws_hub import hub

            for alert in new_alerts:
                await hub.publish(
                    "/realtime/sla-alerts",
                    {"type": "sla.alert", "payload": alert},
                )
                # F-016 紅色警報需額外寫 audit log（PM Q5=B Soft SLA 政策）
                if alert["alert_type"] == "arrival_overdue":
                    await self._write_arrival_overdue_audit(alert)
                # CR-0129：急件補審逾時 → audit log + 連 3 逾時自動開 ChangeRequest
                if alert["alert_type"] == "audit_overdue":
                    await self._handle_audit_overdue(alert)
            logger.info(
                "SLA alerts pushed: %d new (quote=%d, dispatch=%d, response=%d, arrival=%d, audit=%d)",
                len(new_alerts),
                sum(1 for a in new_alerts if a["alert_type"] == "quote_expiring"),
                sum(1 for a in new_alerts if a["alert_type"] == "dispatch_delay"),
                sum(1 for a in new_alerts if a["alert_type"] == "response_overdue"),
                sum(1 for a in new_alerts if a["alert_type"] == "arrival_overdue"),
                sum(1 for a in new_alerts if a["alert_type"] == "audit_overdue"),
            )
        except Exception:  # noqa: BLE001
            logger.exception("ws publish sla.alert failed (non-fatal)")

    async def _write_arrival_overdue_audit(self, alert: dict) -> None:
        """記錄 F-016 SLA 紅色警報事件到 audit_events。

        PM Q5=B 拍板：Soft SLA — 警報只升級 Ops Manager + 寫稽核日誌，
        不串接賠償 / 自動退款 / 沖銷。本函式刻意 **不** import 任何
        refund / voucher / settlement service。
        """
        try:
            from services.audit_log_service import log_event

            await log_event(
                event_type="escalation",
                actor_id=None,
                actor_role="system",
                action="sla.arrival_overdue",
                target_type="work_order",
                target_id=alert["target_id"],
                payload={
                    "alert_type": "arrival_overdue",
                    "threshold_minutes": alert.get("threshold_minutes"),
                    "severity": alert.get("severity"),
                    "escalated_to": alert.get("escalated_to"),
                    "technician_id": alert.get("technician_id"),
                    "policy": "Q5=B Soft SLA",
                    "compensation": "none",
                    "auto_refund": False,
                },
            )
        except Exception:  # noqa: BLE001 — audit 失敗不影響主流程
            logger.exception("audit log for arrival_overdue failed (non-fatal)")


    async def _handle_audit_overdue(self, alert: dict) -> None:
        """急件補審逾時處置（CR-0129 / 15_SDS §4.5 步驟5 / BR-WO-04）。

        1. audit log（升主管軌跡）。
        2. 同租戶**最近 3 件**已起算補審窗的急件報價全數逾時（未達 accepted 且逾 due，
           或事後才補完＝accepted 但完成時間晚於 due）→ 自動開 ChangeRequest
           （type=emergency_audit_breach，pending_approval 進主管佇列）；
           已有未結案同型 CR 則不重複開。
        """
        try:
            from services.audit_log_service import log_event

            await log_event(
                event_type="escalation",
                actor_id=None,
                actor_role="system",
                action="sla.audit_overdue",
                target_type="quote",
                target_id=alert["target_id"],
                payload={
                    "alert_type": "audit_overdue",
                    "work_order_id": alert.get("work_order_id"),
                    "audit_due_at": alert.get("audit_due_at"),
                    "escalated_to": alert.get("escalated_to"),
                    "policy": "15_SDS §4.5 逾時升級",
                },
            )
        except Exception:  # noqa: BLE001 — audit 失敗不影響主流程
            logger.exception("audit log for audit_overdue failed (non-fatal)")

        tenant_id = alert.get("tenant_id")
        if not tenant_id:
            return
        try:
            cur = await db_module._conn.execute(
                "SELECT q.state, q.audit_due_at, q.updated_at "
                "FROM quote q "
                "WHERE q.tenant_id = %s::uuid AND q.audit_due_at IS NOT NULL "
                "ORDER BY q.audit_due_at DESC LIMIT 3",
                (tenant_id,),
            )
            rows = await cur.fetchall()
            if len(rows) < 3:
                return

            def _overdue(row) -> bool:
                state, due, updated = row
                if state in ("retrospective_audit_only", "sent"):
                    return True  # 本 scan 由逾期觸發；未完成且列入近 3 件即逾時中
                return bool(due and updated and updated > due)  # 完成但晚於窗

            if not all(_overdue(r) for r in rows):
                return
            # 已有未結案同型 CR → 不重複開
            cur = await db_module._conn.execute(
                "SELECT 1 FROM saas.change_request "
                "WHERE tenant_id = %s::uuid AND type_code = 'emergency_audit_breach' "
                "  AND state IN ('draft', 'pending_approval') LIMIT 1",
                (tenant_id,),
            )
            if await cur.fetchone():
                return
            await db_module._conn.execute(
                "INSERT INTO saas.change_request "
                "  (tenant_id, type_code, state, payload_diff, reason, created_by) "
                "VALUES (%s::uuid, 'emergency_audit_breach', 'pending_approval', %s::jsonb, %s, "
                "        '00000000-0000-0000-0000-000000000000')",
                (
                    tenant_id,
                    __import__("json").dumps({
                        "trigger": "sla_monitor.audit_overdue",
                        "consecutive_overdue": 3,
                        "latest_quote_id": alert["target_id"],
                    }),
                    "急件補審連續 ≥3 件逾時（BR-WO-04 自動開立）——請主管檢討急件流程",
                ),
            )
            logger.warning(
                "急件補審連 3 逾時 → 自動開 ChangeRequest（tenant=%s，BR-WO-04）", tenant_id,
            )
        except Exception:  # noqa: BLE001 — CR 開立失敗不可卡死 SLA 掃描
            logger.exception("emergency_audit_breach ChangeRequest 開立失敗 tenant=%s", tenant_id)


# 單例
monitor = SLAMonitor()
