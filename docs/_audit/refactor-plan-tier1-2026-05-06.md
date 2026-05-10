---
status: superseded
superseded_by: docs_v2/4-exploration/change-requests/CR-0003-refactor-tier1-multi-tenant.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 重構計畫 — Tier1（多租戶 / B2B / 大型系統演進）

- **日期**: 2026-05-06
- **適用期間**: V1 上線穩定後 + 第一個 OEM 客戶簽約後
- **核心原則**: 業務驅動、契約先行、漸進演進；**未啟動前不寫 code**
- **配套文件**:
  - 短期重構計畫：[refactor-plan-phase1-2-2026-05-06.md](./refactor-plan-phase1-2-2026-05-06.md)
  - 源頭脈絡（audit）：
    - [code-architecture-review-2026-05-06-1521.md](./code-architecture-review-2026-05-06-1521.md) — D1 LLM registry 雙輸（對應 Phase A3 + ADR-007）
    - [consistency-matrix-2026-05-06-1521.md](./consistency-matrix-2026-05-06-1521.md) — 議長原則與判決框架
  - 多租戶設計藍本：[../02-design/platform-multi-tenant/multi-tenant-architecture.md](../02-design/platform-multi-tenant/multi-tenant-architecture.md)
  - B2B API 規格：[../02-design/specs/b2b-api-spec.md](../02-design/specs/b2b-api-spec.md)
  - Brand OEM 上傳：[../02-design/specs/brand-data-api-spec.md](../02-design/specs/brand-data-api-spec.md)

---

## Context — 為什麼要分開寫

`refactor-plan-phase1-2` 是「**清地基**」（內部品質 + 觀測），與業務強耦合，必須做。
本計畫是「**演進路線**」，**只在業務需求出現時觸發**。提早做 = 過度工程。

### 啟動門檻（任一達成即可開始 Phase A）
- 第一個 OEM 客戶簽約意向書
- 第一家連鎖鎖匠加盟需求
- 法規要求（PDPA / GDPR 認證）
- 競品逼近、需要 SaaS 化護城河

**還沒達成 → 留在 Phase 1-2，不要碰本計畫**。

---

## 全景路線圖

```
Phase A: 多租戶基礎          (4-6 週)   ── 第一個外部租戶上線
   ↓
Phase B: B2B API 化          (6-8 週)   ── OEM 客戶可自助
   ↓
Phase C: 韌性與隔離          (4-6 週)   ── SLA 可承諾
   ↓
Phase D: 合規與大客戶        (3-6 月)   ── SOC2 + 大型 OEM
   ↓
Phase E: 全球化與 cell-based (6-12 月)  ── 跨區、超大規模
```

---

## Phase A — 多租戶基礎（V3.0 第一步）

### 觸發條件
- 第二家鎖匠店或品牌商有意願使用平台
- 或：第一個社區管委會詢問

### 預期成果
- 所有業務表帶 `tenant_id`，PostgreSQL RLS 強制隔離
- JWT 帶 `tenant_id` claim，middleware 注入 ContextVar
- LLM / memory / storage 三層 backend 可依 tenant 切換
- 第一個非預設租戶可獨立運作、與預設租戶完全隔離

### 工作項

#### A1 ── DB Schema 加 `tenant_id` + RLS（最大工程）
- **範圍**：所有業務表（`users` / `conversations` / `messages` / `user_facts` / `audit_logs` / `data_corrections` / `work_orders` / `technicians` / `manuals` / `case_entries` / `problem_cards` 等）
- **遷移策略**（不可一次砍）：
  1. **PR1**：所有表加 `tenant_id UUID` 欄位（`NULLABLE` 起步），預設 tenant 寫入固定 UUID
  2. **PR2**：應用層每個 query 加 `WHERE tenant_id = ?`（middleware 強制 inject）
  3. **PR3**：所有表 `tenant_id NOT NULL` + 加索引
  4. **PR4**：啟用 PostgreSQL RLS policy，`USING (tenant_id = current_setting('app.tenant_id')::uuid)`
  5. **PR5**：移除應用層手動 `WHERE` 條件（RLS 接管）
- **設計模式**：
  - **Tenant routing**：JWT → middleware → ContextVar → DB session var
  - **Repository pattern**：所有 DB 存取走 repository，repository 內部從 ContextVar 取 tenant_id
- **配套 ADR**：
  - `adr-008-multi-tenant-isolation-strategy.md`：選定 shared DB + RLS（vs schema-per-tenant / DB-per-tenant 的權衡）
  - `adr-009-tenant-context-propagation.md`：選定 ContextVar + JWT claim（vs subdomain / header）
- **工作量**：3-4 週
- **風險**：高（schema migration 影響全表；要在 staging full backup-restore 演練）

#### A2 ── Tenant lifecycle 管理 API
- **範圍**：建租戶、停用、資料匯出（GDPR right to be forgotten）、資料移轉
- **設計模式**：
  - **Saga**：建租戶 = 建 LINE channel + 建管理員帳號 + 建預設 skill 包 + 開計費帳號（任一失敗要 compensate）
  - **Outbox**：租戶建立後發 `TenantCreated` event 給內部訂閱者（計費、監控、稽核）
- **API 端點**：
  ```
  POST   /api/admin/tenants                     # 平台 super admin 建立
  GET    /api/admin/tenants/{id}
  PATCH  /api/admin/tenants/{id}/status         # active / suspended / deactivated
  POST   /api/admin/tenants/{id}/export         # GDPR 資料匯出
  DELETE /api/admin/tenants/{id}                # 連帶觸發 RLS-aware cascade
  ```
- **工作量**：1-2 週
- **依賴**：A1

#### A3 ── LLM / memory / storage 的 tenant-aware registry
- **問題**：目前 registry 是全域單例；多租戶下不同租戶可能要不同 LLM provider
- **改法**：
  - registry 加 `get_for_tenant(tenant_id) -> Backend` 方法
  - `agent/llms/__init__.py` 補 dict registry（解決 audit D1 雙輸）
  - tenant 配置存 `tenant_config` 表（JSON column）
- **設計模式**：
  - **Strategy pattern**：每個 tenant 有自己的策略集（LLM / memory / storage / SLA / billing）
  - **Factory + Cache**：per-tenant lazy 建 instance、cache 在 ContextVar 範圍
- **配套 ADR**：
  - `adr-007-llm-registry-pattern.md`（已在 audit D1 提案）
- **工作量**：1 週
- **依賴**：A1

#### A4 ── Audit log 不可篡改化
- **問題**：目前 audit log 是普通 INSERT，可被改
- **改法**：
  - 加 `prev_hash`、`hash` 欄位形成 hash chain
  - 加 `tenant_id` 強制隔離
  - 寫入後唯讀（DB role 權限收斂）
- **工作量**：1 週
- **依賴**：A1

### Phase A 完工驗收
- [ ] 所有業務表 `tenant_id NOT NULL` + RLS enforced
- [ ] 跨 tenant query 在 RLS 阻擋下回 0 row（測試覆蓋）
- [ ] JWT 中 tenant_id 缺失時 middleware 拒絕請求
- [ ] LLM / memory / storage 可 per-tenant 切換 backend
- [ ] Tenant lifecycle 5 個 API 完整可用
- [ ] Audit log hash chain 可驗證連續性

---

## Phase B — B2B API 化

### 觸發條件
- Phase A 完成
- 第一個 OEM 客戶（品牌商）簽約

### 預期成果
- OEM 可自助上傳手冊 / 故障碼 / 韌體 / 保固條款
- OEM 可查詢自家品牌的故障統計 / 保固索賠 / 品質報告
- 平台與 OEM 之間有 webhook 雙向通信
- 第三方 SDK 文檔齊全（Postman / OpenAPI / TS / Python client）

### 工作項

#### B1 ── Anti-Corruption Layer（ACL）
- **問題**：每個 OEM 的 schema 不同，不能讓他們的 schema 滲進 domain
- **架構**：
  ```
  data/pipeline/
    ├── source_to_raw/        (既有，OEM 上傳檔案進來)
    ├── raw_to_bronze/        (既有，PDF 解析、ASR 等)
    ├── bronze_to_canonical/  (新增！ACL 層)
    │   ├── chatlock_adapter.py
    │   ├── dormakaba_adapter.py
    │   └── canonical/
    │       ├── fault_event.py     # 統一 FaultEvent dataclass
    │       ├── warranty_policy.py # 統一 WarrantyPolicy dataclass
    │       └── ...
    ├── bronze_to_silver/     (改：讀 canonical 而非 bronze)
    └── silver_to_skill/      (既有)
  ```
- **設計模式**：
  - **Anti-Corruption Layer**：所有外部資料先過 ACL 才進 silver
  - **Adapter pattern**：每個 brand 一個 adapter
  - **Canonical model**：domain 層只認 canonical，不認原始 vendor schema
- **配套 ADR**：
  - `adr-010-anti-corruption-layer.md`
- **工作量**：3-4 週
- **依賴**：A1（tenant_id 已有，因 OEM 是租戶）

#### B2 ── Brand Adapter 框架
- **目的**：未來新增品牌商只需加一個 adapter 檔
- **架構**：
  ```python
  # agent/adapters/base.py
  class BrandAdapter(Protocol):
      async def fetch_status(self, device_id: str) -> DeviceStatus: ...
      async def push_command(self, device_id: str, cmd: Command) -> Result: ...
      def parse_fault_code(self, raw_code: str) -> CanonicalFault: ...
      def validate_warranty(self, claim: dict) -> WarrantyVerdict: ...

  # agent/adapters/chatlock.py
  class ChatlockAdapter(BrandAdapter): ...

  # agent/adapters/__init__.py
  ADAPTERS: dict[str, BrandAdapter] = {
      "Chatlock": ChatlockAdapter(),
      "Dormakaba": DormakabaAdapter(),
  }
  ```
- **設計模式**：
  - **Adapter pattern** + **Strategy pattern** 結合
  - **Hexagonal Architecture**：BrandAdapter 是 driven adapter
- **工作量**：2 週
- **依賴**：B1

#### B3 ── API Gateway 上線
- **選型**：GCP API Gateway（與 Cloud Run 整合最順）；或 Apigee（更強功能）
- **能力**：
  - JWT 驗證（與 IAM 整合）
  - Rate limiting（per API key 配額）
  - API Versioning 路由（`/api/v1/*` vs `/api/v2/*`）
  - Observability（access log → BigQuery）
  - WAF / DDoS（GCP Cloud Armor 整合）
- **設計模式**：
  - **API Gateway pattern**：認證、限流、版本路由集中
  - **BFF pattern**：未來不同 portal 各自 BFF（社區管委會 portal、OEM portal、經銷商 portal）
- **配套 ADR**：
  - `adr-011-api-gateway-selection.md`
- **工作量**：2 週
- **依賴**：A1

#### B4 ── Webhook 規範化
- **目前**：`webhook-spec.md` 雛形
- **要補**：
  - HMAC 簽章 + key rotation
  - Replay 保護（timestamp + nonce + 5min 窗口）
  - 自動重試（指數退避，最多 5 次）
  - DLQ + 重放工具（管理員可手動 re-deliver 失敗 webhook）
  - 訂閱管理 UI（OEM 可選擇要訂閱哪些事件）
- **設計模式**：
  - **Webhook pattern**：簽章 + 重試 + idempotency
  - **Outbox pattern**：DB transaction 與 webhook publish 原子
  - **Dead Letter Queue**：失敗訊息隔離
- **工作量**：2-3 週
- **依賴**：A1

#### B5 ── Idempotency Key 機制
- **範圍**：所有 POST / PATCH / DELETE 端點
- **實作**：
  - Header `Idempotency-Key: <uuid>`
  - DB table `idempotency_keys`（key + tenant_id + response_hash + created_at + ttl）
  - 同一 key 重複請求直接回 cached response
- **設計模式**：
  - **Idempotency Key pattern**（仿 Stripe）
- **工作量**：1 週
- **依賴**：A1

#### B6 ── Consumer-Driven Contract Testing
- **工具**：Pact + GitHub Actions
- **流程**：
  1. OEM 客戶端寫 Pact contract（他們期望平台回什麼）
  2. 平台 CI 跑 Pact verification
  3. Break = CI 紅
- **設計模式**：
  - **Consumer-Driven Contract**
- **工作量**：1-2 週
- **依賴**：B3

### Phase B 完工驗收
- [ ] OEM 可上傳 4 類資料（manual / fault_code / firmware / warranty），都過 ACL → canonical
- [ ] 至少 2 個 brand adapter 完整實作（Chatlock + Dormakaba）
- [ ] API Gateway 處理 100% 流量、JWT 驗證、限流生效
- [ ] Webhook 簽章 + 重試 + DLQ 完整可用
- [ ] Idempotency Key 在所有變更端點生效
- [ ] Pact 與第一個 OEM 客戶端建立 contract

---

## Phase C — 韌性與隔離（SLA 可承諾）

### 觸發條件
- 第二個 OEM 客戶或第一個大型客戶簽 SLA
- 或：發生跨租戶事故（一個租戶壓垮其他人）

### 預期成果
- 跨 tenant 故障隔離（bulkhead）
- 第三方 API 故障自動斷路 + fallback
- Outbox + Saga 完整覆蓋關鍵業務流程
- 可承諾 SLA：99.9% uptime、p95 latency < 1s

### 工作項

#### C1 ── Bulkhead：per-tenant resource pool
- **改法**：
  - PostgreSQL connection pool 分 tenant（或至少分 tier：enterprise / standard）
  - LLM call rate limiter per tenant（避免一個租戶吃光配額）
  - asyncio Semaphore per tenant
- **設計模式**：
  - **Bulkhead pattern**
- **工作量**：1-2 週
- **依賴**：A1

#### C2 ── Circuit Breaker：第三方 API 隔離
- **工具**：`circuitbreaker` Python 函式庫（in-process 起步）
- **適用**：LiteLLM / Vertex AI / 各 BrandAdapter / OEM webhook receiver
- **設計模式**：
  - **Circuit Breaker pattern**
  - **Timeout pattern**（搭配）
  - **Fallback pattern**（如 LLM 失敗回固定話術）
- **工作量**：1-2 週

#### C3 ── Saga + Outbox 完整覆蓋
- **目前**：Phase A2 / B4 已有局部 Saga / Outbox
- **要補**：
  - 派工流程 Saga（建單 → 配技師 → 通知 → 結算）
  - 保固索賠 Saga（驗證 → 扣額度 → 通知 OEM → 開發票）
  - 統一 Outbox table + worker（取代散落各處的 publish）
- **配套 ADR**：
  - `adr-012-saga-orchestration.md`：選 orchestration（中央協調）vs choreography（事件驅動）
- **工作量**：3-4 週
- **依賴**：B4

#### C4 ── CQRS：讀模型分離
- **問題**：B2B 查詢（OEM 看故障統計）會壓垮 OLTP DB
- **改法**：
  - PostgreSQL read replica + 預先聚合表（`fault_stats_daily` / `warranty_summary_monthly`）
  - 寫入路徑走 master，讀取路徑走 replica
  - Materialized view + 定時 refresh（或 streaming refresh via CDC）
- **設計模式**：
  - **CQRS（Command Query Responsibility Segregation）**
- **工作量**：3-4 週
- **依賴**：A1

#### C5 ── Backpressure + DLQ
- **適用**：OEM 大量上傳手冊、品牌資料 ETL pipeline
- **改法**：
  - 訊息佇列（GCP Pub/Sub）放 ETL 任務
  - 消費端 backpressure：消費速度跟不上時不 ack，自動 throttle
  - 失敗 N 次進 DLQ，管理員 dashboard 處理
- **工作量**：2 週
- **依賴**：B4

### Phase C 完工驗收
- [ ] 模擬一個 tenant 流量爆 10x，其他 tenant 不受影響
- [ ] 模擬 LLM API 故障，circuit breaker 在 5s 內斷路、fallback 生效
- [ ] 派工 Saga 失敗任一步驟可正確 compensate
- [ ] CQRS 讀模型查詢 p95 < 500ms（vs 直查 OLTP > 5s）
- [ ] 上線 SLA dashboard，承諾 99.9% uptime

---

## Phase D — 合規與大客戶

### 觸發條件
- 大型 OEM 客戶要求 SOC2 / ISO 27001 認證
- 或：進入受監管市場（金融機構鎖具、醫療場域）

### 工作項

#### D1 ── PII 加密與 Tokenization
- DB 欄位加密（pgcrypto）：phone、address、email
- 報表 Tokenization：給 OEM 的報表用 `u_xxx` 不洩真實電話
- KMS 整合（GCP KMS / HashiCorp Vault）
- **工作量**：3-4 週

#### D2 ── mTLS for high-stakes API
- 工單派發、保固扣款這類 API 改 mTLS
- 客戶端 cert 由平台簽發、可撤銷
- **工作量**：2-3 週

#### D3 ── Schema-per-tenant（高階租戶）
- 大型 OEM 升級為獨立 schema（`tenant_chatlock` / `tenant_dormakaba`）
- 工具：自動 schema migration runner
- **工作量**：4-6 週

#### D4 ── SOC2 Type II 準備
- 流程文件、稽核日誌、控制矩陣
- 第三方稽核公司合作
- **工作量**：3-6 月（含外部稽核時間）

#### D5 ── DR / RPO / RTO 承諾
- PostgreSQL PITR + 跨 region 備援
- 演練：每季模擬 region 故障
- **工作量**：1-2 月

---

## Phase E — 全球化與 Cell-based（超大規模）

### 觸發條件
- 跨地區擴張（東南亞 / 北美）
- 單區 cluster 達 capacity 上限
- 法規要求 data residency

### 工作項

#### E1 ── Cell-based Architecture
- 每個大型 OEM / 地區獨立 cell（DB + service shard）
- Cell router 在 API Gateway 層
- 故障爆炸半徑限縮在單 cell
- **工作量**：4-6 月

#### E2 ── Multi-region 部署
- GCP 多 region（asia-east1 / asia-southeast1 / us-central1）
- Cloud Spanner（跨 region 強一致）或 Yugabyte
- **工作量**：3-6 月

#### E3 ── Service Mesh
- Istio on GKE（取代純 Cloud Run）
- mTLS 自動化、流量管理、observability
- **工作量**：2-3 月

#### E4 ── Federated Identity
- OAuth 2.0 + OIDC + Token Exchange
- 與大型 OEM 的 SSO 整合
- **工作量**：1-2 月

---

## 設計模式總覽（按 Phase）

| Phase | 主要模式 |
|-------|---------|
| A | Repository / Strategy / Factory / Saga / Outbox / Tenant Routing |
| B | Anti-Corruption Layer / Adapter / Hexagonal / API Gateway / BFF / Webhook / Idempotency / Pact |
| C | Bulkhead / Circuit Breaker / Timeout / Fallback / CQRS / Saga (深化) / Backpressure / DLQ |
| D | Encryption-at-rest / Tokenization / mTLS / Schema-per-tenant |
| E | Cell-based / Service Mesh / Federated Identity / Multi-region |

---

## ADR 預定清單

```
adr-007-llm-registry-pattern.md           (Phase A3 觸發)
adr-008-multi-tenant-isolation-strategy.md (Phase A1)
adr-009-tenant-context-propagation.md     (Phase A1)
adr-010-anti-corruption-layer.md          (Phase B1)
adr-011-api-gateway-selection.md          (Phase B3)
adr-012-saga-orchestration.md             (Phase C3)
adr-013-cqrs-read-model-strategy.md       (Phase C4)
adr-014-pii-encryption-strategy.md        (Phase D1)
adr-015-cell-based-routing.md             (Phase E1)
```

---

## 工作量總覽

| Phase | 觸發後工作量 | 工程師數 | 月曆時間 |
|-------|-----------|--------|--------|
| A 多租戶基礎 | 5-7 週 | 2 人 | 4-6 週 |
| B B2B API 化 | 11-14 週 | 2-3 人 | 6-8 週 |
| C 韌性與隔離 | 11-14 週 | 2-3 人 | 4-6 週 |
| D 合規與大客戶 | 6-12 月 | 2-3 人 + 外部稽核 | 6-12 月 |
| E 全球化 | 12-18 月 | 4-5 人 | 12-18 月 |

> Phase A→B 合計約 5-6 個月，是「可支持第一批 OEM」的最小配置。
> Phase C 是「敢承諾 SLA」的門檻。
> Phase D-E 是「進入大企業客戶 / 全球市場」的長期目標。

---

## 與 Phase 1-2（短期計畫）的銜接點

| 短期計畫項 | 為哪個 tier1 Phase 鋪路 |
|----------|-----------------------|
| P1-2 抽 pg_pool.py | A1 multi-tenant connection pool 的基礎 |
| P1-5 memory dict registry | A3 tenant-aware registry 的基礎 |
| P1-D1 結構化日誌 | tenant_id 加入 log context 的基礎 |
| P1-D2 OpenTelemetry middleware | tenant_id 加入 trace span 的基礎 |
| P1-D3 Opik per-skill cost | A 後變 per-tenant cost 的基礎 |
| P2-1 debounce 拆分 | A 的 tenant context 注入點變清楚 |
| P2-2/3 反向耦合修復 | B2 BrandAdapter 的 hexagonal 邊界基礎 |

短期計畫不是 tier1 的前置條件，但**做了短期計畫，tier1 就便宜很多**。

---

## 一句話

> 本計畫是**業務驅動的演進路線**，不是工程驅動的待辦清單。每個 Phase 觸發前都要問：「**真的有客戶需要嗎？**」沒有，就回去做 Phase 1-2、強化前端體驗、累積真實使用者數據。等業務拉力出現了，本計畫就是現成的執行手冊。
