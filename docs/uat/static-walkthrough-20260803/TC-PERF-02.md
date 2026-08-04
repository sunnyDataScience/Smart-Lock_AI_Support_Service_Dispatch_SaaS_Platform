# TC-PERF-02 — 100 併發（V2）首回應 p95 與 graceful 退化

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `loadtest/locustfile.py`、`loadtest/sla.py`、`loadtest/README.md`、`.github/workflows/loadtest-mini.yml`、`scripts/deploy/api.sh`、`scripts/deploy/agent.sh`、`api/config.toml`、`api/core/errors.py`、`api/core/db.py`、`agent/lockcore/channels/line_gateway.py` |
| 優先級 / 路徑類型 | P1 / ⚠ 未標註 |

判定理由：本 TC 的兩個判定條件分屬兩類。**數值條件**（100 併發下 p95 < 5s）為執行期量測，靜態走查不可得，此部分為「無法靜態判定」。**機制條件**可靜態判定且結果分歧——100 VU 壓測資產存在（`loadtest/README.md:44-52` 明列 `-u 100 -r 5 -t 30m` 與門檻判讀腳本），PR 級 CI 觸發器亦存在（`.github/workflows/loadtest-mini.yml:41-47`）；但壓測門檻常數為 `p95_get_ms=500` / `p95_post_ms=1000`（`loadtest/sla.py:34-38`），與 TC 的 5s 不同數量級且標的為 API 而非 AI 首回應；壓測 task 六支全為技師工單流程（`loadtest/locustfile.py:103-197`）不含 LINE 通道。「不 5xx」的機制方面：未捕捉例外仍回 500 `INTERNAL_ERROR`（`api/core/errors.py:252-258`），LLM 內部錯誤在 agent 端被 sentinel 攔成罐頭回覆（`agent/lockcore/channels/line_gateway.py:1005-1007`）。另查得 `scripts/deploy/api.sh:66` 的 `MAX_INSTANCES` 預設值為 `1`。故整體為「部分實作」。

**TC 原文**｜章節：10. 非功能案例（TC-PERF / TC-SEC-INJ / TC-A11Y）｜前置：（空）｜步驟：100 併發（V2）｜判定基準：p95 < 5s；退化 graceful 不 5xx｜路徑類型：⚠ 未標註｜驗證面向：功能｜優先級：P1｜驗證哪些需求：NFR-Perf-001、NFR-Scal-002｜旅程：—

---

## 逐條驗收條件對照

| 條件 | 類型 | 程式碼落點 | 狀態 |
|---|---|---|---|
| 存在 100 併發壓測資產 | 機制存在 | `loadtest/README.md:44-52`、`loadtest/locustfile.py:103-197` | 存在（標的為技師工單 API） |
| 壓測門檻判讀可自動化 | 機制存在 | `loadtest/sla.py:34-38`、`:44` | 存在 |
| PR 級 CI 觸發壓測 | 機制存在 | `.github/workflows/loadtest-mini.yml:4-8`、`:41-47` | 存在（預設 10 VU / 60s） |
| 門檻常數 = p95 5s | 機制存在 | `loadtest/sla.py:34-38` | **不存在**（值為 500 / 1000 ms） |
| 壓測涵蓋 LINE AI 首回應 | 機制存在 | `loadtest/locustfile.py:103-197` | **不存在**（六 task 皆為工單 API） |
| 100 併發實測 p95 < 5s | 數值達標 | — | **無法靜態判定** |
| 退化不回 5xx（未捕捉例外） | 機制存在 | `api/core/errors.py:252-258` | 未捕捉例外仍回 500 |
| 退化不回 5xx（LLM 錯誤） | 機制存在 | `agent/lockcore/channels/line_gateway.py:1005-1007` | sentinel → 罐頭回覆（HTTP 仍 200） |
| 退化不回 5xx（DB 不可用） | 機制存在 | `api/main.py:428-437` | `/health` 回 503（刻意設計） |
| 100 併發實測 5xx 率 | 數值達標 | — | **無法靜態判定** |
| 併發承載上限（實例數） | 機制存在 | `scripts/deploy/api.sh:65-66`、`scripts/deploy/agent.sh:59-60` | api `MIN/MAX_INSTANCES` 預設 1/1；agent 1/3 |

---

## Event Storming

本案例為非功能需求，無 domain event。改列機制與落點對照：

| Actor | 動作 | 期待機制 | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|
| 壓測工具 | 100 VU 併發打 API | 產生 p95 樣本 | `loadtest/locustfile.py:103-197` | 六個工單 task（pool 40 / accept 25 / subflow 15 / schedule 10 / complete 5 / detail 5） |
| SLA gate | 讀 CSV 判門檻 | p95 < 5s | `loadtest/sla.py:34-38` | 門檻為 500ms(GET) / 1000ms(POST) / error ≤1% / rps ≥100 |
| CI | PR 觸發壓測 | 自動跑 | `.github/workflows/loadtest-mini.yml:41-47` | 預設 10 VU / 60s；`STAGING_HOST` 未設即 skip |
| API | 未預期例外 | 不回 5xx | `api/core/errors.py:252-258` | 回 500 `INTERNAL_ERROR`（RFC7807） |
| Agent | LLM/provider 出錯 | 降級不外洩 | `agent/lockcore/channels/line_gateway.py:1005-1007` | 偵測 `[litellm error]` sentinel → 回 `_FALLBACK_REPLY` |
| Cloud Run | 併發擴容 | 水平擴展 | `scripts/deploy/api.sh:65-66` | `MAX_INSTANCES` 預設 `1` |

---

## 逐層走查

### 第 1 層 — 100 併發壓測資產是否存在

`loadtest/README.md:44-52`

```
### Full run（pre-release，HD-5=b 後段）

locust -f loadtest/locustfile.py --headless \
    -u 100 -r 5 -t 30m \
    --host https://api-staging.example.com \
    --csv loadtest/results/full
python loadtest/sla.py loadtest/results/full_stats.csv

100 VU rampup 5/s 達成 5 分 → 持續 30 分。SLA 門檻全套驗。
```

`loadtest/README.md:3` 記載此資產對應「CR-0019 Load Testing — 100 技師併發」，即 100 併發是既有設計目標。

### 第 2 層 — 判定門檻常數

`loadtest/sla.py:33-38`

```python
@dataclass(frozen=True)
class SlaThresholds:
    p95_get_ms: int = 500
    p95_post_ms: int = 1000
    error_rate_pct: float = 1.0
    min_throughput_rps: float = 100.0
```

TC 判定基準寫「p95 < 5s」（出處：`smartlock-docs/enterprise/20_Test_Cases.md` 之 TC-PERF-02 列；需求端 `smartlock-docs/enterprise/05_NFR.md:41` NFR-Perf-001 為「LINE AI 首回應 latency｜p95 < 5s（V1）/ p99 < 8s」）／`loadtest/sla.py:34-38` 的門檻為 500ms(GET)、1000ms(POST)，且 `loadtest/sla.py:9-13` 的 docstring 自述其為「read-heavy endpoint」「write-heavy，含 DB transaction」。兩者標的與量級皆不同。此處僅並陳，不裁定。

`error_rate_pct` 的計算涵蓋 5xx：`loadtest/sla.py:12` 註記「error rate ≤ 1%（含 5xx 與 4xx 異常）」。

### 第 3 層 — 壓測腳本涵蓋的端點

`loadtest/locustfile.py` 的 task 清單：

```
103:    @task(40)
104:    def get_pool(self) -> None:
111:    @task(25)
112:    def accept_work_order(self) -> None:
127:    @task(15)
128:    def post_subflow(self) -> None:
154:    @task(10)
155:    def patch_schedule(self) -> None:
177:    @task(5)
178:    def complete_work_order(self) -> None:
196:    @task(5)
197:    def get_work_order_detail(self) -> None:
```

六支 task 皆為技師工單 API；`loadtest/` 目錄內容為 `locustfile.py`、`sla.py`、`README.md`（無 `results/`）。`loadtest/README.md:100-104` 的「不在本 BUILD 範圍」列出「WebSocket scenario — 需另寫 WS user class；Phase II 補」。

### 第 4 層 — CI 觸發條件與門檻寬嚴

`.github/workflows/loadtest-mini.yml:4-8`

```yaml
on:
  pull_request:
    paths:
      - 'api/**'
      - 'loadtest/**'
      - '.github/workflows/loadtest-mini.yml'
```

`.github/workflows/loadtest-mini.yml:24-27`

```yaml
    env:
      VU_COUNT: ${{ inputs.vu_count || '10' }}
      DURATION: ${{ inputs.duration || '60s' }}
      STAGING_HOST: ${{ secrets.LOADTEST_STAGING_HOST }}
```

`.github/workflows/loadtest-mini.yml:44-49`：`STAGING_HOST` 未設時輸出 `::warning::STAGING_HOST secret not set — skip loadtest` 並 `exit 0`。

`.github/workflows/loadtest-mini.yml:71-77`

```yaml
      - name: Evaluate SLA (PR 寬鬆模式 — 只警示，不 fail PR)
        continue-on-error: true
        run: |
          python loadtest/sla.py loadtest/results/mini_stats.csv || true
```

100 VU 的 full run 依 `.github/workflows/loadtest-mini.yml:9-19` 為 `workflow_dispatch` 手動輸入參數；`loadtest/README.md:89` 記「Pre-release full run 為 manual trigger（避免 staging budget 失控）」。

### 第 5 層 — 「不 5xx」的機制面

未捕捉例外的處理，`api/core/errors.py:252-258`

```python
        # 500 回應在 CORSMiddleware 外側產生 → 手動補 CORS header（見函式 docstring）
            ...
                error_code="INTERNAL_ERROR",
                ...
                status_code=500,
```

`api/core/errors.py:55` 定義 `"INTERNAL_ERROR": (500, "Internal Server Error")`。

DB 健康檢查，`api/main.py:428-437`

```python
@app.get("/health")
async def health():
    """Health check — DB 連線存活檢測。"""
    db_ok = await healthcheck()
    from fastapi.responses import JSONResponse
    status = "ok" if db_ok else "degraded"
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"status": status, "version": app.version, "checks": {"db": "ok" if db_ok else "disconnected"}},
    )
```

Agent 端 LLM 錯誤的降級，`agent/lockcore/channels/line_gateway.py:1005-1007`

```python
    if _ERROR_SENTINEL in content:
        logger.warning("LLM/provider 內部錯誤,改回友善訊息(不外洩):{}", content[:160])
        return _FALLBACK_REPLY
```

`agent/lockcore/channels/line_gateway.py:47-48` 定義 `_ERROR_SENTINEL = "[litellm error]"`；`:56` 定義罐頭文字。webhook 端點在任何情況下回 `web.Response(text="OK")`（`agent/lockcore/channels/line_gateway.py:1299`），簽章驗證失敗回 400（`:1205`）。

### 第 6 層 — 併發承載的部署參數

`scripts/deploy/api.sh:59-67`

```bash
MEMORY="1Gi"
CPU=1
...
MIN_INSTANCES="${MIN_INSTANCES:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-1}"
TIMEOUT=300
```

`scripts/deploy/agent.sh:57-61`

```bash
MEMORY="2Gi"
CPU=2
MIN_INSTANCES=1
MAX_INSTANCES=3
TIMEOUT=300
```

兩支腳本皆未出現 `--concurrency` 旗標（`scripts/deploy/api.sh:429-435`、`scripts/deploy/agent.sh:377-384` 的 `gcloud run deploy` 參數列）。

### 第 7 層 — DB 連線池上限

`api/core/db.py:316-326`

```python
        pool = AsyncConnectionPool(
            ...
            min_size=int(os.getenv("DB_POOL_MIN", "1")),
            max_size=int(os.getenv("DB_POOL_MAX", "10")),
            ...
        )
        await pool.open(wait=True, timeout=30)
```

`api/core/db.py:361-362` 註記 http 請求包 `pool_scope`、websocket 不包（長連線佔池）。

### 第 8 層 — 全域限流狀態（影響「退化 graceful」）

`api/config.toml:38-41`

```toml
[rate_limit]
# in-memory token bucket（先簡化，僅回 header 不真擋）
enabled = false
requests_per_minute = 120
```

`api/core/config.py:21` 與 `:48` 僅把該段讀成 `rate_limit: dict`；`api/main.py:248` 於 CORS `expose_headers` 列出 `RateLimit-Limit` / `RateLimit-Remaining` / `RateLimit-Reset`。全 repo 中會 raise 429 的限流只有兩處（`api/services/technician_kyc_service.py:86`、`api/services/brand_application_service.py:165`），皆為 per-IP in-memory。

---

## 既有測試證據

`api/tests/` 與 `agent/tests/` 中無 100 併發測試。本次實跑與本 TC 相關的既有測試（本機 Docker 測試庫，`POSTGRES_URI=postgresql://lock:0000@localhost:5433/lock_scratch_test`，Windows 需 `-p winloop_plugin`）：

```
cd agent && python -m pytest tests/test_fallback_wiring.py -q -p winloop_plugin
3 passed in 9.06s

cd agent && python -m pytest tests/test_fallback_reply_no_handoff.py -q -p winloop_plugin
6 passed in 0.10s

cd agent && python -m pytest tests/test_cr_0196_reply_latency.py -q -p winloop_plugin
5 passed in 4.85s

cd agent && python -m pytest tests/test_line_gateway.py -q -p winloop_plugin
1 failed, 91 passed in 8.67s
```

`test_line_gateway.py` 的單一失敗為 `test_debouncer_serializes_fires_per_session`，錯誤訊息 `AssertionError: 合併輪必須串行,實際: [('start', ['a', 'b']), ('end', ['a', 'b'])]`。同一測試不加 `-p winloop_plugin` 重跑：

```
cd agent && python -m pytest tests/test_line_gateway.py::test_debouncer_serializes_fires_per_session -q
1 passed in 0.83s
```

該測試以 `0.03s` debounce 視窗與 `0.06s`／`0.35s` sleep 判定串行（`agent/tests/test_line_gateway.py:757-779`），兩種事件迴圈下結果不同。

`agent/tests/test_cr_0196_reply_latency.py:90-96` 為單 turn 阻塞守線（mock provider、斷言 `elapsed < 1.0`），非 100 併發、非 p95。

---

## 事實結論

1. 100 併發的壓測資產存在且參數明列於 `loadtest/README.md:44-52`，執行方式為手動 `workflow_dispatch`（`.github/workflows/loadtest-mini.yml:9-19`）。
2. 壓測 SLA 門檻常數為 `p95_get_ms=500` / `p95_post_ms=1000`（`loadtest/sla.py:34-38`），與 TC 判定基準的 5s 不同；`5000` 或 `5s` 在 `loadtest/` 下零命中。
3. 壓測腳本六支 task 全為技師工單 API（`loadtest/locustfile.py:103-197`），不含 LINE 通道與 AI 首回應路徑。
4. `error_rate_pct ≤ 1.0`（`loadtest/sla.py:36`）為既有的 5xx/4xx 判讀機制，`loadtest/sla.py:12` 明載其涵蓋 5xx。
5. API 未捕捉例外仍回 500 `INTERNAL_ERROR`（`api/core/errors.py:252-258`、`:55`）；DB 不可用時 `/health` 回 503（`api/main.py:433`）。
6. Agent 端 LLM 錯誤以 sentinel 攔截後回罐頭文字（`agent/lockcore/channels/line_gateway.py:1005-1007`），LINE webhook 端點成功路徑固定回 200 OK（`:1299`）。
7. 全域限流 `enabled = false`（`api/config.toml:40`），實際生效的限流僅兩處 per-IP in-memory 桶。
8. Cloud Run 部署預設 `api` `MIN/MAX_INSTANCES` 皆為 1（`scripts/deploy/api.sh:65-66`）、`agent` 為 1/3（`scripts/deploy/agent.sh:59-60`），部署腳本未設 `--concurrency`。
9. 「100 併發下實測 p95」與「實測 5xx 率」需執行期量測，本次未取得。
