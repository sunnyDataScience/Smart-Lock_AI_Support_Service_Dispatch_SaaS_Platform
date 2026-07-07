---
title: 05 非功能需求（NFR）— Smart Lock AI 客服與派工 SaaS 平台
version: 1.0
status: active
owner: 架構師 + SRE
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P002_SigNoz_單一可觀測性平台.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P003_Casdoor_統一IdP_租戶_License.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P005~P008、ADR-P014
  - smartlock-docs/{agent,api,web,data-pipeline,knowledge-refinery,technician-platform}/P1/05_architecture_and_design.md（各系統 NFR 節）
  - smartlock-docs/{agent,api,web,data-pipeline}/P3/13_security_checklist.md（目標欄）
---

# 05 非功能需求（NFR）

## §0 分層框架與編號規則

NFR 不是「越高越好」，而是「目標 tier 與產品 tier 對齊」。本平台每項指標歸屬兩層之一：

- **合約下限（Contract baseline）**：由合約 4.4 / SOW 2.1(4) / §9 終止條款界定，**違反 = block release**。
- **營運目標（Operational SLO）**：bounded context 內自我約束，未達不擋上線但消耗 error budget。

框架對齊 ISO/IEC/IEEE 29148 + Google SRE SLI/SLO + NIST SSDF + DORA。Trade-off 軸：performance vs cost、availability vs operability、privacy vs auditability。

| 維度 | 目標 tier | 主要指標 |
|:---|:---|:---|
| Performance | 一般 SaaS | AI 首回應 5s p95 / RAG 8s p95 / Admin 2s p95 |
| Availability | 一般 SaaS / 商業關鍵 | 95% 合約下限 / 99.5% 營運目標 |
| Reliability | 商業關鍵 | LINE webhook ≥ 99.9%（含 retry + DLQ）|
| Privacy | 金流 / 醫療 tier | crypto-shredding + GDPR forget ≤ 7d |
| Auditability | 金流 tier | append-only ledger + hash chain |
| DORA | High | Lead time < 1d / CFR < 15% / MTTR < 1d |

**編號規則**：`NFR-<屬性>-NNN`。每條 NFR 三欄必備：**目標值 / 驗證方式 / 分層**。量化目標為**設計目標值**；標 `[待確認]` 者表示尚無實測基線，量測方法以「驗證方式」欄為準。子系統內部 NFR ID（如 api `NFR-PERF-01`）與平台級指標的映射見 §13。

## §1 Performance 效能

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-Perf-001 | LINE AI 首回應 latency | p95 < 5s（V1）/ p99 < 8s | k6 load 50 concurrent（實測 `[待確認]`）| 營運目標 |
| NFR-Perf-002 | 案例庫向量搜尋 | p95 < 3s | benchmark（HNSW m=16, ef_construction=64）| 營運目標 |
| NFR-Perf-003 | RAG pipeline 端到端 | p95 < 8s | benchmark | 營運目標 |
| NFR-Perf-004 | 品牌後台頁面（Admin）| p95 < 2s | RUM | 營運目標 |
| NFR-Perf-005 | 讀取類 API 回應 | p95 < 300ms（設計目標；實測 `[待確認]`）| APM（SigNoz）| 營運目標 |
| NFR-Perf-006 | WS 推播延遲（事件 → 訂閱者）| < 1s（同實例）；跨實例經 Redis pub/sub（🔜 規劃中）| 整合測試 + APM | 營運目標 |
| NFR-Perf-007 | OHS 派工媒合 `POST /technicians:match` | p95 < 300ms（設計目標；實測 `[待確認]`）| k6 + read replica 路由驗證 | 營運目標 |
| NFR-Perf-008 | 派工推播（指派事件 → 技師收到）| < 2s（跨 Kafka + WS）| 端到端整合測試 | 營運目標 |
| NFR-Perf-009 | Outbox → 事件骨幹 lag | p99 ≤ 30s / p99.9 ≤ 2min | metric（SigNoz）| 營運目標 |
| NFR-Perf-010 | Agent Config Studio config read（cache hit）| p99 ≤ 50ms（in-process cache, TTL 30s）| APM + k6 read benchmark | 營運目標 |
| NFR-Perf-011 | web 首次內容繪製 FCP | ≤ 3s `[待確認]` | Lighthouse / RUM | 營運目標 |
| NFR-Perf-012 | LLM 呼叫逾時上限 | 300s（`NANOBOT_LLM_TIMEOUT_S`）；超時走 fallback 話術 | 單元 + 整合測試 | 營運目標 |

**策略**：pgvector HNSW 索引；GET 共享 in-flight + 30s staleTime（web）；context governance 每輪壓縮（agent）；讀寫分離——清單/報表/媒合查詢走 read replica（ADR-P007，🔜 規劃中）；Model Orchestration Layer 集中快取/批次/平行工具呼叫（ADR-P008）。

## §2 Availability + Reliability 可用性與可靠性

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-Avail-001 | 系統 Uptime | ≥ 95%（V1）| 30-day rolling SLO | **合約下限** |
| NFR-Avail-002 | 系統 Uptime | ≥ 99.5% | 30-day rolling SLO | 營運目標 |
| NFR-Avail-003 | LINE webhook 成功率 | ≥ 99.9%（含 24h dedup + DLQ retry）| 自動化 webhook test | 營運目標 |
| NFR-Avail-004 | LINE webhook ack latency | p99 ≤ 200ms | Cloud Run autoscale + k6 burst test | 營運目標 |
| NFR-Avail-005 | Webhook autoscale | 突發流量 10x，60s 內補 instance | 自動化 burst test | 營運目標 |
| NFR-Avail-006 | Webhook 非同步處理 | 處理 > 5s → 先 ack 後 BackgroundTask 續跑 | 整合測試 | 營運目標 |
| NFR-Avail-007 | 技師平台 HA | OHS API + `lock_tech` HA（媒合不可用 = 全品牌派工受阻）| HA 演練 + failover test | 營運目標 |
| NFR-Avail-008 | Casdoor HA | IdP 為關鍵單點，HA + 備份 | HA 演練 | 營運目標 |
| NFR-Avail-009 | Kafka 事件最終一致 | 持久可重播；訂閱者當機恢復後可補投影 | 重播演練（🔜 規劃中）| 營運目標 |
| NFR-Avail-010 | 認證降級 | DB 抖動時服務不中斷（安全狀態查詢 fail-open，退回 claims-only）| chaos test | 營運目標 |
| NFR-Avail-011 | 即時通道降級 | WS 未配置/斷線 100% 靜默降級，不阻塞頁面 | E2E 測試 | 營運目標 |
| NFR-Rel-001 | Error rate | < 0.5%（5xx + business errors）| APM（SigNoz）| 營運目標 |
| NFR-Rel-002 | DLQ 處理 | 失敗事件 1h 內人工 review | runbook（[./24_Runbook.md](./24_Runbook.md)）| 營運目標 |
| NFR-Rel-003 | 案子不蒸發 | 需轉真人案件 100% 進後台問題卡（transfer 唯一出口 + deterministic 兜底）| 整合測試 + escalation 對帳 | 營運目標 |
| NFR-SLA-001 | 派工→技師抵達 SLA（soft）| > 2hr → dashboard 標紅 + push operations_manager；V1 不賠償 | dashboard widget + alert pipeline | 營運目標 |
| NFR-SLA-002 | SLA breach 邊界 | T+2:00:00 可接受；T+2:00:01 進 breach；技師主動回報延遲不發 alert 但仍標 breached | 整合測試 | 營運目標 |
| NFR-SLA-003 | SLA alert fallback | push 失敗 → retry queue + email fallback；主管離線 → 升 operations_director | runbook 演練 | 營運目標 |

**策略**：agent 錯誤外洩防線（LLM sentinel / 空回覆 → 友善話術）；旁路整合 fail-soft（對話持久化 fire-and-forget，接管查詢失敗照回）；Cloud Run min-instances=1 降冷啟；多供應商 failover（FallbackProvider，🔜 規劃中接上，ADR-P008）。

## §3 Scalability 可擴展性

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-Scal-001 | V1 併發 | ≥ 50 同時在線 | k6 load test | 營運目標 |
| NFR-Scal-002 | V2 併發 | ≥ 100 同時在線 | k6 load test | 營運目標 |
| NFR-Scal-003 | 註冊用戶容量（3-5 年）| ≥ 30 萬戶 | capacity plan | 營運目標 |
| NFR-Scal-004 | ProblemCard 累積（3-5 年）| ≥ 50 萬張 | retention plan | 營運目標 |
| NFR-Scal-005 | Evidence 儲存（3-5 年）| ≥ 30 萬件（avg 2MB）≈ 600GB | storage plan | 營運目標 |
| NFR-Scal-006 | Tenant（品牌）數 | V1: 1 / V2: 10 / V3+: 30+ | per-brand provisioning 演練 | 營運目標 |
| NFR-Scal-007 | 多品牌線性擴展 | 新增品牌 = 新 OHS 消費者 + Kafka 訂閱者；技師平台不需 per-brand 複製 | 架構驗證 + 契約測試 | 營運目標 |
| NFR-Scal-008 | 大量技師併發上線/接單不卡頓 | WS 走 Redis pub/sub 水平擴展（🔜 規劃中）| k6 WS 併發測試 | 營運目標 |

**擴展策略（ADR-P007 三層分工）**：Redis（WS fanout + 熱讀 cache + 分散式鎖 + 連線池，Phase 1）→ Postgres 讀寫分離（Phase 1/2）→ Kafka 事件骨幹（Phase 2）。水平擴展前提 = ws_hub 與 cron worker 由進程內狀態遷出（🔜 規劃中，Phase 1 交付）。

## §4 Security 安全

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-Sec-001 | 傳輸加密 | TLS 1.2+ 全站 | SSL Labs | 營運目標 |
| NFR-Sec-002 | 認證 | Casdoor OIDC 統一 token（授權碼流；token httpOnly cookie / 安全儲存）（🔜 規劃中全面 OIDC 化）| OWASP ASVS 檢核 | 營運目標 |
| NFR-Sec-003 | 授權 | 四方 RBAC resource-level enforce，**deny-by-default**；未授權寫入 100% 403；SoD 任二角色相同 → 403 | 授權矩陣測試（每敏感端點）| 營運目標 |
| NFR-Sec-004 | At-rest 加密 | AES-256（平台）+ PII 欄位 app 層 Fernet + Evidence envelope 加密（per-tenant DEK）| 平台保證 + 加密欄位掃描 | 營運目標 |
| NFR-Sec-005 | Prompt injection 攔截率 | ≥ 95% | 50 題誘導測試 | 營運目標 |
| NFR-Sec-006 | 內容過濾誤攔率 | < 1% | 100 題正常對話 | 營運目標 |
| NFR-Sec-007 | Output Guardrail | 政治 / 宗教 / 競品禁回；NTD 數字無修飾語 → regen | 50 題誘導測試 | 營運目標 |
| NFR-Sec-008 | AI Forbidden Eval | pass rate ≥ 95%（**block deploy**）| 200 題自動化，每次 deploy | **合約下限** |
| NFR-Sec-009 | 影像辨識禁用（SOW 2.1(4)）| violation count = 0 | webhook + runtime double-gate + 稽核 | **合約下限** |
| NFR-Sec-010 | webhook 驗簽 | 100% 驗 `X-Line-Signature`，失敗 400 | 單元 + 滲透測試 | 營運目標 |
| NFR-Sec-011 | 服務間認證 | agent → api `X-Internal-Token`（api 側 fail-closed、常數時間比對）；品牌 api → OHS 服務憑證（機制 `[待確認]`）| 整合測試 | 營運目標 |
| NFR-Sec-012 | 工具沙箱 | agent 客服面僅 6 工具白名單（`CS_TOOL_ALLOWLIST` 單點控管）| `test_tool_allowlist` | 營運目標 |
| NFR-Sec-013 | Secrets 管理 | GCP Secret Manager；原始碼 / env-var 零洩漏 | secret scan + audit | 營運目標 |
| NFR-Sec-014 | CVE 回應 | high ≤ 7d / critical ≤ 24h | SCA tooling | 營運目標 |

**設計本體**：身分/授權基線 = **Casdoor OIDC + RBAC enforce + deny-by-default**（ADR-P003 / P006）；enforce 鋪開採灰度——先高風險金流/派工端點（🔜 規劃中逐端點完成）。agent 三層 guardrail：輸入（prompt injection / 內容過濾）→ 行為（工具白名單 + 紅線決策樹）→ 輸出（Guardrail 三規則 + forbidden eval gate）。細項見 [./13_Security_Architecture.md](./13_Security_Architecture.md)。

## §5 Privacy 隱私

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-Priv-001 | PII 分類 | L4 sensitive（phone / address / signature）| data classification 檢核 | 營運目標 |
| NFR-Priv-002 | PII retention default | 1y | api GDPR cron + audit | **合約下限** |
| NFR-Priv-003 | RMA / 客訴 retention | +3y | retention rule 測試 | **合約下限** |
| NFR-Priv-004 | 法律相關 retention | eternal（`legal_hold=true`；解除須 ADR change）| audit + ADR 流程 | **合約下限** |
| NFR-Priv-005 | GDPR forget | ≤ 7d 執行 OR customer notice | forget 流程端到端測試 + audit | **合約下限** |
| NFR-Priv-006 | 跨租戶隔離 | 0 leakage | **一品牌一 DB 物理隔離驗證** + 三密鑰（品牌/技師/平台）隔離測試 + agent 記憶 tenant+user_id default-deny 測試 | **合約下限** |
| NFR-Priv-007 | DEK rotation | 90d | KMS schedule | 營運目標 |
| NFR-Priv-008 | Two-phase purge | T0 銷毀加密金鑰 + T+30d 硬刪 | purge phase audit（`purge_audit.entry`）| **合約下限** |
| NFR-Priv-009 | 觀測資料 PII | SigNoz / OPIK trace、log 一律 PII scrubbing | trace 抽樣稽核 | 營運目標 |
| NFR-Priv-010 | 跨系統投影最小化 | 技師工單投影僅摘要/地址/狀態/時窗/金額（不整包複製品牌資料）| 投影欄位隱私審查 | 營運目標 |

**執行機制**：GDPR forget 與 retention 硬刪由 **api GDPR cron worker** 統一執行（BR-PII-003 單一執行者原則）；two-phase purge 為隱私設計原則（先 crypto-shredding 後物理刪除）。隔離設計本體 = per-brand 物理隔離（ADR-P005 / data-pipeline ADR-003），`tenant_id` 為欄位級輔助。

## §6 Observability 可觀測性（ADR-P002）

**兩層分工、互補並存**：

1. **系統／服務層 = SigNoz（單一平台）**：OTel 一站收 api / agent / web / knowledge-refinery / technician-platform 的 trace + metric + log；prod 常開。
2. **Agent LLM Ops 層 = OPIK / Comet**：LLM trace / prompt / eval，prompt 工程與 agent 品質迭代必備；**dev 必開、prod 經環境旗標可關**（省資源）。

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-Obs-001 | OTel 接入覆蓋 | 5 個線上服務 100% 接 SigNoz | 部署檢核 | 營運目標 |
| NFR-Obs-002 | Alert MTTA | < 15min（office）/ < 30min（off-hours）| alert 演練 | 營運目標 |
| NFR-Obs-003 | Runbook 覆蓋 | 100% 關鍵 incident path | [./24_Runbook.md](./24_Runbook.md) 對帳 | 營運目標 |
| NFR-Obs-004 | Rollback 時間 | < 30min；Agent config rollback ≤ 1min（前版保留 ≥ 24h）| chaos test + runbook drill | 營運目標 |
| NFR-Obs-005 | Staged rollout（config）| canary 10% ≥ 10min → 50% ≥ 10min → 100%；每段卡 SLO（error rate / p99）超 baseline 自動 halt | staged rollout pipeline + alert | 營運目標 |

**主 SLI（SigNoz dashboard，對齊使用者體驗）**：`line_push_success_rate`、`line_webhook_ack_p99`、`ws_delivery_latency_p99`、`vertex_llm_latency_p99`、`db_query_p95`、`dispatch_event_lag_p99`（Kafka consumer lag）、`ohs_match_latency_p95`、`outbox_lag_p99_seconds`（≤ 30s，> 120s page）。

**KPI metrics（週期量測）**：`ai_accuracy_50qa`（K1, weekly）、`self_service_rate_pc_unit`（K2, weekly）、`sentiment_negative_detection_rate`（K3, weekly N=100 + monthly audit）、`pc_completeness_rate`（K4, daily）、`acceptance_sla_compliance`（K5, daily）、`ai_first_response_p95`（K6）、`uptime_30d`（K7）、`forbidden_eval_pass_rate`（K8, every deploy）、`concurrent_users_max`（K9, weekly）、`ai_proactive_human_transfer_rate`、`k1_k2_drift_7d`（AI gaming trip-wire, daily）、`abandon_rate_pc_unit`（daily）、`gdpr_forget_completion_time`（monthly）。

監控告警細節見 [./25_Monitoring_Spec.md](./25_Monitoring_Spec.md)。

## §7 Auditability 稽核性

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-Aud-001 | 全變更 audit log | append-only、JSON + trace_id、retention eternal；`audit_events` hash chain 完整性可驗證 | hash chain 驗證 job | **合約下限** |
| NFR-Aud-002 | 7 帳本 | borrow = lend；更正一律 reversal entry；reason code 制 | 帳本對帳測試 | **合約下限** |
| NFR-Aud-003 | Evidence retention | 1y / RMA+3y / eternal / GDPR ≤ 7d | retention 稽核 | **合約下限** |
| NFR-Aud-004 | Family Reviewer 紀錄 | 100% 覆核、不可篡改、SLA ≤ 24h | 覆核率報表 + hash chain（`family_reviews`）| **合約下限** |
| NFR-Aud-005 | AI 決策可追溯 | `saas.ai_decision_trace` 全量記錄；`transfer_event.rule_triggered_by` 由 deterministic engine 寫入 | trace 抽樣稽核 | 營運目標 |
| NFR-Aud-006 | Config change audit | 100% 記錄 who / when / what diff / why；retention ≥ 7y | audit log API + cron retention check | 營運目標 |
| NFR-Aud-007 | Read-side access log | 稽核員唯讀存取入同一 audit stream；flagged item full deny + log | access log 稽核 | 營運目標 |

## §8 Data Quality + Reproducibility 資料品質與可重現

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-DQ-001 | 知識來源可信度 | 100% 源自 bronze（bronze-only sourcing）；PDF 只引 URL 不抄內容 | Publisher 灌注前 source 白名單校驗 + 抽查 | **合約下限**（知識正確性紅線）|
| NFR-DQ-002 | Provenance 正確性 | silver `source`/`source_type` 由 Python 強制覆寫（防 LLM 幻覺竄改）| pipeline 單元測試 | 營運目標 |
| NFR-DQ-003 | Pipeline 冪等 | 重跑同一 bronze 不產生重複 silver 知識點 | 重跑比對測試 | 營運目標 |
| NFR-DQ-004 | 審核品質 | HITL 為品質防線；核可通過率 / 抽樣誤放率門檻 `[待確認]` | 抽樣人審 | 營運目標 |
| NFR-PUB-001 | 未核可零落地 | draft 未經 HITL 核可，0 筆寫入 pgvector / skill | Publisher gate 測試 | 營運目標 |
| NFR-PUB-002 | append-only 落地 | skill 更新只增不刪；git 可完整回溯每次落地 | git history 稽核 | 營運目標 |
| NFR-PUB-003 | references ↔ pgvector 同源 | CI 同源檢查通過（🔜 規劃中）| CI job | 營運目標 |
| NFR-PUB-004 | 語料租戶隔離 | 灌入事實必帶 `tenant_id`/brand 過濾欄，default deny | 灌注測試 | 營運目標 |
| NFR-Sch-001 | Migration 可重套 | 100% idempotent（`ADD COLUMN IF NOT EXISTS` 等）| 重套測試 | 營運目標 |
| NFR-Sch-002 | 套用真相可查 | `schema_migrations` 表為唯一真相；registry drift CI 告警（🔜 規劃中）| CI drift-check | 營運目標 |
| NFR-Sch-003 | 演進策略 | forward-only（無 down migration）；破壞性變更走新 migration + 備份還原 | 流程稽核 | 營運目標 |
| NFR-Rep-001 | Pipeline 可重現 | config-driven，同 config 產同結構輸出 | 重跑驗證 | 營運目標 |
| NFR-Rep-002 | raw → bronze 可重建 | 原始資產保存策略 `[待確認]` | 保存位置文件化 | 營運目標 |

## §9 Maintainability 可維護性

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-Maint-001 | 後端測試覆蓋率 | ≥ 70%（pytest）| coverage 報表（CI）| 營運目標 |
| NFR-Maint-002 | 供應商解耦 | LLM swap < 5 天 / IngressChannel swap < 14 天（Model Orchestration Layer：供應商 = 配置，零 SDK 耦合）| swap 演練 | 營運目標 |
| NFR-Maint-003 | OpenAPI additive-only | breaking change 需決策紀錄（ADR/DR）| schema diff CI | 營運目標 |
| NFR-Maint-004 | ADR coverage | 重大架構決策 100% 有 ADR（append-only；新決策以新 ADR 取代，不改舊文）| ADR 索引對帳 | 營運目標 |
| NFR-Maint-005 | 前端型別安全 | TypeScript strict；API 型別由 `openapi.yaml` 生成（`types/api.generated.ts`）| tsc + codegen CI | 營運目標 |
| NFR-Maint-006 | 跨系統契約測試 | 品牌 api ↔ OHS API + Kafka event schema 走 consumer-driven contract test（🔜 規劃中）| 契約測試 CI | 營運目標 |
| NFR-Maint-007 | 知識可攜性 | skill 採 Agent Skills 標準純核心 frontmatter，複製到其他 harness 直接可用 | 可攜性測試 | 營運目標 |
| NFR-Maint-008 | E2E 覆蓋 | Playwright 覆蓋關鍵營運流程（範圍 `[待確認]`）| E2E CI | 營運目標 |

## §10 Accessibility 可及性

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-A11y-001 | LINE 端 | LINE 原生 a11y | 平台保證 | 營運目標 |
| NFR-A11y-002 | 全部 Web portal（dispatch / tech / platform / landing / LIFF）| WCAG 2.2 AA | axe 自動掃描 + 人工抽測 | **合約下限** |
| NFR-A11y-003 | 對比 | ≥ 4.5:1 | 設計系統 token 檢核（[./11_Design_System.md](./11_Design_System.md)）| 營運目標 |
| NFR-A11y-004 | 鍵盤導覽 | 全功能可鍵盤操作 | E2E 鍵盤測試 | 營運目標 |
| NFR-A11y-005 | Screen reader | ARIA labels 完整 | axe + 人工抽測 | 營運目標 |

## §11 Compliance + DORA 合規與交付效能

| ID | NFR | 目標值 | 驗證方式 | 分層 |
|:---|:---|:---|:---|:---|
| NFR-Comp-001 | 合約 4.4(a) 負面情緒識別 | ≥ 90%（UAT）；連續 2 週 < 88% → block release；連續 4 週 < 85% → incident | 週抽 100 題 + 月稽核 | **合約下限** |
| NFR-Comp-002 | 合約 4.4(d) 家族覆核 | 覆核率 100% | 覆核報表 | **合約下限** |
| NFR-Comp-003 | SOW 2.1(4) 影像辨識禁用 | violation count = 0 | double-gate 稽核（同 NFR-Sec-009）| **合約下限** |
| NFR-Comp-004 | GDPR / 個資法 | forget ≤ 7d、retention 分級、visibility fail-closed（§5）| 合規測試套件 | **合約下限** |
| NFR-DORA-001 | Lead time | < 1 day | CI/CD metrics | 營運目標 |
| NFR-DORA-002 | Change Failure Rate | < 15% | release 統計 | 營運目標 |
| NFR-DORA-003 | MTTR | < 1 day | incident 統計 | 營運目標 |

## §12 Failure Modes Catalogue

> 每個 bounded context 的 failure mode + blast radius + 緩解。未盤 failure mode 即上線 = 盲飛。

| Failure Mode | 影響 SLO | Blast Radius | 緩解 |
|:---|:---|:---|:---|
| LINE webhook 失敗 | NFR-Avail-003 | 客服對話 BC | retry 3x → DLQ → 1h 內 review |
| LLM API 超時 / quota | NFR-Perf-001 | AI agent BC | timeout → sentinel → 友善話術 → 轉真人；cost ceiling + rate limit + cache |
| 主供應商（Vertex）中斷 | NFR-Perf-001 / Avail | AI agent BC | FallbackProvider 多供應商 failover（🔜 規劃中）；期間全客服降級友善話術 + 轉真人 |
| 案例庫向量索引 stale | K1 準確率 | 知識 BC | 60s 強制刷新 + nightly full reindex |
| Kafka broker 不可用 / consumer lag > 2min | NFR-Perf-009 / Avail-009 | 事件骨幹 BC（跨系統投影/結算延遲）| 事件持久可重播；lag alert + page > 120s；對帳閘門兜底 |
| OHS 媒合服務不可用 | NFR-Avail-007 | **全品牌派工受阻**（跨品牌單點）| HA + read replica；品牌側 ACL adapter 降級策略（快取候選 / 排隊重試 `[待確認]`）|
| Casdoor 不可用 | 全平台登入 | 身分 BC（跨租戶單點）| HA + 備份；token TTL 內既有 session 可續用 |
| Redis 不可用 | NFR-Perf-006 | 即時推播 BC | WS 降級輪詢；cache miss 直讀 DB |
| ws_hub 跨實例事件遺失 | NFR-Perf-006 | 即時推播 BC | min-instances=1 過渡；Redis pub/sub 遷移（🔜 規劃中）|
| cron 多實例重複執行 | 重複推播 / 告警 | 背景任務 BC | 分散式鎖（Redis，🔜 規劃中）；冪等設計 |
| Family Reviewer 缺席 | 合約 4.4(d) | SOP BC | 24h SLA；暫停 SOP publish；ChangeRequest 替補提名 |
| AI gaming K2（假自助）| K2 漂移 | KPI 量測 BC | `k1_k2_drift_7d` trip-wire + abandon counter + reopen 回退 |
| AI gaming 轉真人歸因 | 量測可信度 | KPI 量測 BC | `rule_triggered_by` 由 deterministic engine 寫入 |
| Image vision API 呼叫外洩 | SOW 2.1(4) | Security BC | webhook + runtime double-gate；violation=0 稽核 |
| 跨租戶寫入嘗試 | NFR-Priv-006 | 租戶 BC（blast radius 全平台）| 一品牌一 DB 物理隔離（連線層即不可達）+ audit |
| pricing engine down | 報價流程 | 定價 BC | admin banner + 客服手填降級；override SLI > 20% 7 天 → page |
| agent 記憶後端故障 | per-user 記憶 | 記憶 BC | SAVE try/except 包覆絕不讓 turn 失敗；Postgres `agent.*` 持久化 |
| DB 抖動（認證查詢）| NFR-Avail-010 | 認證 BC | fail-open 退 claims-only（取捨：停權撤銷延遲）；關鍵操作 fail-closed 白名單（🔜 規劃中）|

## §13 各子系統 NFR 對照矩陣

| 子系統內部 ID | 指標 | 對應平台級 NFR |
|:---|:---|:---|
| agent NFR-AVAIL-01/02 | LINE 回覆成功率 / 冷啟容忍 | NFR-Avail-003~006 |
| agent NFR-REL-01/02 | 案子不蒸發 / 記憶隔離 | NFR-Rel-003 / NFR-Priv-006 |
| agent NFR-PERF-01/02 | 首回應延遲 / LLM 逾時 | NFR-Perf-001 / NFR-Perf-012 |
| agent NFR-SEC-01~04 | 驗簽 / 工具沙箱 / 服務間認證 / 記憶 PII | NFR-Sec-010~012 / NFR-Priv-006 |
| agent NFR-MAINT-01/02 | 知識可攜 / 測試 | NFR-Maint-007 / NFR-Maint-001 |
| api NFR-PERF-01/02 | 讀 API p95 / WS 推播 | NFR-Perf-005 / NFR-Perf-006 |
| api NFR-SCAL-01/02 | 水平擴展 / 多租戶隔離 | NFR-Scal-008 / NFR-Priv-006 |
| api NFR-AVAIL-01/02 | 認證降級 / health check | NFR-Avail-010 |
| api NFR-SEC-01~03 | RBAC enforce / internal token / 密鑰隔離 | NFR-Sec-003 / NFR-Sec-011 |
| api NFR-MAINT-01/02 | 測試覆蓋 / 版本收斂 | NFR-Maint-001 / NFR-Maint-003 |
| web NFR-PERF-01~03 | FCP / 列表分頁 / WS 端到端 | NFR-Perf-011 / NFR-Perf-004 / NFR-Perf-006 |
| web NFR-AVAIL-01 | 即時降級不阻塞 | NFR-Avail-011 |
| web NFR-SEC-01~04 | token 儲存 / 路由授權 / deny-by-default / 租戶 | NFR-Sec-002/003 / NFR-Priv-006 |
| web NFR-MAINT-01~03 | TS strict / openapi 型別 / E2E | NFR-Maint-005/008 |
| data NFR-DQ-01~03 / REP / SCH-01~04 | bronze-only / 冪等 / migration | NFR-DQ-001~003 / NFR-Rep / NFR-Sch |
| data NFR-VEC-01/02 | 檢索延遲 / 命中門檻 ≥ 0.85 | NFR-Perf-002 |
| refinery NFR-DQ / PUB-01~04 / UI-01~03 | 未核可零落地 / append-only / 同源 / 隔離 / 審核服務 | NFR-DQ-004 / NFR-PUB-001~004 / NFR-Obs-001 |
| technician NFR-PERF-01/02 | OHS 媒合 / 派工推播 | NFR-Perf-007/008 |
| technician NFR-SCAL-01/02 | 技師併發 / 多品牌線性 | NFR-Scal-007/008 |
| technician NFR-AVAIL-01/02 | OHS HA / 事件最終一致 | NFR-Avail-007/009 |
| technician NFR-SEC-01~04 | OIDC / enforce / 服務憑證 / KYC 加密 | NFR-Sec-002/003/011 / NFR-Sec-004 |
| technician NFR-MAINT-01/02 | 契約測試 / 事件一致性 | NFR-Maint-006 |

---

*文件結尾 — 05_NFR v1.0 / 2026-07-07*
