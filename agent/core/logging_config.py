"""Structured logging configuration via structlog.

Use:
    from core.logging_config import get_logger

    log = get_logger(__name__)
    log.info("event_name", user_id=uid, skill="ts-door-stuck")

Production rendering: JSON (Cloud Run friendly + Cloud Logging auto-parse)
Local dev rendering: ConsoleRenderer (colored + readable)

Switchable via env LOG_FORMAT={json,console}; defaults based on ENV={production,*}.
"""
from __future__ import annotations

import logging
import os
import sys

import structlog

# Idempotency guard — configure_logging() can be safely called multiple times.
_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog + stdlib logging.

    Idempotent — safe to call multiple times. Subsequent calls are no-ops.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_format = os.getenv(
        "LOG_FORMAT",
        "json" if os.getenv("ENV") == "production" else "console",
    )

    # stdlib logging baseline (so libraries' loggers route through the same stream)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,  # pull ContextVar-bound fields
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger. Caller can `.bind(user_id=...)` for request context."""
    return structlog.get_logger(name)


# Module-level convenience helpers for ContextVar-based request context
def bind_request_context(**kwargs) -> None:
    """Bind request-scoped fields (user_id, request_id, tenant_id, etc.)
    to contextvars; picked up by all subsequent log calls in this async context.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_request_context() -> None:
    """Clear request-scoped contextvars (e.g. at the end of a request)."""
    structlog.contextvars.clear_contextvars()


# Auto-configure on first import — keeps app.py untouched (avoids merge conflicts
# with concurrent PRs touching app.py, e.g. RP1.D.5 health endpoint).
# Idempotent: safe even if downstream code calls configure_logging() again.
configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
