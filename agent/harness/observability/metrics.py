"""Session-level metrics aggregation from trace events.

Consumes traces from tracer.py session buffer to compute
L1 hit rate, transfer rate, latency breakdown, and other KPIs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from harness.observability.tracer import get_session_traces

logger = logging.getLogger("harness.metrics")


@dataclass
class SessionMetrics:
    """Metrics collected during a single conversation session."""

    session_id: str = ""
    problem_card_id: str = ""
    node_path: list[str] = field(default_factory=list)
    resolution_level: str = ""          # L1 | L2 | L3 | transfer
    total_latency_ms: float = 0.0
    diagnosis_status: str = ""          # need_more_info | hypothesis_formed | ready_to_conclude
    symptoms_extracted: list[str] = field(default_factory=list)
    transferred: bool = False
    feedback_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


def aggregate_session_metrics(session_id: str = "") -> SessionMetrics:
    """Aggregate trace events into a SessionMetrics summary.

    Call this at the end of a conversation turn (e.g., in post_process).
    """
    traces = get_session_traces()
    if not traces:
        return SessionMetrics(session_id=session_id)

    metrics = SessionMetrics(session_id=session_id)
    metrics.node_path = [t.get("node_name", "") for t in traces]
    metrics.total_latency_ms = sum(t.get("duration_ms", 0) for t in traces)

    for t in traces:
        tag = t.get("history_tag", "")
        if "task_decompose" in t.get("node_name", ""):
            metrics.diagnosis_status = t.get("diagnosis_status", "")
            metrics.symptoms_extracted = t.get("symptoms", [])
        if "transfer" in tag.lower():
            metrics.transferred = True
            metrics.resolution_level = "transfer"

    if not metrics.resolution_level:
        metrics.resolution_level = "L1"

    return metrics


async def emit_session_report(metrics: SessionMetrics) -> None:
    """Write session metrics to log (Phase 0-1: JSONL, Phase 2: PostgreSQL)."""
    report = {
        "type": "session_report",
        "session_id": metrics.session_id,
        "problem_card_id": metrics.problem_card_id,
        "node_path": metrics.node_path,
        "resolution_level": metrics.resolution_level,
        "total_latency_ms": round(metrics.total_latency_ms, 1),
        "diagnosis_status": metrics.diagnosis_status,
        "symptoms_extracted": metrics.symptoms_extracted,
        "transferred": metrics.transferred,
        "feedback_score": metrics.feedback_score,
        "created_at": metrics.created_at.isoformat(),
    }
    logger.info(json.dumps(report, ensure_ascii=False, default=str))
