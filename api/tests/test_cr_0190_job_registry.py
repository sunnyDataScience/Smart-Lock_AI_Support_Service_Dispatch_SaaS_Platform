"""ADR-037：job inventory、pilot run-once 與 API/runtime cutover guard。"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from realtime import job_registry


@pytest.mark.unit
def test_registry_has_complete_unique_operational_contracts():
    assert len(job_registry.JOB_SPECS) == 14
    assert len(job_registry.JOB_REGISTRY) == 14
    for spec in job_registry.JOB_SPECS:
        assert spec.owner
        assert spec.schedule
        assert spec.data_scope
        assert spec.idempotency_key
        assert spec.lock_key
        assert spec.timeout_seconds > 0
        assert spec.retry_policy
        assert spec.compensation
        assert spec.audit_event.startswith("background_job.")
        assert {
            "success_total",
            "failure_total",
            "duration_seconds",
            "lag_seconds",
            "oldest_pending_seconds",
            "retry_exhausted_total",
        }.issubset(spec.sli)


@pytest.mark.unit
def test_cleanup_pilot_is_bounded_and_repeat_safe():
    pilot = job_registry.JOB_REGISTRY["webhook-idempotency-cleanup"]
    assert pilot.kind == "scheduled"
    assert pilot.run_once_method == "run_once"
    assert "repeat-safe" in pilot.retry_policy
    assert pilot.timeout_seconds <= 300


@pytest.mark.asyncio
async def test_run_once_records_success_metrics(monkeypatch):
    class FakeWorker:
        async def run_once(self):
            return 7

    async def leader(_key):
        return True

    monkeypatch.setattr(job_registry, "resolve_job_object", lambda _spec: FakeWorker())
    monkeypatch.setattr(job_registry, "ensure_leader", leader)
    before = job_registry.metrics_snapshot().get(
        "webhook-idempotency-cleanup", {}
    ).get("success_total", 0)
    scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    result = await job_registry.run_job_once(
        "webhook-idempotency-cleanup", scheduled_at=scheduled_at
    )
    metrics = job_registry.metrics_snapshot()["webhook-idempotency-cleanup"]
    assert result == {
        "job_id": "webhook-idempotency-cleanup",
        "audit_event": "background_job.webhook-idempotency-cleanup",
        "status": "succeeded",
        "result": 7,
    }
    assert metrics["success_total"] == before + 1
    assert metrics["duration_seconds"] is not None
    assert metrics["lag_seconds"] >= 4
    assert metrics["oldest_pending_seconds"] == 0.0
    assert metrics["last_error"] is None


@pytest.mark.asyncio
async def test_terminal_attempt_records_retry_exhausted(monkeypatch):
    class FailingWorker:
        async def run_once(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        job_registry, "resolve_job_object", lambda _spec: FailingWorker()
    )
    before = job_registry.metrics_snapshot()["webhook-idempotency-cleanup"][
        "retry_exhausted_total"
    ]
    with pytest.raises(RuntimeError, match="boom"):
        await job_registry.run_job_once(
            "webhook-idempotency-cleanup",
            acquire_lock=False,
            attempt_number=3,
            max_attempts=3,
        )
    assert (
        job_registry.metrics_snapshot()["webhook-idempotency-cleanup"][
            "retry_exhausted_total"
        ]
        == before + 1
    )


@pytest.mark.asyncio
async def test_hybrid_api_runtime_excludes_externalized_pilot(monkeypatch):
    calls: list[str] = []

    class FakeWorker:
        def start(self):
            calls.append("start")

        async def stop(self):
            calls.append("stop")

    monkeypatch.setattr(job_registry, "resolve_job_object", lambda _spec: FakeWorker())
    monkeypatch.setattr(
        job_registry,
        "externalized_job_ids",
        lambda: frozenset({"webhook-idempotency-cleanup"}),
    )
    manager = job_registry.JobRuntimeManager()
    started = manager.start_for_api("hybrid")
    assert "webhook-idempotency-cleanup" not in started
    assert len(started) == 13
    await manager.stop()
    assert calls.count("start") == 13
    assert calls.count("stop") == 13


@pytest.mark.unit
def test_main_uses_registry_instead_of_hand_maintained_worker_list():
    source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
    assert "from realtime.job_registry import runtime_manager" in source
    assert "webhook_idem_cleanup.start()" not in source
    worker_main = (Path(__file__).parents[1] / "worker_main.py").read_text(
        encoding="utf-8"
    )
    assert "run_job_once" in worker_main
    assert "JOB_SPECS" in worker_main
    assert '"status": "failed"' in worker_main


@pytest.mark.unit
def test_api_deploy_propagates_cutover_mode_instead_of_hardcoding_hybrid():
    root = Path(__file__).parents[2]
    deploy = (root / "scripts/deploy/api.sh").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/cloud-run-deploy.yml").read_text(
        encoding="utf-8"
    )
    assert "BACKGROUND_RUNTIME_MODE=${BACKGROUND_RUNTIME_MODE}" in deploy
    assert "EXTERNALIZED_JOB_IDS=${EXTERNALIZED_JOB_IDS}" in deploy
    assert "BACKGROUND_RUNTIME_MODE: ${{ vars.BACKGROUND_RUNTIME_MODE || 'api' }}" in workflow
    assert "BACKGROUND_RUNTIME_MODE=hybrid ./scripts/deploy/api.sh" not in workflow
