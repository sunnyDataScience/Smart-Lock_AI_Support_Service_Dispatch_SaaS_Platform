"""M18 Phase II — canary rollout 自動 stage advance cron。

解凍 `config_m18_service._advance_canary_stage`（已從 [DEFERRED]
stub 升級為真實實作）。每 5 分鐘掃所有 `current_stage IN ('5%','50%')
AND next_stage_eta < NOW` 的 config_rollout → 呼 service helper 推進。

SLO halt（觀察 SLO 指標決定 rollback）仍 DEFERRED — 涉 metrics
collection + threshold 判斷，本輪只解 stage advance 缺口。

對齊既有 worker pattern (SLAMonitor / LinePushOutboxWorker /
ReconExceptionDetector / DisputeEscalationCron):
  - 300s (5 min) 預設 interval（env: CONFIG_CANARY_ADVANCE_INTERVAL）
  - 30s 啟動延遲
  - try/except per-rollout 隔離；不阻 lifespan
  - run_once 公開可呼供 admin manual trigger
"""

from __future__ import annotations

import asyncio
import logging
import os

import core.db as db_module
from core.observability import job_span
from core.db import _ensure_conn
from core.distributed_lock import ensure_leader as _ensure_leader

logger = logging.getLogger("api.config_canary_advance_cron")

DEFAULT_INTERVAL_S = int(os.getenv(
    "CONFIG_CANARY_ADVANCE_INTERVAL", "300",  # 5 min
))
DEFAULT_STARTUP_DELAY_S = int(os.getenv(
    "CONFIG_CANARY_ADVANCE_STARTUP_DELAY", "30",
))


class ConfigCanaryAdvanceCron:
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
            "ConfigCanaryAdvanceCron started (interval=%ds, startup_delay=%ds)",
            self._interval, self._startup_delay,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("ConfigCanaryAdvanceCron stopped")

    async def _run(self) -> None:
        try:
            await asyncio.wait_for(
                self._stopping.wait(), timeout=self._startup_delay,
            )
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("config_canary_advance_cron"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
            try:
                summary = await self.run_once()
                if summary["advanced"] or summary["errors"]:
                    logger.info("canary advance tick: %s", summary)
            except Exception:  # noqa: BLE001
                logger.exception("canary advance run_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval,
                )
                return
            except asyncio.TimeoutError:
                continue


async def _latest_slo_says_halt(rollout_id: str) -> bool:
    """該 rollout 最近一次 SLO 檢查是否結論為「該 halt」（CR-0210 D4(b)）。

    為什麼要查這個：現況是**一邊自動推、一邊不自動停**——canary cron 純依 ETA
    推進（不讀任何 SLO），而 `check_slo_halt` 只回建議、不真實 halt
    （`config_m18_service.py:985-986` 明文，那是「避免自動 trigger 風險」的刻意設計）。
    淨效果：admin 已經看到指標破線、跑過檢查、系統也把「should_halt=true」寫進 audit 了，
    **cron 下一輪照樣把壞版本推到 50% / 100%**。

    本檢查**不自動 halt、不改 rollout 狀態**（維持人工 rollback 的設計），
    只是「破線就不要再往前推」——壞版本停在原 stage 等人處理，而不是自己爬到全量。
    這是 D4(b) 的誠實版：cron 沒有 metrics 來源可以自己算 SLO
    （那是 A 群的缺口，綁 SigNoz），但它讀得到人已經做過的判斷。

    查不到紀錄／查詢失敗 → 回 False（維持既有推進行為，fail-open）。
    理由：這道檢查是額外保護，不該因為它自己壞掉而讓正常 rollout 全部卡住。
    """
    try:
        cur = await db_module._conn.execute(
            """
            SELECT a.diff
            FROM saas.config_audit a
            JOIN saas.config_rollout r ON r.config_version_id = a.config_version_id
            WHERE r.id = %s::uuid
              AND a.diff->>'slo_check' = 'true'
            ORDER BY a.ts DESC
            LIMIT 1
            """,
            (rollout_id,),
        )
        row = await cur.fetchone()
    except Exception:  # noqa: BLE001 — 保護性檢查失敗不可卡住正常 rollout
        logger.warning("canary: SLO 檢查查詢失敗，維持既有推進行為 rollout=%s", rollout_id)
        return False
    if not row or not isinstance(row[0], dict):
        return False
    return bool(row[0].get("should_halt"))

    async def run_once(self) -> dict:
        """掃所有 due rollout → 呼 service.advance；回 summary。"""
        # CR-0209 TC-NFR-OBS-01：背景 job 此前全樹零 span
        with job_span("cron.config_canary_advance"):
            if not await _ensure_conn():
                return {"skipped": "db_unavailable", "advanced": 0, "errors": 0}

            cur = await db_module._conn.execute(
                """
                SELECT id FROM saas.config_rollout
                WHERE strategy = 'canary_5_50_100'
                  AND current_stage IN ('5%', '50%')
                  AND next_stage_eta IS NOT NULL
                  AND next_stage_eta < NOW()
                ORDER BY next_stage_eta
                LIMIT 100
                """,
            )
            rows = await cur.fetchall()
            advanced = 0
            errors = 0
            halted_skips = 0
            for row in rows:
                rollout_id = str(row[0])
                # CR-0210 D4(b)：最近一次 SLO 檢查說該 halt → 不再往前推。
                # 不改狀態（維持人工 rollback 設計），只是停止自動擴散。
                if await _latest_slo_says_halt(rollout_id):
                    logger.warning(
                        "canary: rollout=%s 最近一次 SLO 檢查結論為 should_halt，"
                        "跳過本次自動推進（狀態不變，等 admin 顯式 rollback）",
                        rollout_id,
                    )
                    halted_skips += 1
                    continue
                try:
                    from services import config_m18_service
                    result = await config_m18_service._advance_canary_stage(
                        rollout_id=rollout_id,
                    )
                    advanced += 1
                    logger.info(
                        "canary advanced: rollout=%s new_stage=%s",
                        rollout_id[:8], result["new_stage"],
                    )
                except Exception:  # noqa: BLE001
                    errors += 1
                    logger.exception("canary advance failed: rollout=%s", rollout_id)
            # CR-0059 / BR-M18-02：順帶啟用到期的排程 config（effective_at<=now 的 draft）
            scheduled = 0
            try:
                from services import config_m18_service
                scheduled = await config_m18_service.activate_due_scheduled()
                if scheduled:
                    logger.info("scheduled config activated: %d", scheduled)
            except Exception:  # noqa: BLE001
                logger.exception("activate_due_scheduled failed")
            return {"advanced": advanced, "errors": errors, "scheduled_activated": scheduled,
                    "halted_skips": halted_skips}


# Singleton — main.py lifespan 引用
worker = ConfigCanaryAdvanceCron()
