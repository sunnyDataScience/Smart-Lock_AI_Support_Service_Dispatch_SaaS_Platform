"""可觀測性基線（CR-0156 / ADR-007 補課）——OTLP opt-in，未配置＝零行為變化。

照 `api/core/observability.py` 範式（CR-0136）移植到 knowledge-refinery：
  - `OTEL_EXPORTER_OTLP_ENDPOINT` 設定時：啟用 OTel tracer + FastAPI 自動埋點
    （每 request span，含 route/status/latency），OTLP 匯出到 SigNoz collector。
  - 未設定 or otel 套件缺：**no-op**（單機/測試/本機零依賴、行為完全不變）。
  - 匯入/初始化任何失敗＝降級 no-op + WARNING（可觀測性不可癱瘓服務）。
  - **PII scrubbing（25_Monitoring §3 硬性）**：span 出站前字串屬性一律過
    `scrub_text()`——電話/email/地址遮蔽、LINE user id 雜湊化（sha256 前 12 碼，
    保留關聯性不留身分）、token 參數遮蔽。

依賴 opentelemetry-* 為 optional（refinery pyproject `[otel]` extra）；未裝時安靜略過。
"""

from __future__ import annotations

import hashlib
import logging
import os
import re

logger = logging.getLogger("refinery.observability")

_enabled = False

# ── PII scrubbing（純函式，無 otel 依賴，可單測）─────────────────────────────
# 順序有意義：LINE uid 先於 token（U 開頭 33 字元）；電話先於地址（門牌數字）。
_LINE_UID_RE = re.compile(r"\bU[0-9a-f]{32}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 台灣手機（09xxxxxxxx / +8869xxxxxxxx，容忍 - 或空白分隔）與市話（0x-xxxxxxxx）
_PHONE_RE = re.compile(
    r"(?:\+886[-\s]?9\d{2}|09\d{2})[-\s]?\d{3}[-\s]?\d{3}"
    r"|\b0\d{1,2}-\d{6,8}\b"
)
# 台灣地址啟發式：縣市 …（區鄉鎮）… 路/街/大道/巷/弄 … 號（保守，寧漏勿誤殺）
_ADDR_RE = re.compile(
    r"\S{1,6}[縣市]\S{0,12}?[區鄉鎮市]?\S{0,20}?(?:路|街|大道|巷|弄)[\S]{0,12}?號?"
)
# URL query 內的憑證參數（FastAPI 埋點的 http.url/http.target 可能帶）
_TOKEN_PARAM_RE = re.compile(r"((?:access_|refresh_)?token=)[^&\s]+")


def _hash_line_uid(m: re.Match) -> str:
    return "U#" + hashlib.sha256(m.group(0).encode()).hexdigest()[:12]


def scrub_text(value: str) -> str:
    """遮蔽字串中的 PII（25_Monitoring §3）：LINE uid 雜湊化、電話/email/地址/
    token 以占位符取代。非 PII 內容原樣保留。"""
    value = _LINE_UID_RE.sub(_hash_line_uid, value)
    value = _TOKEN_PARAM_RE.sub(r"\1[TOKEN]", value)
    value = _EMAIL_RE.sub("[EMAIL]", value)
    value = _PHONE_RE.sub("[PHONE]", value)
    value = _ADDR_RE.sub("[ADDR]", value)
    return value


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


def setup_observability(app, *, service_name: str = "knowledge-refinery") -> bool:
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
        # excluded_urls：health / docs 不產 span（噪音）
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
