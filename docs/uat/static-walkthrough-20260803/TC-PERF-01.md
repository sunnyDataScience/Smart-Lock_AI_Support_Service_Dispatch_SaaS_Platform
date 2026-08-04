# TC-PERF-01 — 50 併發 LINE 對話的首回應 p95

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **無法靜態判定** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務 |
| 走查時間 | 2026-08-03 15:38（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/observability.py`、`agent/lockcore/agent/loop.py`、`loadtest/` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 判定基準為執行期效能數據（p95 < 5s），無程式碼可據以判定；另查得 agent 端無 p95 量測或 SLO 定義，`loadtest/` 的壓測標的為 API 而非 LINE 通道。 |

**TC 原文**｜前置：（空）｜步驟：50 併發 LINE 對話（V1）｜判定基準：AI 首回應 p95 < 5s｜需求：NFR-Perf-001、NFR-Scal-001｜旅程：SC-01、SC-02

---

## 為何無法靜態判定

判定基準是「50 併發下的首回應 p95 延遲」，屬執行期量測值。原始碼可以顯示是否**存在**量測機制，但無法產生延遲數據——需要實際啟動 agent、LINE 通道與 LLM 供應商並施加負載。本批走查的前提是不啟動服務，故此條無法取得判定所需事實。

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 壓測工具 | 50 併發送訊 | `TurnCompleted` ×N | 首回應 p95 < 5s | — | 不可觀察（需執行期數據） |
| 系統 | 記錄延遲 | `LatencyRecorded` | 可聚合出 p95 | `agent/lockcore/agent/loop.py:1527` | 每輪記單筆 `turn_latency_ms`，無百分位聚合 |

---

## 走查紀錄

### 步驟 1 — agent 端是否有 p95 量測或 SLO

- **動作**：搜尋 observability 模組中的百分位／SLO 定義
- **預期**：有量測機制
- **實際**：`agent/lockcore/observability.py` 中 `p95`／`latency`／`SLO` 零命中

### 步驟 2 — 現有的延遲記錄形式

- **動作**：找 turn 延遲的記錄點
- **預期**：可聚合的量測
- **實際**：單筆 metadata，無聚合

`agent/lockcore/agent/loop.py:1527`

```python
ctx.turn_latency_ms = max(0, int((time.time() - ctx.turn_wall_started_at) * 1000))
```

寫入 `meta["latency_ms"]`（`loop.py:1297-1298`）。

### 步驟 3 — 既有壓測資產的標的

- **動作**：檢視 `loadtest/`
- **預期**：可用於 LINE 對話壓測
- **實際**：內含 `locustfile.py`、`sla.py`、`README.md`；門檻針對 API 的 GET／POST，非 AI 首回應

`loadtest/sla.py:34-38`

```python
class SlaThresholds:
    p95_get_ms: int = 500
    p95_post_ms: int = 1000
    error_rate_pct: float = 1.0
    min_throughput_rps: float = 100.0
```

`loadtest/README.md:13-20` 記載壓測 host 指向 API；`loadtest/` 目錄下無 `results/`，而 `sla.py` 只讀 Locust 產生的 CSV。

### 步驟 4 — 既有測試

- **動作**：找相關測試
- **預期**：能提供延遲證據
- **實際**：`agent/tests/test_cr_0196_reply_latency.py` 為單 turn 阻塞守線測試（mock provider，斷言 `elapsed < 1.0`），非 50 併發、非 p95

`agent/tests/test_cr_0196_reply_latency.py:90-96`

```python
    t0 = time.monotonic()
    out = await loop._process_message(msg, session_key="locksmart:userLatency")
    elapsed = time.monotonic() - t0
    assert out is not None
    assert elapsed < 1.0, (
        f"turn 耗時 {elapsed:.2f}s —— 記憶抽取（2s）被算進客人的等待時間了"
    )
```

該測試於本次批次執行中通過。

---

## 判定所需的前置條件

要把此 TC 從「無法靜態判定」推進到可判定，需要：可運行的 agent 與 LINE 通道、可用的 LLM 供應商憑證、針對 LINE 通道的壓測腳本（現有 `loadtest/` 不涵蓋），以及施加 50 併發的授權。
