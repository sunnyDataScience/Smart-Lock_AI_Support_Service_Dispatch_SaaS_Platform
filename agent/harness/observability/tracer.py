"""Structured trace emitter for graph nodes.

Emits JSON-structured trace events for every decorated node.
Dual output: stdout JSONL (always) + PostgreSQL harness_traces (when DB available).
"""

import asyncio
import functools
import json
import logging
import os
from datetime import datetime, timezone

from harness import is_layer_enabled
from core.config import HARNESS_CONFIG

logger = logging.getLogger("harness.trace")

# Module-level trace buffer for session aggregation
_session_traces: list[dict] = []

# Background DB write queue (fire-and-forget, non-blocking)
_write_queue: list[dict] = []


def _emit_trace(event: dict) -> None:
    """Emit a structured trace event.

    Always: append to session buffer + stdout JSONL.
    Background: queue for PostgreSQL write (non-blocking).
    """
    _session_traces.append(event)
    _write_queue.append(event)
    logger.info(json.dumps(event, ensure_ascii=False, default=str))


async def flush_traces_to_db(session_id: str = "") -> int:
    """Write queued traces to PostgreSQL harness_traces table.

    Called at end of request (non-blocking). Returns number of traces written.
    """
    if not _write_queue:
        return 0

    backend = HARNESS_CONFIG.get("observability", {}).get("metrics_backend", "stdout")
    if backend != "postgres":
        _write_queue.clear()
        return 0

    uri = os.getenv("POSTGRES_URI")
    if not uri:
        _write_queue.clear()
        return 0

    traces = list(_write_queue)
    _write_queue.clear()

    try:
        from psycopg import AsyncConnection
        conn = await AsyncConnection.connect(uri)

        for event in traces:
            await conn.execute("""
                INSERT INTO harness_traces (
                    session_id, node_name, timestamp, status,
                    duration_ms, history_tag, diagnosis_status,
                    symptoms, error, metadata
                ) VALUES (
                    %(session_id)s, %(node_name)s, %(timestamp)s, %(status)s,
                    %(duration_ms)s, %(history_tag)s, %(diagnosis_status)s,
                    %(symptoms)s, %(error)s, %(metadata)s
                )
            """, {
                "session_id": session_id or "unknown",
                "node_name": event.get("node_name", ""),
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "status": event.get("status", "ok"),
                "duration_ms": event.get("duration_ms"),
                "history_tag": event.get("history_tag", ""),
                "diagnosis_status": event.get("diagnosis_status"),
                "symptoms": json.dumps(event.get("symptoms"), ensure_ascii=False) if event.get("symptoms") else None,
                "error": event.get("error"),
                "metadata": json.dumps({k: v for k, v in event.items()
                                        if k not in ("node_name", "timestamp", "status", "duration_ms",
                                                      "history_tag", "diagnosis_status", "symptoms", "error")},
                                       ensure_ascii=False, default=str),
            })

        await conn.commit()
        await conn.close()
        return len(traces)

    except Exception as e:
        logger.warning(f"[tracer] DB write failed: {e}")
        return 0


def get_session_traces() -> list[dict]:
    """Return collected traces for the current session (for metrics aggregation)."""
    return list(_session_traces)


def clear_session_traces() -> None:
    """Clear trace buffer (call at session start)."""
    _session_traces.clear()
    _write_queue.clear()


def traced(node_name: str):
    """Decorator that emits structured trace events for any graph node.

    Usage:
        @traced("router")
        async def router(state, config):
            ...

    Zero latency impact — logging is synchronous but non-blocking.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(state, *args, **kwargs):
            if not is_layer_enabled("observability"):
                return await func(state, *args, **kwargs)

            start = datetime.now(timezone.utc)
            event = {
                "node_name": node_name,
                "timestamp": start.isoformat(),
            }

            try:
                result = await func(state, *args, **kwargs)
                duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                event.update({
                    "status": "ok",
                    "duration_ms": round(duration_ms, 1),
                })

                # Extract diagnostic metadata if available
                if isinstance(result, dict):
                    if "history" in result:
                        event["history_tag"] = result["history"][-1] if result["history"] else ""
                    task = result.get("task", {})
                    if task.get("diagnosis_status"):
                        event["diagnosis_status"] = task["diagnosis_status"]
                    if task.get("extracted_symptoms"):
                        event["symptoms"] = task["extracted_symptoms"]

                _emit_trace(event)
                return result

            except Exception as e:
                duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                event.update({
                    "status": "error",
                    "duration_ms": round(duration_ms, 1),
                    "error": str(e),
                })
                _emit_trace(event)
                raise

        return wrapper
    return decorator
