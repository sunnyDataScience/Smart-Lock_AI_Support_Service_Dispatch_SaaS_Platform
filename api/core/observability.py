"""可觀測性基線（SA / CR-0136 / WBS 1.4.1）——OTLP opt-in，未配置＝零行為變化。

設計（ADR-007：SigNoz 系統監控吃 OpenTelemetry OTLP；OPIK Agent LLM Ops 另線）：
  - `OTEL_EXPORTER_OTLP_ENDPOINT` 設定時：啟用 OTel tracer + FastAPI 自動埋點
    （每 request span，含 route/status/latency），OTLP 匯出到 SigNoz collector。
  - 未設定 or otel 套件缺：**no-op**（單機/測試/本機零依賴、行為完全不變）。
  - 匯入/初始化任何失敗＝降級 no-op + WARNING（可觀測性不可癱瘓服務）。

依賴 opentelemetry-* 為 optional（api pyproject `[otel]` extra）；未裝時安靜略過。
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("api.observability")

_enabled = False


def observability_enabled() -> bool:
    return _enabled


def setup_observability(app, *, service_name: str = "lock-ai-api") -> bool:
    """OTLP endpoint 設定時啟用 OTel + FastAPI 埋點；回是否啟用。絕不 raise。"""
    global _enabled
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        logger.info("observability: OTEL_EXPORTER_OTLP_ENDPOINT 未設 → 停用（單機語意）")
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", service_name),
            "deployment.environment": os.environ.get("DEPLOY_ENV", "local"),
        })
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        # excluded_urls：health / metrics 不產 span（噪音）
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics,docs,openapi.json,redoc")
        _enabled = True
        logger.info("observability: OTel OTLP 啟用 → %s（SigNoz collector）", endpoint)
        return True
    except ImportError:
        logger.warning("observability: opentelemetry 套件未安裝（pip install '.[otel]'）→ 停用")
        return False
    except Exception:  # noqa: BLE001 — 可觀測性初始化失敗不可癱瘓服務
        logger.exception("observability: OTel 初始化失敗 → 降級停用")
        return False
