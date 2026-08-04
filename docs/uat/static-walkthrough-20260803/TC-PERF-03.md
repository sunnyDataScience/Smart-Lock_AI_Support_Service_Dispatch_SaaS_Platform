# TC-PERF-03 — OHS 媒合 benchmark p95 < 300ms

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **無法靜態判定** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 6） |
| 走查時間 | 2026-08-03 19:32（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `loadtest/`、`api/services/dispatch_service.py`、`api/routers/dispatch_v2.py`、`api/core/observability.py`、`api/core/db.py` |
| 優先級 / 路徑類型 | P1 / ⚠ 未標註 |
| 事實結論 | 判定基準為執行期效能數據（p95 < 300ms），無程式碼可據以判定。另查得：`300` 這個門檻在 `loadtest/` 與 `api/` 中均無對應常數；`loadtest/sla.py` 的門檻為 `p95_get_ms=500` / `p95_post_ms=1000`，`loadtest/locustfile.py` 的 task 全為技師工單流程（pool / accept / subflow / schedule / complete / detail），不含媒合端點；TC 指名的 `POST /technicians:match` 在程式碼零命中，實際媒合端點為 `POST /tenants/{tenantId}/dispatch:auto-match`。 |

**TC 原文**｜前置：（空）｜步驟：OHS 媒合 benchmark｜判定基準：p95 < 300ms｜⚠ 未標註｜P1｜FR-TEC-03、NFR-Perf-007｜SC-05

---

## 為何無法靜態判定

判定基準是「OHS 媒合的 p95 延遲低於 300ms」，屬執行期量測值。原始碼可以顯示是否**存在**門檻常數、量測點與壓測腳本，但無法產生延遲數據——需要實際啟動 API、連上資料庫（媒合路徑至少 3 次 DB 查詢）並施加負載取樣。本批走查的前提是不啟動服務，故此條無法取得判定所需事實。

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 壓測工具 | 反覆呼叫媒合端點 | `MatchCompleted` ×N | p95 < 300ms | — | 不可觀察（需執行期數據） |
| 系統 | 記錄延遲 | `LatencyRecorded` | 可聚合出 p95 | — | **找不到** api 端的 p95 聚合或 SLO 常數 |
| 壓測資產 | 定義門檻 | `ThresholdChecked` | 300ms | `loadtest/sla.py:34-38` | 門檻為 500 / 1000ms，標的為泛用 GET / POST |

---

## 走查紀錄

### 步驟 1 — 是否有 300ms 門檻常數

- **動作**：搜尋門檻值與 p95 字串
- **預期**：程式碼中有對應常數
- **實際**：`loadtest/*.py` 中無 `300`、無 `match`、無 `dispatch`

```
grep -rn "300\|match\|dispatch" loadtest/*.py
（無輸出）
```

`loadtest/sla.py:34-38`

```python
class SlaThresholds:
    p95_get_ms: int = 500
    p95_post_ms: int = 1000
    error_rate_pct: float = 1.0
    min_throughput_rps: float = 100.0
```

`smartlock-docs/enterprise/05_NFR.md:47`（NFR-Perf-007）記載「OHS 派工媒合 `POST /technicians:match`｜p95 < 300ms（設計目標；實測 `[待確認]`）」。此處僅並陳，不裁定。

### 步驟 2 — 壓測腳本的標的

- **動作**：列出 locust task
- **預期**：包含媒合端點
- **實際**：六個 task 全為技師工單流程

```
grep -n "task\|def " loadtest/locustfile.py
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

`loadtest/` 目錄內容為 `locustfile.py`、`sla.py`、`README.md`（無 `results/`）。

### 步驟 3 — 被量測的端點是否存在

- **動作**：搜尋 TC 指名端點
- **預期**：`POST /technicians:match` 存在
- **實際**：`api`／`web` 零命中

```
git grep -rn "technicians:match" -- api web SQL agent
（無輸出）
```

實際媒合端點為 `api/routers/dispatch_v2.py:112-118`（`POST /tenants/{tenantId}/dispatch:auto-match`，`operation_id="planDispatchAutoMatchV2"`）。

### 步驟 4 — 媒合路徑的成本結構

- **動作**：列出媒合一次的 DB 往返
- **預期**：可辨識效能熱點
- **實際**：至少 5 次查詢 + 純 Python 評分/排序

`api/services/dispatch_service.py:575-582`（取 problem_card brand）、`:589-594`（取最新 WO 地址）、`:601`（`_fetch_tenant_technicians` 撈全租戶技師）、`:606`（`_brand_authorized_ids`）、`:610` `_enrich_gis_performance` 內的 `:225-228`、`:612` `_enrich_workload_fairness` 內的 `:267-282`（兩次 COUNT 聚合）。

`api/services/dispatch_service.py:405-411`

```python
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        f"SELECT {_TECH_SELECT} FROM technicians t "
        f"WHERE t.tenant_id = %s::uuid",
        (tenant_id,),
    )
    return await cur.fetchall()
```

該查詢無 LIMIT，撈該租戶全部技師後在 Python 端過濾與排序（`_score_rows`，`:414-478`）。

### 步驟 5 — api 端的延遲量測

- **動作**：檢視 observability 模組
- **預期**：有 p95 或 SLO 定義
- **實際**：`api/core/observability.py` 只有 OpenTelemetry span 匯出與屬性清洗，無百分位聚合

```
grep -n "def " api/core/observability.py
30:def _scrub_span_attributes(span) -> None:
52:def observability_enabled() -> bool:
56:def setup_observability(app, *, service_name: str = "lock-ai-api") -> bool:
```

`git grep -n "p95" -- api` 無輸出。

### 步驟 6 — 既有測試

- **動作**：找相關測試
- **預期**：能提供延遲證據
- **實際**：`api/tests/` 中無媒合效能／benchmark 測試；派工相關測試第一輪在無 DB 環境下多數失敗，第二輪於本機測試庫全數通過，但兩輪皆不產生 p95 延遲數據

第一輪（無資料庫，由統籌者於本批次執行，數字沿用）：

```
cd api && python -m pytest tests/test_cr_0051_dispatch_eligibility.py tests/test_cr_0030_dispatch_mode.py \
  tests/test_manual_dispatch.py tests/test_dispatch_v2_endpoint.py tests/test_dispatch_plan_v2_endpoint.py \
  tests/test_cr_0164_tech_mirror_projection.py tests/test_cr_0172_tech_dispatch_outbox.py \
  tests/test_dispatch_fairness_load.py -q --tb=no
13 failed, 39 passed in 3.87s
```

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」），逐檔執行 `cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/<檔名> -q -p winloop_plugin --tb=no`：

```
test_cr_0051_dispatch_eligibility.py       8 passed in 0.38s
test_cr_0030_dispatch_mode.py              3 passed in 2.97s
test_manual_dispatch.py                   10 passed in 2.99s
test_dispatch_v2_endpoint.py               6 passed in 2.97s
test_dispatch_plan_v2_endpoint.py          8 passed in 2.96s
test_cr_0164_tech_mirror_projection.py     5 passed in 0.46s
test_cr_0172_tech_dispatch_outbox.py       5 passed in 0.40s
test_dispatch_fairness_load.py             7 passed in 0.40s
```

八檔 52 項全數通過。這些為功能性測試，pytest 只輸出整體耗時、不採樣單一請求延遲，`test_dispatch_fairness_load.py` 檔頭自述「純評分函式與權重和=1.0（不碰 DB）」，驗的是評分因子而非延遲；本機測試庫的資料量與硬體也不對應正式環境，故第二輪不提供 p95 判讀所需的量測。

---

## 判定所需的前置條件

要把此 TC 從「無法靜態判定」推進到可判定，需要：可運行的 API 實例與已載入技師／工單資料的資料庫（含足量技師以反映 `_fetch_tenant_technicians` 的無 LIMIT 行為）、針對媒合端點的壓測腳本（現有 `loadtest/locustfile.py` 不涵蓋）、300ms 門檻的判讀規則（`loadtest/sla.py` 目前只有 500/1000ms），以及施加負載的授權。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/20_Test_Cases.md:133` 對 NFR-Perf-007 標註「⚠ V10：P0 旅程需要，卻只有正向案例」。
- `smartlock-docs/enterprise/05_NFR.md:47` 的驗證方式欄寫「k6 + read replica 路由驗證」；`loadtest/` 使用的是 Locust，非 k6。
- `smartlock-docs/enterprise/05_NFR.md:286` 記載「§54 讀寫分離 read replica（階段二）」仍為未做項。
