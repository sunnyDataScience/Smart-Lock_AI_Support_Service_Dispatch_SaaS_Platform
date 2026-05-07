---
title: E7x — Test Plan and Readiness Roadmap
phase: DESIGN
gate: TR5
status: Active
owners:
  - QA Lead
  - Tech Lead
  - PM
related:
  - "[[_flows-bdd-test/v-model-right/E7--bdd-scenarios]]"
  - "[[02-design/E5--api-design-specification]]"
  - "[[02-design/specs/_MOC]]"
  - "[[_flows-bdd-test/v-model-left/E1x--user-journey-map]]"
  - "[[_flows-bdd-test/v-model-left/E5x--workflow-work-order]]"
  - "[[_flows-bdd-test/v-model-left/E5x--workflow-dispatch]]"
  - "[[_flows-bdd-test/v-model-left/E5x--workflow-admin-governance]]"
  - "[[03-develop/GR6--code-complete]]"
  - "[[03-develop/GR7--integration]]"
  - "[[04-deliver/GR10--ga-readiness]]"
last_reviewed: 2026-05-07
last_updated: 2026-05-07 (§1/§2 雙向對齊：🟢13/🟡7/🔴3，TL;DR 與對齊矩陣完全一致)
---

# E7x — Test Plan and Readiness Roadmap

> **目的**：以第三方 BDD 視角，對齊 [[_flows-bdd-test/v-model-right/E7--bdd-scenarios|E7 BDD scenarios]] 中描述的使用者流程與既有前端 / 後端 / 即時通訊實作，找出**文件、UI、API、外部系統**四個面向的缺口，並提出 30 天 Sprint 1 的測試 readiness 路線圖。
>
> **預期讀者**：QA Lead、Tech Lead、PM。
>
> **方法論借鏡**：Google Test Certified L3、Spotify Test Pyramid Reborn、Atlassian shift-left、Stripe contract testing、Martin Fowler / Meta 測試分類學。

---

## 0. Context

Smart-Lock AI Support & Service Dispatch SaaS Platform 是台灣電子鎖售後客服 / 派工 / 帳務 SaaS：
- C 端透過 LINE Bot 智能客服（LangGraph + Vertex AI Gemini 2.5 Flash），故障無法遠端排除即升級派工
- B 端 Next.js 後台（41 頁）+ 技師 mobile-first 介面
- FastAPI 後端 91 個 operationId、AsyncAPI 10 個即時 channel、PostgreSQL + GCS + LINE
- V1.0 已上線（AI 客服 + 知識庫管理）；V2.0 規劃中（派工、技師端、帳務、退款、爭議、保固）

**為什麼要這份文件**：
1. [[_flows-bdd-test/v-model-right/E7--bdd-scenarios|E7 BDD scenarios]] 已寫 21 Feature ~100 Scenarios，但**沒有測試執行計畫**；既有自動化覆蓋率：smoke ~20% endpoints + agent evals 67 題 + 5 個 api/tests，無 E2E、無 contract test、無 visual regression、無 load test。
2. V2.0 上線前需要的測試基礎設施 + Gap 補完，必須在 30 天內形成可信的測試 baseline。
3. 文件描述的使用者流程與前端元件 / API spec / 外部系統整合**並非處處對齊**，須先標明 Gap，再規劃測試。

---

## 1. TL;DR — 現在能測什麼、不能測什麼、為什麼

> **2026-05-07 PR #40 後狀態（spec-driven 升級）**：23 條流程 = **🟢15 / ⚠5 / ⚠3 / ❌0**（與 [[../_SSOT-alignment-matrix|_SSOT §3]] 一致）。
>
> 📋 **「立即可測 🟢」定義**：spec + test infrastructure + PM 拍板齊備 → 可寫 BDD scenarios + contract test + factory test。**不要求 production code 100%**（用 `@wip` tag + `RUN_WIP_TESTS` opt-in 處理 stub 測試 CI 噪音）。

**🟢 立即可測（15 條）**：
- 原 13 條（Wave 1+2）：F-001 LINE 報修、F-002 客服審 PC、F-003 自動派工、F-005 技師接單、F-006 到場拍照、F-009 完工簽名、F-013 對帳爭議雙簽、F-015 保固申訴、F-017 SOP 草稿審核、F-018 客服接管對話、F-020 稽核日誌、F-021 Dashboard / 報表、F-023 錯誤頁 / 離線
- PM 拍板後升 🟢：F-010 改約 / 延遲（Q8=A V1.0 only LINE）
- **PR #40 平行 follow-up 升 🟢（5 條）**：F-004 手動派工（T1 dispatcher seed）/ F-008 Scope Change（T2 Web token spec）/ F-016 SLA 警報（T4 F-110 BDD）/ F-019 RBAC（T1 dispatcher 角色）/ F-022 消費者追蹤（T2 getWorkOrderPublicStatus spec）

**⚠ 部分可測（5 條）**：F-002 客服審 PC（待補 module-spec 業務模組）、F-007 材料申請（等 F-210 規格 PM+BE）、F-018 客服接管對話（LINE Push API 真實串接 TODO）、F-021 報表（後端 filter TODO）、F-023 錯誤頁（cross-cutting 屬性）。

**⚠ 阻塞（3 條）**：F-011 消費者付款 V1.0、F-012 技師月結撥款 V1.0、F-014 退款金流回沖 — **全綁 Q7=B provider 選型**（PR #39 follow-up 4 sub-decision 矩陣已備齊，等 PM/TL/CEO/Finance 90 min 會議）。

> ❌ orphan = 0（PM 拍板後全部 BDD 缺口已定方向）。

**根本原因（已解）**：V1.0 / V2.0 範圍切分 + 角色階層 + Hard / Soft SLA 三大產品決策已於 **2026-05-07 PM 全部拍板**（[[_flows-bdd-test/decision-log/E7x--pm-alignment-Q1-Q10|Q1–Q10]]）。新阻塞點：
- **Q7=B 反向**：V1.0 含金流 → 上線延 ~1.5 個月（待 provider 選型 + PCI 審查）
- **Q3=C / Q9=B 反向**：消費者追蹤 + Scope Change 入口走 Web 匿名 token（共用機制，需建公開 API + Playwright spec）
- **Q4=C 反向**：月結 SLA 工作日+國定假日（需 holidays 套件 + calendar 維護）

實作工作（詳見 [[_flows-bdd-test/_SSOT-alignment-matrix#5-修正動作優先級給-phase-4|_SSOT-alignment-matrix §5]]）已可開始排程，BDD scenarios 也可以開始寫具體 Given/When/Then。

> 📊 **完整統計**（按角色 / Realtime / 外部依賴 / BDD 覆蓋）：見 §2 對齊矩陣 + [[_flows-bdd-test/v-model-right/E7--bdd-scenarios#ⅲb-feature--e7x-流程編號對照f-101f-201--f-001f-023|E7 §Ⅲ.b Feature ↔ E7x 流程對照表]]。

---

## 2. 使用者流程 × 前端頁面 × API × 即時 channel × 外部依賴 對齊矩陣

評等：🟢 立即可測 / 🟡 需補規格或 UI / 🔴 阻塞

| # | 流程 | 角色 | 前端頁面 | API operationId | Realtime | 外部 | 評等 | 阻塞項 |
|---|------|------|---------|----------------|----------|------|------|-------|
| F-001 | LINE 報修 → ProblemCard | 消費者 | (LINE Bot 後端) | `createConversation`, `analyzeMedia`, `createProblemCard` | — | LINE / Vertex / GCS | 🟢 | — |
| F-002 | 客服審 PC → 開 WO | 客服 | `web/src/app/problem-cards/page.tsx`, `[id]/page.tsx` | `listProblemCards`, `getProblemCard`, `convertToWorkOrder` | `work-orders` | — | 🟢 | — |
| F-003 | 自動派工規則引擎 | 系統 | `web/src/app/admin/dispatch-queue/page.tsx` | `runDispatch`, `listDispatchQueue` | `dispatch-queue`, `pool` | — | 🟢 | ✅ 權重 SSOT 已建：[[02-design/specs/dispatch-weights]] |
| F-004 | 手動派工 | 客服 / 派工員 | `web/src/app/admin/dispatch-manual/page.tsx` | `manualAssign`, `reassignWorkOrder` | `dispatch-queue` | — | 🟡 | 「派工員」角色定義 (Q1)；reassign 雙簽 (Q6) |
| F-005 | 技師接單 → 出發 | 技師 | `web/src/app/pool/page.tsx`, `my-orders/page.tsx` | `claimOrder`, `updateWorkOrderStatus` | `pool`, `work-orders` | — | 🟢 | — |
| F-006 | 到場拍照 | 技師 | `web/src/app/my-orders/[id]/door-check/page.tsx` | `checkIn`, `uploadMedia` | `work-orders` | GCS / Vision | 🟢 | — |
| F-007 | 材料申請 | 技師 → 客服 | `my-orders/[id]/material-request/page.tsx`, `admin/inventory/page.tsx` | `requestMaterial`, `approveMaterial`, `listInventory` | `inventory low-stock` | — | 🟡 | F-210 庫存規格不全（多倉 / 借調） |
| F-008 | Scope Change | 技師 → 消費者 | `my-orders/[id]/scope-change/page.tsx` | `proposeScopeChange`, `approveScopeChange` | `work-orders` | LINE | 🟡 | 同意入口 LINE vs Web (Q9) |
| F-009 | 完工簽名 | 技師 + 消費者 | `my-orders/[id]/signature/page.tsx` | `submitSignature`, `completeWorkOrder` | `work-orders` | — | 🟢 | — |
| F-010 | 改約 / 延遲 | 技師 | `my-orders/[id]/reschedule/page.tsx`, `delay/page.tsx`, `admin/schedule-requests/page.tsx` | `requestReschedule`, `approveReschedule`, `notifyDelay` | `user-notifications` | LINE / (SMS 缺) | 🟡 | 非 LINE 用戶 fallback (Q8) |
| F-011 | 消費者付款 V2.0 | 消費者 | (未實作) | (缺 paymentIntent) | — | **金流缺** | 🔴 | V2.0 阻塞 |
| F-012 | 技師月結撥款 | 系統 + 財務 | `web/src/app/accounting/page.tsx` | `runSettlement`, `listSettlements` | — | **撥款 API 缺** | 🔴 | 計算可單測；實際撥款 0 整合 |
| F-013 | 對帳爭議雙簽 | 技師 ↔ 客服 | `web/src/app/accounting/page.tsx` (reconciliation), `admin/disputes/page.tsx` | `raiseDispute`, `dualSignDispute`（現 `submitRefundDecision`） | `disputes` | — | 🟢 | SLA 工作日 / 自然日 (Q4) |
| F-014 | 退款流程 | 客服 + 主管 | `web/src/app/admin/refunds/page.tsx` | `submitRefundDecision` | `refunds` | **金流缺** | 🟡 | 規則可測；金流回沖無 |
| F-015 | 保固申訴 | 消費者 → 客服 | `web/src/app/admin/warranty-claims/page.tsx` | `submitWarrantyDecision` | — | LINE | 🟢 | warranty-dispute spec 已有 |
| F-016 | SLA 紅色警報（2hr 到場） | 系統 + 主管 | `admin/sentiment-alerts/page.tsx`, dashboard | (隱含於監控) | `sla-alerts` | LINE | 🟡 | hard vs soft (Q5) |
| F-017 | SOP 草稿審核 | AI → 客服 → 主管 | `web/src/app/knowledge-base/sop-drafts/page.tsx` | `listSopDrafts`, `reviewSopDraft`, `adoptSopDraft` | — | Vertex AI | 🟢 | — |
| F-018 | 客服接管對話 | 客服 | `web/src/app/conversations/[id]/page.tsx`, `components/conversations/HandoverComposer.tsx` | `escalateConversation`, `sendChatMessage` ✅ | `user-notifications` | LINE | 🟢 | ✅ HandoverComposer + sendChatMessage 已實作（LINE Push integration TODO） |
| F-019 | RBAC 動態調整 | 管理員 | `web/src/app/admin/roles/page.tsx` | `listRoles`（缺 `updateRolePermissions`） | `rbac` | — | 🟡 | Manager / Director 階層 (Q2) |
| F-020 | 稽核日誌 | 管理員 | `web/src/app/admin/audit-events/page.tsx`, `components/admin/AuditExportModal.tsx` | `listAuditLogs`, `exportAuditEvents` ✅ | — | — | 🟢 | ✅ CSV stream + Modal 已建（>100k 筆 background job 預留 202 contract） |
| F-021 | Dashboard / 報表 | 管理員 | `web/src/app/dashboard/page.tsx`, `admin/reports/*`, `components/ui/DateRangePicker.tsx` | `getDashboardStats`, `getKpiReport`, `getRevenueSummary` | — | — | 🟢 | ✅ DateRangePicker 已建並接 4 頁（revenue / technician-ranking 後端 filter TODO） |
| F-022 | 消費者端工單追蹤 | 消費者 | (Web 缺) | (缺 `getWorkOrderPublicStatus`) | `work-orders` | LINE / Maps | 🔴 | 入口 LINE vs Web (Q3) |
| F-023 | 錯誤頁 / 離線 | 任何 | `web/src/app/{not-found,error,global-error}.tsx`, `components/ui/NetworkErrorBanner.tsx` | — | — | — | 🟢 | ✅ 4 個錯誤邊界已建（Service Worker 完整離線策略仍待 §4.1 P1） |

---

## 3. 必須先向 PM 釐清的 10 個問題 → ✅ **全部已拍板（2026-05-07）**

> ✅ 2026-05-07 **PM 全部拍板**（10/10）：6 採預設（Q1/Q2/Q5/Q6/Q8/Q10）+ 4 採反向（Q3=C / Q4=C / Q7=B / Q9=B）。
> 📋 **完整脈絡 + 影響評估 + 後續行動**請見 **[[_flows-bdd-test/decision-log/E7x--pm-alignment-Q1-Q10|決策矩陣]]** §12 / §12.1。

| # | 問題 | 合理預設 | **PM 決策** | 影響流程 | 後續關鍵行動 |
|---|------|---------|------------|---------|------------|
| Q1 | 派工員角色 | A 新角色 | ✅ **A** | F-004 / F-019 | dispatcher 新角色 seed + roles enum |
| Q2 | 雙簽終簽人 | A 階層 | ✅ **A** | F-013 / F-014 | Director > Manager 階層；既有 test_refund_dual_sign 已對齊 |
| Q3 | 消費者追蹤入口 | A LINE only | ✅ **C**（反向）| F-022 | LINE 主 + Web VIP 備並存；建 Web 匿名 token + getWorkOrderPublicStatus |
| Q4 | 月結 SLA 計時 | B 自然日 | ✅ **C**（反向）| F-013 | 工作日 + 國定假日跳過；引入 holidays 套件 |
| Q5 | F-016 SLA 屬性 | B Soft | ✅ **B** | F-016 | Soft：dashboard 紅 + 升主管，無賠償；補 BDD F-110 |
| Q6 | 客服繞過派工 | A 可+audit | ✅ **A** | F-004 | manualAssign 不需雙簽；強制 audit log |
| Q7 | V1.0 金流 | A 不含 | 🔴 **B**（反向 + 重大）| F-011/F-014/V1.0 整體 | **緊急排 provider 選型會議**；上線延 ~30 dev-day + PCI 審查 |
| Q8 | 非 LINE fallback | A 拒收 | ✅ **A** | F-001 / F-010 | V1.0 only LINE，範圍縮小 |
| Q9 | Scope Change 同意 | A LINE quick reply | ✅ **B**（反向）| F-008 | Web 匿名 token + Playwright；與 Q3=C 共用機制 |
| Q10 | 派工失敗 rollback | A 重派 3 次 | ✅ **A** | F-003 / F-005 | 自動重派 3 次後升級客服 |

> 📊 **決策影響統計**（詳見 [[_flows-bdd-test/_SSOT-alignment-matrix#3-對齊狀態彙總|_SSOT-alignment-matrix §3]]）：
>
> - PM 拍板後 ⚠ blocked 從 5 → 4（4 條仍待實作 / provider 選型）
> - ❌ orphan 從 4 → 0（全部已決定方向，待補 BDD Feature）
> - ✅ aligned 從 8 → 10（F-010 / F-013 升級）
>
> ⚠ **Q7=B 為最重大決策**：V1.0 含金流 → 上線延 ~1.5 個月，需 PCI compliance 審查。建議 PM/TL/CEO 立即評估：
> 1. 是否願意延 1.5 個月換金流整合？
> 2. 或拆 V1.0a（不含金流）+ V1.0b（含金流）兩階段？

---

## 4. 缺口分類 + 優先級

### 4.1 文件缺口

| 缺口 | 影響流程 | P | 工時 | 負責 | 狀態 |
|------|---------|---|------|------|------|
| ~~派工規則 5 因子權重表 + tie-breaker~~ | F-003 / F-004 | **P0** | 2d | PM + TL | ✅ 已建 [[02-design/specs/dispatch-weights]] |
| 角色矩陣 v1.0（含派工員、Manager / Director） | F-004 / F-016 / F-019 | **P0** | 2d | PM | 待 PM Q1/Q2 |
| Hard SLA vs Soft Target 對照表 | F-016 | **P0** | 1d | PM | 待 PM Q5 |
| 月結 SLA 計時單位（工作日 / 自然日） | F-013 | **P0** | 0.5d | PM + 法務 | 待 PM Q4 |
| 消費者端追蹤入口（LINE / Web / 兩者） | F-022 | **P0** | 1d | PM | 待 PM Q3 |
| SMS / Email / FCM fallback 通知策略 | F-010 / F-011 / F-016 | P1 | 1.5d | PM | 待 PM Q8 |
| 庫存 F-210 完整規格 | F-007 | P1 | 3d | PM + BE | pending |
| 離線 / Service Worker 完整策略 | F-023 + 技師端 | P1 | 2d | FE Lead | 部分（NetworkErrorBanner 已建，PWA 仍 pending） |

### 4.2 前端 UI 缺口

| 缺口 | P | 工時 | 狀態 |
|------|---|------|------|
| ~~404 / 500 / Network Error page~~ | **P0** | 1d | ✅ A1 Wave 1 完成（commit `da61b1f`） |
| ~~客服接管後的 chat UI~~ | **P0** | 3d | ✅ A4 Wave 2 完成（HandoverComposer.tsx） |
| ~~Modal / Drawer / Toast 統一 library~~ | **P0** | 3d | ✅ A2 Wave 1 完成（Radix UI） |
| ~~Dashboard 日期範圍選擇器~~ | P1 | 1d | ✅ A3 Wave 2 完成（DateRangePicker） |
| ~~稽核 CSV 匯出 Modal~~（accounting / reports 仍待） | P1 | 2d | 部分（A5 完成 audit；accounting / reports 匯出仍 pending） |
| 客戶 admin「新增 / 編輯」表單 | P1 | 1.5d | pending |
| 消費者端工單追蹤頁（若 Q3 = Web） | P0 或不做 | 5d | 待 PM Q3 |
| i18n / 深色模式 | — | 不做 | — |

### 4.3 後端 API 缺口

| 缺口 | P | 工時 | 狀態 |
|------|---|------|------|
| ~~`sendChatMessage`~~ | **P0** | 1.5d | ✅ A4 完成（LINE Push integration TODO） |
| ~~`exportAuditEvents`~~ | P1 | 2d | ✅ A5 完成（>100k 背景 job 留 202 contract） |
| `getWorkOrderPublicStatus`（消費者匿名追蹤，若 Q3 = Web） | P0 | 1.5d | 待 PM Q3 |
| `updateCustomer` / `createCustomer` | P1 | 1d | pending |
| `updateMyAvailability`（技師在線狀態切換） | P1 | 1d | pending |
| `exportReport`（KPI / 營收 CSV / PDF） | P1 | 2d | pending |
| 通知 channel 抽象層（為 SMS / FCM 預留） | P1 | 2d | pending |

### 4.4 外部系統整合缺口（V2.0 阻塞）

| 缺口 | P | 工時 |
|------|---|------|
| 金流（消費者付款 + 退款回沖）— provider 選型 | **P0** V2.0 | 10d+ |
| 撥款 API（技師薪資） | **P0** V2.0 | 8d+ |
| SMS provider | P1 | 2d |
| Email provider | P1 | 1.5d |
| FCM / APNs 推播 | P2 | 3d |
| Whisper 語音轉文字 | P2 | 2d |
| 鼎新 A1 會計對接 | P2 | 10d+ |

### 4.5 角色 / 權限矛盾（影響 BDD `Given` 步驟）
- 「派工員」V2.0 是否獨立角色 (Q1)
- Ops_Manager vs Ops_Director 階層 (Q2)
- 客服可否手動繞過自動派工 (Q6)
- 技師拒單上限與懲罰 (P1)

### 4.6 資料模型 / 狀態機矛盾（影響 fixture 設計）
- WorkOrder 是否含 `paused` / `material-waiting` 狀態
- ProblemCard → WorkOrder 是否 1:N（多技師協作）
- Dispute 狀態機分支（reject vs dual-sign）
- Refund 是否依賴金流結果改狀態
- Inventory 移動最小單位（批號 vs SKU）

---

## 5. BDD 測試金字塔策略

### 5.1 三項操作原則

1. **Spec-as-source-of-truth, not test-as-source-of-truth** — [[02-design/specs/_MOC|OpenAPI 91 op + AsyncAPI 10 channel]] 是契約。測試驗證契約，不重新定義。對應 Google "Test Certified" L3、Atlassian shift-left。
2. **Cost-asymmetry rules the pyramid shape** — Vertex AI 每呼叫 ~$0.01、flaky LINE webhook E2E 每次數小時人力。盡量推到 fake / stub，真實呼叫只放 nightly + release gate。
3. **BDD scenarios are governance, not execution** — [[_flows-bdd-test/v-model-right/E7--bdd-scenarios|E7]] ~100 個 scenario 是利害關係人契約（PM、UAT、法務），prose 永遠留在 markdown，只挑 ~30 條機械化橋接。**拒絕 100% E2E 化**（Spotify 2017 反模式）。

### 5.2 金字塔配置（按 cost-asymmetry 設計，非教條 33/33/33）

| Layer | 占比 | Wall-clock | Tool | 為什麼選這個 |
|-------|------|-----------|------|-------------|
| **Unit**（純函數、定價矩陣、派工計分、狀態機 reducer） | 55% | <2 min | pytest + hypothesis | hypothesis 對派工計分 + 帳務 Decimal 做 property test |
| **Component**（單 router + DB stub、單頁 + mocked fetch） | 15% | <3 min | pytest + httpx.AsyncClient；React Testing Library + MSW | MSW 直接吃 `api.generated.ts` types 當 mock factory |
| **Integration**（router + 真 Postgres via testcontainers、LangGraph node + fake Vertex） | 10% | <5 min | pytest + testcontainers-python + respx | settlement 必須真 SQL；respx 是唯一不會在 retry 上說謊的 httpx mocker |
| **Contract**（OpenAPI 形狀、AsyncAPI envelope） | 5% | <2 min | Schemathesis + 自寫 AsyncAPI validator + Pact-Python（僅 tech mobile ↔ pool） | Schemathesis 自動從 91 op 衍生 ~600 fuzz；Pact 只用在 trust boundary |
| **E2E**（admin + tech browser；LINE 模擬器 → backend → admin） | 5% | <8 min PR / ~25 min nightly | Playwright TS 多 project | 既有 Playwright MCP 已用，POM 共享 |
| **Visual regression** | 3%（~40 stories） | <3 min | Playwright `toHaveScreenshot` | 設計團隊 < 3 人前不上 Chromatic |
| **Load** | 2%（10–15 場景） | nightly | k6 | 第一線 WS / SSE 支援，10 channel 必須 |
| **Chaos** | 2%（5–6 fault drills） | weekly | toxiproxy + pytest fixtures | 1 cluster 不需 Chaos Monkey；toxiproxy 注 Postgres / Vertex 延遲 |
| **AI / LLM eval** | 3%（67 → 300 cases） | nightly + release | 既有 `agent/evals/` + Promptfoo（model A/B） | 保留 judge.py，加 Promptfoo 比 model 更強 |

> **金字塔形狀理由**：55% unit 偏高是**刻意**的 — 最高風險邏輯（派工計分、月結帳務、RBAC permission diffing、refund dual-sign 狀態機）都是 deterministic 純程式碼，屬於 unit + property test 的領域。拒絕 Spotify 舊式 33 / 33 / 33 — 它強迫過多 integration test，ROI 不佳。

### 5.3 BDD scenarios 三層治理（避免 100 scenarios 全 E2E 化的陷阱）

| Tier | Scenario 數 | 機制 | 何時跑 |
|------|-------------|------|-------|
| **A. 可執行規格**（V1.0 流程 1 / 2 / 3、V2.0 流程 5 / 7） | ~20 | pytest-bdd 綁 integration fixture（真 Postgres + fake Vertex + fake LINE） | PR + nightly |
| **B. Contract-backed**（形狀 + 條件） | ~30 | Schemathesis hooks，Gherkin 提取 → parametrize | PR + nightly |
| **C. Documentation-only**（邊界 / 法規 / UAT walkthrough） | ~50 | 標 `[doc-only]` tag，僅 GR6 review | release 前 |

**Gherkin → executable 橋接**：寫一個 ~200 行 markdown extractor，從 [[_flows-bdd-test/v-model-right/E7--bdd-scenarios|E7]] 提取 `[tier-a|tier-b]` 的 scenario，產生 pytest-bdd `features/`。**約 3 dev-day，後續維護近 0**（Spotify「living documentation」模式）。

**LINE Bot 不對真 LINE 做 E2E**：建 `LINESimulator` fixture（forge HMAC-SHA256 webhook + capture reply / push via respx + YAML script 驅動多輪對話），約 1 dev-week。每條 LINE scenario 在 < 100 ms 跑完。

---

## 6. Five-layer Mock 光譜 + 環境分層

每個 fixture 必須標明屬於哪一層（Martin Fowler / Meta 測試分類學）：

| Layer | 定義 | 用在 | 範例 |
|-------|-----|-----|------|
| **Live** | 真實第三方、真錢 | 僅 prod synthetic | prod canary 真 Vertex |
| **Sandbox** | 廠商提供測試模式 | Staging | LINE 測試 channel、Vertex 測試 project |
| **Virtual** | 錄製重播 | Integration nightly | VCR.py cassettes for Vertex |
| **Stub** | 手寫匹配 spec | PR-gate integration | Prism @ 4010、fake LangGraph LLM |
| **Fake** | in-memory 同介面 | Unit | `InMemoryGCS`、`InMemoryWSHub` |

### 6.1 環境矩陣

| 環境 | 用途 | 必跑測試 | 預算 |
|------|------|---------|------|
| **Local** | dev 筆電 | docker-compose.mock + Prism + Postgres，unit / component / first-tier integration < 90 s。**不要求 GCP credentials**（onboarding 殺手） | 0 |
| **CI / PR** | 每 PR | unit + component + contract（Schemathesis 50） + E2E-smoke 5 journey + agent-eval-mini 10（fake LLM） | 12 min p95 |
| **CI / Nightly** | 每晚 | + 全 E2E + visual + k6 50 VU 5 min + agent eval 100（真 Vertex，月預算 $50 cap，超出 fail-open warning） | 25 min |
| **Staging** | 從 main 自動部署 | 5 min Playwright synthetic + weekly chaos drill | $3/月 synthetic |
| **Prod** | 唯讀 synthetic + canary | flag-gated rollout | — |

### 6.2 測試資料策略
- **Factories over fixtures**：`factory_boy`（Python） + 從 `api.generated.ts` 衍生 TS factory generator。schema migration 自動跟著走。
- **Golden datasets**：派工計分 50 case、月結對帳 30 case、refund dual-sign 20 case、agent eval 67 → 300。版本鎖在 git，tag spec version。
- **DB 隔離**：unit / component → transaction rollback；integration → testcontainers 一個容器 per test file。**避免單一共享 DB**（flaky 噩夢源頭）。

---

## 7. 高風險場景的特別測試

### 7.1 派工計分（5 因子 + 3 輪擴大）
- **property + golden 並行**：hypothesis 驗單調性（更近不會排更後、評分 tie-breaker 正確、技師不會派給自己、給定輸入結果 deterministic） + 50 case golden（手調邊界，`--update-golden` flag 通過 PR review 才能改）
- 避免 golden-test-rot anti-pattern

### 7.2 月結對帳金額（最高風險）
- **Decimal 而非 float**，custom ruff plugin lint 強制
- **property test**：`sum(line_items) == total` 永真
- **並發**：`asyncio.gather(100 settlements)` 對同 tenant，DB row-version 驗無雙計（Stripe 模式）
- **冪等**：同期間二次跑產生 0 新 entries

### 7.3 RBAC 即時撤銷（3 個 race condition）
- WS 訂閱中被撤角色 → 2 s 內收到強制取消訂閱
- 撤銷前已發 in-flight HTTP → 下次 request 403
- tech mobile 快取角色 → 透過 BroadcastChannel 失效

### 7.4 紅色警報 SLA（30 s push / 15 min ack / 2 hr 到場）
- **時間旅行**：unit 用 freezegun；跨進程 integration 用 `ClockFixture` 暴露 `clock.advance(seconds=120)`，SLA monitor 改用它而非 `time.time()`
- **不容妥協**：testing wall-clock = 2 小時測試

### 7.5 Idempotency-Key（3 種模式）
- 同 key 同 body → 單一 side-effect
- 同 key 不同 body → 422
- 並發同 key 跨 worker（pytest-xdist 2 process + `asyncio.gather`） → 恰一成功（Stripe documented test）

---

## 8. AI / LLM 測試策略（既有 67 → 300 case 演進）

### 8.1 Dataset 成長（90 天）
- 67 stay 為 smoke set，PR 跑 **deterministic fake LLM**（response 用 question hash 索引），cost $0、wall-clock < 30 s
- 加 200 case，按類別 tag：`intent_classification` / `entity_extraction` / `retrieval_relevance` / `sop_generation` / `safety_jailbreak` / `cost_latency_budget`
- 每 case metadata 標 `evaluator: exact_match | semantic_similarity | judge_llm | regex | tool_call_assertion`

### 8.2 LLM-as-Judge bias 控制
- **多 judge 投票**（Gemini 2.5 Pro + Claude Sonnet + GPT-4o）對 10% 樣本，分歧升級人工。DeepMind Self-Refine：3-judge majority 88% reliability vs 單 judge 70%
- **pairwise > absolute scoring**：A / B 比較時 LLM 對「哪個好」可靠度比「打 0–10」高 20–30%
- **校準集 30 hand-graded case**：每 release 重跑，judge 與人工 agreement < 0.85 = judge prompt 是 bug

### 8.3 Hallucination / 安全
30 case adversarial prompt（Anthropic red-team + 10 個台灣社工攻擊繁中）。Pass：refusal ≥ 95%、無 PII 洩漏、無離域回答。失敗阻 [[03-develop/GR7--integration|GR7]]。

### 8.4 Cost / Latency budget
Eval pipeline 算 `mean_tokens_in/out / p95_latency_ms / cost_per_1k_calls`。PR comment 貼 main 對比 delta。**Hard gate：cost regression > 15% 阻 merge**（Stripe / OpenAI 內部慣例）。

### 8.5 CI cost containment
- PR 跑 67 case smoke vs fake LLM（$0）
- Nightly 跑 200 case vs 真 Vertex 預算 cap
- Release gate（[[03-develop/GR6--code-complete|GR6]]） 跑全 300 + 多 judge ≈ $15 / release

---

## 9. 「不要先做」清單（短期不投入測試資源）

| 範圍 | 原因 | 重評時點 |
|------|------|---------|
| 消費者付款 / 撥款 E2E | 無 provider 整合，無程式碼 | V2.0 啟動 |
| 鼎新 A1 自動會計 | V3 規劃 | V3 |
| AI Layer 6 PDCA 持續學習 | 路線圖未定 | V3 |
| 多語系 i18n 測試 | 無 i18n 框架 | 國際化專案啟動 |
| 深色模式視覺回歸 | 無切換 UI | UX 階段 2 |
| Whisper 語音 | 未整合 | LINE 語音占比 > 10% |
| FCM 推播 | tech 端可用 LINE 替代 | 自有 App 啟動 |
| 多技師協作 | V2.0 後段 | V2.0 中 |
| 報表 PDF 匯出 | 內部用戶可先用 CSV | P1 完成後 |
| 瀏覽器相容性（IE / 舊 Safari） | Cloudflare logs < 0.3% 流量 | **不做** |
| Mutation testing | Test L4 才需要 | 跳過 |
| Chromatic 視覺回歸 | 設計團隊 < 3 人 | 用 Playwright snapshot 替代 |

**原則**：不為「未來會做」的功能寫 placeholder test。改用 `@wip` tag 在 BDD 中標記但 skip。

---

## 10. 30 天 Sprint 1 交付物清單

假設團隊：2 BE + 1 FE + 1 QA + 0.5 SRE。

### Week 1：對齊 + 文件補完（解 Q1–Q10）
1. 召開 90 min PM / TL 對齊會，產出**角色矩陣 v1.0**、~~派工權重 + tie-breaker 表~~ ✅、**SLA hard / soft 對照表**、**WO / Dispute / Refund 狀態機 single source**
2. 凍結 V1.0 範圍（金流、SMS、鼎新明確 OUT）
3. [[_flows-bdd-test/v-model-right/E7--bdd-scenarios|E7]] scenarios 加 `[tier-a|tier-b|tier-c|doc-only]` tag

### Week 2：測試基礎設施
4. ~~統一 **Modal / Toast library**~~ ✅ A2 完成（Radix UI）
5. ~~補 **404 / 500 / Network Error page**~~ ✅ A1 完成
6. **`LINESimulator` fixture** + 8 reference test 對 V1.0 對話流程（3 dev-days）
7. **金流 / SMS / Email fake provider**（contract first，等真 integration）
8. **種子資料**：3 客戶 / 5 技師 / 20 工單跨狀態 / 5 庫存
9. **Prism mock server** 擴 18 → 50 endpoints
10. **Playwright 基礎 fixture**（登入 / 切角色 / 種資料）

> **附加完成（Wave 2 - 原列為後續 Sprint）**：
> - ✅ Dashboard / 報表日期區間 UI（DateRangePicker，原 §4.2 P1）
> - ✅ 客服接管 chat UI + sendChatMessage API（HandoverComposer，原 §4.2/4.3 P0）
> - ✅ 稽核 CSV 匯出 + exportAuditEvents API（AuditExportModal，原 §4.2/4.3 P1）

### Week 3：Happy Path E2E 8 條跑通
11. F-001 LINE 報修 → PC（mock LINE）
12. F-002 客服開單 → WO
13. F-003 自動派工
14. F-005 + F-006 技師接單到場
15. F-009 完工簽名
16. F-013 對帳爭議雙簽（沿用 existing `test_refund_dual_sign.py`）
17. F-015 保固申訴
18. F-017 SOP 草稿審核

> **目標**：**8 條 Happy Path 綠燈**，宣稱「核心可運轉」。

### Week 4：Edge Case + Contract Test
19. 每條 Happy Path 各 2 個 negative case（共 16）
20. F-007 / F-008 / F-010 加入測試
21. **Schemathesis** 對 Prism + 真 FastAPI dev server，PR-gate
22. **AsyncAPI envelope validator** script + nightly job（10 channel 各 1 fixture，dispatch-queue 為 reference 12-test parametrized base，後續 9 channel 1 day each）
23. F-016 SLA 警報自動化（依 Q5 結論決定 hard / soft）
24. **Settlement property + 30 case golden**（Decimal-only ruff lint）
25. **Dispatch scoring property + 50 case golden**
26. **Agent eval CI 整合**：fake-LLM smoke on PR + nightly 真 Vertex $50 / month cap + Promptfoo A / B harness
27. **PR template + ownership matrix**；coverage diff via `pytest-cov` + `diff-cover` 貼 PR comment

**Sprint 1 總人日 ~30**，4.5 人 30 天可吸收（70% bandwidth）。

**Sprint 1 explicit non-goals**：chaos drills、k6 load > 5 min、tech mobile Pact contract、Chromatic、mutation testing、全 20 個 BDD Tier A bridge（只做 5 個 reference）。

---

## 11. Quality Gates（對應 [[03-develop/GR6--code-complete|GR6]] / [[03-develop/GR7--integration|GR7]] / [[04-deliver/GR10--ga-readiness|GR10]]）

| Gate | 觸發 | 必跑測試 | KPI | Flaky 容忍 | 失敗 |
|------|-----|---------|-----|----------|------|
| **PR-gate** | 每 PR | unit + component + contract（Schemathesis 50） + E2E-smoke 5 + agent-eval-mini | 全綠；coverage Δ ≥ -1% | E2E ≤ 1 retry | 阻 merge |
| **Pre-merge to main** | squash | + k6 load smoke 5 min + visual regression | per-endpoint p95 latency budget | 0 | 阻 + revert |
| **GR6 — V2.0 spec freeze** | 手動 | + 全 BDD Tier A + AsyncAPI contract + AI eval 全集 | 100% Tier A pass；eval ≥ baseline | 0 | reopen design |
| **GR7 — Pre-prod release** | release branch | + chaos drill + security scan（gitleaks / trivy） + agent eval 300 + axe-core a11y | 0 critical security；eval cost regression < 15% | 0 | 阻 release |
| **GR10 — Post-launch sign-off** | 14 d post-deploy | synthetic 99%+ green + RUM SLA met + 0 P0 | 99.5% uptime per channel | n/a | hotfix backlog |

**Rollback triggers**：synthetic probe red > 5 min，或 prod log 出現 AsyncAPI envelope validation failure，自動建 incident + page on-call。Rollback = Cloud Run revision flip + 向後相容 migration revert（migration 強制 backward-compat，sqlfluff custom rule lint）。

---

## 12. Test Ownership Matrix

| Layer | Primary | Reviewer | Gate |
|-------|---------|----------|------|
| Unit | Feature dev | Peer | PR |
| Component | Feature dev | QA spot-check | PR |
| Integration | Feature dev | QA + BE Lead | PR |
| Contract | BE Lead | API platform | PR + nightly |
| E2E | QA | FE Lead | PR-smoke + nightly |
| Visual | FE dev | Designer | nightly |
| Load | SRE | BE Lead | nightly |
| Chaos | SRE | BE Lead | weekly |
| AI eval | ML eng | Domain expert（鎖匠師傅） | nightly + GR6 |
| Synthetic | SRE | QA | continuous |
| BDD Tier A | PM 寫 Gherkin / QA 實作 | TL | GR6 |
| BDD Tier C | PM | Stakeholder | GR6 review |

**借鏡模式**：
- **Spotify Squad**：每 squad 全擁自己 layer；contract / AsyncAPI 等橫切由「平台公會」1–2 senior eng 守
- **Google Test Certified**：每季自評，V2.0 launch target = L3（持續測試 + 正確金字塔 + 0 manual regression）。L5 暫不追求
- **Atlassian shift-left**：PM 在 [[_flows-bdd-test/v-model-right/E7--bdd-scenarios|E7]] 寫 Gherkin 才能讓票進 estimation。**硬規則**

---

## 13. Verification — 怎麼驗證這份文件落地

實作 Sprint 1 後，端到端驗證步驟：

1. **CI pipeline 完整跑通**：
   ```bash
   # PR-gate 模擬
   make test-unit        # < 2 min, 55% case
   make test-component   # < 3 min, 15% case
   make test-contract    # Schemathesis 50 cases
   make test-e2e-smoke   # Playwright 5 journeys
   make test-agent-mini  # 10 case, fake LLM
   ```

2. **8 條 Happy Path E2E 綠燈**（Week 3 目標）：
   ```bash
   cd web && npx playwright test --project=admin   # F-002, F-013, F-015, F-017
   cd web && npx playwright test --project=tech    # F-005, F-006, F-009
   pytest tests/bdd/features/F-001-line-report.feature  # F-001 透過 LINESimulator
   ```

3. **AsyncAPI 10 channel 連線測試**：
   ```bash
   pytest api/tests/realtime/ -v   # 連線 + 訂閱 + 訊息順序 + 斷線重連
   ```

4. **Mock server 對前端可用**：
   ```bash
   ./scripts/ci/mock-server.sh   # Prism @ 4010
   cd web && PUBLIC_API_URL=http://localhost:4010 npm run dev
   # 開瀏覽器逛 41 頁，確認無 4xx / 5xx
   ```

5. **Coverage diff 出現在 PR**：建任意 PR，確認 `diff-cover` bot 留言

6. **Agent eval cost cap 生效**：手動觸發 nightly workflow，確認超 $50 / month 時 fail-open warning 而非硬擋

7. **Synthetic monitoring 上線**：staging Cloud Scheduler 5 min 跑 5 個 Playwright 旅程，Cloud Monitoring dashboard 看到 99% green line

---

## 14. Critical Files

### API 合約 SSOT
- `docs/02-design/specs/openapi.yaml` — 91 operationId
- `docs/02-design/specs/asyncapi.yaml` — 10 channel
- `docs/02-design/specs/generated/api.generated.ts` — TS types

### 現有測試資產（要擴展，非重寫）
- `tests/smoke/api.sh` — 18 endpoints smoke
- `api/tests/conftest.py` — pytest fixtures（AsyncClient + JWT factory）
- `api/tests/test_refund_dual_sign.py` — 雙簽 reference
- `api/tests/test_sla_monitor.py` — SLA reference
- `agent/evals/runner.py`, `agent/evals/judge.py`, `agent/evals/reporter.py` — eval pipeline
- `agent/quality/quality_check.py` — 67 題 + LLM-as-Judge

### BDD 規格來源
- [[_flows-bdd-test/v-model-right/E7--bdd-scenarios|E7]] — 21 Feature ~100 Scenarios
- [[_flows-bdd-test/v-model-left/E1x--user-journey-map|E1x User Journey Map]] — 4 角色旅程地圖
- [[_flows-bdd-test/v-model-left/E5x--workflow-work-order]] — 13 個 WO flow
- [[_flows-bdd-test/v-model-left/E5x--workflow-dispatch]] — 派工 7 模組
- [[_flows-bdd-test/v-model-left/E5x--workflow-admin-governance]] — RBAC + 稽核

### 治理 / 對齊文件
- **[[_flows-bdd-test/decision-log/E7x--pm-alignment-Q1-Q10|Q1–Q10 PM 對齊文件]]** — §3 表格的完整版（含選項對比、影響範圍、會議議程、PM 決策欄位、追蹤表）
- [[02-design/specs/dispatch-weights]] — F-003 派工權重 SSOT

### 前端待補關鍵頁
- `web/src/app/conversations/[id]/page.tsx` — 接管後 chat UI 缺
- `web/src/app/admin/dispatch-manual/page.tsx` — 與 Q1 / Q6 綁定
- `web/src/app/dashboard/page.tsx` — 日期範圍選擇器缺
- `web/src/app/admin/audit-events/page.tsx` — 匯出 UI 缺
- `web/src/lib/api.ts` — JWT + Idempotency-Key 已實作（測試入口）
- 缺：`web/src/app/not-found.tsx`、`web/src/app/error.tsx`、Modal / Toast library

### CI / Mock 基礎
- `scripts/ci/mock-server.sh` — Prism @ 4010
- `.github/workflows/mock-smoke.yml`、`spec-lint.yml`、`api-types-sync.yml`、`orphan-check.yml`
- `scripts/ci/check-operationid-orphans.sh` — 91 op 雙向對應 lint

### 新建（Sprint 1 交付）
- `tests/bdd/features/` — pytest-bdd Tier A scenarios
- `tests/bdd/extractor.py` — E7 markdown → pytest-bdd bridge（~200 行）
- `tests/fixtures/line_simulator.py` — LINE webhook 模擬器
- `tests/fixtures/fake_payment.py`、`fake_sms.py`、`fake_email.py` — V2.0 stub
- `tests/factories/` — factory_boy + TS generator
- `tests/golden/dispatch_scoring/`、`tests/golden/settlement/` — 80 case
- `tests/realtime/channel_kit.py` — 10 channel parametrized base
- `scripts/ci/asyncapi-validate.mjs` — AsyncAPI envelope validator
- `web/playwright.config.ts`、`web/tests/e2e/{admin,tech}/` — Playwright POM
- `web/src/components/ui/{Modal,Toast,Drawer}.tsx` — 統一 library

---

## 15. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | Claude (assisted) | 初始版本：對齊矩陣、Gap 分類、PM Q1–Q10、金字塔、Sprint 1 路線圖 |
| 2026-05-07 | Claude (assisted) | **Wave 1+2 補完狀態同步**：5 流程從 🔴/🟡 變 🟢，🟢 從 8 條增為 13 條、🔴 從 5 條降為 3 條（F-014 從 🔴 降為 🟡 規則可測；F-013 從 🟡 升為 🟢 既有 dual-sign 雙簽測試完整）。詳見 §15.1。 |
| 2026-05-07 | Claude (assisted) | **測試基礎設施 Wave（autonomous-only）**：補齊「不需外力」的測試金字塔骨架：Makefile、pytest markers、tests/fixtures、tests/factories、schemathesis、AsyncAPI validator、Playwright config + login smoke、test-suite.yml workflow。詳見 §15.2。 |
| 2026-05-07 | Claude (assisted) | **§3 PM Q1–Q10 抽出為獨立對齊文件**：[[_flows-bdd-test/decision-log/E7x--pm-alignment-Q1-Q10|Q1–Q10 對齊文件]] 提供完整選項對比、會議議程、PM 決策欄位、追蹤表、下游更新清單。§3 表保留為摘要，每行加 `詳細` 連結至對齊文件對應章節。Q4 / Q5 預設更新為「自然日 / soft」（重新評估技術成本）。 |
| 2026-05-07 | Claude (assisted) | **§1 / §2 雙向對齊**：TL;DR 數字與 §2 對齊矩陣逐行對照修正。修正內容：(a) 🟡 部分可測列表加入 F-014（移除 F-013，因 F-013 §2 已是 🟢）；(b) 🔴 不能測從「4 條 (F-011/F-012/F-014/F-022)」修正為「3 條 (F-011/F-012/F-022)」；(c) 🟡 條數明確標 7 條；(d) 加 cross-link 至 [[_flows-bdd-test/v-model-right/E7--bdd-scenarios|E7 §Ⅲ.b]] BDD 對照表。理由：§2 為 SSOT，§1 為摘要，過去 §1 落後 §2。 |
| 2026-05-07 | PM + Claude (sync) | **PM Q1-Q10 全拍板同步**：§1 TL;DR 改寫「根本原因（已解）」+ 列出新阻塞（Q7=B 金流 / Q3=C+Q9=B Web 匿名 token / Q4=C 工作日 calendar）；§3 從 10 row 待拍表變「拍板結果 + 後續行動」表，標明 4 反向選項；指向 _SSOT-alignment-matrix §3 對齊狀態彙總。Q7=B 為最重大決策（V1.0 含金流，延 ~1.5 月）。 |
| 2026-05-07 | Claude (assisted) | **PR #40 5-track 後流程升級**（spec-driven 定義）：§1 TL;DR 統計 🟢13→15 / ⚠7→5 / 🔴3→3。5 條升 🟢：F-004（T1 dispatcher）、F-008（T2 Web token spec）、F-016（T4 F-110 BDD）、F-019（T1 dispatcher 角色）、F-022（T2 getWorkOrderPublicStatus）。剩 3 條 ⚠ 阻塞全綁 Q7=B provider 選型（PR #39 follow-up 矩陣等會議）。明確區分「立即可測」採 spec-driven（規格 + test infra + PM 拍板齊備即 🟢，不要求 production code 100%）。詳見 [[_flows-bdd-test/_SSOT-alignment-matrix#7-change-log\|_SSOT §7]]。 |

### 15.1 Wave 1+2 補完明細（2026-05-07）

依 [[#10-30-天-sprint-1-交付物清單]] Week 1/2 + 部分 Week 3/4 提前完成，採 git worktree 兩波平行開發：

**Wave 1（dev → 3 worktree → merge）**

| Task | Branch | Commit | Files |
|------|--------|--------|-------|
| A6 派工權重 SSOT | `docs/dispatch-weights` | `d427503` | `docs/02-design/specs/dispatch-weights.md` + E5x cross-link |
| A1 錯誤頁 | `feat/error-pages` | `da61b1f` | `not-found.tsx` / `error.tsx` / `global-error.tsx` / `_error-parts/BackButton.tsx` / `NetworkErrorBanner.tsx` |
| A2 UI library | `feat/ui-foundation` | `63f8305` | `Modal.tsx` / `Drawer.tsx` / `Toast.tsx` + ToastProvider 接入 layout + globals.css 動效 keyframes，依賴 `@radix-ui/react-dialog`、`@radix-ui/react-toast` |

**Wave 2（dev → 3 worktree → merge，A2 已可用）**

| Task | Branch | Commit | Files |
|------|--------|--------|-------|
| A3 日期選擇器 | `feat/dashboard-daterange` | `3776c6a` | `DateRangePicker.tsx` + `lib/dateRange.ts`，接到 dashboard / kpi / revenue / technician-ranking 4 頁，依賴 `@radix-ui/react-popover` |
| A4 接管 chat | `feat/handover-chat` | `770a628` | `sendChatMessage` operationId + `HandoverComposer.tsx` + `conversation_service.send_message`（`assistant` role + metadata.sender_role=agent_human 零破壞）|
| A5 稽核匯出 | `feat/audit-export` | `2bdcf96` | `exportAuditEvents` operationId + `AuditExportModal.tsx` + StreamingResponse CSV + `api.downloadPost` |

**驗證**：
- OpenAPI 從 91 → 93 operationIds，無重複
- `tsc --noEmit` 0 error
- Python AST parse 全 OK
- spectral lint 0 new error

**殘留 TODO**（標記在程式碼中）：
- A4：LINE Push API integration、audit log write（在 `conversation_service.send_message`）
- A5：>100k 筆 background job + email notification + signed URL（202 contract 已預留）
- A5：權限檢查暫硬編 `role in {admin, ops}`，待 F-019 RBAC 動態化後改 `audit.read.all`
- A4：`SendChatMessageRequest` 暫放 `internal.py`，下次 codegen 一併歸位
- 整體：`web/types/api.generated.ts` 待統一 regenerate

### 15.2 測試基礎設施 Wave（2026-05-07）

依「**前後端分離視角，先區分『可自主補齊』vs『需外力介入』，再把可補齊項全做完**」原則執行。
路線圖見 [`/home/sunny/.claude/plans/home-sunny-python-workstation-github-sm-temporal-parnas.md`](file:///home/sunny/.claude/plans/home-sunny-python-workstation-github-sm-temporal-parnas.md)。

**5 個 commit 拆分（chore/test-readiness-foundation + chore/test-readiness-ci-docs 兩分支）**

| # | Commit | Branch | 內容 |
|---|--------|--------|------|
| 1 | `1ffb8d8` | foundation | 根 `Makefile`（5 layer target + coverage / mock / clean）+ `pyproject.toml [dependency-groups] test`（schemathesis / pytest-cov / diff-cover / factory-boy / respx / hypothesis）+ `[tool.pytest.ini_options] markers` + 7 個既有 test 加 `pytestmark`（5 component / 2 unit）|
| 2 | `4fec6d2` | foundation | `tests/fixtures/line_simulator.py`（lift `create_line_signature` HMAC-SHA256 + `LINESimulator` dataclass + 3 fixture）+ `tests/factories/{tenant,technician,problemcard,workorder}.py`（factory_boy + Faker zh_TW）|
| 3 | `887f252` | foundation | `scripts/ci/contract-schemathesis.sh`（OpenAPI fuzz；`--check-only` 模式 PR-gate 用）+ `scripts/ci/asyncapi-validate.mjs`（`@asyncapi/parser` 驗 spec + 列 10 channels）+ `scripts/ci/package.json`（與 web/ 隔離）|
| 4 | `714291f` | foundation | `web/playwright.config.ts`（admin Desktop Chrome / tech Pixel 7 mobile 兩 project）+ `web/tests/e2e/admin/login.spec.ts`（不打 submit 的 smoke）+ `web/tests/e2e/README.md` |
| 5 | `06a2a10` | ci-docs | `.github/workflows/test-suite.yml`（unit / asyncapi / contract-check 3 個獨立 PR-gate job）+ `tests/README.md`（金字塔規範首頁）+ `scripts/README.md` 補 Makefile + contract / asyncapi 工具用法 |

**對應 §10 Sprint 1 完成度**

| Sprint 1 任務 | 狀態 |
|--------------|------|
| #4 Modal / Toast library | ✅ Wave 1 A2（既有） |
| #5 404 / 500 / Network Error page | ✅ Wave 1 A1（既有） |
| #6 LINESimulator fixture（基礎版） | ✅ commit 4fec6d2 |
| #8 種子資料 factory_boy 基礎版 | ✅ commit 4fec6d2（factory layer，DB 寫入由測試自管） |
| #21 Schemathesis PR-gate | ✅ commit 887f252（`--check-only` mode；真打 mode 留 nightly） |
| #22 AsyncAPI envelope validator | ✅ commit 887f252（spec 結構；envelope golden 對拍待 SSE 整合） |
| #27 PR template + ownership matrix（部分） | ✅ commit 06a2a10（test-suite.yml + tests/README.md） |

**驗證**：
- `make test-unit` → 25 passed in 0.86s
- `bash scripts/ci/contract-schemathesis.sh --check-only` → ✓ OpenAPI YAML 結構合法
- `node scripts/ci/asyncapi-validate.mjs` → ✓ AsyncAPI 2.6.0, 10 channels, 0 error / 26 warning
- `npx playwright --version` → 1.59.1（裝在 web/node_modules）
- `make help` → 完整列出 9 個 target

**外力介入清單（本 Wave 不做）**：
- PM Q1–Q10 全部（角色矩陣、SLA hard/soft、消費者追蹤入口、SMS fallback、Scope Change 入口）
- 金流 / 撥款 / SMS / Email / FCM / LINE Push 真實整合
- Vertex AI nightly 真打預算決策、Opik workspace
- 客製化測試資料（QA + 真客戶協助）
- 設計團隊視覺回歸（Chromatic / 設計人力 < 3）

**Sprint 1 仍待後續處理**：
- #7 金流 / SMS / Email fake provider（綁 PM Q7 V1.0 是否含金流）
- #9 Prism mock 18 → 50 endpoints（spec 補完後再擴）
- #10 Playwright 基礎 fixture（登入 / 切角色 / 種資料）— 綁 PM Q1
- #11–#18 Happy Path 8 條 E2E — 全綁 PM Q1–Q10
- #19 negative cases / #20 F-007 / F-008 / F-010 — 綁 PM 拍板
- #23 F-016 SLA — 綁 PM Q5
- #24 Settlement property + golden / #25 Dispatch scoring property + golden — 雖權重已建但邊界 case 未拍
- #26 Agent eval CI 整合（fake-LLM smoke / nightly 真 Vertex / Promptfoo）— 綁預算決策
- 完整 coverage diff PR comment（diff-cover bot）— 需 component test 進 CI 才有意義
