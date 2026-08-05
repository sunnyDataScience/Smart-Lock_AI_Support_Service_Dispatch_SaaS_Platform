"""可觀測性基線(CR-0156 / ADR-007 補課)——OTLP opt-in,未配置=零行為變化。

照抄 api/core/observability.py 範式(SigNoz 系統監控吃 OpenTelemetry OTLP):
  - `OTEL_EXPORTER_OTLP_ENDPOINT` 設定時:啟用 OTel TracerProvider + OTLP exporter,
    提供 `turn_span()` 給 agent turn / LINE webhook 每請求埋點。
  - 未設定 or otel 套件缺:**no-op**(單機/測試/本機零依賴、行為完全不變)。
  - 匯入/初始化任何失敗=降級 no-op + WARNING(可觀測性不可癱瘓服務)。
  - **PII scrubbing(25_Monitoring §3 硬性)**:span 出站前字串屬性一律過
    `scrub_text()`——電話/email/地址遮蔽、LINE user id 雜湊化(sha256 前 12 碼,
    保留關聯性不留身分)、token 參數遮蔽。agent 面 span 屬性常含 LINE uid,
    雜湊化最關鍵;`turn_span()` 進場屬性也先遮一層(雙重防線)。

依賴 opentelemetry-* 為 optional(agent pyproject `[otel]` extra);未裝時安靜略過。
"""

from __future__ import annotations

import hashlib
import os
import re
from contextlib import nullcontext
from typing import Any

from loguru import logger

_initialized = False
_enabled = False
_tracer: Any = None

# ── PII scrubbing(純函式,無 otel 依賴,可單測;複製自 api/core/observability.py)──
# 順序有意義:LINE uid 先於 token(U 開頭 33 字元);電話先於地址(門牌數字)。
_LINE_UID_RE = re.compile(r"\bU[0-9a-f]{32}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 台灣身分證字號（CR-0209 TC-NFR-OBS-01 補漏）。
# api 側的 pii_scrub.py:27 一直有這條，agent 側**漏了** —— 而 agent 才是直接
# 面對客人自由輸入的那一端（客人在 LINE 打身分證字號辦保固並不罕見），
# 少了它等於 trace 裡會留下明碼身分證。順序放在 email/phone 之前：
# 身分證形狀（1 英文 + 9 數字）不會與其他 regex 衝突，先遮先安全。
_NATIONAL_ID_RE = re.compile(r"\b[A-Z][12]\d{8}\b")
# 台灣手機(09xxxxxxxx / +8869xxxxxxxx,容忍 - 或空白分隔)與市話(0x-xxxxxxxx)
_PHONE_RE = re.compile(
    r"(?:\+886[-\s]?9\d{2}|09\d{2})[-\s]?\d{3}[-\s]?\d{3}"
    r"|\b0\d{1,2}-\d{6,8}\b"
)
# 台灣地址啟發式:縣市 …(區鄉鎮)… 路/街/大道/巷/弄 … 號(保守,寧漏勿誤殺)
_ADDR_RE = re.compile(
    r"\S{1,6}[縣市]\S{0,12}?[區鄉鎮市]?\S{0,20}?(?:路|街|大道|巷|弄)[\S]{0,12}?號?"
)
# URL query 內的憑證參數(span 屬性可能帶 http.url/http.target 類字串)
_TOKEN_PARAM_RE = re.compile(r"((?:access_|refresh_)?token=)[^&\s]+")


def _hash_line_uid(m: re.Match) -> str:
    return "U#" + hashlib.sha256(m.group(0).encode()).hexdigest()[:12]


def scrub_text(value: str) -> str:
    """遮蔽字串中的 PII(25_Monitoring §3):LINE uid 雜湊化、電話/email/地址/
    token 以占位符取代。非 PII 內容原樣保留。"""
    value = _LINE_UID_RE.sub(_hash_line_uid, value)
    value = _TOKEN_PARAM_RE.sub(r"\1[TOKEN]", value)
    value = _NATIONAL_ID_RE.sub("[ID]", value)
    value = _EMAIL_RE.sub("[EMAIL]", value)
    value = _PHONE_RE.sub("[PHONE]", value)
    value = _ADDR_RE.sub("[ADDR]", value)
    return value


def _scrub_span_attributes(span: Any) -> None:
    """就地遮蔽單一 ReadableSpan 的字串屬性(含 str tuple 成員)。絕不 raise。"""
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
        logger.exception("observability: span PII 遮蔽失敗(span 照出,屬性未改)")


def _scrub_attributes(attrs: dict[str, Any]) -> dict[str, Any]:
    """遮蔽 turn_span 進場屬性(建新 dict,不改原物件):str 過 scrub_text、
    數值/布林原樣、其他型別 str() 後再遮(寧保守勿外洩)。"""
    out: dict[str, Any] = {}
    for k, v in attrs.items():
        if isinstance(v, str):
            out[k] = scrub_text(v)
        elif isinstance(v, (bool, int, float)):
            out[k] = v
        else:
            out[k] = scrub_text(str(v))
    return out


def observability_enabled() -> bool:
    return _enabled


def setup_observability(*, service_name: str = "lock-cs-agent") -> bool:
    """OTLP endpoint 設定時啟用 OTel tracer;回是否啟用。冪等、絕不 raise。"""
    global _initialized, _enabled, _tracer
    if _initialized:
        return _enabled
    _initialized = True
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        logger.info("observability: OTEL_EXPORTER_OTLP_ENDPOINT 未設 → 停用(單機語意)")
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            SpanExporter,
            SpanExportResult,
        )

        class _PIIScrubExporter(SpanExporter):
            """出站前遮蔽(25_Monitoring §3 硬性):包裝 OTLP exporter,
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

        resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", service_name),
            "deployment.environment": os.environ.get("DEPLOY_ENV", "local"),
        })
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(_PIIScrubExporter(OTLPSpanExporter(endpoint=endpoint)))
        )
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("lockcore")
        _enabled = True
        logger.info("observability: OTel OTLP 啟用 → {}(SigNoz collector)", endpoint)
        return True
    except ImportError:
        logger.warning("observability: opentelemetry 套件未安裝(pip install '.[otel]')→ 停用")
        return False
    except Exception:  # noqa: BLE001 — 可觀測性初始化失敗不可癱瘓服務
        logger.exception("observability: OTel 初始化失敗 → 降級停用")
        return False


def turn_span(name: str, **attrs: Any):
    """回傳 span context manager(sync `with` 於 async 函式內亦可用)。

    - observability 未啟用(env 未設/套件缺/初始化失敗)→ `nullcontext()`,零行為變化。
    - 啟用時 → OTel current span;進場屬性先過 `_scrub_attributes`(出站 exporter
      再遮一層,雙重防線)。絕不 raise。
    """
    if not _initialized:
        setup_observability()
    if not _enabled or _tracer is None:
        return nullcontext()
    try:
        return _tracer.start_as_current_span(name, attributes=_scrub_attributes(attrs))
    except Exception:  # noqa: BLE001 — 建 span 失敗不可癱瘓主流程
        logger.warning("observability: 建立 span 失敗 → 本次降級 no-op")
        return nullcontext()


def inject_trace_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """把目前 span 的 W3C traceparent 注入 headers（CR-0209 TC-NFR-OBS-01）。

    為什麼需要：agent 有 `line.webhook` / `agent.turn` 兩個 span，api 有
    FastAPI 自動埋點，但**兩邊的 trace 是斷開的**——agent 打給 api 的 httpx
    請求沒帶 traceparent，所以 SigNoz 上看到的是兩棵互不相關的樹。
    一則客人訊息從 webhook 進來、轉發到 api 建卡、再由 worker 推播出去，
    這條鏈在 trace 上完全串不起來，出事時只能靠時間戳猜。

    未啟用 observability（env 未設／套件缺）時原樣回傳，零行為變化、絕不 raise。
    """
    out = dict(headers or {})
    if not _enabled:
        return out
    try:
        from opentelemetry.propagate import inject
        inject(out)
    except Exception:  # noqa: BLE001 — trace 傳播失敗不可影響主流程
        pass
    return out
