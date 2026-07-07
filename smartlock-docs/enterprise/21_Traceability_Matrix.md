---
title: 需求追蹤矩陣（Traceability Matrix）
version: 1.0
status: active
owner: QA Lead
last-updated: 2026-07-07
upstream:
  - smartlock-docs/enterprise/04_SRS.md
  - smartlock-docs/enterprise/05_NFR.md
  - smartlock-docs/enterprise/14_ADR/
  - smartlock-docs/00_platform/P2/09_integration_data_flow.md
  - smartlock-docs/00_platform/P1/07_workorder_platform_design.md
---

# 21. 需求追蹤矩陣（Traceability Matrix）

> 本文件回答：**每條 FR ↔ 設計來源 ↔ 測試案例是否閉環？哪些 FR 尚無覆蓋（gap）？**
> FR 編號源＝[./04_SRS.md](./04_SRS.md)（唯一主鍵）；TC 編號源＝[./20_Test_Cases.md](./20_Test_Cases.md)；NFR 編號源＝[./05_NFR.md](./05_NFR.md)。

## 1. 矩陣說明

| 欄位 | 定義 |
|---|---|
| FR-ID | 04_SRS 定版之功能需求編號（`[待確認：依 04_SRS 定版]` 標示尚未定案處）|
| 設計來源 | ADR（[./14_ADR/](./14_ADR/) 及平台 ADR-P001~P014）、各系統 SDS（`../{system}/P1/05`）、[./15_SDS.md](./15_SDS.md)、[./16_API_Spec.yaml](./16_API_Spec.yaml)、[./18_DB_Design.md](./18_DB_Design.md) |
| 測試案例 | 20_Test_Cases 之 TC-ID |
| 覆蓋狀態 | ✅ 閉環（設計 + 測試皆有）｜🟡 部分（測試僅覆蓋主路徑）｜🔴 缺測試｜🔜 規劃中（功能未實作，測試待功能落地）|

**閉環判準**：P0 FR 須「≥1 happy + ≥1 負向/例外」皆綠；P1 FR 須 ≥1 案例；任何 FR 不得只有設計無測試而標 ✅。

## 2. 主追蹤表（FR ↔ 設計 ↔ 測試）

### 2.1 agent（AI 客服）

| FR-ID | 需求摘要 | 設計來源 | 測試案例 | 覆蓋 |
|---|---|---|---|---|
| FR-0001 | LINE 進線 → 對話 → 建案 | `../agent/P1/05` §7.1；ADR-P013 受保護層 | TC-CS-AI-01/02 | ✅ |
| FR-0018 | 轉真人接管（escalation）| `../agent/P1/05` §7.2；`transfer_to_human` 唯一出口 | TC-CS-AI-04/10 | ✅ |
| FR-0024 | LINE webhook 高可用（dedup + retry）| agent ADR-005（單 channel fan-out）| TC-CS-AI-09、TC-EXC-01 | ✅ |
| FR-0025 | 多模態進線（影像不辨識，僅存證）| 合約 SOW 2.1(4)；agent P3 C-05 | TC-CS-AI-07、TC-COMPLIANCE-06 | ✅ |
| FR-0026 | debounce 1.5s / dedup 24h | agent P3 C-05 / FA-05 | TC-CS-AI-08/09 | 🟡（debounce 接線 🔜 規劃中）|
| FR-0027 | 品牌 profile resolver（多租戶配置）| ADR-P013 Agent Config Studio | `[待確認：依 04_SRS 定版]` | 🔜 規劃中 |
| FR-0028 | Skill 驅動 agent（LockCore）| `../agent/P1/05` §4；agent ADR-001~003 | TC-CS-AI-03、`test_skills_loaded.py` | ✅ |
| FR-0029 | 知識庫（skill references + pgvector RAG）| ADR-P001；agent ADR-004 | TC-CS-AI-03、TC-COMPLIANCE-08 | 🟡（RAG-via-MCP 🔜 規劃中）|
| FR-0030 | AI 越權紅線（不報價/不折扣/不免保固）| agent P3 C-07/C-08；ADR-P013 domain-safety | TC-CS-AI-05/06、TC-QUOTE-02/03 | ✅ |
| FR-0032 | eval / 觀測性（OPIK LLM trace）| ADR-P002 | TC-CS-AI-05 | 🟡（OPIK 接線 🔜 規劃中）|
| FR-0034 | AI 員工憲章（永不自轉工單）| api E-04（internal ingest 只建草擬卡）| TC-WO-01 | ✅ |

### 2.2 api（派工控制平面）

| FR-ID | 需求摘要 | 設計來源 | 測試案例 | 覆蓋 |
|---|---|---|---|---|
| FR-0002 | 問題卡分診（草擬 → 確認）| `../api/P1/05` §5；00_platform/P1/07 §3 | TC-WO-01/03、TC-QUOTE-06 | ✅ |
| FR-0003 | 自動派工媒合 | ADR-P004（OHS API）；`../technician-platform/P1/05` §7.1 | TC-DISPATCH-01 | ✅ |
| FR-0004 | 手動派工 + audit | api RBAC 守衛鏈 | TC-DISPATCH-02 | ✅ |
| FR-0005 | 技師接單（事件驅動）| ADR-P007（Kafka）；ADR-P014 §2.2 | TC-DISPATCH-03/04 | 🟡（逾時自動改派 🔴 缺，見 §4 gap）|
| FR-0006 | 到場存證（GPS + 照片）| 00_platform/P1/07（evidence 表）| TC-ONSITE-01 | ✅ |
| FR-0008 | 現場加價三段式（≤500 / 501–2000 / >2000）| 00_platform/P1/07 flow DSL guard | TC-ONSITE-02/03/04/05 | ✅ |
| FR-0009 | 完工硬閘（照片≥3 / 簽名 / serial / override）| 00_platform/P1/07 §5.3 積木 precondition | TC-WO-04~07 | ✅ |
| FR-0010 | 改期 / 例外回報 | 例外框架（high_risk_hold）| TC-WO-11、TC-ONSITE-06 | ✅ |
| FR-0011 | 消費者付款 | 金流軌（ADR-P009 核心原語）| `[待確認：依 04_SRS 定版]` | 🔜 規劃中（正式金流 provider 未接，見 §4 gap）|
| FR-0012 | 月結結算 | ADR-P014 §2.1（Billing/Settlement 分離）| TC-SETTLE-01 | 🟡 |
| FR-0013 | 雙簽爭議處理 | api C-07 SoD | TC-SETTLE-06 | ✅ |
| FR-0014 | 退款（L1–L5 分層 + SoD 三維）| api C-07；13_Security_Architecture | TC-SETTLE-02~05 | ✅ |
| FR-0015 | 保固 + RMA | 保固模式引擎（起算/延長/零件）| 保固 5-mode 套件（api tests）| ✅ |
| FR-0016 | 派工 SLA（2h soft）| flow DSL `sla` 段（PT2H on_breach）| TC-WO-10 | 🟡 |
| FR-0019 | 動態 RBAC | ADR-P006（四方模型 + enforce）| TC-SEC-RBAC-01~05 | ✅（enforce 為 GA P0 條件）|
| FR-0020 | 稽核 log + hash chain + 匯出 | api E-02（audit_events hash chain）| TC-SETTLE-07 | ✅ |
| FR-0041 | 客戶/場址/裝置主檔 | 18_DB_Design | api tests（customer CRUD / 跨租）| ✅ |
| FR-0042 | 報價內外部視圖分離 | 00_platform/P1/07（quotes / quote_line_items）| TC-QUOTE-01/04/05/07/08 | ✅ |
| FR-0043 | 後台 config 治理（版本化 + staged rollout + rollback ≤1min）| ADR-P009 領域配置層 | config 套件（api tests）+ UAT S5 | ✅ |
| FR-0049 | 例外收件匣 + 核准 | 例外框架 | TC-WO-11 | 🟡（前端 inbox 頁 🔜 規劃中）|
| FR-0052 | 取消費 5 階段 | flow DSL cancelled 轉移 + 費率表 | TC-WO-12 | ✅ |
| FR-0053 | GDPR forget 全流程 | api B-09（forget v2 + T+30 cron）| TC-COMPLIANCE-01/02 | ✅ |

### 2.3 web / data-pipeline / knowledge-refinery / technician-platform / 00_platform

| FR-ID | 需求摘要 | 設計來源 | 測試案例 | 覆蓋 |
|---|---|---|---|---|
| FR-0019（web 面）| 前端路由 gate（UX 層）+ 後端唯一授權邊界 | web ADR-003；`../web/P3/13` C-03 | TC-SEC-WEB-01/02、Playwright role-ui-isolation | ✅ |
| FR-0020（web 面）| audit 後台頁 tenant-scoped | web P1/05 | Playwright audit-events spec | ✅ |
| FR-0021 | Dashboard / 報表 | web P1/05 | api reports 套件 + Playwright | 🟡 |
| FR-0022 | 消費者進度追蹤 | web P1/05 | `[待確認：依 04_SRS 定版]` | 🔴 |
| FR-0023 | 錯誤 / 離線頁 | web error boundary | web G-03 驗證 | 🟡 |
| FR-0035~0037 | 同步管線（intake / facts / 問題卡轉換）| data-pipeline P1/05（Medallion）| TC-COMPLIANCE-08、TC-SEC-PIPE-01 | 🟡 |
| FR-0038 | 問題卡 → 工單轉換 | 00_platform/P1/07 §5 | TC-WO-01/02/08/09 | ✅ |
| FR-0039 | 派工事件同步（CQRS 投影）| ADR-P014 §2.2 | TC-DISPATCH-05、TC-EXC-06 | 🟡（投影表 🔜 規劃中）|
| FR-0040 | evidence 回寫 | data-pipeline P1/05 | TC-COMPLIANCE-04 | 🟡 |
| FR-0017 / FR-0051 | SOP draft → 人審 → 發布（HITL 螺旋）| ADR-P001；`../knowledge-refinery/P1/05` | TC-COMPLIANCE-05 + UAT S3 | 🟡 |
| FR-0044 | 技師 onboarding / 停權（KYC）| ADR-P004；technician-platform P1/05 | TC-DISPATCH-06 + lifecycle 套件 | 🟡 |
| FR-0045 | 技師 AP 結算 | ADR-P014 §2.1 | TC-SETTLE-01/08 | 🟡 |
| FR-0046 | 派工小編佣金 | ADR-P014 | TC-SETTLE-08 | 🟡 |
| FR-0050 | AI 治理追溯（decision trace）| api E-04 | api ai_governance 套件 | ✅ |

## 3. 反向覆蓋檢查（TC → FR）

- 20_Test_Cases 全部 TC 均標注「對應 FR」欄；無孤兒 TC。
- TC-SEC-* 系列多數對映 FR-0019（RBAC）與 13_Security_Architecture 之安全需求；TC-PERF-* 對映 NFR（§5）。
- 對映總表由 CI 腳本自動比對（TC 表格解析 ↔ 本矩陣），漂移即失敗（🔜 規劃中自動化，落地前每 release 人工對帳）。

## 4. 覆蓋缺口清單（gap）

| # | 缺口 | 影響 FR | 優先級 | 處置 |
|---|---|---|---|---|
| G-1 | **RBAC 授權強制（enforce）**：非授權角色寫入敏感端點須 403，全矩陣負向掃描須綠 | FR-0019 全域 | **P0（GA 退出條件，未達即 rollback）** | TC-SEC-RBAC-01/02 為 gate |
| G-2 | **付款 gate 控派工**：payments 主檔 + 派工前付款/報價確認檢核 | FR-0011 | P0 | 🔜 規劃中；落地前派工段以業主豁免手動跳過，E2E 整鏈標 blocked |
| G-3 | **接單 SLA 引擎**：accept_deadline + 逾時自動改派 | FR-0005 / FR-0016 | P0 | 🔜 規劃中；TC-DISPATCH-04 為驗收 |
| G-4 | **AI 輸出第二道防線（output guardrail）**：紅線目前由 SOP skill + eval gate 把守，程式層兜底 | FR-0030 | P1 | 🔜 規劃中；落地前以 Forbidden Eval block-deploy + 真機抽驗補償 |
| G-5 | **Kafka 事件 schema 契約測試**（consumer-driven）| FR-0005 / FR-0039 | P1 | 🔜 規劃中（`../00_platform/P2/09` §5 R-02）|
| G-6 | **速率限制**：api rate-limit middleware + agent webhook 頻率上限 | 橫切 | P1 | 🔜 規劃中（api C-12 / agent C-11）|
| G-7 | 問題卡 completeness gate（完整度 ≥ 門檻才可轉工單）| FR-0002 | P1 | 🔜 規劃中，門檻值 `[待確認：依 03_PRD 定版]` |
| G-8 | 消費者進度追蹤頁測試 | FR-0022 | P2 | 補 Playwright spec |
| G-9 | 效能壓測工具鏈導入（大併發 / burst）| NFR 全域 | P1 | 🔜 規劃中（RC gate 前）|
| G-10 | 技師工單投影表 + 對帳閘門測試 | FR-0039 / FR-0045 | P1 | 隨 ADR-P014 實作補契約 + 對帳測試 |

## 5. 非功能需求追蹤（NFR ↔ 驗證 ↔ TC）

指標定版見 [./05_NFR.md](./05_NFR.md)；下表為驗證方式對映。

| NFR 群 | 代表指標（設計目標）| 驗證方式 | TC |
|---|---|---|---|
| 效能 | AI 首回應 p95<5s / RAG p95<8s / Admin p95<2s / OHS 媒合 p95<300ms / config read p99≤50ms | 負載測試 + benchmark + RUM | TC-PERF-01~05 |
| 可用 | Uptime 契約下限 ≥95%、營運目標 ≥99.5%；webhook ≥99.9%（ack p99≤200ms、autoscale 10x/60s）| 30d rolling SLO + burst test | TC-EXC-01、TC-PERF-04 |
| 可靠 | error rate <0.5%；DLQ 1h 人工 review；outbox lag p99≤30s | APM + metric 斷言 | TC-EXC-01/06、TC-PERF-05 |
| 擴展 | V1 ≥50 / V2 ≥100 併發；租戶 V1:1 / V2:10 / V3:30+ | 壓測 + capacity plan | TC-PERF-01/02 |
| 安全 | injection 攔截 ≥95%、誤攔 <1%；Forbidden ≥95% block-deploy；CVE high ≤7d | 題庫 eval + SCA | TC-SEC-INJ-01/02、TC-CS-AI-05 |
| 隱私 | 跨租戶 0 洩漏；GDPR forget ≤7d；兩階段 purge（T0 + T+30）| mutation test + E2E | TC-SEC-TENANT-01、TC-COMPLIANCE-01/02 |
| 稽核 | audit append-only + hash chain；家族覆核 100%（SLA 24h）；config audit 100% | 篡改測試 + 抽驗 | TC-SETTLE-07、TC-COMPLIANCE-05 |
| 無障礙 | WCAG 2.2 AA；AT 任務成功率 ≥90% | AT 使用者測試 + 自動掃描 | TC-A11Y-01/02 |
| 維運 | rollback <30min；config rollback ≤1min；DORA lead<1d / CFR<15% / MTTR<1d | chaos drill + pipeline metric | UAT 框架第 10/11 類 |

## 6. 跨系統整合點追蹤（整合契約 ↔ TC）

依 `../00_platform/P2/09_integration_data_flow.md` 之平台整合資料流 DAG，每條 edge 對應整合測試：

| # | 整合點（edge）| 協議 / 契約 | 對應 TC | 覆蓋 |
|---|---|---|---|---|
| I-1 | LINE → agent `/callback` | webhook + `X-Line-Signature` 驗簽 | TC-CS-AI-01/02 | ✅ |
| I-2 | agent → Vertex Gemini | LiteLLM model 字串路由 | `test_litellm_provider.py`、TC-EXC-02 | ✅ |
| I-3 | agent → MCP-RAG → 品牌庫 pgvector | cosine + tenant ACL | TC-COMPLIANCE-08 | 🔜 規劃中（RAG-via-MCP 分階段建）|
| I-4 | agent → api `/internal/*` | `X-Internal-Token`（fail-closed）| TC-SEC-INT-01、TC-CS-AI-01 | ✅ |
| I-5 | agent → 品牌庫 `agent.*` 記憶 | tenant+user_id default deny | TC-SEC-MEM-01 | ✅ |
| I-6 | web → api | REST + WS（OIDC token）| TC-SEC-WEB-01、Playwright E2E | ✅ |
| I-7 | api → 品牌庫 | 寫 primary / 讀 replica | TC-EXC-04 | 🟡（讀寫分離 🔜 規劃中）|
| I-8 | api → technician-platform OHS API | 派工媒合契約 | TC-DISPATCH-01 | 🟡（契約測試 🔜 規劃中）|
| I-9 | api ↔ Kafka ↔ technician-platform | `dispatch.assigned` / `technician.*` / `commission.accrued` 事件 | TC-DISPATCH-03、TC-EXC-06、TC-SETTLE-01 | 🟡（schema registry + 契約測試 🔜 規劃中）|
| I-10 | web / api → Casdoor | OIDC 授權碼流 + 角色 claim | TC-SEC-RBAC-02/04 | 🔜 規劃中（Casdoor 導入 Phase）|
| I-11 | knowledge-refinery → 品牌庫 / agent | 事實 chunk+embed 灌語料；行為 → skill | TC-COMPLIANCE-05/08 | 🟡 |
| I-12 | Agent Config Registry → agent | 受保護層 + 客製層合成配置 | UAT S5 + config 套件 | 🔜 規劃中 |
| I-13 | api / agent → SigNoz | OTel trace/metric | 監控 SLI 驗證（見 [./25_Monitoring_Spec.md](./25_Monitoring_Spec.md)）| 🔜 規劃中 |
| I-14 | Casdoor License → provisioning | 品牌開通 → per-brand bundle 部署 | UAT 框架（部署驗收類）| 🔜 規劃中 |

---

*文件結尾 — 21_Traceability_Matrix.md v1.0 / 2026-07-07*
