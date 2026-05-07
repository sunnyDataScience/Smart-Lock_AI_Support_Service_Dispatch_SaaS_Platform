---
title: Performance Baseline — Load / Stress / Spike Tests
phase: V-MODEL RIGHT (System Test, performance dimension)
gate: TR5 / TR7
status: SKELETON
last_updated: 2026-05-07
owners: [DevOps, Tech Lead]
---

# Performance Baseline — Load / Stress / Spike Tests

> **狀態**: 骨架文件（SKELETON）— SLA 目標、測試場景、PT-NNN 範例就位，實際 baseline 數字待 DevOps 跑 k6 後填入。

---

## §0 Purpose

補齊 V-Model 右翼 **效能測試** 覆蓋率（**0% → 80%**），對應：

- **ISO/IEC 25010**: Performance Efficiency（Time Behaviour / Resource Utilization / Capacity）
- **ISTQB Advanced Level**: Performance Testing（Load / Stress / Spike / Soak / Volume）
- 雙北極星 → `north-star-requirements.md` 的 `QA-001`（端到端延遲）/ `QA-002`（SLA breach）

效能測試的兩大產出：
1. **Baseline 基準線** — 系統健康狀態的數字定義（p95、RPS、error rate）
2. **Capacity Plan 容量規劃** — 多少資源可承載多少流量

---

## §1 SLA Targets (per-endpoint)

| API operationId | p50 | p95 | p99 | max RPS | 對應 QA-NNN | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `createConversation` | < 80ms | < 200ms | < 500ms | 100 | QA-001 | ⚠ TBD baseline |
| `runDispatch` | < 800ms | < 2s | < 5s | 10 | QA-001 | TBD |
| `listWorkOrders` | TBD | TBD | TBD | TBD | TBD | TBD |
| `uploadEvidence` | TBD | TBD | TBD | TBD | TBD | TBD |
| ... | ... | ... | ... | ... | ... | ... |

**規範**：
- 每個 operationId 必須有 SLA；無 SLA 的端點在 spec lint 時報警（Phase 3 加入）
- `max RPS` 為單實例 baseline；水平擴展能力另列 §2.5 容量規劃

---

## §2 Test Scenarios

### 2.1 Smoke Test
- **目標**：每次部署後 5 分鐘內驗證系統「沒掛」
- **負載**：50 VU × 2 min
- **失敗條件**：error rate > 1% 或 p95 > SLA × 1.5

### 2.2 Load Test
- **目標**：驗證正常營運負載下 SLA 達標
- **負載**：500 VU × 10 min（漸增）
- **失敗條件**：任一 operationId p95 超 SLA

### 2.3 Stress Test
- **目標**：找系統破壞點（capacity ceiling）
- **負載**：1000+ VU 漸增，直到 error rate > 5%
- **產出**：breaking point 報告（VU 數 + RPS + 瓶頸資源）

### 2.4 Spike Test
- **目標**：模擬突發流量（如 LINE 廣播後 10× 湧入）
- **負載**：50 VU baseline → 突增 500 VU × 1 min → 回降
- **失敗條件**：spike 後 5 min 內 p95 未回到 baseline

### 2.5 Soak Test
- **目標**：偵測記憶體洩漏 / 連線池耗盡
- **負載**：50 VU × 4hr
- **失敗條件**：記憶體單調遞增 / DB 連線數不釋放

---

## §3 Tooling

| 工具 | 用途 | 已建置? |
| :--- | :--- | :--- |
| **k6** (open-source) | 主要負載產生器 | TBD |
| **Grafana k6 cloud** | 雲端執行 + 結果儲存 + 趨勢圖 | TBD |
| **Prometheus + Grafana** | 系統端 metrics（Cloud Run / CloudSQL） | TBD |

腳本位置（規劃中）：`tests/perf/k6/{operationId}.js`

參考：`E7x--test-plan-and-readiness.md` §5.2 已定義 k6 baseline 框架。

---

## §4 Cost Cap — Vertex AI Budget

效能測試會大量呼叫 Gemini（agent + judge），**必須** 設定預算上限避免燒錢：

| 項目 | 月度上限 | 觸發動作 |
| :--- | :--- | :--- |
| Vertex AI nightly perf test | $50/month | 超過 80% → 告警；100% → 停 nightly job |
| ad-hoc stress test | $20/event | 需 Tech Lead 預核 |

對應：`E7x--test-plan-and-readiness.md` §8.4 預算控制。

---

## §5 PT-NNN Matrix

| PT-ID | 場景 | 工具 | 對應 QA-NNN | 對應 operationId | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| PT-001 | createConversation smoke @ 50 VU × 2min | k6 | QA-001 | createConversation | ⚠ TBD baseline |
| PT-002 | TBD（runDispatch load @ 500 VU） | k6 | QA-001 | runDispatch | TBD |
| PT-003 | TBD（spike test — LINE 廣播模擬） | k6 | QA-001 | createConversation | TBD |
| PT-NNN | TBD | TBD | TBD | TBD | TBD |

**規範**：
- ID 格式：`PT-NNN`
- 每個 SLA target 至少 1 條 PT；高風險端點（dispatch / payment）至少含 load + spike + soak

---

## §6 Change Log

| 日期 | 版本 | 變更內容 | 作者 |
| :--- | :--- | :--- | :--- |
| 2026-05-07 | 0.1.0 | 骨架建立 | Claude / DevOps |
| TBD | 0.2.0 | k6 腳本上版 + baseline 數字填入 | DevOps |
| TBD | 0.3.0 | Capacity plan + 水平擴展驗證 | Tech Lead |
