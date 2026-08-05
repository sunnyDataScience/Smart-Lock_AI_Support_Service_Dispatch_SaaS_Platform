"""可觀測性基線（SA / CR-0136 / WBS 1.4.1）——OTLP opt-in，未配置＝零行為變化。

設計（ADR-007：SigNoz 系統監控吃 OpenTelemetry OTLP；OPIK Agent LLM Ops 另線）：
  - `OTEL_EXPORTER_OTLP_ENDPOINT` 設定時：啟用 OTel tracer + FastAPI 自動埋點
    （每 request span，含 route/status/latency），OTLP 匯出到 SigNoz collector。
  - 未設定 or otel 套件缺：**no-op**（單機/測試/本機零依賴、行為完全不變）。
  - 匯入/初始化任何失敗＝降級 no-op + WARNING（可觀測性不可癱瘓服務）。
  - **PII scrubbing（25_Monitoring §3 硬性，2026-07-10 架構稽核補）**：span 出站前
    字串屬性一律過 `scrub_text()`——電話/email/地址遮蔽、LINE user id 雜湊化
    （sha256 前 12 碼，保留關聯性不留身分）、token 參數遮蔽。

依賴 opentelemetry-* 為 optional（api pyproject `[otel]` extra）；未裝時安靜略過。
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("api.observability")

_enabled = False
_tracer: object | None = None

# ── PII scrubbing ─────────────────────────────────────────────────────────
# CR-0166 R1-8：regex 與 scrub_text 昇格至 core/pii_scrub.py（共用），此處 re-export
# 保持既有 import 相容（OTel span 遮蔽仍用全遮蔽版 scrub_text）。
from contextlib import nullcontext
from typing import Any

from core.pii_scrub import scrub_text  # noqa: E402,F401 — re-export 相容


def _scrub_span_attributes(span) -> None:
    """就地遮蔽單一 ReadableSpan 的字串屬性（含 str tuple 成員）。絕不 raise。"""
    try:
        attrs = getattr(span, "_attributes", None)
        if not attrs:
            return
        target = getattr(attrs, "_dict", attrs)  # BoundedAttributes 內部 dict 或 plain dict
        for k in list(target.keys()):
            v = target[k]
            if isinstance(v, str):
                nv = scrub_text(v)
                if nv != v:
                    target[k] = nv
            elif isinstance(v, (tuple, list)):
                if any(isinstance(i, str) for i in v):
                    target[k] = type(v)(
                        scrub_text(i) if isinstance(i, str) else i for i in v
                    )
    except Exception:  # noqa: BLE001 — 遮蔽失敗不可癱瘓匯出
        logger.exception("observability: span PII 遮蔽失敗（span 照出，屬性未改）")


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
        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

        class _PIIScrubExporter(SpanExporter):
            """出站前遮蔽（25_Monitoring §3 硬性）：包裝 OTLP exporter，
            每個 span 的字串屬性過 scrub_text 後才交棒。"""

            def __init__(self, inner: SpanExporter) -> None:
                self._inner = inner

            def export(self, spans) -> SpanExportResult:
                for span in spans:
                    _scrub_span_attributes(span)
                return self._inner.export(spans)

            def shutdown(self) -> None:
                self._inner.shutdown()

            def force_flush(self, timeout_millis: int = 30_000) -> bool:
                return self._inner.force_flush(timeout_millis)

        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(_PIIScrubExporter(OTLPSpanExporter(endpoint=endpoint)))
        )
        trace.set_tracer_provider(provider)
        global _tracer
        _tracer = trace.get_tracer(__name__)
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


# ── 背景 job 的 span（CR-0209 TC-NFR-OBS-01）──────────────────────────────
#
# FastAPIInstrumentor 只涵蓋 **HTTP 請求**。`api/realtime/` 的 11 支 worker/cron
# 是 lifespan 起的背景迴圈，完全在 HTTP 之外 —— 此前全樹零 span，
# 也就是「結算沒跑出來」「推播卡住」這類問題在 trace 上完全看不到。
#
# 設計與 agent 側的 `turn_span` 對齊（同樣的 nullcontext 降級、同樣絕不 raise）：
# 未啟用 observability 時回 nullcontext，零行為變化、零效能成本。
def job_span(name: str, **attrs: Any):
    """背景 job 的 span context manager。未啟用時回 nullcontext，絕不 raise。

    用法（每支 worker/cron 的入口）：
        async def run_once(self):
            with job_span("cron.auto_confirm"):
                ...
    """
    if not _enabled or _tracer is None:
        return nullcontext()
    try:
        clean = {k: (scrub_text(v) if isinstance(v, str) else v) for k, v in attrs.items()}
        return _tracer.start_as_current_span(name, attributes=clean)
    except Exception:  # noqa: BLE001 — 建 span 失敗不可癱瘓背景 job
        logger.warning("observability: 建立 job span 失敗 → 本次降級 no-op")
        return nullcontext()
