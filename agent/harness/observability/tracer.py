"""Structured trace emitter for graph nodes.

Emits JSON-structured trace events for every decorated node.
Phase 0-1: stdout (JSONL). Phase 2: PostgreSQL harness_traces table.
"""

import functools
import json
import logging
from datetime import datetime, timezone

from harness import is_layer_enabled

logger = logging.getLogger("harness.trace")

# Module-level trace buffer for session aggregation
_session_traces: list[dict] = []


def _emit_trace(event: dict) -> None:
    """Emit a structured trace event.

    Phase 0-1: stdout JSONL (append to session buffer for metrics).
    Phase 2: async write to PostgreSQL harness_traces table.
    """
    _session_traces.append(event)
    logger.info(json.dumps(event, ensure_ascii=False, default=str))


def get_session_traces() -> list[dict]:
    """Return collected traces for the current session (for metrics aggregation)."""
    return list(_session_traces)


def clear_session_traces() -> None:
    """Clear trace buffer (call at session start)."""
    _session_traces.clear()


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
