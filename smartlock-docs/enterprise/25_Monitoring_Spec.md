---
title: 監控規格（Monitoring Spec）
version: 1.0
status: active
owner: 平台維運（SRE / DevOps）
last-updated: 2026-07-10
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P002_SigNoz_單一可觀測性平台.md
  - smartlock-docs/00_platform/P1/05_platform_architecture_L1.md
  - smartlock-docs/api/P1/05_architecture_and_design.md
  - smartlock-docs/agent/P1/05_architecture_and_design.md
---

# 25. 監控規格 — 可觀測性、SLI/SLO 與告警

> 讀者：SRE / DevOps / 平台維運 / 產品營運。
> 本文件回答：用什麼觀測系統？監控哪些 metrics / logs / traces？SLI 怎麼定義、SLO 目標多少、error budget 多少？告警怎麼分層？agent 的 LLM 品質怎麼觀測？
> 故障處置劇本見 [24_Runbook.md](./24_Runbook.md)；事故指標定義見 [26_Incident_Postmortem.md](./26_Incident_Postmortem.md) §9。

---

## 1. 可觀測性架構 — 雙層分工（ADR-P002）

平台可觀測性分**兩個不同層次**，互補並存、不可互相取代：

| 層 | 工具 | 涵蓋 | 開關策略 |
|---|---|---|---|
| **系統／服務層** | **SigNoz**（單一平台，OTel 一站涵蓋 trace / metric / log）| api（FastAPI）/ agent（LockCore）/ web（Next.js）/ knowledge-refinery / Kafka 事件消費 | **prod 常開**，跨全系統單一 pane |
| **Agent LLM Ops 層** | **OPIK / Comet**（prompt 追蹤、LLM trace、eval）| agent 的 LLM turn 級觀測 | **dev 必開 / prod 預設關**（可經環境旗標按需開；OPIK 耗資源）|

分工原則一句話：**SigNoz 看「服務健不健康」，OPIK 看「AI 答得好不好」**。系統監控**只用 SigNoz 單一平台**（降低維運面）；OpenObserve 保留為未來 log 量爆增時的長存選項（roadmap，不導入）。

部署位置：SigNoz 為**跨品牌集中共用元件**（ADR-P005 分層），各 per-brand bundle 的服務將 OTel 資料送往集中 SigNoz。

## 2. Instrumentation（接線計畫）

各服務接 OTel SDK（系統層 trace + metric + log）→ SigNoz：

| 服務 | SDK | 狀態 |
|---|---|---|
| api（FastAPI）| OTel Python（auto-instrument FastAPI + psycopg）| 🔜 規劃中（Phase 1）|
| agent（LockCore）| OTel Python（aiohttp + turn 級 span）| 🔜 規劃中（Phase 1）|
| web（Next.js）| OTel JS（server side）| 🔜 規劃中 |
| knowledge-refinery | OTel Python | 🔜 規劃中（隨 ADR-P001 服務落地）|
| Kafka | 事件消費 lag exporter | 🔜 規劃中（隨 ADR-P007 Phase 3）|
| **agent → OPIK** | OPIK SDK：消費既有 `OPIK_API_KEY` / `OPIK_WORKSPACE` secret，LLM call 送 trace / prompt / eval + 環境旗標（dev 開 / prod 關）| 🔜 規劃中（Phase 1）|

接線前的過渡觀察手段（現行可用）：Cloud Run 應用日誌、api `/health`（ok/degraded）、平台 console「維運監控」紅綠燈（跨品牌 `/health` fan-out，30s 輪詢 / 單目標逾時 3s，即時快照不存歷史）。

## 3. 三支柱：Metrics / Logs / Traces

| 支柱 | 規格 |
|---|---|
| **Metrics** | OTel metric → SigNoz；命名遵循 `<domain>_<name>_<unit>`；核心 SLI 見 §4 |
| **Logs** | 結構化 JSON + `request_id`（api `RequestIdMiddleware` 注入）；等級：ERROR 進告警評估、INFO 供查案；保留期 `[待確認]` |
| **Traces** | 分散式追蹤關鍵鏈：LINE webhook → agent turn → `/internal/*` → api service → DB；WS publish 鏈；LINE push outbox 鏈 |

**PII scrubbing（硬性）**：trace / log 進 SigNoz 前必須遮蔽 PII（電話、地址、LINE user id 雜湊化）；OPIK 的 prompt / trace 含對話原文，屬 PII 敏感面——dev 環境使用測試資料，prod 開啟 OPIK 前須先過 PII 遮蔽評估（詳見 [13_Security_Architecture.md](./13_Security_Architecture.md)）。〔標注 2026-07-10：api 面已落地——feat/otel-pii-scrub 之 `scrub_text` + 出站包裝器（2026-07-10）；agent / OPIK 面仍待（排程待業主）〕〔標注 2026-07-10（續）：agent／refinery 面亦已落地（CR-0156，scrub 同源複製）；OPIK 為 opt-in 接線——prod 開啟前仍須過本節 PII 遮蔽評估（OPIK_API_KEY 未配置＝不上報）〕

## 4. 系統層 SLI dashboard（SigNoz）

權威 SLI 清單（ADR-P002 §5）——五個核心面板：

| SLI | 定義 | 對應 Runbook |
|---|---|---|
| **LINE push 成功率** | `line_push ok / (ok + failed)`（outbox worker）| [24](./24_Runbook.md) RB-06 |
| **WS 連線數 / 推播延遲** | 各頻道活躍連線數；publish → client 收到延遲（同實例目標 < 1s，NFR-PERF-02）| RB-02 |
| **Vertex 延遲 P99** | LLM call 完成時間 P99（含逾時 / sentinel 率）| RB-04 |
| **DB P95** | api → Postgres 查詢延遲 P95（三庫分列）| RB-01 / RB-05 |
| **派工事件 lag** | 事件產生 → 消費完成延遲（cron / outbox；Kafka 上線後含 consumer lag）| RB-03 |

輔助觀察點：`/health` ok/degraded、Cloud Run 實例數（>1 即 RB-02/03 風險）、escalation ingest 成功率（RB-09）。

## 5. SLO 與 error budget

> SLO 分兩檔位：**契約下限**（對客戶承諾，違反即合約風險）與**營運目標**（內部自我要求，違反燒 error budget 不違約）。

### 5.1 核心 SLO

| # | SLI | 契約下限 | 營運目標 | 量測窗 |
|---|---|---|---|---|
| SLO-1 | 系統 Uptime（`1 − 5xx率`）| ≥ 95% | ≥ 99.5% | 30d rolling |
| SLO-2 | LINE AI 首回應 latency | — | p95 < 5s / p99 < 8s | 30d rolling |
| SLO-3 | Chatbot 回覆率（含 fallback 話術）| — | ≥ 99% 於 5s 內有回 | 30d rolling |
| SLO-4 | RAG 檢索全路徑 latency | — | p95 < 8s 🔜（語義 RAG 層建成後生效）| 30d rolling |
| SLO-5 | 後台（Admin）頁面載入 | — | p95 < 2s | 30d rolling |
| SLO-6 | LINE webhook 成功率 | — | ≥ 99.9% | 30d rolling |
| SLO-7 | WS 推播延遲（同實例）| — | < 1s | 事件級 |
| SLO-8 | 派工回應 SLA compliance（一般件 10min / 急件 5min 內回應）| ≥ 95% | ≥ 95% | 月 |
| SLO-9 | 事件 / outbox lag | — | p99 ≤ 30s | 小時級 |

讀取類 API p95 < 300ms（NFR-PERF-01）為工程目標，`[待確認]` 無負載實測 baseline，暫不列 SLO。

### 5.2 Error budget

- **預算**：以營運目標 99.5% 計，30 天可容忍不可用 **3.6h**；以契約下限 95% 計為 36.5h/月（僅作合約護欄，不作營運預算）。
- **Burn rate 告警三層**（Google SRE workbook）：1h 燒 2% 預算（14.4x）→ Critical；6h 燒 5%（6x）→ Warning page；24h 燒 10%（3x）→ Warning 通道。
- **政策**：月度預算消耗 > 50% → 暫緩高風險部署；> 75% → 凍結 feature 部署（只留 rollback / hotfix）；耗盡 → halt-deployment 至下月或業主 override。重置週期 = 日曆月。

## 6. 告警規則與分層

| 層 | 觸發 | 路由 | 回應 SLA |
|---|---|---|---|
| **Critical** | P0 事件：Uptime 契約線告急、LINE 主入口全斷、跨租戶洩漏疑慮、fast-burn 14.4x | on-call（24/7）| MTTA ≤ 15 min |
| **Warning** | SLO burn 中速、單一 SLI 持續超標（如 Vertex P99 > 門檻 10min）、cron lag、drift 偵測 | 團隊通道 | 上班 ≤ 15 min / 非上班 ≤ 30 min |
| **Info** | budget 50% 標記、每週 SLI 回顧、部署後觀察正常 | 儀表板 / 週會 | 週期性檢視 |

規則設計原則：**每條告警必可動作**——附 Runbook 劇本連結（RB-01~09）+ first responder 動作；不設無人處理的 vanity alert。告警發送工具 `[待確認]`（SigNoz alert channel 對接目標待定；升級鏈以角色定義，見 [26](./26_Incident_Postmortem.md) §4）。〔標注 2026-07-10：過渡告警鏈已實作——`scripts/ops/` check_monitors_health → classify_severity → PagerDuty / Slack + `monitors-health.yml` CI cron；正式收編（工具定案）待業主〕

範例規則（SigNoz alert）：

| 規則 | 條件 | 層級 → 劇本 |
|---|---|---|
| AI 首回應退化 | p95 > 8s 持續 10min | Warning → RB-04 / RB-01 |
| LINE push 失敗 | 成功率 < 99% rolling 1h | Warning → RB-06 |
| webhook 入站歸零 | 5min 無 inbound | Critical → RB-06 |
| DB degraded | `/health` degraded 持續 5min | Critical → RB-05 |
| 事件 lag | p99 > 120s | Critical → RB-03 |
| 實例數異常 | api 實例 > 1 | Warning → RB-02/03 |

## 7. Agent LLM Ops 觀測（OPIK）

agent 接 OPIK 送 **LLM trace / prompt / eval**（🔜 規劃中 Phase 1，接線見 §2）：

- **Trace**：每個 turn 的 LLM call 鏈（BUILD → RUN 迭代 → 工具呼叫 → 回覆），含 token 用量與延遲。
- **Prompt**：system prompt 版本（skill 摘要 + 記憶區塊）與實際送出的 messages。
- **Eval**：紅線行為評測（領域外婉拒、金錢/派工 → transfer_to_human 觸發正確率）、fallback / sentinel 率。
- **開關策略**：dev 預設開（prompt 工程與品質迭代必備）；**prod 預設關**（省資源），需要排查 AI 品質時經環境旗標臨時開啟。
- 與 SigNoz 分界：OPIK 只看 LLM 層；agent 的 HTTP / 進程健康仍走 SigNoz OTel。

## 8. 營運儀表板 🔜 規劃中

面向營運與管理層的彙總視圖（資料源 = SigNoz SLI + 事故紀錄）：

| 面板 | 內容 | 週期 |
|---|---|---|
| KPI 四週滾動 | Uptime、AI 首回應 p95、LINE push 成功率、派工 SLA compliance | 週更 |
| 事故指標 | MTTA / MTTR / incident count by severity / CFR（定義見 [26](./26_Incident_Postmortem.md) §9）| 月回顧 |
| 服務健康 | 各系統（agent/api/web/refinery/technician-platform）uptime、error rate、p95 | 即時 |
| on-call 品質 | handoff 成功率、告警可動作率（誤報率）| 月回顧 |

現行過渡：平台 console「維運監控」分頁提供跨品牌即時紅綠燈（非技術者視角）；「詳細用量」連結導向雲端監控介面（`NEXT_PUBLIC_GCP_MONITORING_URL`，未設不顯示）。

---

*本文件為 SLI/SLO 唯一定義處；Runbook 僅引用 SLI 名稱作診斷觀察點。監控範圍限於可觀測的性能 / 可用性面；安全與合規監測歸 [13_Security_Architecture.md](./13_Security_Architecture.md)。*
