# TC-NFR-OBS-01 — request／LLM／worker trace 串接、PII 不外送、dashboard/alert 維度與 recovery

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/core/observability.py`、`api/core/pii_scrub.py`、`agent/lockcore/observability.py`、`agent/lockcore/agent/loop.py`、`agent/lockcore/channels/line_gateway.py`、`agent/lockcore/providers/litellm_provider.py`、`api/realtime/sla_monitor.py`、`api/realtime/config_canary_advance_cron.py`、`api/routers/lifespan_health.py`、`.github/workflows/monitors-health.yml`、`scripts/ops/check_monitors_health.py`、`smartlock-docs/enterprise/25_Monitoring_Spec.md` |
| 優先級 / 路徑類型 | P1 / failure＋recovery |

判定理由：**PII 不外送**這一段機制完整且雙防線——api 與 agent 兩側都以 `_PIIScrubExporter` 包住 OTLP exporter，span 出站前逐屬性過 `scrub_text()`（`api/core/observability.py:76-89`、`agent/lockcore/observability.py:123-139`），agent 側另在 `turn_span()` 進場再遮一層（`agent/lockcore/observability.py:174`），regex 覆蓋 LINE uid 雜湊化、email、電話、身分證、地址、token 參數（`api/core/pii_scrub.py:19-32`）。**trace 面部分實作**——request span 由 `FastAPIInstrumentor` 自動產生（`api/core/observability.py:100`），agent 有 `line.webhook`（`agent/lockcore/channels/line_gateway.py:1195`）與 `agent.turn`（`agent/lockcore/agent/loop.py:1175`）兩個 span；**LLM 呼叫層無 OTel span**（`agent/lockcore/providers/` 中 `span` 零命中，LLM 觀測走另一條 OPIK callback，`agent/lockcore/providers/litellm_provider.py:19-35`）；**背景 worker 無 span**（`api/realtime/` 中 `turn_span`／`start_as_current_span` 零命中）；跨服務 trace context 傳遞（`traceparent`）在 agent → api 的 HTTP 呼叫中零命中。**dashboard/alert 維度與 recovery**——SLA 告警有五類 alert_type 與 recovery 清除（`api/realtime/sla_monitor.py:275-279`），健康頁有彙總 `alert` 布林（`api/routers/lifespan_health.py:135-141`），告警路由 pipeline 定義於 `.github/workflows/monitors-health.yml:66-79`；但 SLO breach 的自動判定為 DEFERRED（`api/realtime/config_canary_advance_cron.py:7-9`），`p95`/`p99` 在 `api/` 中零命中。**實際 trace 是否串得起來、alert 是否顯示正確維度**需執行期，靜態不可得。

**TC 原文**｜章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）｜前置：OTel/PII scrub、故障與高延遲 fixture｜步驟：產生 request/LLM/worker trace、植入 PII、觸發 error/lag/SLO breach｜判定基準：trace 可串接；PII 不外送；dashboard/alert 顯示正確維度與 recovery 狀態｜路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P1｜驗證哪些需求：NFR-Obs-001～005｜旅程：—

---

## 逐條驗收條件對照

| 條件 | 類型 | 程式碼落點 | 狀態 |
|---|---|---|---|
| OTel 接入（api） | 機制存在 | `api/core/observability.py:56-104` | 存在（opt-in，`OTEL_EXPORTER_OTLP_ENDPOINT`） |
| OTel 接入（agent） | 機制存在 | `agent/lockcore/observability.py:102-159` | 存在（同 opt-in） |
| request span | 機制存在 | `api/core/observability.py:100` | 存在（`FastAPIInstrumentor.instrument_app`） |
| webhook span | 機制存在 | `agent/lockcore/channels/line_gateway.py:1193-1196` | 存在（`line.webhook`） |
| agent turn span | 機制存在 | `agent/lockcore/agent/loop.py:1175` | 存在（`agent.turn`，attrs 只放 channel） |
| LLM 呼叫 span | 機制存在 | `agent/lockcore/providers/` | **零命中**（LLM 觀測走 OPIK callback，非 OTel span） |
| worker span | 機制存在 | `api/realtime/` | **零命中** |
| 跨服務 trace context 傳遞 | 機制存在 | `agent/lockcore/channels/line_gateway.py:354`、`:448`、`:532` 等 httpx 呼叫 | **零命中**（無 `traceparent` 注入） |
| PII scrub（出站） | 機制存在 | `api/core/observability.py:76-89`、`agent/lockcore/observability.py:123-139` | 存在（exporter wrapper） |
| PII scrub（進場） | 機制存在 | `agent/lockcore/observability.py:174` | 存在（agent 側雙防線） |
| PII regex 覆蓋 | 機制存在 | `api/core/pii_scrub.py:19-32` | LINE uid／email／電話／身分證／地址／token 六類 |
| health/metrics 不產 span | 機制存在 | `api/core/observability.py:100` | 存在（`excluded_urls`） |
| 可觀測性失敗不癱瘓服務 | 機制存在 | `api/core/observability.py:103-108`、`agent/lockcore/observability.py:156-159` | 存在（降級 no-op + WARNING） |
| error 告警 | 機制存在 | `api/routers/lifespan_health.py:135-141` | 存在（彙總布林 `alert`） |
| lag 告警 | 機制存在 | `api/routers/lifespan_health.py:130` | 存在（`backlog_stalled = oldest > 900`） |
| SLO breach 自動判定 | 機制存在 | `api/realtime/config_canary_advance_cron.py:7-9` | **DEFERRED**（檔內註解自述） |
| 百分位聚合（p95/p99）於 api | 機制存在 | `api/` | **零命中**（`p95` 在 `api/` 無輸出） |
| recovery 狀態 | 機制存在 | `api/realtime/sla_monitor.py:275-279` | 存在（`recovered` 集合差集 + log） |
| 告警路由（PD/Slack） | 機制存在 | `.github/workflows/monitors-health.yml:66-79` | 存在（需 secrets） |
| trace 實際可串接 | 執行期 | — | **無法靜態判定** |
| dashboard 維度正確 | 執行期 | — | **無法靜態判定** |

---

## Event Storming

本案例為非功能需求，無 domain event。改列機制與落點對照：

| Actor | 動作 | 期待機制 | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|
| 客人 | 送 LINE 訊息 | webhook span | `agent/lockcore/channels/line_gateway.py:1195` | `with _turn_span("line.webhook")` |
| Agent | 跑一輪 turn | turn span | `agent/lockcore/agent/loop.py:1175` | `with _turn_span("agent.turn", channel=msg.channel)` |
| Agent | 呼叫 LLM | LLM span | `agent/lockcore/providers/litellm_provider.py:23-35` | 無 OTel span；OPIK callback（`OPIK_API_KEY` 設定時） |
| 前端／技師 App | 打 API | request span | `api/core/observability.py:100` | FastAPI 自動埋點，排除 health/metrics/docs |
| 背景 worker | 跑一輪 | worker span | `api/realtime/*` | **找不到**：無 span 建立點 |
| Exporter | 出站 | PII 遮蔽 | `api/core/observability.py:82-86` | 逐 span 屬性過 `scrub_text` |
| SLA monitor | 偵測逾期 | alert 事件 | `api/realtime/sla_monitor.py:281-292` | 五類 alert 推 `/realtime/sla-alerts` WS 頻道 |
| SLA monitor | 條件解除 | recovery | `api/realtime/sla_monitor.py:275-279` | 差集算 `recovered` 並 log |
| 監控排程 | 每 30 分探測 | 告警可收到 | `.github/workflows/monitors-health.yml:20-22`、`:66-79` | health check fail → `alert_pipeline.sh` |

---

## 逐層走查

### 第 1 層 — api 側 OTel 接入

`api/core/observability.py:1-14`

```python
"""可觀測性基線（SA / CR-0136 / WBS 1.4.1）——OTLP opt-in，未配置＝零行為變化。

設計（ADR-007：SigNoz 系統監控吃 OpenTelemetry OTLP；OPIK Agent LLM Ops 另線）：
  - `OTEL_EXPORTER_OTLP_ENDPOINT` 設定時：啟用 OTel tracer + FastAPI 自動埋點
    （每 request span，含 route/status/latency），OTLP 匯出到 SigNoz collector。
  - 未設定 or otel 套件缺：**no-op**（單機/測試/本機零依賴、行為完全不變）。
  - 匯入/初始化任何失敗＝降級 no-op + WARNING（可觀測性不可癱瘓服務）。
  - **PII scrubbing（25_Monitoring §3 硬性，2026-07-10 架構稽核補）**：span 出站前
    字串屬性一律過 `scrub_text()`——電話/email/地址遮蔽、LINE user id 雜湊化
    （sha256 前 12 碼，保留關聯性不留身分）、token 參數遮蔽。
```

`api/core/observability.py:56-62`

```python
def setup_observability(app, *, service_name: str = "lock-ai-api") -> bool:
    """OTLP endpoint 設定時啟用 OTel + FastAPI 埋點；回是否啟用。絕不 raise。"""
    global _enabled
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        logger.info("observability: OTEL_EXPORTER_OTLP_ENDPOINT 未設 → 停用（單機語意）")
        return False
```

`api/core/observability.py:70-74`（resource 屬性）

```python
        resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", service_name),
            "deployment.environment": os.environ.get("DEPLOY_ENV", "local"),
        })
```

`api/core/observability.py:98-101`

```python
        trace.set_tracer_provider(provider)
        # excluded_urls：health / metrics 不產 span（噪音）
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics,docs,openapi.json,redoc")
        _enabled = True
```

掛載點 `api/main.py:257-259`

```python
from core.observability import setup_observability  # noqa: E402
setup_observability(app)
```

### 第 2 層 — PII scrub 的兩層防線

api 出站遮蔽，`api/core/observability.py:76-89`

```python
        class _PIIScrubExporter(SpanExporter):
            """出站前遮蔽（25_Monitoring §3 硬性）：包裝 OTLP exporter，
            每個 span 的字串屬性過 scrub_text 後才交棒。"""

            def __init__(self, inner: SpanExporter) -> None:
                self._inner = inner

            def export(self, spans) -> SpanExportResult:
                for span in spans:
                    _scrub_span_attributes(span)
                return self._inner.export(spans)
```

屬性遍歷，`api/core/observability.py:33-51`（str 過 `scrub_text`；tuple/list 逐成員遮蔽；整段包 `try/except` 且註記「遮蔽失敗不可癱瘓匯出」）。

regex 清單，`api/core/pii_scrub.py:19-32`

```python
_LINE_UID_RE = re.compile(r"\bU[0-9a-f]{32}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
...
_NATIONAL_ID_RE = re.compile(r"\b[A-Z][12]\d{8}\b")
_ADDR_RE = re.compile(
...
_TOKEN_PARAM_RE = re.compile(r"((?:access_|refresh_)?token=)[^&\s]+")
```

agent 側同型 exporter，`agent/lockcore/observability.py:123-139`；agent 側 regex 為 `agent/lockcore/observability.py:31-44`（無 `_NATIONAL_ID_RE`，其餘五類相同，`:39` 檔內自述「複製自 api/core/observability.py」）。

agent 側進場遮蔽，`agent/lockcore/observability.py:162-176`

```python
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
```

LINE uid 的處理為雜湊而非直接遮除，`agent/lockcore/observability.py:47-48`

```python
def _hash_line_uid(m: re.Match) -> str:
    return "U#" + hashlib.sha256(m.group(0).encode()).hexdigest()[:12]
```

`agent/lockcore/observability.py:10-11` 說明用意：「LINE user id 雜湊化(sha256 前 12 碼,保留關聯性不留身分)」。

### 第 3 層 — 現有 span 的範圍

```
grep -rn "turn_span\|_turn_span\|start_as_current_span" --include=*.py api/realtime/ agent/lockcore/
agent/lockcore/agent/loop.py:67, :70, :1172-1175
agent/lockcore/channels/line_gateway.py:36, :40, :1194-1195
agent/lockcore/observability.py:5, :11, :85, :162, :171, :174
（api/realtime/ 無輸出）
```

`agent/lockcore/agent/loop.py:1171-1175`

```python
        _turn_span=nullcontext,零行為變化)。attrs 只放 channel,不放 sender_id
        原值(PII);字串屬性另由 turn_span 進場遮蔽 + exporter 出站遮蔽雙防線。
        """
        with _turn_span("agent.turn", channel=msg.channel):
```

`agent/lockcore/channels/line_gateway.py:1192-1196`

```python
    async def callback(request):
        # CR-0156/ADR-007:每個 webhook 請求包 "line.webhook" span
        # (observability 未啟用時 _turn_span=nullcontext,零行為變化)。
        with _turn_span("line.webhook"):
            return await _handle_callback(request)
```

`api/realtime/`（11 支背景 worker／cron）中無任何 span 建立點。

### 第 4 層 — LLM 觀測的另一條線

`agent/lockcore/providers/litellm_provider.py:19-35`

```python
# CR-0156/ADR-007:OPIK LLM 追蹤只掛一次(process 級 litellm callback)
_OPIK_WIRED = False


def _maybe_enable_opik() -> None:
    """OPIK_API_KEY 設定時掛 OPIK LLM call 追蹤(CR-0156/ADR-007);未設=零行為變化。

    接法採 litellm 字串 callback(`litellm.callbacks += ["opik"]`)——OPIK 官方
    ...
    此處選字串法,由 litellm 內建 OpikLogger 讀 OPIK_API_KEY / OPIK_* env 上報,
    不確定 opik SDK 版本細節時最穩)。opik 套件缺=安靜略過 + WARNING;
```

`api/core/observability.py:3` 亦記載此分工：「ADR-007：SigNoz 系統監控吃 OpenTelemetry OTLP；OPIK Agent LLM Ops 另線」。

TC 步驟寫「產生 request/LLM/worker trace」且判定基準為「trace 可串接」／程式碼中 LLM 觀測與 request/turn trace 分屬兩個後端（OPIK 與 SigNoz），LLM 呼叫不產生 OTel span、無共同 trace_id。此處僅並陳，不裁定。

### 第 5 層 — 跨服務 trace context

```
grep -rn "traceparent\|propagat\|inject(" --include=*.py api/ agent/
（命中皆為業務語意的 propagate_to_sop_feedback_* 與 error propagate 註解，無 OTel context 傳遞）
```

agent → api 的 HTTP 呼叫點（`agent/lockcore/channels/line_gateway.py:354`、`:448`、`:532`、`:898`、`:940`）皆以 `httpx.AsyncClient(timeout=...)` 建立，headers 只帶 `_bridge_auth_headers(token)`（`agent/lockcore/channels/line_gateway.py:90-94`），無 `traceparent`。

### 第 6 層 — alert 維度與 recovery

SLA 告警的五類 alert_type，`api/realtime/sla_monitor.py:3-5`

```
對應 docs/02-design/specs/asyncapi.yaml /realtime/sla-alerts。

五類 alert_type（原 spec 四類 + CR-0129 audit_overdue）：
```

各類的產生點：`quote_expiring`（`:151`）、`dispatch_delay`（`:174`）、`response_overdue`（`:210`）、`arrival_overdue`（`:237`）、`audit_overdue`（`:264`）。

去重與 recovery，`api/realtime/sla_monitor.py:20`（`in-memory _alerted dict[(alert_type, target_id)] 防止重複告警`）、`:275-279`

```python
        # 從 _alerted 移除已恢復（不再符合條件）的告警
        recovered = self._alerted - active_keys
        if recovered:
            logger.info("SLA recovered: %d alerts cleared", len(recovered))
        self._alerted = active_keys
```

推播 `api/realtime/sla_monitor.py:287-293`（`hub.publish("/realtime/sla-alerts", {"type": "sla.alert", "payload": alert})`）。

健康頁的彙總 alert，`api/routers/lifespan_health.py:134-141`

```python
    # 告警旗標：讓監控只需盯一個布林，不必自己組合條件
    alert = (
        not all_running
        or bool(outbox.get("needs_manual_replay"))
        or bool(outbox.get("backlog_stalled"))
        or "error" in outbox
    )
```

每個 monitor 的狀態維度，`api/routers/lifespan_health.py:38-54`（`not_started` / `stopping` / `crashed` / `running`，附 `interval_seconds` / `task_started` / `task_done` / `stopping_signal`）。

告警路由，`.github/workflows/monitors-health.yml:66-79`（PagerDuty routing key + Slack webhook + `#ops-alerts` / `#ops-info` 兩個頻道）；`scripts/ops/check_monitors_health.py:10-16` 的 exit code 0/1/2。

### 第 7 層 — SLO breach 判定

`api/realtime/config_canary_advance_cron.py:1-9`

```python
"""M18 Phase II — canary rollout 自動 stage advance cron。

解凍 `config_m18_service._advance_canary_stage`（已從 [DEFERRED]
stub 升級為真實實作）。每 5 分鐘掃所有 `current_stage IN ('5%','50%')
AND next_stage_eta < NOW` 的 config_rollout → 呼 service helper 推進。

SLO halt（觀察 SLO 指標決定 rollback）仍 DEFERRED — 涉 metrics
collection + threshold 判斷，本輪只解 stage advance 缺口。
"""
```

`smartlock-docs/enterprise/05_NFR.md:146`（NFR-Obs-005）記載「canary 10% ≥ 10min → 50% ≥ 10min → 100%；每段卡 SLO（error rate / p99）超 baseline 自動 halt」／`api/realtime/config_canary_advance_cron.py:4` 掃描的 stage 為 `('5%','50%')`。此處僅並陳，不裁定。

百分位聚合，`grep -n "p95" -- api` 無輸出；`api/core/observability.py` 只有 span 匯出與屬性清洗（函式清單為 `_scrub_span_attributes` / `observability_enabled` / `setup_observability`）。api 端唯一的百分位實作在 `api/realtime/line_push_outbox_worker.py:59-78`（outbox lag，見 TC-PERF-05）。

`smartlock-docs/enterprise/25_Monitoring_Spec.md:78-90` 定義九條 SLO（SLO-1～SLO-9），`:97` 定義 burn rate 三層告警，`:105` 定義 Warning 分層與回應時限。這些為文件定義；`api/` 與 `agent/` 中無對應的 SLO 常數或 burn-rate 計算。

### 第 8 層 — 可觀測性失效的降級

`api/core/observability.py:103-108`

```python
    except ImportError:
        logger.warning("observability: opentelemetry 套件未安裝（pip install '.[otel]'）→ 停用")
        return False
    except Exception:  # noqa: BLE001 — 可觀測性初始化失敗不可癱瘓服務
        logger.exception("observability: OTel 初始化失敗 → 降級停用")
        return False
```

`agent/lockcore/observability.py:156-159` 為同型。agent 側 import 失敗時的替身，`agent/lockcore/channels/line_gateway.py:35-42`

```python
try:
    from lockcore.observability import turn_span as _turn_span
except Exception:  # noqa: BLE001 — 防禦:可觀測性缺失不可影響 webhook 主流程
    from contextlib import nullcontext

    def _turn_span(name: str, **attrs: Any):  # type: ignore[misc]
        return nullcontext()
```

---

## 既有測試證據

本次於本機 Docker 測試庫實跑（Windows 需 `-p winloop_plugin`）：

```
cd api && python -m pytest tests/test_cr_0136_observability.py -q -p winloop_plugin
3 passed in 0.59s

cd api && python -m pytest tests/test_observability_pii_scrub.py -q -p winloop_plugin
9 passed in 0.24s

cd api && python -m pytest tests/test_cr_0166_pii_scrub.py -q -p winloop_plugin
6 passed in 0.26s

cd api && python -m pytest tests/test_sla_monitor.py -q -p winloop_plugin
3 passed in 0.91s

cd api && python -m pytest tests/test_lifespan_health.py -q -p winloop_plugin
（併於本批 38 項合跑，全數通過）

cd agent && python -m pytest tests/test_observability.py -q -p winloop_plugin
11 passed in 3.31s
```

合計 32 項通過。這些為純函式與結構層測試（scrub regex、span 屬性遮蔽、monitor 狀態推導），不產生跨服務 trace，也不驗證 dashboard 顯示。

`api/tests/` 與 `agent/tests/` 中無「高延遲 fixture」或「SLO breach 觸發」的測試檔。

---

## 事實結論

1. OTel 接入在 api 與 agent 兩側皆為 opt-in（`OTEL_EXPORTER_OTLP_ENDPOINT`），未設定即 no-op；初始化失敗降級為 no-op 並記 WARNING/EXCEPTION。
2. PII 遮蔽為 exporter wrapper 形式（`api/core/observability.py:76-89`、`agent/lockcore/observability.py:123-139`），agent 側另在 `turn_span()` 進場再遮一層（`agent/lockcore/observability.py:174`）。
3. PII regex 在 api 側涵蓋六類（LINE uid、email、電話、身分證、地址、token 參數，`api/core/pii_scrub.py:19-32`），agent 側五類（無身分證，`agent/lockcore/observability.py:31-44`）。LINE uid 為 sha256 前 12 碼雜湊而非全遮。
4. 現存 OTel span 共三種：FastAPI 自動 request span（排除 health/metrics/docs/openapi.json/redoc）、`line.webhook`、`agent.turn`。
5. LLM 呼叫無 OTel span；LLM 觀測走 `litellm.callbacks += ["opik"]` 上報 OPIK（`agent/lockcore/providers/litellm_provider.py:23-35`），與 SigNoz 為兩條獨立線（`api/core/observability.py:3`）。
6. `api/realtime/` 的 11 支背景 worker／cron 中無 span 建立點。
7. agent → api 的 HTTP 呼叫未注入 `traceparent`；`traceparent` 在 `api/`、`agent/` 中零命中。
8. alert 維度：SLA monitor 五類 alert_type + `(alert_type, target_id)` 去重 + `recovered` 差集清除（`api/realtime/sla_monitor.py:275-279`）；健康頁四種 monitor 狀態 + 一個彙總 `alert` 布林（`api/routers/lifespan_health.py:38-54`、`:135-141`）。
9. SLO breach 的自動判定與 halt 為 DEFERRED（`api/realtime/config_canary_advance_cron.py:7-9`）；`p95` 在 `api/` 中零命中；api 端唯一的百分位實作為 outbox lag（`api/realtime/line_push_outbox_worker.py:59-78`）。
10. `smartlock-docs/enterprise/25_Monitoring_Spec.md:78-90` 的九條 SLO 與 `:97` 的 burn rate 三層告警為文件定義，程式碼中無對應常數或計算。
11. 告警管道定義於 `.github/workflows/monitors-health.yml:66-79`（PagerDuty + Slack 兩頻道），需 secrets 才執行。
12. 「trace 是否實際串接」「dashboard/alert 是否顯示正確維度」需執行期與外部監控服務，本次未取得。
