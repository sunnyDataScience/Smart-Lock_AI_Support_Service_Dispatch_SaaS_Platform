# TC-NFR-PERF-01 — NFR 壓測與降級行為

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **無法靜態判定** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務 |
| 走查時間 | 2026-08-03 15:50（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `loadtest/`、`agent/lockcore/observability.py`、`agent/tests/test_cr_0196_reply_latency.py` |
| 優先級 / 路徑類型 | P1 / failure＋recovery |
| 事實結論 | 判定基準要求保存 p95/p99、錯誤率與降級行為的實測數據，且明訂「資料不足一律 Fail/Blocked，不以估計值通過」，無法由原始碼取得；另查得既有壓測資產標的為 API，且需 k6/RUM/WS/RAG/OHS 等 fixture 才能執行。 |

**TC 原文**｜前置：k6、RUM、WS、RAG、OHS 與 config cache fixture｜步驟：依 NFR 指定併發壓測，逐一令 RAG/WS/OHS/快取過載或中斷｜判定基準：保存 p95/p99、錯誤率與降級行為；超門檻或資料不足一律 Fail/Blocked，不以估計值通過｜需求：NFR-Perf-001～012（共 11 項）｜旅程：SC-01、SC-05、SC-18

---

## 為何無法靜態判定

判定基準是執行期量測值（p95/p99、錯誤率）與故障注入下的降級行為。原始碼可以顯示是否存在壓測腳本與門檻定義，但無法產生數據。TC 本身明訂「資料不足一律 Fail/Blocked，不以估計值通過」——本批走查不啟動服務，故不具備產生數據的條件。

前置條件（k6、RUM、WS、RAG、OHS 與 config cache fixture）在本批走查中皆不成立。

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 壓測工具 | 依 NFR 併發壓測 | `LoadTestCompleted` | 保存 p95/p99、錯誤率 | `loadtest/sla.py:34-38` | 門檻常數存在，但針對 API 的 GET／POST |
| 稽核者 | 注入 RAG/WS/OHS 過載或中斷 | `DegradedBehaviorObserved` | 記錄降級行為 | — | 不可觀察（需執行期故障注入） |

---

## 走查紀錄

### 步驟 1 — 既有壓測資產

- **動作**：檢視 `loadtest/`
- **預期**：涵蓋 NFR-Perf-001～012
- **實際**：內含 `locustfile.py`、`sla.py`、`README.md`，無 `results/`

`loadtest/sla.py:1-14`

```python
"""CR-0019 SLA pass/fail gate — HD-2 保守門檻。
...
門檻（CIA HD-2 採納保守立場）：
  p95 GET    ≤ 500ms      （read-heavy endpoint，容忍 Cloud Run cold-start）
  p95 POST   ≤ 1000ms     （write-heavy，含 DB transaction）
  error rate ≤ 1%         （含 5xx 與 4xx 異常）
  throughput ≥ 100 req/s  （MVP 目標）
```

門檻為 p95，未見 p99；標的為 API（`loadtest/README.md:13-20` 的 host 指向 API），未涵蓋 agent／LINE 通道。

### 步驟 2 — 門檻檢核的輸入來源

- **動作**：讀 `sla.py` 的資料來源
- **預期**：可離線判定
- **實際**：讀 Locust 產生的 CSV；未執行壓測即無 CSV，`loadtest/` 下亦無既有結果檔

### 步驟 3 — agent 端的量測能力

- **動作**：搜尋 p95/p99 聚合
- **預期**：存在
- **實際**：`agent/lockcore/observability.py` 中 `p95`／`latency`／`SLO` 零命中；僅 `loop.py:1527` 記單筆 `turn_latency_ms`

### 步驟 4 — 降級行為的注入點

- **動作**：找 RAG/WS/OHS/快取的故障注入或降級路徑
- **預期**：可觀察
- **實際**：需執行期注入，本批不可觀察

---

## 判定所需的前置條件

k6（或 Locust）壓測環境、RUM 資料來源、WebSocket 端點、RAG MCP server、OHS 與 config cache 的可控 fixture，且需授權對目標環境施加 NFR 指定的併發量。缺任一項時，依 TC 判定基準本身的規定應為 Fail/Blocked，而非以估計值通過。
