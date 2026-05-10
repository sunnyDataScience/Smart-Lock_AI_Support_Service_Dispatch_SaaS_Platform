---
status: superseded
superseded_by: docs_v2/4-exploration/change-requests/CR-0003-wbs.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 重構 WBS — Tier1（多租戶 / B2B / 大型系統）

- **日期**: 2026-05-06
- **適用期間**: V1 穩定 + 業務觸發後（**未觸發前不啟動**）
- **總工作量**: ~32 週（不含 D-E 長期項）
- **配套**: [refactor-plan-tier1-2026-05-06.md](./refactor-plan-tier1-2026-05-06.md) / [wbs-refactor-phase1-2-2026-05-06.md](./wbs-refactor-phase1-2-2026-05-06.md)

> **狀態圖例**：⬜ pending / 🟡 in-progress / ✅ done / 🔴 blocked / ⏸️ paused / 🔒 not-triggered

---

## 進度儀表板（Updated: 2026-05-06）

| 區段 | 工作量 | 月曆時間 | 狀態 | 觸發條件 | ADR |
|------|------|--------|------|---------|-----|
| RT-A 多租戶基礎 | 5-7 週 | 4-6 週 | 🔒 | 第 2 個租戶意願 | adr-007/008/009 |
| RT-B B2B API 化 | 11-14 週 | 6-8 週 | 🔒 | 第 1 個 OEM 簽約 | adr-010/011 |
| RT-C 韌性與隔離 | 11-14 週 | 4-6 週 | 🔒 | SLA 承諾需求 | adr-012/013 |
| RT-D 合規與大客戶 | 24-50 週 | 6-12 月 | 🔒 | SOC2/ISO 需求 | adr-014 |
| RT-E 全球化 | 48+ 週 | 12-18 月 | 🔒 | 跨地區擴張 | adr-015 |

> **🔒 not-triggered**：未觸發業務條件前，所有任務維持此狀態，不啟動執行。

---

## WBS 總覽

```
RT 重構計畫（Tier1，業務驅動）
├── RT-A 多租戶基礎（V3.0 第一步）
│   ├── RT-A.1 DB Schema 加 tenant_id + RLS
│   ├── RT-A.2 Tenant lifecycle 管理 API
│   ├── RT-A.3 LLM/memory/storage 的 tenant-aware registry
│   └── RT-A.4 Audit log 不可篡改化
├── RT-B B2B API 化
│   ├── RT-B.1 Anti-Corruption Layer（ACL）
│   ├── RT-B.2 Brand Adapter 框架
│   ├── RT-B.3 API Gateway 上線
│   ├── RT-B.4 Webhook 規範化
│   ├── RT-B.5 Idempotency Key 機制
│   └── RT-B.6 Consumer-Driven Contract Testing
├── RT-C 韌性與隔離
│   ├── RT-C.1 Bulkhead：per-tenant resource pool
│   ├── RT-C.2 Circuit Breaker：第三方 API 隔離
│   ├── RT-C.3 Saga + Outbox 完整覆蓋
│   ├── RT-C.4 CQRS：讀模型分離
│   └── RT-C.5 Backpressure + DLQ
├── RT-D 合規與大客戶
│   ├── RT-D.1 PII 加密與 Tokenization
│   ├── RT-D.2 mTLS for high-stakes API
│   ├── RT-D.3 Schema-per-tenant
│   ├── RT-D.4 SOC2 Type II 準備
│   └── RT-D.5 DR/RPO/RTO 承諾
└── RT-E 全球化與 Cell-based
    ├── RT-E.1 Cell-based Architecture
    ├── RT-E.2 Multi-region 部署
    ├── RT-E.3 Service Mesh
    └── RT-E.4 Federated Identity
```

---

## RT-A — 多租戶基礎

### 觸發條件（任一達成）
- [ ] 第二家鎖匠店或品牌商簽 LOI
- [ ] 第一個社區管委會付費意願
- [ ] 法規要求（PDPA / GDPR）

### 工作量：5-7 週 / 月曆 4-6 週 / 2 工程師

| WBS ID | 任務 | 工作量 | 依賴 | 風險 | 設計模式 | ADR | 狀態 |
|--------|------|------|------|------|---------|-----|------|
| **RT-A.1** | **DB Schema tenant_id + RLS** | 3-4 週 | Phase 1-2 完工 | 高 | Repository / RLS | adr-008 | 🔒 |
| RT-A.1.1 | 全表加 `tenant_id UUID NULL` 欄位（PR1） | 1 週 | — | 中 | — | — | 🔒 |
| RT-A.1.2 | 預設 tenant 寫入固定 UUID（migration script） | 0.5 週 | RT-A.1.1 | 中 | — | — | 🔒 |
| RT-A.1.3 | 應用層 query 強制 `WHERE tenant_id = ?`（PR2） | 1 週 | RT-A.1.2 | 高 | Repository | — | 🔒 |
| RT-A.1.4 | `tenant_id NOT NULL` + 索引（PR3） | 0.5 週 | RT-A.1.3 | 中 | — | — | 🔒 |
| RT-A.1.5 | 啟用 PostgreSQL RLS policy（PR4） | 1 週 | RT-A.1.4 | 高 | RLS | adr-008 | 🔒 |
| RT-A.1.6 | 移除應用層手動 WHERE（RLS 接管，PR5） | 0.5 週 | RT-A.1.5 | 中 | — | — | 🔒 |
| RT-A.1.7 | Tenant routing middleware（JWT → ContextVar → DB session var） | 0.5 週 | RT-A.1.5 | 中 | Tenant Routing | adr-009 | 🔒 |
| RT-A.1.8 | 跨 tenant query 阻擋測試（紅綠燈 E2E） | 0.5 週 | RT-A.1.7 | 中 | — | — | 🔒 |
| **RT-A.2** | **Tenant lifecycle API** | 1-2 週 | RT-A.1 | 中 | Saga / Outbox | — | 🔒 |
| RT-A.2.1 | `POST /api/admin/tenants`（建立 + Saga） | 0.5 週 | — | 中 | Saga | — | 🔒 |
| RT-A.2.2 | `GET /api/admin/tenants/{id}` | 0.25 週 | — | 低 | — | — | 🔒 |
| RT-A.2.3 | `PATCH /api/admin/tenants/{id}/status`（active/suspended/deactivated） | 0.25 週 | — | 中 | — | — | 🔒 |
| RT-A.2.4 | `POST /api/admin/tenants/{id}/export`（GDPR 資料匯出） | 0.5 週 | RT-A.1 | 中 | — | — | 🔒 |
| RT-A.2.5 | `DELETE /api/admin/tenants/{id}`（cascade） | 0.5 週 | RT-A.2.4 | 高 | — | — | 🔒 |
| RT-A.2.6 | TenantCreated event 發給內部訂閱者 | 0.25 週 | RT-A.2.1 | 中 | Outbox | — | 🔒 |
| **RT-A.3** | **tenant-aware registry** | 1 週 | RT-A.1 | 中 | Strategy / Factory | adr-007 | 🔒 |
| RT-A.3.1 | registry 加 `get_for_tenant(tenant_id)` 方法 | 0.25 週 | — | 中 | — | — | 🔒 |
| RT-A.3.2 | `agent/llms/__init__.py` 補 dict registry（解 D1） | 0.25 週 | — | 中 | Registry | adr-007 | 🔒 |
| RT-A.3.3 | `tenant_config` 表（JSON column）| 0.25 週 | RT-A.1 | 低 | — | — | 🔒 |
| RT-A.3.4 | per-tenant lazy build + cache | 0.25 週 | RT-A.3.1-3 | 中 | Factory + Cache | — | 🔒 |
| **RT-A.4** | **Audit log 不可篡改** | 1 週 | RT-A.1 | 中 | Hash chain | — | 🔒 |
| RT-A.4.1 | 加 `prev_hash` / `hash` 欄位 | 0.25 週 | — | 低 | — | — | 🔒 |
| RT-A.4.2 | 寫入時計算 hash chain | 0.5 週 | RT-A.4.1 | 中 | — | — | 🔒 |
| RT-A.4.3 | DB role 收斂為 append-only | 0.25 週 | RT-A.4.2 | 中 | — | — | 🔒 |

### RT-A 完工驗收
- [ ] 所有業務表 `tenant_id NOT NULL` + RLS enforced
- [ ] 跨 tenant query 在 RLS 阻擋下回 0 row（測試覆蓋）
- [ ] JWT 中 tenant_id 缺失時 middleware 拒絕請求
- [ ] LLM / memory / storage 可 per-tenant 切換
- [ ] Tenant lifecycle 6 個 API 完整可用
- [ ] Audit log hash chain 可驗證連續性
- [ ] adr-007 / adr-008 / adr-009 寫入

---

## RT-B — B2B API 化

### 觸發條件
- [ ] RT-A 完工
- [ ] 第一個 OEM 客戶簽合約（不只是 LOI）

### 工作量：11-14 週 / 月曆 6-8 週 / 2-3 工程師

| WBS ID | 任務 | 工作量 | 依賴 | 風險 | 設計模式 | ADR | 狀態 |
|--------|------|------|------|------|---------|-----|------|
| **RT-B.1** | **Anti-Corruption Layer** | 3-4 週 | RT-A.1 | 高 | ACL / Adapter | adr-010 | 🔒 |
| RT-B.1.1 | 新增 `data/pipeline/bronze_to_canonical/` 層 | 1 週 | — | 中 | ACL | — | 🔒 |
| RT-B.1.2 | 建 canonical 領域模型（FaultEvent / WarrantyPolicy / ...） | 1 週 | — | 中 | Canonical Model | — | 🔒 |
| RT-B.1.3 | Chatlock adapter | 0.5 週 | RT-B.1.2 | 中 | Adapter | — | 🔒 |
| RT-B.1.4 | Dormakaba adapter | 0.5 週 | RT-B.1.2 | 中 | Adapter | — | 🔒 |
| RT-B.1.5 | 改 `bronze_to_silver` 改讀 canonical | 0.5 週 | RT-B.1.1-4 | 中 | — | — | 🔒 |
| RT-B.1.6 | adr-010 anti-corruption-layer 寫入 | 0.25 週 | RT-B.1.1 | 低 | — | adr-010 | 🔒 |
| **RT-B.2** | **Brand Adapter 框架** | 2 週 | RT-B.1 + RP2.2/2.3 | 中 | Adapter / Hexagonal | — | 🔒 |
| RT-B.2.1 | 建 `BrandAdapter` Protocol（agent/adapters/base.py） | 0.5 週 | — | 中 | Hexagonal | — | 🔒 |
| RT-B.2.2 | Chatlock adapter 完整實作（fetch_status / push_command / ...） | 0.5 週 | RT-B.2.1 | 中 | Adapter | — | 🔒 |
| RT-B.2.3 | Dormakaba adapter 完整實作 | 0.5 週 | RT-B.2.1 | 中 | Adapter | — | 🔒 |
| RT-B.2.4 | adapters dict registry + 動態解析 | 0.5 週 | RT-B.2.2-3 | 中 | Registry | — | 🔒 |
| **RT-B.3** | **API Gateway 上線** | 2 週 | RT-A.1 | 中 | API Gateway / BFF | adr-011 | 🔒 |
| RT-B.3.1 | 選型評估（GCP API Gateway vs Apigee vs Kong） | 0.5 週 | — | 低 | — | adr-011 | 🔒 |
| RT-B.3.2 | Gateway 部署 + JWT 驗證設定 | 0.5 週 | RT-B.3.1 | 中 | API Gateway | — | 🔒 |
| RT-B.3.3 | Rate limiting per API key | 0.5 週 | RT-B.3.2 | 中 | Rate Limiter | — | 🔒 |
| RT-B.3.4 | API versioning 路由（/api/v1/、/api/v2/） | 0.25 週 | RT-B.3.2 | 低 | API Versioning | — | 🔒 |
| RT-B.3.5 | Access log → BigQuery + WAF 整合 | 0.25 週 | RT-B.3.2 | 低 | Observability | — | 🔒 |
| **RT-B.4** | **Webhook 規範化** | 2-3 週 | RT-A.1 | 中 | Webhook / Outbox / DLQ | — | 🔒 |
| RT-B.4.1 | HMAC 簽章 + key rotation 機制 | 0.5 週 | — | 中 | — | — | 🔒 |
| RT-B.4.2 | Replay 保護（timestamp + nonce + 5min 窗口） | 0.5 週 | RT-B.4.1 | 中 | — | — | 🔒 |
| RT-B.4.3 | 自動重試（指數退避，最多 5 次） | 0.5 週 | RT-B.4.1 | 中 | Retry | — | 🔒 |
| RT-B.4.4 | Outbox table + worker（取代散落 publish） | 1 週 | — | 高 | Outbox | — | 🔒 |
| RT-B.4.5 | DLQ + 重放工具（管理員 dashboard） | 0.5 週 | RT-B.4.4 | 中 | DLQ | — | 🔒 |
| RT-B.4.6 | 訂閱管理 UI（OEM 自選事件） | 0.5 週 | RT-B.4.4 | 低 | — | — | 🔒 |
| **RT-B.5** | **Idempotency Key** | 1 週 | RT-A.1 | 中 | Idempotency Key | — | 🔒 |
| RT-B.5.1 | `idempotency_keys` 表 schema | 0.25 週 | — | 低 | — | — | 🔒 |
| RT-B.5.2 | Middleware：抽 header + cache lookup | 0.5 週 | RT-B.5.1 | 中 | Idempotency | — | 🔒 |
| RT-B.5.3 | TTL cleanup job | 0.25 週 | RT-B.5.2 | 低 | — | — | 🔒 |
| **RT-B.6** | **Consumer-Driven Contract Testing** | 1-2 週 | RT-B.3 | 低 | Pact | — | 🔒 |
| RT-B.6.1 | Pact broker 建置 | 0.5 週 | — | 低 | — | — | 🔒 |
| RT-B.6.2 | 與第一個 OEM 客戶建立 contract | 0.5-1 週 | RT-B.6.1 | 中 | CDC | — | 🔒 |
| RT-B.6.3 | CI 跑 Pact verification | 0.25 週 | RT-B.6.2 | 低 | — | — | 🔒 |

### RT-B 完工驗收
- [ ] OEM 可上傳 4 類資料，全部過 ACL → canonical
- [ ] 至少 2 個 brand adapter 完整實作
- [ ] API Gateway 處理 100% 流量
- [ ] Webhook 簽章 + 重試 + DLQ 完整可用
- [ ] Idempotency Key 全變更端點生效
- [ ] Pact 與第一個 OEM 客戶端建立 contract
- [ ] adr-010 / adr-011 寫入

---

## RT-C — 韌性與隔離

### 觸發條件
- [ ] RT-A + RT-B 完工
- [ ] 第二個 OEM 客戶或第一個大型客戶簽 SLA

### 工作量：11-14 週 / 月曆 4-6 週 / 2-3 工程師

| WBS ID | 任務 | 工作量 | 依賴 | 風險 | 設計模式 | ADR | 狀態 |
|--------|------|------|------|------|---------|-----|------|
| **RT-C.1** | **Bulkhead** | 1-2 週 | RT-A.1 | 中 | Bulkhead | — | 🔒 |
| RT-C.1.1 | PostgreSQL connection pool per tier（enterprise/standard） | 0.5 週 | — | 中 | — | — | 🔒 |
| RT-C.1.2 | LLM call rate limiter per tenant | 0.5 週 | — | 中 | — | — | 🔒 |
| RT-C.1.3 | asyncio Semaphore per tenant | 0.5 週 | — | 中 | — | — | 🔒 |
| **RT-C.2** | **Circuit Breaker** | 1-2 週 | RT-B.2 | 中 | Circuit Breaker / Timeout / Fallback | — | 🔒 |
| RT-C.2.1 | 引入 `circuitbreaker` 函式庫 | 0.25 週 | — | 低 | — | — | 🔒 |
| RT-C.2.2 | LiteLLM / Vertex AI 包 circuit breaker | 0.5 週 | RT-C.2.1 | 中 | — | — | 🔒 |
| RT-C.2.3 | 各 BrandAdapter 包 circuit breaker | 0.5 週 | RT-C.2.1 | 中 | — | — | 🔒 |
| RT-C.2.4 | Fallback 策略（LLM 失敗回固定話術） | 0.25 週 | RT-C.2.2 | 低 | Fallback | — | 🔒 |
| **RT-C.3** | **Saga + Outbox 完整覆蓋** | 3-4 週 | RT-B.4 | 高 | Saga | adr-012 | 🔒 |
| RT-C.3.1 | 派工流程 Saga（建單→配技師→通知→結算） | 1.5 週 | — | 高 | Saga | adr-012 | 🔒 |
| RT-C.3.2 | 保固索賠 Saga（驗證→扣額度→通知→開發票） | 1 週 | — | 高 | Saga | — | 🔒 |
| RT-C.3.3 | 統一 Outbox table + worker | 0.5 週 | — | 中 | Outbox | — | 🔒 |
| RT-C.3.4 | adr-012 saga-orchestration 寫入 | 0.25 週 | RT-C.3.1 | 低 | — | adr-012 | 🔒 |
| **RT-C.4** | **CQRS 讀模型** | 3-4 週 | RT-A.1 | 高 | CQRS | adr-013 | 🔒 |
| RT-C.4.1 | PostgreSQL read replica 設定 | 0.5 週 | — | 中 | — | — | 🔒 |
| RT-C.4.2 | 預先聚合表（fault_stats_daily / warranty_summary_monthly） | 1 週 | — | 中 | — | — | 🔒 |
| RT-C.4.3 | 讀路徑 routing 到 replica | 1 週 | RT-C.4.1 | 高 | CQRS | — | 🔒 |
| RT-C.4.4 | Materialized view + 定時 refresh | 0.5 週 | RT-C.4.2 | 中 | — | — | 🔒 |
| RT-C.4.5 | adr-013 cqrs-read-model-strategy 寫入 | 0.25 週 | RT-C.4.3 | 低 | — | adr-013 | 🔒 |
| **RT-C.5** | **Backpressure + DLQ** | 2 週 | RT-B.4 | 中 | Backpressure / DLQ | — | 🔒 |
| RT-C.5.1 | GCP Pub/Sub 建置 | 0.5 週 | — | 低 | — | — | 🔒 |
| RT-C.5.2 | ETL 任務改走 Pub/Sub | 0.5 週 | RT-C.5.1 | 中 | — | — | 🔒 |
| RT-C.5.3 | 消費端 backpressure（不 ack 自動 throttle） | 0.5 週 | RT-C.5.2 | 中 | Backpressure | — | 🔒 |
| RT-C.5.4 | DLQ + 管理員 dashboard | 0.5 週 | RT-C.5.2 | 中 | DLQ | — | 🔒 |

### RT-C 完工驗收
- [ ] 模擬一個 tenant 流量爆 10x，其他 tenant 不受影響
- [ ] 模擬 LLM API 故障，circuit breaker 5s 內斷路 + fallback
- [ ] 派工 Saga 失敗任一步驟可正確 compensate
- [ ] CQRS 讀模型查詢 p95 < 500ms
- [ ] SLA dashboard 上線，承諾 99.9% uptime
- [ ] adr-012 / adr-013 寫入

---

## RT-D — 合規與大客戶

### 觸發條件
- [ ] RT-C 完工
- [ ] 大型客戶要求 SOC2 / ISO 27001 認證
- [ ] 進入受監管市場（金融機構鎖具、醫療場域）

### 工作量：24-50 週 / 月曆 6-12 月 / 2-3 工程師 + 外部稽核

| WBS ID | 任務 | 工作量 | 依賴 | 風險 | 設計模式 | ADR | 狀態 |
|--------|------|------|------|------|---------|-----|------|
| **RT-D.1** | **PII 加密 + Tokenization** | 3-4 週 | RT-A.1 | 中 | Encryption / Tokenization | adr-014 | 🔒 |
| RT-D.1.1 | DB 欄位加密（pgcrypto，phone/address/email） | 1-2 週 | — | 中 | — | — | 🔒 |
| RT-D.1.2 | 報表 Tokenization（給 OEM `u_xxx`） | 1 週 | — | 中 | — | — | 🔒 |
| RT-D.1.3 | KMS 整合（GCP KMS / Vault） | 1 週 | — | 中 | — | — | 🔒 |
| **RT-D.2** | **mTLS for high-stakes API** | 2-3 週 | RT-B.3 | 中 | mTLS | — | 🔒 |
| RT-D.2.1 | 工單派發 / 保固扣款 API 改 mTLS | 1 週 | — | 中 | — | — | 🔒 |
| RT-D.2.2 | 客戶端 cert 簽發系統 | 1 週 | — | 中 | — | — | 🔒 |
| RT-D.2.3 | Cert revocation 機制 | 0.5 週 | RT-D.2.2 | 中 | — | — | 🔒 |
| **RT-D.3** | **Schema-per-tenant** | 4-6 週 | RT-A.1 | 高 | Schema-per-tenant | — | 🔒 |
| RT-D.3.1 | 自動 schema migration runner | 2 週 | — | 高 | — | — | 🔒 |
| RT-D.3.2 | 大型 OEM 升級為獨立 schema | 1-2 週 | RT-D.3.1 | 高 | — | — | 🔒 |
| RT-D.3.3 | 跨 schema query 抽象層 | 1 週 | RT-D.3.1 | 中 | — | — | 🔒 |
| **RT-D.4** | **SOC2 Type II 準備** | 12-24 週 | RT-D.1-3 | 高 | — | — | 🔒 |
| RT-D.4.1 | 流程文件化 | 4 週 | — | 中 | — | — | 🔒 |
| RT-D.4.2 | 稽核日誌完整性 | 2 週 | RT-A.4 | 中 | — | — | 🔒 |
| RT-D.4.3 | 控制矩陣建立 | 2 週 | — | 中 | — | — | 🔒 |
| RT-D.4.4 | 第三方稽核公司合作 | 8-16 週 | RT-D.4.1-3 | 高 | — | — | 🔒 |
| **RT-D.5** | **DR / RPO / RTO** | 4-8 週 | — | 中 | — | — | 🔒 |
| RT-D.5.1 | PostgreSQL PITR 設定 | 1 週 | — | 中 | — | — | 🔒 |
| RT-D.5.2 | 跨 region 備援 | 2 週 | RT-D.5.1 | 中 | — | — | 🔒 |
| RT-D.5.3 | 季度 DR drill | 1-2 週/季 | RT-D.5.2 | 中 | — | — | 🔒 |

### RT-D 完工驗收
- [ ] PII 全欄位加密 + 報表 tokenize
- [ ] mTLS 在 high-stakes API 上線
- [ ] 至少一個大型 OEM 在獨立 schema
- [ ] SOC2 Type II 報告獲得
- [ ] RPO ≤ 15min / RTO ≤ 1h 演練通過
- [ ] adr-014 寫入

---

## RT-E — 全球化與 Cell-based（超大規模）

### 觸發條件
- [ ] RT-D 完工
- [ ] 跨地區擴張需求（東南亞 / 北美）
- [ ] 單區 cluster 達 capacity 上限

### 工作量：48+ 週 / 月曆 12-18 月 / 4-5 工程師

| WBS ID | 任務 | 工作量 | 依賴 | 設計模式 | ADR | 狀態 |
|--------|------|------|------|---------|-----|------|
| **RT-E.1** | **Cell-based Architecture** | 16-24 週 | RT-D.3 | Cell-based | adr-015 | 🔒 |
| RT-E.1.1 | Cell router 在 API Gateway 層 | 4 週 | — | — | — | 🔒 |
| RT-E.1.2 | 每大型 OEM 獨立 cell（DB + service shard） | 8-12 週 | RT-E.1.1 | — | — | 🔒 |
| RT-E.1.3 | Cross-cell 通訊抽象 | 4 週 | RT-E.1.2 | — | — | 🔒 |
| RT-E.1.4 | adr-015 cell-based-routing | 0.5 週 | RT-E.1.1 | — | adr-015 | 🔒 |
| **RT-E.2** | **Multi-region 部署** | 12-24 週 | RT-D.5 | — | — | 🔒 |
| RT-E.2.1 | GCP 多 region 設定 | 2 週 | — | — | — | 🔒 |
| RT-E.2.2 | Cloud Spanner 或 Yugabyte 評估 + 遷移 | 8-12 週 | RT-E.2.1 | — | — | 🔒 |
| RT-E.2.3 | Data residency 控制 | 4 週 | RT-E.2.2 | — | — | 🔒 |
| **RT-E.3** | **Service Mesh** | 8-12 週 | RT-E.2 | Service Mesh | — | 🔒 |
| RT-E.3.1 | GKE 部署 + Istio 安裝 | 4 週 | — | — | — | 🔒 |
| RT-E.3.2 | mTLS 自動化 | 2 週 | RT-E.3.1 | — | — | 🔒 |
| RT-E.3.3 | 流量管理 / observability | 2-4 週 | RT-E.3.1 | — | — | 🔒 |
| **RT-E.4** | **Federated Identity** | 4-8 週 | — | OIDC / Token Exchange | — | 🔒 |
| RT-E.4.1 | OAuth 2.0 + OIDC 設定 | 2 週 | — | — | — | 🔒 |
| RT-E.4.2 | 與大型 OEM 的 SSO 整合 | 2-4 週 | RT-E.4.1 | — | — | 🔒 |
| RT-E.4.3 | Token Exchange | 1-2 週 | RT-E.4.1 | — | — | 🔒 |

---

## ADR 預定清單（按 Phase 觸發）

| ADR | 主題 | 觸發 Phase | 觸發任務 | 狀態 |
|-----|------|----------|---------|------|
| adr-007 | LLM registry pattern | RT-A | RT-A.3.2 | 🔒 |
| adr-008 | Multi-tenant isolation strategy | RT-A | RT-A.1.5 | 🔒 |
| adr-009 | Tenant context propagation | RT-A | RT-A.1.7 | 🔒 |
| adr-010 | Anti-corruption layer | RT-B | RT-B.1.6 | 🔒 |
| adr-011 | API Gateway selection | RT-B | RT-B.3.1 | 🔒 |
| adr-012 | Saga orchestration | RT-C | RT-C.3.4 | 🔒 |
| adr-013 | CQRS read-model strategy | RT-C | RT-C.4.5 | 🔒 |
| adr-014 | PII encryption strategy | RT-D | RT-D.1 | 🔒 |
| adr-015 | Cell-based routing | RT-E | RT-E.1.4 | 🔒 |

---

## 設計模式索引（依 Phase）

| Phase | 模式 | 主要 WBS |
|-------|------|---------|
| RT-A | Repository | RT-A.1.3 |
| RT-A | RLS（Row-Level Security） | RT-A.1.5 |
| RT-A | Tenant Routing | RT-A.1.7 |
| RT-A | Saga / Outbox（局部） | RT-A.2.1 / RT-A.2.6 |
| RT-A | Strategy / Factory + Cache | RT-A.3 |
| RT-A | Hash chain | RT-A.4 |
| RT-B | Anti-Corruption Layer | RT-B.1.1 |
| RT-B | Adapter / Hexagonal | RT-B.2 |
| RT-B | API Gateway / BFF / Rate Limiter / API Versioning | RT-B.3 |
| RT-B | Webhook / Retry / Outbox / DLQ | RT-B.4 |
| RT-B | Idempotency Key | RT-B.5 |
| RT-B | Consumer-Driven Contract（Pact） | RT-B.6 |
| RT-C | Bulkhead | RT-C.1 |
| RT-C | Circuit Breaker / Timeout / Fallback | RT-C.2 |
| RT-C | Saga（深化）/ Outbox（統一） | RT-C.3 |
| RT-C | CQRS | RT-C.4 |
| RT-C | Backpressure / DLQ | RT-C.5 |
| RT-D | Encryption-at-rest / Tokenization | RT-D.1 |
| RT-D | mTLS | RT-D.2 |
| RT-D | Schema-per-tenant | RT-D.3 |
| RT-E | Cell-based | RT-E.1 |
| RT-E | Service Mesh | RT-E.3 |
| RT-E | OIDC / Token Exchange | RT-E.4 |

---

## 依賴圖（高層）

```
Phase 1-2 (RP)
    │
    ▼
RT-A 多租戶基礎 ──┬──► RT-B B2B API 化 ──┬──► RT-C 韌性與隔離 ──► RT-D 合規 ──► RT-E 全球化
                  │                       │
                  └──► RT-A.4 Audit Hash   └──► RT-C.3 Saga
                                              RT-C.4 CQRS
                                              RT-C.5 DLQ
```

---

## 追蹤儀表板模板（每月更新，未啟動時可月度 review 是否觸發）

```
月報 — Tier1 Refactor
日期：YYYY-MM-DD

觸發狀態檢查：
- RT-A 觸發條件：[未達 / 達成]
  · 第二個租戶意願：[Y/N]
  · 法規要求：[Y/N]
- RT-B 觸發條件：[未達 / 達成]
  · OEM 簽約：[Y/N]
- RT-C 觸發條件：...
- RT-D 觸發條件：...
- RT-E 觸發條件：...

業務動向：
- [本月有什麼業務訊號可能影響觸發]

下月決策：
- 維持 🔒 / 啟動 RT-X
```

---

## 與 Phase 1-2 計畫銜接點

| RT 任務 | 依賴 Phase 1-2 任務 |
|--------|------------------|
| RT-A.1.5 RLS connection pool | RP1.C.2 pg_pool.py |
| RT-A.3 tenant-aware registry | RP1.C.5 memory dict registry |
| RT-A.1 全程 trace tenant_id | RP1.D.2 OpenTelemetry middleware |
| RT-B.2 BrandAdapter hexagonal | RP2.2/2.3 反向耦合修復 |
| RT-A.* tenant context 注入 | RP2.1 debounce 拆分（注入點清楚） |
| RT-C.3 Saga（業務流程編排） | RP2.1 orchestrator.py（基底框架） |

---

## 不啟動原則（重要！）

**未觸發業務條件前，所有 RT 任務維持 🔒 not-triggered，不啟動執行。**

每月 review 觸發狀態，僅在達成條件時將 RT-A 等高層任務從 🔒 改為 ⬜ pending → 開始排程。

過早啟動 = 過度工程 = 浪費。
