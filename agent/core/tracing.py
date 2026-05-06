"""OpenTelemetry tracing configuration.

Default: ConsoleSpanExporter (collect locally, don't ship to backend).
Future: 設 OTEL_EXPORTER_OTLP_ENDPOINT 環境變數即可切到 OTLP（Cloud Trace / Datadog）。

Spans 自動帶上：
- http.method / http.route / http.status_code（FastAPI auto-instrumentation）
- 自訂 attributes：user_id / line_user_id（透過 span.set_attribute 在 webhook handler 加）
"""
from __future__ import annotations

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

logger = logging.getLogger(__name__)
_CONFIGURED = False


def configure_tracing(service_name: str = "smart-lock-agent") -> None:
    """Configure OTel TracerProvider. Idempotent.

    Default exporter: ConsoleSpanExporter (停在本機 stdout)
    若設了 OTEL_EXPORTER_OTLP_ENDPOINT，會自動切到 OTLP（需另外裝 opentelemetry-exporter-otlp）
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            logger.info("otel: using OTLP exporter at %s", otlp_endpoint)
        except ImportError:
            logger.warning(
                "otel: OTLP exporter not installed, falling back to Console"
            )
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        # 開發 / production 預設：ConsoleSpanExporter
        # 注意：Console 會把 span 印到 stdout，可能與業務 log 混雜；
        # 正式 production 建議設 OTEL_EXPORTER_OTLP_ENDPOINT
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _CONFIGURED = True


def instrument_fastapi(app) -> None:
    """Auto-instrument a FastAPI app to capture HTTP spans.

    必須在 app 啟動前（或 first request 前）呼叫一次。
    """
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str | None = None):
    """Get a tracer for manual span creation."""
    return trace.get_tracer(name or __name__)
