# GCP 多品牌統一監控研究備忘錄 — 2026-07-04(AI-12)

> 20260702 會議 §三延伸:「一品牌一 GCP 專案」後,多店/多品牌怎麼統一監控。
> 現況:repo **零 GCP 原生監控設定**(無 alert policy/uptime check/dashboard
> as-code);既有告警只有 `scripts/ops/` 的 Slack/PagerDuty 應用層鏈路。

## 結論(推薦方向)

用 **Cloud Monitoring Metrics Scope**:建一個「監控專案」(如
`lock-ai-ops`),把各品牌專案加為 monitored projects —— 單一 Grafana 式
面板看所有品牌的 Cloud Run/Cloud SQL 指標,**不用進每個專案切來切去**。
這正是 GCP 官方對多專案架構的標準解法,也與 CR-0113 P3(SuperAdmin
console)同一個掛載點。

## 要點

1. **Metrics Scope 上限**:一個 scope 可掛 375 個 monitored projects,
   品牌數量級完全夠;掛載是 O(1) 操作(Console 或
   `gcloud monitoring metrics-scopes create`)。
2. **看什麼(MVP 五項)**:
   | 指標 | 來源 | 告警閾值(起點) |
   |---|---|---|
   | Cloud Run 5xx rate | `run.googleapis.com/request_count` | >1% 5min |
   | Cloud Run p95 latency | `request_latencies` | >1s 5min |
   | Cloud SQL CPU/連線數 | `cloudsql.googleapis.com/*` | CPU>80%、conn>80% 上限 |
   | Cloud Run 實例數/冷啟 | `container/instance_count` | 撞 MAX_INSTANCES |
   | Uptime check(各品牌 /health) | Synthetic | 連續 2 次 fail |
3. **告警路由**:Notification channel 接既有 Slack webhook(scripts/ops 已有
   應用層告警,基礎設施層補上後兩層互補);嚴重度分級可後接 PagerDuty。
4. **IaC 化**:alert policies + uptime checks 用 Terraform
   (`google_monitoring_alert_policy`)或 `gcloud monitoring policies create
   --policy-from-file=policy.yaml` 存 repo(`scripts/ops/monitoring/`),
   新品牌開站時隨 AI-3 的 brands/<brand>.env 一起套。
5. **日誌**:各專案 Cloud Logging 原地保留;需要跨品牌查詢時用
   Log Analytics(BigQuery linked dataset)聚合,MVP 不需要。
6. **成本**:Metrics Scope 本身免費;告警/內建指標免費層通常夠,
   Uptime check 每品牌 3 條內免費額度可涵蓋。

## 落地步驟(1 輪內可完成,建議 UAT 後)

1. 建 `lock-ai-ops` 專案 + Metrics Scope 掛現有 `cedar-scope-489604-g3`。
2. 寫 5 條 alert policy YAML + 每品牌 1 條 uptime check 進
   `scripts/ops/monitoring/`,`gcloud` 腳本套用(參數化 PROJECT_ID,
   對齊 brands/<brand>.env)。
3. Slack notification channel 建立 + 測一次假告警。
4. 新品牌 SOP:開專案 → 掛 scope → 套 policy(進 brands/ README 步驟)。

## 與其他工項的關係

- **CR-0113 P3(SuperAdmin console)**:Metrics Scope 面板就是 console 的
  監控頁雛形,先用 GCP Console 原生介面,不用自建。
- **AI-3(brands/<brand>.env)**:監控套用腳本吃同一份品牌參數。
- **AI-5/6**:Uptime check 對 /health 的探測同時是可用性監控與部署驗證。
