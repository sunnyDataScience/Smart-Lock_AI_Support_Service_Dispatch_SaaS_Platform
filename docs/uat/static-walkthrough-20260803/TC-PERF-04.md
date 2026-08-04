# TC-PERF-04 — 500 併發 ramp-up 負向：429／罐頭回覆降級，無雪崩

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/config.toml`、`api/core/config.py`、`api/core/errors.py`、`api/services/technician_kyc_service.py`、`api/services/brand_application_service.py`、`api/main.py`、`agent/config.toml`、`agent/lockcore/app_config.py`、`agent/lockcore/providers/fallback_provider.py`、`agent/lockcore/providers/litellm_provider.py`、`agent/lockcore/channels/line_gateway.py`、`loadtest/` |
| 優先級 / 路徑類型 | P1 / ⚠ 未標註 |

判定理由：三個機制中兩個部分存在、一個數值面不可判定。**429**：`RATE_LIMITED → 429` 的錯誤碼映射存在（`api/core/errors.py:54`、`:66`），但全域限流開關為 `enabled = false`（`api/config.toml:40`，註記「僅回 header 不真擋」），實際會 raise 429 的只有兩處 per-IP in-memory 桶（`api/services/technician_kyc_service.py:86`、`api/services/brand_application_service.py:165`），皆非 V2 派工／工單端點。**罐頭回覆降級**：機制存在且測試覆蓋（`agent/lockcore/channels/line_gateway.py:56`、`:1005-1007`）。**無雪崩**：熔斷器實作存在（`agent/lockcore/providers/fallback_provider.py:14-15`、`:166-167`），但其啟用條件 `fallback_models` 在 `agent/config.toml:16` 為空陣列，`agent/lockcore/app_config.py:142-143` 於空值時直接回主 provider（不包 FallbackProvider）；API 端無熔斷器、無佇列上限。「500 併發下是否雪崩」為執行期量測，靜態不可得。

**TC 原文**｜章節：10. 非功能案例（TC-PERF / TC-SEC-INJ / TC-A11Y）｜前置：（空）｜步驟：500 併發 ramp-up 負向｜判定基準：429 / 罐頭回覆降級，無雪崩｜路徑類型：⚠ 未標註｜驗證面向：功能｜優先級：P1｜驗證哪些需求：NFR-Scal-002｜旅程：—

---

## 逐條驗收條件對照

| 條件 | 類型 | 程式碼落點 | 狀態 |
|---|---|---|---|
| 429 錯誤碼存在 | 機制存在 | `api/core/errors.py:54`、`:66` | 存在（`RATE_LIMITED` ↔ 429） |
| 全域限流生效 | 機制存在 | `api/config.toml:38-41` | **關閉**（`enabled = false`，註記「僅回 header 不真擋」） |
| V2 派工／工單端點有限流 | 機制存在 | `api/routers/dispatch_v2.py`、`api/routers/work_orders_v2.py` | **零命中**（未呼叫任何限流函式） |
| 公開端點有限流 | 機制存在 | `api/services/technician_kyc_service.py:69-89`、`api/services/brand_application_service.py:156-165` | 存在（per-IP in-memory，單實例） |
| 罐頭回覆存在 | 機制存在 | `agent/lockcore/channels/line_gateway.py:56` | 存在 |
| 罐頭回覆觸發路徑 | 機制存在 | `agent/lockcore/channels/line_gateway.py:1005-1007` | 存在（`[litellm error]` sentinel） |
| LLM 429/overload 可觸發 failover | 機制存在 | `agent/lockcore/providers/fallback_provider.py:17-24`、`:34-37` | 錯誤字面命中清單存在 |
| failover 已接上 | 機制存在 | `agent/config.toml:16`、`agent/lockcore/app_config.py:142-143` | **未啟用**（`fallback_models = []` → 直接回主 provider） |
| 主 provider 熔斷 | 機制存在 | `agent/lockcore/providers/fallback_provider.py:14-15`、`:166-167` | 實作存在，但需 FallbackProvider 生效才走到 |
| LiteLLM 例外不外洩 | 機制存在 | `agent/lockcore/providers/litellm_provider.py:107-113` | 例外映射為 `[litellm error]` 字串回應 |
| API 端熔斷／佇列上限 | 機制存在 | — | **零命中**（`api/` 中無 circuit breaker／bulkhead 實作） |
| 500 併發實測是否雪崩 | 數值達標 | — | **無法靜態判定** |
| 500 併發壓測資產 | 機制存在 | `loadtest/README.md:100-104` | **不存在**（spike test 0→200→0 列為 Phase II） |

---

## Event Storming

本案例為非功能需求，無 domain event。改列機制與落點對照：

| Actor | 動作 | 期待機制 | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|
| 壓測工具 | 500 併發 ramp-up | 觸發限流 | `api/config.toml:40` | 全域限流關閉 |
| API | 超過 per-IP 額度 | 回 429 | `api/services/technician_kyc_service.py:86` | `ApiError("RATE_LIMITED", ..., 429)`（僅 KYC 上傳） |
| API | 未捕捉例外 | 不雪崩 | `api/core/errors.py:252-258` | 回 500 `INTERNAL_ERROR` |
| LLM 供應商 | 回 429 / overloaded | 切備援 | `agent/lockcore/providers/fallback_provider.py:34-37` | 字面命中即視為可 failover；但 `fallback_models` 為空 → 不建立 wrapper |
| Agent | provider 出錯 | 罐頭回覆 | `agent/lockcore/channels/line_gateway.py:1005-1007` | 回 `_FALLBACK_REPLY`，HTTP 仍 200 |
| Agent | 連續失敗 | 熔斷主模型 | `agent/lockcore/providers/fallback_provider.py:166-167` | 3 次失敗記 `_primary_tripped_at`，冷卻 60s |
| Cloud Run | 擴容吸收突發 | 水平擴展 | `scripts/deploy/api.sh:65-66`、`scripts/deploy/agent.sh:59-60` | api 1/1、agent 1/3 |

---

## 逐層走查

### 第 1 層 — 429 的錯誤碼映射

`api/core/errors.py:47-56`

```python
_CODE_MAP: dict[str, tuple[int, str]] = {
    "BAD_REQUEST":       (400, "Bad Request"),
    ...
    "RATE_LIMITED":      (429, "Rate Limited"),
    "INTERNAL_ERROR":    (500, "Internal Server Error"),
}
```

`api/core/errors.py:59-67` 另有反向 `_STATUS_CODE_MAP`，含 `429: "RATE_LIMITED"`。

### 第 2 層 — 全域限流的實際狀態

`api/config.toml:38-41`

```toml
[rate_limit]
# in-memory token bucket（先簡化，僅回 header 不真擋）
enabled = false
requests_per_minute = 120
```

`api/core/config.py:21`（`rate_limit: dict = field(default_factory=dict)`）與 `:48`（`rate_limit=data.get("rate_limit", {})`）僅把該段讀入設定物件。`api/main.py:248` 在 CORS 的 `expose_headers` 列出三個 `RateLimit-*` header。

### 第 3 層 — 實際會 raise 429 的兩處

`api/services/technician_kyc_service.py:66-89`

```python
# 公開端點 per-IP 限流(in-memory,單實例;多 replica 失準已記 CR-0114 已知取捨)
_RATE_WINDOW_SEC = 15 * 60
_RATE_MAX_UPLOADS = 30
_rate_buckets: dict[str, deque[float]] = {}


def rate_limit_check(client_ip: str | None) -> None:
    """同 IP 15 分鐘內最多 30 次上傳;超過 → 429。無 IP(測試)不擋。
    ...
    """
    if not client_ip:
        return
    ...
    if len(bucket) >= _RATE_MAX_UPLOADS:
        raise ApiError("RATE_LIMITED", "上傳過於頻繁,請稍後再試", 429)
```

`api/services/brand_application_service.py:156-165`

```python
def _lookup_rate_limit_check(client_ip: str | None) -> None:
    """同 IP 15 分鐘內最多 20 次進度查詢;超過 → 429。無 IP(測試)不擋。"""
    ...
        raise ApiError("RATE_LIMITED", "查詢過於頻繁，請稍後再試", 429)
```

另 `api/services/brand_application_service.py:114` 有一處申請次數過多的 429、`api/services/platform_admin_service.py:88` 為登入鎖定的 `LOGIN_LOCKED` 429。

全 repo `grep -rn "429\|RATE_LIMITED\|rate_limit" --include=*.py api/`（排除 tests、`__pycache__`）的命中僅上述數處與 `api/services/line_push_service.py:72`（對外呼叫時的**可重試狀態碼集合** `_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}`）、`api/services/technician_line_service.py:233`（同型）。`api/routers/dispatch_v2.py` 與 `api/routers/work_orders_v2.py` 未呼叫任何限流函式。

### 第 4 層 — 罐頭回覆降級

`agent/lockcore/channels/line_gateway.py:47-56`

```python
# 內部錯誤外洩防線:LiteLLMProvider 失敗時 content 會是 "[litellm error] ..."。
# 這類字串(或空回覆)絕不可原文丟給客人,改回友善話術。
_ERROR_SENTINEL = "[litellm error]"
# ⚠️ 這句話**不可以**含 CR-0097 的轉接承諾字樣（_SOFT/_DEFINITIVE_HANDOFF_MARKERS）。
...
_FALLBACK_REPLY = "不好意思,系統暫時無法回應,請稍後再傳一次訊息 🙏"
```

`agent/lockcore/channels/line_gateway.py:1002-1008`

```python
    content = (getattr(out, "content", None) or "") if out is not None else ""
    if not content.strip():
        return ""
    if _ERROR_SENTINEL in content:
        logger.warning("LLM/provider 內部錯誤,改回友善訊息(不外洩):{}", content[:160])
        return _FALLBACK_REPLY
    return content[:_LINE_TEXT_LIMIT]
```

sentinel 的產生點在 `agent/lockcore/providers/litellm_provider.py:106-113`

```python
        try:
            resp = await litellm.acompletion(**kwargs)
        except Exception as e:  # noqa: BLE001 — 映射成可被 retry policy 判讀的 error 回應
            return LLMResponse(
                content=f"[litellm error] {e}",
                finish_reason="error",
                error_kind="connection",
                error_type=type(e).__name__,
            )
```

`agent/lockcore/channels/line_gateway.py:49-55` 的註解記載此罐頭文字曾因含「專員與您」字樣被 `_promised_handoff()` 判為轉接承諾，導致對話翻 escalated、AI 永久靜音，故現行措辭刻意不含轉接字樣。

### 第 5 層 — 多供應商 failover 與熔斷

`agent/lockcore/providers/fallback_provider.py:12-24`

```python
# Circuit breaker tuned to match OpenAICompatProvider's Responses API breaker.
_PRIMARY_FAILURE_THRESHOLD = 3
_PRIMARY_COOLDOWN_S = 60
_MISSING = object()
_FALLBACK_ERROR_KINDS = frozenset({
    "timeout",
    "connection",
    "server_error",
    "rate_limit",
    "overloaded",
})
```

`agent/lockcore/providers/fallback_provider.py:33-40`（可 failover 的錯誤字面）

```python
_FALLBACK_ERROR_TOKENS = (
    "rate_limit",
    "rate limit",
    "too_many_requests",
    "too many requests",
    "overloaded",
    ...
```

熔斷記錄點 `agent/lockcore/providers/fallback_provider.py:166-167`

```python
            if self._primary_failures >= _PRIMARY_FAILURE_THRESHOLD:
                self._primary_tripped_at = time.monotonic()
```

冷卻判定 `:104-106`；成功後歸零 `:148`。

啟用條件 `agent/lockcore/app_config.py:141-143`

```python
    primary = _make_litellm(cfg, cfg.model, cfg.temperature, cfg.max_tokens)
    if not cfg.fallback_models:
        return primary
```

`agent/config.toml:13-16`

```toml
# 多供應商 failover(ADR-009):主模型連續錯誤→熔斷→依序改用這些 fallback 模型。
# 空/省略 = 不啟用。範例(Vertex 主模型掛掉退到 Google AI Studio 免 GCP):
#   fallback_models = ["gemini/gemini-2.5-flash"]
fallback_models = []
```

TC 判定基準要求「無雪崩」／`agent/config.toml:16` 現行值為空陣列，依 `agent/lockcore/app_config.py:142-143` 不會包 `FallbackProvider`，故 `fallback_provider.py` 的熔斷與 failover 在現行設定下不進入呼叫路徑。此處僅並陳，不裁定。

`smartlock-docs/enterprise/05_NFR.md:229` 記載「主供應商（Vertex）中斷 → FallbackProvider 多供應商 failover（🔜 規劃中）；期間全客服降級友善話術 + 轉真人」。

### 第 6 層 — API 端的雪崩抑制面

`api/main.py:271-289` 有一支針對公開上傳端點的 body 上限 middleware：

```python
_PUBLIC_UPLOAD_PATH = "/api/v1/technicians/registration-documents"
_PUBLIC_UPLOAD_MAX_BODY = 12 * 1024 * 1024  # 10 MiB 檔案 + multipart 開銷餘裕


@app.middleware("http")
async def _public_upload_body_cap(request, call_next):
    if request.url.path == _PUBLIC_UPLOAD_PATH:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > _PUBLIC_UPLOAD_MAX_BODY:
            ...
            return JSONResponse(status_code=413, ...)
```

`api/core/db.py:316-326` 的連線池上限 `DB_POOL_MAX` 預設 10、`pool.open(wait=True, timeout=30)`；`api/core/db.py:331` 開池失敗時 `_pool = None`（退回共用單一連線）。

對外呼叫的退避重試存在於 `api/services/line_push_service.py:71-73`

```python
# Transient HTTP statuses that warrant a retry.
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_BACKOFF_SECONDS = (1, 2, 4)  # three retries with exponential backoff
```

`api/` 中無 circuit breaker / bulkhead / semaphore 形式的入站保護實作。

### 第 7 層 — 500 併發壓測資產

`loadtest/README.md:99-104`

```
## 不在本 BUILD 範圍

- HD-3 (c) soak test 4hr — Phase II 收尾
- HD-3 (d) spike test 0→200→0 — Phase II
- WebSocket scenario — 需另寫 WS user class；Phase II 補
```

`loadtest/` 現有參數上限為 100 VU（`loadtest/README.md:44-52`），`500` 在 `loadtest/*.py` 與 `loadtest/README.md` 中零命中。

---

## 既有測試證據

`api/tests/` 與 `agent/tests/` 中無 500 併發或 spike 測試。本次實跑與本 TC 機制相關的既有測試（本機 Docker 測試庫，Windows 需 `-p winloop_plugin`）：

```
cd agent && python -m pytest tests/test_fallback_wiring.py -q -p winloop_plugin
3 passed in 9.06s

cd agent && python -m pytest tests/test_fallback_reply_no_handoff.py -q -p winloop_plugin
6 passed in 0.10s
```

`agent/tests/test_fallback_reply_no_handoff.py` 的檔名與 `agent/lockcore/channels/line_gateway.py:55` 的註解「改動這句話時請務必重跑 agent/tests/test_fallback_reply_no_handoff.py」對應，驗的是罐頭回覆不得觸發轉真人承諾。

`api/tests/` 中對兩處 per-IP 限流的既有測試：本次未執行專屬檔案（`grep -l "RATE_LIMITED" api/tests/` 之命中檔於本批次未列入執行清單）。

---

## 事實結論

1. `RATE_LIMITED ↔ 429` 的錯誤碼映射存在於 `api/core/errors.py:54` 與 `:66`。
2. 全域限流開關 `enabled = false`（`api/config.toml:40`），其註解自述「僅回 header 不真擋」；`api/main.py:248` 僅 expose 三個 `RateLimit-*` header。
3. 實際會 raise 429 的入站限流有兩處（`api/services/technician_kyc_service.py:86` 上傳、`api/services/brand_application_service.py:165` 進度查詢），皆為 per-IP in-memory 桶，`api/services/technician_kyc_service.py:66` 的註解載明「多 replica 失準已記 CR-0114 已知取捨」。
4. V2 派工／工單端點（`api/routers/dispatch_v2.py`、`api/routers/work_orders_v2.py`）未呼叫任何限流函式。
5. 罐頭回覆機制完整存在：sentinel 產生於 `agent/lockcore/providers/litellm_provider.py:110`、攔截於 `agent/lockcore/channels/line_gateway.py:1005-1007`、文字定義於 `:56`。
6. 多供應商 failover 與主模型熔斷（3 次失敗 / 60s 冷卻）實作於 `agent/lockcore/providers/fallback_provider.py:14-15`、`:166-167`，但 `agent/config.toml:16` 的 `fallback_models = []` 使 `agent/lockcore/app_config.py:142-143` 直接回主 provider，該 wrapper 於現行設定不生效。
7. `api/` 中無 circuit breaker／bulkhead 形式的入站保護；對外呼叫端有 429/5xx 退避重試（`api/services/line_push_service.py:71-73`）。
8. 500 併發的壓測資產不存在，`loadtest/README.md:100-104` 將 spike test 列為 Phase II。
9. 「500 併發 ramp-up 下是否雪崩」需執行期量測，本次未取得。
