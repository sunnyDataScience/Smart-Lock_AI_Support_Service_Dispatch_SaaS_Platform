"""ADR-037：背景工作 SSOT registry、runtime manager 與一次性執行 metrics。"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Literal

from core.distributed_lock import ensure_leader
from core.errors import ApiError

JobKind = Literal["continuous", "scheduled"]


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    owner: str
    object_path: str
    kind: JobKind
    schedule: str
    data_scope: str
    idempotency_key: str
    lock_key: str
    timeout_seconds: int
    retry_policy: str
    compensation: str
    audit_event: str
    run_once_method: str | None
    pending_sli: bool = False
    sli: tuple[str, ...] = (
        "success_total",
        "failure_total",
        "duration_seconds",
        "lag_seconds",
        "oldest_pending_seconds",
        "retry_exhausted_total",
    )

    def public_record(self) -> dict[str, Any]:
        value = asdict(self)
        value["sli"] = list(self.sli)
        return value


def _job(
    job_id: str,
    object_path: str,
    *,
    kind: JobKind,
    schedule: str,
    scope: str,
    idempotency: str,
    timeout: int,
    retry: str,
    compensation: str,
    run_once: str | None,
    pending_sli: bool = False,
) -> JobSpec:
    return JobSpec(
        job_id=job_id,
        owner="API Owner / SRE",
        object_path=object_path,
        kind=kind,
        schedule=schedule,
        data_scope=scope,
        idempotency_key=idempotency,
        lock_key=job_id.replace("-", "_"),
        timeout_seconds=timeout,
        retry_policy=retry,
        compensation=compensation,
        audit_event=f"background_job.{job_id}",
        run_once_method=run_once,
        pending_sli=pending_sli,
    )


JOB_SPECS: tuple[JobSpec, ...] = (
    _job(
        "inventory-monitor",
        "realtime.inventory_monitor:monitor",
        kind="continuous",
        schedule="every 60s",
        scope="brand.inventory_items",
        idempotency="item_id + low-stock state transition",
        timeout=55,
        retry="next poll; no destructive side effect",
        compensation="re-run scan",
        run_once="_scan_once",
    ),
    _job(
        "sla-monitor",
        "realtime.sla_monitor:monitor",
        kind="continuous",
        schedule="every 60s",
        scope="brand work-order/quote SLA",
        idempotency="alert_type + target_id in active runtime",
        timeout=55,
        retry="next poll",
        compensation="re-run scan and inspect notification audit",
        run_once="_scan_once",
    ),
    _job(
        "line-push-outbox",
        "realtime.line_push_outbox_worker:worker",
        kind="continuous",
        schedule="short poll",
        scope="brand.line_push_outbox",
        idempotency="outbox id + LINE delivery state",
        timeout=55,
        retry="bounded attempts/backoff; failed/dead state",
        compensation="operator requeue dead row after cause fixed",
        run_once="_poll_once",
        pending_sli=True,
    ),
    _job(
        "commission-outbox",
        "realtime.commission_outbox_worker:worker",
        kind="continuous",
        schedule="every 20s",
        scope="brand.commission_event_outbox",
        idempotency="stable event_id + consumer dedup",
        timeout=55,
        retry="8 attempts exponential backoff; dead state",
        compensation="operator requeue with original event_id",
        run_once="_poll_once",
        pending_sli=True,
    ),
    _job(
        "reconciliation-exception-detector",
        "realtime.reconciliation_exception_detector:worker",
        kind="scheduled",
        schedule="daily",
        scope="brand reconciliation",
        idempotency="tenant + reconciliation + exception type",
        timeout=900,
        retry="Scheduler retry + advisory lock",
        compensation="manual rerun/date window",
        run_once="run_once",
    ),
    _job(
        "dispute-escalation",
        "realtime.dispute_escalation_cron:worker",
        kind="scheduled",
        schedule="daily",
        scope="brand disputes older than threshold",
        idempotency="dispute state transition",
        timeout=900,
        retry="Scheduler retry + state predicate",
        compensation="manual rerun by tenant",
        run_once="run_once",
    ),
    _job(
        "config-canary-advance",
        "realtime.config_canary_advance_cron:worker",
        kind="scheduled",
        schedule="every 5m",
        scope="brand runtime config rollout",
        idempotency="config version + current rollout stage",
        timeout=240,
        retry="next schedule; halt on SLO gate",
        compensation="rollback config version",
        run_once="run_once",
    ),
    _job(
        "statement-auto-approval",
        "realtime.statement_auto_approval_cron:worker",
        kind="scheduled",
        schedule="daily",
        scope="three statement authorities",
        idempotency="statement state transition",
        timeout=900,
        retry="Scheduler retry + state predicate",
        compensation="financial correction workflow",
        run_once="run_once",
    ),
    _job(
        "statement-generate",
        "realtime.statement_generate_cron:worker",
        kind="scheduled",
        schedule="monthly",
        scope="brand technician statements",
        idempotency="tenant + technician + statement month unique",
        timeout=1800,
        retry="Scheduler retry + unique constraint",
        compensation="manual rerun for target month",
        run_once="run_once",
    ),
    _job(
        "gdpr-hard-delete",
        "realtime.gdpr_hard_delete_cron:worker",
        kind="scheduled",
        schedule="daily",
        scope="brand GDPR erasure queue T+30",
        idempotency="forget request state",
        timeout=1800,
        retry="Scheduler retry; audit each request",
        compensation="security/operator review; deletion is irreversible",
        run_once="run_once",
    ),
    _job(
        "media-retention",
        "realtime.media_retention_cron:worker",
        kind="scheduled",
        schedule="daily",
        scope="brand.media_files retention",
        idempotency="deleted_at IS NULL predicate",
        timeout=900,
        retry="Scheduler retry",
        compensation="soft-delete can be restored by governed workflow",
        run_once="run_once",
    ),
    _job(
        "auto-confirm",
        "realtime.auto_confirm_cron:worker",
        kind="scheduled",
        schedule="hourly",
        scope="brand work orders awaiting customer response",
        idempotency="work-order state transition",
        timeout=900,
        retry="Scheduler retry + state predicate",
        compensation="case correction workflow",
        run_once="run_once",
    ),
    _job(
        "webhook-idempotency-cleanup",
        "realtime.webhook_idempotency_cleanup_cron:worker",
        kind="scheduled",
        schedule="daily",
        scope="brand.webhook_idempotency older than 7d",
        idempotency="DELETE where processed_at before fixed retention boundary",
        timeout=300,
        retry="Scheduler retry; deletion predicate is repeat-safe",
        compensation="none required; expired dedup rows only",
        run_once="run_once",
    ),
    _job(
        "family-review-sla",
        "realtime.family_review_sla_cron:worker",
        kind="scheduled",
        schedule="hourly",
        scope="brand family review queue",
        idempotency="review id + escalation state",
        timeout=600,
        retry="Scheduler retry + state predicate",
        compensation="manual SLA escalation review",
        run_once="run_once",
    ),
)

JOB_REGISTRY = {spec.job_id: spec for spec in JOB_SPECS}
if len(JOB_REGISTRY) != len(JOB_SPECS):
    raise RuntimeError("Duplicate job_id in JOB_SPECS")

_RUN_METRICS: dict[str, dict[str, Any]] = {
    spec.job_id: {
        "success_total": 0,
        "failure_total": 0,
        "retry_exhausted_total": 0,
        "lag_seconds": None,
        "oldest_pending_seconds": None if spec.pending_sli else 0.0,
        "duration_seconds": None,
        "last_started_at": None,
        "last_finished_at": None,
        "last_error": None,
    }
    for spec in JOB_SPECS
}


def resolve_job_object(spec: JobSpec) -> Any:
    module_name, attribute = spec.object_path.split(":", 1)
    return getattr(importlib.import_module(module_name), attribute)


def _scheduled_lag_seconds(
    scheduled_at: str | datetime | None, started_at: datetime
) -> float | None:
    if scheduled_at is None:
        return None
    if isinstance(scheduled_at, str):
        try:
            scheduled = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ApiError(
                "JOB_SCHEDULED_AT_INVALID",
                "scheduled_at must be an ISO-8601 timestamp",
                422,
            ) from exc
    else:
        scheduled = scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    return round(max(0.0, (started_at - scheduled).total_seconds()), 6)


async def _collect_worker_sli(
    worker: Any, spec: JobSpec, metric: dict[str, Any]
) -> None:
    """讀 worker 的 durable queue probe；不適用 pending 的 job 明確回 0。

    probe 失敗不能把已完成的業務 job 改判失敗，故保留 last_error 供告警，
    下一輪仍可重新採樣。
    """
    probe = getattr(worker, "get_job_sli", None)
    if probe is None:
        if not spec.pending_sli:
            metric["oldest_pending_seconds"] = 0.0
        return
    try:
        values = probe()
        if inspect.isawaitable(values):
            values = await values
        if not isinstance(values, dict):
            return
        oldest = values.get("oldest_pending_seconds")
        if isinstance(oldest, (int, float)) and oldest >= 0:
            metric["oldest_pending_seconds"] = round(float(oldest), 6)
        exhausted = values.get("retry_exhausted_total")
        if isinstance(exhausted, int) and exhausted >= 0:
            metric["retry_exhausted_total"] = max(
                metric["retry_exhausted_total"], exhausted
            )
    except Exception as exc:  # noqa: BLE001 - SLI probe 不反轉已完成的 job
        metric["last_error"] = f"SLI probe failed: {type(exc).__name__}: {exc}"[:500]


async def run_job_once(
    job_id: str,
    *,
    acquire_lock: bool = True,
    scheduled_at: str | datetime | None = None,
    attempt_number: int = 1,
    max_attempts: int = 1,
) -> dict:
    spec = JOB_REGISTRY.get(job_id)
    if spec is None:
        raise ApiError("JOB_NOT_FOUND", f"Unknown job_id: {job_id}", 404)
    if not spec.run_once_method:
        raise ApiError("JOB_NOT_RUNNABLE_ONCE", f"{job_id} has no run-once handler", 409)
    if acquire_lock and not await ensure_leader(spec.lock_key):
        return {
            "job_id": job_id,
            "audit_event": spec.audit_event,
            "status": "skipped_not_leader",
        }

    worker = resolve_job_object(spec)
    handler = getattr(worker, spec.run_once_method)
    metric = _RUN_METRICS[job_id]
    started = datetime.now(timezone.utc)
    metric["last_started_at"] = started.isoformat()
    metric["lag_seconds"] = _scheduled_lag_seconds(scheduled_at, started)
    clock = monotonic()
    try:
        result = await asyncio.wait_for(handler(), timeout=spec.timeout_seconds)
    except Exception as exc:
        metric["failure_total"] += 1
        if max(1, attempt_number) >= max(1, max_attempts):
            metric["retry_exhausted_total"] += 1
        metric["last_error"] = f"{type(exc).__name__}: {exc}"[:500]
        await _collect_worker_sli(worker, spec, metric)
        raise
    else:
        metric["success_total"] += 1
        metric["last_error"] = None
        await _collect_worker_sli(worker, spec, metric)
        return {
            "job_id": job_id,
            "audit_event": spec.audit_event,
            "status": "succeeded",
            "result": result,
        }
    finally:
        metric["duration_seconds"] = round(monotonic() - clock, 6)
        metric["last_finished_at"] = datetime.now(timezone.utc).isoformat()


def metrics_snapshot() -> dict[str, dict[str, Any]]:
    return {job_id: dict(values) for job_id, values in _RUN_METRICS.items()}


def externalized_job_ids() -> frozenset[str]:
    raw = os.getenv(
        "EXTERNALIZED_JOB_IDS", "webhook-idempotency-cleanup"
    )
    values = frozenset(item.strip() for item in raw.split(",") if item.strip())
    unknown = values - JOB_REGISTRY.keys()
    if unknown:
        raise RuntimeError(f"Unknown EXTERNALIZED_JOB_IDS: {sorted(unknown)}")
    return values


class JobRuntimeManager:
    """API/worker 共用 start/stop；啟動順序反向停止。"""

    def __init__(self) -> None:
        self._started: list[Any] = []
        self.started_job_ids: list[str] = []

    def start_for_api(self, mode: str) -> list[str]:
        if mode not in {"api", "hybrid", "external"}:
            raise RuntimeError(
                "BACKGROUND_RUNTIME_MODE must be api, hybrid, or external"
            )
        excluded = externalized_job_ids() if mode == "hybrid" else frozenset()
        if mode == "external":
            excluded = frozenset(JOB_REGISTRY)
        for spec in JOB_SPECS:
            if spec.job_id in excluded:
                continue
            worker = resolve_job_object(spec)
            worker.start()
            self._started.append(worker)
            self.started_job_ids.append(spec.job_id)
        return list(self.started_job_ids)

    async def stop(self) -> None:
        for worker in reversed(self._started):
            await worker.stop()
        self._started.clear()
        self.started_job_ids.clear()


runtime_manager = JobRuntimeManager()
