# SLA 與可用性規格書

**文件編號：** SPEC-SLA-001
**版本：** 1.0
**日期：** 2026-04-04
**狀態：** Draft
**關聯缺口：** GAP Analysis -- 99.5% vs 95% uptime 目標差異達 10 倍，且無任何 SLA 文件

---

## 背景

缺口分析報告指出，平台各子系統的可用性目標存在顯著差異（AI 客服 99.5% vs 管理後台 95%），但目前完全沒有正式的 SLA 定義文件。不同子系統的業務關鍵性不同，需要分層定義可用性目標、監控機制與降級策略，才能在合約談判、架構設計與日常維運中有明確依據。

---

## 1. SLA 分層定義

根據各子系統的業務關鍵性與使用者影響範圍，定義四個可用性層級：

| Subsystem | Target Uptime | 每月最大停機時間 | Response Time | 層級 |
|-----------|--------------|----------------|---------------|------|
| AI Customer Service (LINE Bot) | 99.5% | 3.6 小時 | < 5 seconds | Tier-1 |
| Dispatch System | 99.0% | 7.2 小時 | < 10 seconds | Tier-2 |
| Admin Panel | 95.0% | 36 小時 | < 3 seconds | Tier-3 |
| Data Pipeline (ETL) | 90.0% | 72 小時 | batch processing | Tier-4 |

### 1.1 定義說明

- **Uptime 計算方式：** `(總分鐘數 - 非計畫停機分鐘數) / 總分鐘數 * 100%`
- **排除項目：** 預定維護窗口（見第 5 節）不計入停機時間
- **量測週期：** 按自然月計算，每月 1 日 00:00 UTC+8 至月底 23:59 UTC+8
- **量測來源：** 以外部監控服務（見第 2 節）的探測結果為準，非內部 log

### 1.2 層級設計理由

- **Tier-1 (99.5%)：** AI 客服是終端客戶的唯一入口，停機直接等於業務停擺。LINE Bot 無法使用時客戶無法報修、無法取得進度，影響品牌信任。
- **Tier-2 (99.0%)：** Dispatch System 影響師傅派工效率，但短暫停機可由管理員手動調度補救。
- **Tier-3 (95.0%)：** Admin Panel 為內部工具，使用者為管理員，可容忍較長的維護窗口。
- **Tier-4 (90.0%)：** ETL pipeline 為批次處理，延遲數小時不影響即時業務。

---

## 2. 監控架構

### 2.1 Health Check Endpoints

所有服務必須實作以下標準化健康檢查端點：

| Endpoint | 檢查範圍 | 正常回應 | 異常回應 |
|----------|---------|---------|---------|
| `GET /health` | 服務本身是否存活 | `200 {"status": "ok"}` | `503 {"status": "unhealthy"}` |
| `GET /health/llm` | LLM provider 連線狀態 | `200 {"status": "ok", "provider": "openai", "latency_ms": 320}` | `503 {"status": "degraded", "fallback": true}` |
| `GET /health/db` | Cloud SQL 連線池狀態 | `200 {"status": "ok", "pool_active": 5, "pool_idle": 15}` | `503 {"status": "unhealthy", "error": "connection_timeout"}` |
| `GET /health/redis` | Redis 連線狀態 | `200 {"status": "ok", "latency_ms": 2}` | `503 {"status": "unhealthy"}` |

### 2.2 外部 Uptime 監控

- **工具選擇：** UptimeRobot（免費方案 5 分鐘間隔）或 Pingdom（付費方案 1 分鐘間隔）
- **探測目標：** `/health` endpoint，從外部公網發起
- **探測頻率：** Tier-1 服務每 1 分鐘，Tier-2/3 每 5 分鐘，Tier-4 每 15 分鐘
- **探測區域：** 至少包含亞太區（東京或新加坡）節點
- **SLA 報告來源：** 以外部監控服務的月度報告為 uptime 量測依據

### 2.3 LLM 可用性監控

採用 circuit breaker pattern：

```
狀態轉換：
  CLOSED (正常) → 連續 3 次 LLM 呼叫失敗 → OPEN (斷路)
  OPEN → 等待 30 秒 → HALF-OPEN (試探)
  HALF-OPEN → 1 次成功 → CLOSED
  HALF-OPEN → 1 次失敗 → OPEN
```

- Circuit breaker 開啟時自動切換至 fallback 模式（見第 3 節）
- 記錄每次狀態轉換事件至 structured log

### 2.4 Database 監控

- **Connection pool：** 監控 `pool_active`、`pool_idle`、`pool_waiting` 指標
- **告警閾值：** `pool_active / pool_max > 80%` 觸發 P1 告警
- **Replica failover：** Cloud SQL 啟用 high availability 配置，自動 failover 至 standby replica
- **慢查詢：** 超過 2 秒的查詢記錄至 slow query log，每日審查

### 2.5 核心 Metrics

| Metric | 說明 | 告警閾值 |
|--------|------|---------|
| `response_time_p99` | 第 99 百分位回應時間 | > 8 seconds |
| `error_rate` | HTTP 5xx 比率（5 分鐘滑動窗口） | > 5% |
| `llm_latency` | LLM API 呼叫延遲（p95） | > 10 seconds |
| `llm_fallback_rate` | 觸發 fallback 的比率 | > 20% |
| `db_connection_pool_usage` | 連線池使用率 | > 80% |
| `redis_hit_rate` | Redis cache 命中率 | < 70% |

---

## 3. 降級策略 (Graceful Degradation)

核心原則：服務不可因單一依賴故障而完全停擺。每個外部依賴都必須有 fallback 路徑。

### 3.1 LLM 不可用

**觸發條件：** Circuit breaker 進入 OPEN 狀態

**降級行為：**
1. 停止向 LLM provider 發送請求
2. 切換至 template-based SOP 回應模式
3. 從本地 SOP 知識檔載入預設回應：
   - 一般客服場景：`SOP-CS-001.json`（標準客服流程）
   - 緊急場景：`SOP-EMERGENCY-001.json`（緊急應變流程）
   - 硬體問題：`SOP-HW-001.json`
   - 派工場景：`SOP-DISPATCH-001.json`
4. 回應中附加提示：「目前為簡化服務模式，如需進一步協助請稍後再試或聯繫客服專線」
5. 記錄所有 fallback 期間的對話，待 LLM 恢復後可供人工審查

**影響範圍：** AI 對話品質下降，但客戶仍可取得基本資訊與 SOP 指引。

### 3.2 Database 不可用

**觸發條件：** Cloud SQL 連線失敗超過 3 次重試

**降級行為：**
1. 讀取操作：改從 Redis cache 取得資料
2. 允許使用最多 30 分鐘內的 stale data（過期資料）
3. 寫入操作：暫存至本地 queue，待 database 恢復後批次寫回
4. 對使用者顯示：「部分資料可能非最新狀態」

**影響範圍：** 資料可能有最多 30 分鐘延遲，但服務不中斷。新建工單等寫入操作會延遲生效。

### 3.3 Redis 不可用

**觸發條件：** Redis 連線失敗

**降級行為：**
1. 切換至 in-memory cache（process-level dictionary）
2. Cache 僅對當前 session 有效，跨 session 不共享
3. Cache TTL 縮短至 5 分鐘（避免記憶體膨脹）
4. 所有請求直接查詢 database（增加 DB 負載）

**影響範圍：** 回應速度略慢，database 負載上升。多實例部署時 cache 不一致。

### 3.4 外部 API Timeout

**觸發條件：** 第三方 API（地圖服務、簡訊服務等）回應超過設定的 timeout 閾值

**降級行為：**
1. 跳過資料補充（enrichment）步驟
2. 使用已有資料繼續處理流程
3. 將失敗的 enrichment 請求記錄至 retry queue
4. 背景重試（exponential backoff，最多 3 次）

**影響範圍：** 部分輔助資訊可能缺失（如地圖距離估算），但核心流程不受阻。

### 3.5 降級狀態總覽

```
正常模式
  |
  +-- LLM down --------> SOP template 模式（功能降級，服務不中斷）
  +-- DB down ----------> Redis read + queue write（資料延遲，服務不中斷）
  +-- Redis down -------> In-memory + direct DB（效能降低，服務不中斷）
  +-- External API down > Skip enrichment（資訊不完整，流程不中斷）
  |
  +-- LLM + DB down ----> SOP template + Redis only（嚴重降級，唯讀模式）
  +-- 全部 down --------> 靜態頁面 + 客服電話（最終 fallback）
```

---

## 4. 告警與通報

### 4.1 告警分級

| 等級 | 定義 | 觸發條件 | 回應時間 | 通報方式 |
|------|------|---------|---------|---------|
| **P0** | 服務完全中斷 | Tier-1 服務 health check 連續失敗 3 次 | 立即 | PagerDuty 電話 + LINE Notify to on-call |
| **P1** | 服務降級 | error_rate > 5% 持續 5 分鐘，或 circuit breaker OPEN | 15 分鐘內 | Slack channel alert (#ops-alerts) |
| **P2** | 指標異常 | p99 latency > 8s，或 DB pool > 80%，或 LLM fallback rate > 20% | 下次值班審查 | Dashboard warning，納入每日 review |

### 4.2 On-Call 輪班

- **輪班週期：** 每週輪換
- **值班時段：** 24/7（P0 事件）；工作日 09:00-21:00 UTC+8（P1 事件）
- **升級路徑：** On-call 工程師 15 分鐘未回應 → 自動升級至 Tech Lead → 30 分鐘未回應 → CTO

### 4.3 Incident 處理流程

1. **偵測：** 監控系統觸發告警
2. **確認：** On-call 工程師確認告警，建立 incident ticket
3. **通報：** 依告警等級通知相關人員
4. **處理：** 執行對應的 runbook（每個 P0 場景必須有預寫的 runbook）
5. **恢復：** 確認服務恢復，通知利害關係人
6. **Postmortem：** P0/P1 事件必須在 48 小時內完成事後檢討報告

---

## 5. 合約附件建議

### 5.1 建議合約條文

> AI 客服子系統（LINE Bot）目標每月可用性為 99.5%，以外部 health check 監控服務量測為準，排除預定維護窗口期間。

> 各子系統可用性目標依本規格書第 1 節定義之分層標準執行。

> 如單月可用性低於目標值，乙方應於下月提交根因分析報告及改善計畫。連續兩個月未達標，甲方得要求服務費用減免。

### 5.2 預定維護窗口 (Scheduled Maintenance Window)

- **時段：** 每週二 02:00 - 04:00 UTC+8
- **頻率：** 每週一次，需要時使用
- **提前通知：** 至少 24 小時前通知
- **內容範圍：** 系統更新、database migration、安全性修補
- **計算方式：** 維護窗口內的停機不計入 SLA downtime

### 5.3 不可抗力條款 (Force Majeure)

以下情況不計入 SLA 違約：

- **LLM Provider 中斷：** OpenAI / Anthropic / Google 等 LLM 供應商服務中斷，超出平台控制範圍
- **雲端平台故障：** GCP region-level 故障
- **LINE Platform 故障：** LINE Messaging API 服務中斷
- **法規或政策變更：** 因法規要求而必須緊急關閉服務
- **自然災害、網路骨幹中斷**等傳統不可抗力事件

平台有責任在 LLM provider 中斷時啟動降級策略（見第 3 節），使核心服務維持運作。

---

## 6. 容量規劃

### 6.1 當前架構 (V1.0)

- **Compute：** 單一 GCP Compute Engine instance
- **Database：** Cloud SQL for PostgreSQL（含 pgvector extension）
- **Cache：** Cloud Memorystore for Redis
- **瓶頸風險：** 單點故障（single point of failure）、無水平擴展能力

### 6.2 擴展觸發條件

| 觸發指標 | 閾值 | 應對動作 |
|----------|------|---------|
| Concurrent sessions | > 500 | 水平擴展（增加 instance） |
| Response time p99 | > 8 seconds | 水平擴展 + LLM request 優化 |
| DB connection pool usage | > 80% 持續 10 分鐘 | 增加 connection pool size 或 read replica |
| Redis memory usage | > 70% | 擴大 Redis instance 規格 |

### 6.3 V2.0 目標架構

- **Compute：** GKE (Google Kubernetes Engine) cluster with Horizontal Pod Autoscaler
- **Auto-scaling 規則：** CPU > 60% 或 memory > 70% 時自動擴展 pod 數量
- **最小 pod 數：** 2（確保高可用）
- **最大 pod 數：** 10（成本上限控制）
- **Database：** Cloud SQL with read replica + connection pooling (PgBouncer)
- **CDN：** Cloud CDN for Admin Panel 靜態資源

### 6.4 容量估算基準

以目前業務規模估算：

| 指標 | V1.0 預估量 | V2.0 預估量 |
|------|------------|------------|
| 日均對話數 | 100-300 | 1,000-3,000 |
| 同時在線 session | 10-50 | 100-500 |
| LLM API calls / day | 500-1,500 | 5,000-15,000 |
| Database storage growth | 1-2 GB / month | 5-10 GB / month |

---

## 附錄 A：相關文件

| 文件 | 路徑 |
|------|------|
| GAP 分析報告 | `docs/_gap-analysis/gap-analysis-report-cn.md` |
| SOP-CS-001 (客服流程) | `agent/harness/task/knowledge/sop/SOP-CS-001.json` |
| SOP-EMERGENCY-001 (緊急應變) | `agent/harness/task/knowledge/sop/SOP-EMERGENCY-001.json` |
| SOP-HW-001 (硬體問題) | `agent/harness/task/knowledge/sop/SOP-HW-001.json` |
| SOP-DISPATCH-001 (派工流程) | `agent/harness/task/knowledge/sop/SOP-DISPATCH-001.json` |

## 附錄 B：變更紀錄

| 版本 | 日期 | 變更內容 | 作者 |
|------|------|---------|------|
| 1.0 | 2026-04-04 | 初版建立 | -- |
| 1.1 | 2026-05-11 | 新增測試情境（6 cases，IT-0057 ~ IT-0062）| Claude (assisted) |

---

## §C. 測試情境與案例 (SLAMonitor)

<!-- TC-ID: IT-0057 -->
#### 情境 1: 正常路徑 — Tier-1 服務 uptime 計算當月達標

*   **描述**: LINE Bot Tier-1 目標 99.5%，當月實際停機 2 小時（< 3.6h 上限），uptime 應 ≥ 99.5%。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 當月共 30 天 = 43200 分鐘。
        - 注入 stop_events: `[(2026-05-08T14:00, 2026-05-08T16:00)]` = 120 分鐘 downtime。
    2.  **Act**: 呼叫 `sla_monitor.compute_uptime(subsystem="line_bot", month="2026-05")`。
    3.  **Assert**:
        - uptime = (43200-120)/43200 = 99.722%。
        - 回傳 `{"subsystem":"line_bot","tier":1,"target":99.5,"actual":99.722,"sla_met":true}`。
        - 無 alert 發出。

<!-- TC-ID: IT-0058 -->
#### 情境 2: 正常路徑 — Circuit breaker 連續 3 次失敗後切換 fallback

*   **描述**: per §2.3 LLM circuit breaker，CLOSED → 連 3 次失敗 → OPEN → 啟用 fallback。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Circuit state=CLOSED，連續失敗計數=0。
        - Mock LLMGateway 連續 3 次回 timeout。
    2.  **Act**: 呼叫 3 次 LLMGateway，每次都收到 timeout。
    3.  **Assert**:
        - 第 3 次後 state=OPEN，fallback mode 啟用。
        - structured log 含 `circuit_breaker.transition`，from=CLOSED, to=OPEN。
        - 第 4 次呼叫不再嘗試 LLM，直接走 fallback 路徑。

<!-- TC-ID: IT-0059 -->
#### 情境 3: 邊界情況 — uptime 剛好等於 Tier-1 上限 99.5% 視為達標

*   **描述**: 停機剛好 3.6 小時時，uptime = 99.500%，per §1 應視為 `sla_met=true`（不嚴格小於）。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: 注入 216 分鐘 downtime（= 3.6h）。
    2.  **Act**: compute_uptime。
    3.  **Assert**:
        - uptime = 99.5%（exact）。
        - `sla_met=true`。
        - 與 `downtime=217min` (uptime=99.498%) 對比，後者應 `sla_met=false`。

<!-- TC-ID: IT-0060 -->
#### 情境 4: 邊界情況 — 預定維護窗口不計入停機時間

*   **描述**: per §1.1，預定維護窗口（第 5 節定義）必須排除在 downtime 計算之外。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 注入 2 個 stop_events：(維護窗口 `2026-05-08T02:00 ~ 03:00`，type=`scheduled_maintenance`) 與 (意外 `2026-05-15T14:00 ~ 16:00`，type=`incident`)。
    2.  **Act**: compute_uptime。
    3.  **Assert**:
        - 只有 incident 120 min 計入 downtime。
        - scheduled 60 min 不計。
        - 報告詳細列出 `scheduled_excluded_minutes` 與 `incident_minutes` 兩欄。

<!-- TC-ID: IT-0061 -->
#### 情境 5: 異常處理 — Health check endpoint 部分失敗仍標 degraded

*   **描述**: per §2.1，`/health` ok 但 `/health/llm` 503 → 整體狀態應 `degraded`，非 `ok`。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Mock DB ok、Redis ok、LLM 連線 timeout。
    2.  **Act**: GET /health/aggregate。
    3.  **Assert**:
        - 回 503 `{"status":"degraded","checks":{"db":"ok","redis":"ok","llm":"unhealthy"}}`。
        - 不可回 200（即使 db/redis ok）。
        - alert 發送給 oncall（per §6）。

<!-- TC-ID: IT-0062 -->
#### 情境 6: 業務規則 — F-110 SLA Soft Alert dashboard 變紅 + 升主管（Q5=B）

*   **描述**: 派工建立到技師抵達 > 2hr → dashboard 紅色 + push 主管，per FR-0016 SLA。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - WorkOrder `wo-001` created_at=`T`，technician_arrived_at 為 null，T+2h05m。
    2.  **Act**: SLA monitor cron 在 T+2h05m 執行 `check_arrival_sla_breach()`。
    3.  **Assert**:
        - dashboard widget `wo-001` 標 `severity=red`。
        - notifications 含 1 筆 target=`operations_manager` (per ADR-0013/0022 升級路徑)。
        - 不應觸發退費（per FR-0016 V1.0 不賠償），audit_logs 含 `sla.breach.no_compensation` 標記。
