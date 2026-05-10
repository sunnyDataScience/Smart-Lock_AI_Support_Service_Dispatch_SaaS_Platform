---
title: ⭐ _flows-bdd-test/ Master Alignment Matrix (SSOT — 流程北極星)
phase: CROSS-PHASE
status: SSOT (Single Source of Truth — 23 user flows F-001~F-023)
last_updated: 2026-05-07
owners: [PM, Tech Lead, QA Lead]
related:
  - "[[_MOC]]"
  - "[[north-star-requirements]]"
  - "[[_review-notes]]"
  - "[[v-model-right/E7x--test-plan-and-readiness]]"
  - "[[v-model-right/E7--bdd-scenarios]]"
  - "[[decision-log/E7x--pm-alignment-Q1-Q10]]"
---

# ⭐ _flows-bdd-test/ — Master Alignment Matrix (SSOT)

> **本檔為 `_flows-bdd-test/` 的流程北極星**（Single Source of Truth）。任何關於 23 條 user flow（F-001~F-023）的問題，都從這裡開始查。
>
> **配對北極星**：[[north-star-requirements]]（需求北極星，REQ-NNN catalog）。流程 SSOT（本檔）對應 V-Model 的「user flow 層」；需求 SSOT 對應 V-Model 左上頂點「Requirements 層」。
>
> **使用方式**：
> 1. 找你關心的 F-XXX → §1 主對齊矩陣查橫排所有對應
> 2. 對齊狀態為 ⚠ / ❌ 的 row → 看「修正動作」column
> 3. 有 PM 阻塞 column 標 Q-N → 推 PM 拍板（[[decision-log/E7x--pm-alignment-Q1-Q10|決策矩陣]]）

> **目的**：以 **E7x F-001~F-023（23 條 user flow，現有 SSOT）為主鍵**，建立**單一對照表**，讓 PM / TL / QA 從任何一個 F-XXX 編號可一眼看出：
> - E1x 對應角色 + stage
> - E5x workflow 對應 Flow 編號
> - E7 BDD 對應 Feature ID（F-1XX / F-2XX）
> - E7x module-spec 對應規格
> - 測試準備度
> - PM 阻塞題號
> - **對齊狀態 + 修正動作**
>
> **資料來源**：E7x test plan §2 + E7 §Ⅲ.b + [[_review-notes]] 觀察。
>
> **使用方式**：
> 1. 找你關心的 F-XXX → 查橫排所有對應
> 2. 找對齊狀態為 ⚠ / ❌ 的 row → 看「修正動作」column
> 3. 找有 PM 阻塞 column 標 Q-N 的 row → 推 PM 拍板該題

---

## 1. 主對齊矩陣（23 user flows × 8 dimensions）

| F-XXX | 流程名稱 | 角色 | E1x 旅程 | E5x Workflow | E7 BDD Feature | Module Spec | Test Status | PM Block | 對齊 | 修正動作 |
|-------|---------|------|---------|--------------|----------------|-------------|-------------|----------|------|---------|
| **F-001** | LINE 報修 → ProblemCard | 消費者 | 消費者旅程 §1 階段 1-4（問題發生→LINE→AI→PC）| work-order Flow 1 (S1 詢問) | F-101, F-102, F-107, F-108 | 模組 1 ConversationManager + 模組 2 ProblemCardEngine | 🟢 | — | ✅ aligned **(impl complete)** | 5/9 evening sprint：補 `createConversation` endpoint + agent webhook bridge `_ensure_conversation_record`（`agent/app.py`）+ `AdminAPIClient`（`agent/integrations/admin_api.py`，30 min cache）。Status note：work-order S1 階段對應已確認 |
| **F-002** | 客服審 PC → 開 WO | 客服 | 管理員旅程 §3 階段 1（儀表板）| work-order Flow 1（PC → created）| F-105 admin V1.0 | 模組 1（會話）+ 模組 9 ProblemCardReviewEngine | 🟢 | — | ✅ aligned **(impl complete)** | 5/8 模組 9 規格補完；5/9 production code 補完：`convertToWorkOrder` endpoint + `work_order_service.create_from_problem_card()` + 「開單」UI（7 integration test）|
| **F-003** | 自動派工規則引擎 | 系統 | 隱含於消費者 §1 階段 6（派工建立）| work-order Flow 1 → dispatch §2 媒合演算法 | F-202 智慧派工引擎 | 模組 7 TechnicianMatcher（V2.0 業務層）| 🟢 | — | ✅ aligned | 確認 dispatch §2 ↔ F-202 ↔ dispatch-weights |
| **F-004** | 手動派工 | 客服 / 派工員 | 管理員旅程 §3 階段 3（派工監控） | dispatch §4 拒單重派 + work-order Flow 2 | F-202（含 manual override） | 模組 7 TechnicianMatcher | 🟢 | ✅ Q1=A / Q6=A | ✅ aligned **(impl complete)** | **PR #45**：assignWorkOrder + assignDispatch 從 require_tenant 升 role_required（修補 P0 漏洞）+ 客服繞過自動 audit log（10 component test pass）|
| **F-005** | 技師接單 → 出發 | 技師 | 技師旅程 §2 階段 1-3（推播→案件池→接單） | work-order Flow 1 + dispatch §4 | F-201 師傅工作台 | 業務模組未明列 | 🟢 | — | ✅ aligned | 補 module-spec |
| **F-006** | 到場拍照 | 技師 | 技師旅程 §2 階段 4（到場） | work-order Flow 1 | F-201 師傅工作台 | 業務模組未明列 | 🟢 | — | ✅ aligned | 補 module-spec |
| **F-007** | 材料申請 | 技師 → 客服 | 異常流程 §7.2（缺料 + Flow 4） | work-order Flow 4 + admin-governance G3 庫存 | F-210 庫存與材料管理 | 業務模組未明列（V2.0）| 🟡 | F-210 規格不全 | ⚠ partial | 等 F-210 詳細規格（PM + BE） |
| **F-008** | Scope Change | 技師 → 消費者 | 異常流程 §7.1（範圍變更） | work-order Flow 3（範圍變更） | F-203 標準化定價引擎（隱含） | 模組 8 PricingEngine | 🟢 | ✅ Q9=B | ✅ aligned **(impl complete)** | **PR #46**：HMAC-SHA256 + base64url 真實實作 + scope_change_service real（CAS 防 race，accept → in_progress；27 unit+component test pass）|
| **F-009** | 完工簽名 | 技師 + 消費者 | 技師 §2 階段 5 + 消費者 §1 階段 7 | work-order Flow 1 完成節點 | F-201 師傅工作台 | 業務模組未明列 | 🟢 | — | ✅ aligned | 補 module-spec |
| **F-010** | 改約 / 延遲 | 技師 | 異常流程 §7（延遲 + Flow 5） | work-order Flow 5（延遲 / 改約） | F-201（部分）| 業務模組未明列 | 🟢 | ✅ Q8=A | ✅ aligned **(impl complete)** | **PR #47**：3 新 ops（requestReschedule/approveReschedule/notifyDelay）+ LINE Push 真實串接（retry+fail-soft，順手解 F-018 殘留 TODO；12 component test）|
| **F-011** | 消費者付款 **V1.0**（升級！）| 消費者 | 消費者 §1 階段 8（結算）| work-order Flow 12 | **❌ BDD 缺** | 業務模組（金流未列）| 🔴 | ✅ Q7=B（重大）| ⚠ blocked | **緊急**：選 provider（Stripe / 綠界 / 藍新 / Linepay）+ PCI compliance 審查 + 補 BDD F-211 |
| **F-012** | 技師月結撥款 **V1.0**（升級！）| 系統 + 財務 | 管理員旅程 §3 階段 5（月度結算） | work-order Flow | F-204 自動化會計 | 業務模組（撥款未列）| 🔴 | ✅ Q7=B（重大）| ⚠ blocked | 與 F-011 同 provider；撥款 API 整合 + 補 BDD |
| **F-013** | 對帳爭議雙簽 | 技師 ↔ 客服 | 管理員旅程 §3 階段 5 + 客服主管 §6 | work-order Flow 6（退款）+ admin-governance G4（爭議） | F-204 + F-207 退款審批 | 模組 6 RefundService | 🟢 | ✅ Q2=A / Q4=C | ✅ aligned | 實作 Director 階層雙簽 + 工作日+國定假日 calendar lib（holidays 套件） |
| **F-014** | 退款流程 | 客服 + 主管 | 客服主管旅程 §6 階段 3-5 | work-order Flow 6 退款 | F-207 退款審批與雙簽 | 模組 6 RefundService | 🟡 | ✅ Q7=B（重大）| ⚠ partial | 5/9 evening sprint：補 `createRefundRequest` dual-trigger（CS web Modal + agent intent skeleton）+ business unique key (work_order_id, reason_code) + auto dual-sign threshold NT$100,000；剩金流回沖仍綁 Q7=B provider 選型整合 |
| **F-015** | 保固申訴 | 消費者 → 客服 | 異常流程 §7.4（品質不合格） | work-order Flow 7（保固爭議） | F-208 保固爭議處理 | 模組 12 WarrantyClaim | 🟢 | — | ✅ aligned **(impl complete)** | 5/9 evening sprint：補 `createWarrantyClaim` dual-trigger（CS web Modal + agent intent skeleton）。warranty-dispute spec 已有 |
| **F-016** | SLA 紅色警報（2hr 到場） | 系統 + 主管 | 異常流程 §7.3（Red Code） | work-order §3 SLA + admin-governance G4 升級 | ✅ F-110 | 業務模組（sla_monitor.py）| 🟢 | ✅ Q5=B | ✅ aligned **(impl complete)** | **PR #48**：sla_monitor.py 加 arrival_overdue alert_type + WS publish `/realtime/sla-alerts` + dashboard 紅燈（SlaAlertBanner）+ Q5=B 合規驗證（payload 0 賠償/沖銷字串；audit policy marker；8 component test）|
| **F-017** | SOP 草稿審核 | AI → 客服 → 主管 | 管理員旅程 §3 階段 2（知識庫） | work-order §15 知識沉澱 | F-104 自進化知識庫 | 模組 5 SOPGenerator | 🟢 | — | ✅ aligned **(impl complete)** | 5/9 evening sprint：補 `createSopDraft` endpoint + rating>=4 trigger skeleton（`agent/harness/sop_extractor.py`，LLM extract 仍 placeholder，V2.0 升級）|
| **F-018** | 客服接管對話 | 客服 | 消費者 §1 階段 5（三層解決最後降級）| 隱含於 work-order Flow 1 升級 | F-103 三層解決機制 | 模組 3 ThreeLayerResolver | 🟢 | — | ✅ aligned **(impl complete)** | **PR #47**（順手解）：conversation_service.py LINE Push real impl（line_push_service.py 含 retry 1s/2s/4s + audit + fail-soft）|
| **F-019** | RBAC 動態調整 | 管理員 | 管理員旅程 §3 階段 4（客訴升級隱含 RBAC） | admin-governance G1 RBAC 角色生命週期 | F-209 動態 RBAC | 模組 14 RBACService | 🟢 | ✅ Q1=A / Q2=A | ✅ aligned **(impl complete)** | **PR #49**：updateRolePermissions API + ROLE_HIERARCHY (super_admin>tenant_admin>director>manager>...) + can_grant 嚴格 > + WS publish `/realtime/rbac` + RolePermissionsEditor UI（10 BE test + 2 @wip Playwright）|
| **F-020** | 稽核日誌 | 管理員 | 管理員旅程 §3 階段 4 隱含 | admin-governance G2 稽核日誌 | F-205 admin V2.0 + F-209 | 模組 13 AuditLogger | 🟢 | — | ✅ aligned | exportAuditEvents 已實作 |
| **F-021** | Dashboard / 報表 | 管理員 | 管理員旅程 §3 階段 1（儀表板） | dispatch §7 報表 SQL + API | F-105 + F-205 | 業務模組未明列 | 🟢 | — | ✅ aligned **(impl complete)** | 5/10 morning：補完 `getKpiReport` + `getRevenueSummary` 的 `start_date` / `end_date` query params（commit `4c1d74b`），DateRangePicker 4 頁 wiring 全通 |
| **F-022** | 消費者端工單追蹤 | 消費者 | 消費者 §1 階段 6-7（已派工後） | work-order Flow 1 後段 | （待補 F-211）| 業務模組（消費者 API 未列）| 🟢 | ✅ Q3=C | ✅ aligned | PR #40 T2：getWorkOrderPublicStatus spec + skeleton + Web placeholder 齊；可寫 contract test + @wip Playwright。HMAC token 簽章 + BDD F-211 follow-up |
| **F-023** | 錯誤頁 / 離線 | 任何 | （cross-cutting，無單一旅程） | （cross-cutting） | ✅ F-110 錯誤邊界 cross-cutting Feature（4 scenarios）| （cross-cutting）| 🟢 | — | ✅ aligned | PR #40 T4 已建 F-110 + 4 scenarios，本次同步矩陣狀態（先前與 §4 row 211 不一致）|

> **2026-05-09 evening 後狀態（P0 bridge sprint 後）**：✅ aligned (18，含 10 條 impl complete) / ⚠ partial (3) / ⚠ blocked (2) / ❌ orphan (0)
>
> 📋 **狀態定義**：✅ aligned 含兩階段 — (a) **spec-driven**（規格 + test infra + PM 拍板齊，PR #41 階段）；(b) **impl complete**（production code 完成 + component test pass，PR #45-49 + 5/9 evening sprint 階段）。標 `(impl complete)` 註明已升至第二階段。
>
> PR #45-49 production code 完成（5 流程 + 1 順手）：
> - F-004 ✅(impl complete)：PR #45 dispatcher RBAC + 客服繞過 audit
> - F-008 ✅(impl complete)：PR #46 HMAC 真實簽章 + scope_change service real
> - F-010 ✅(impl complete)：PR #47 3 reschedule/delay ops + LINE Push real
> - F-018 ⚠partial → ✅(impl complete)：PR #47 順手解 LINE Push real
> - F-016 ✅(impl complete)：PR #48 SLA Soft alert + 紅燈（Q5=B 合規驗證）
> - F-019 ✅(impl complete)：PR #49 updateRolePermissions + 階層 + UI + WS
>
> **5/9 evening P0 bridge sprint 完成（commit `44873f0` merged 到 dev）— ADR-009 §8 D pattern HTTP call from agent to admin API**：
> - F-001 ✅ → ✅(impl complete)：`createConversation` endpoint + agent webhook bridge `_ensure_conversation_record` + `AdminAPIClient`（30 min cache）
> - F-014 ⚠blocked → ⚠partial：`createRefundRequest` dual-trigger + business unique key (work_order_id, reason_code) + auto dual-sign threshold NT$100,000（規則層完成；金流回沖仍綁 Q7=B）
> - F-015 ✅ → ✅(impl complete)：`createWarrantyClaim` dual-trigger（CS web Modal + agent intent skeleton）
> - F-017 ✅ → ✅(impl complete)：`createSopDraft` + rating>=4 trigger skeleton（`agent/harness/sop_extractor.py`）
> - 附帶 `Schema_doc_numbering.sql`：5 表加 `document_number`（ERP-style `XX-YYYYMMDD-NNNN`）+ `agent_outbox` 表 + 業務 unique keys
> - 測試：Backend integration 29/29 pass + Playwright E2E 3/3 pass + OpenAPI lint 0 errors
>
> F-011 / F-012 仍 ⚠blocked（綁 Q7=B provider 選型，待 PR #39 follow-up 4 sub-decision 拍板）

---

## 1.5 Legacy ID → New ID 對照表（Phase 3 漸進遷移第一步）

> **本表是 Phase 3 漸進遷移的第一步（alias 不改舊 ID）**：
> - 既有檔（_SSOT 全 23 row、E7 BDD 19 Features、E5x×3 Flows）**不重命名**
> - 新增內容用新前綴：例如新建 BDD scenarios 用 `FT-NNN`、新加測試用 `AT/ST/IT/UT/PT/SEC-NNN`
> - 完整遷移（所有舊 ID 改名）等下次 PR 評估
> - 詳細設計見 [[_RESTRUCTURE-PROPOSAL#3-提案-b統一-id-系統|提案 §3.1]]

### 1.5.a User Flows（F-001~F-023 → US-001~US-023）

| Legacy ID | 描述 | New ID（Phase 3 預留）| 推薦使用時機 |
|-----------|-----|-------------------|------------|
| F-001 | LINE 報修 → ProblemCard | US-001 | 新 BDD scenario / spec 引用時用 |
| F-002 | 客服審 PC → 開 WO | US-002 | 同上 |
| F-003 | 自動派工規則引擎 | US-003 | 同上 |
| F-004 | 手動派工 | US-004 | 同上 |
| F-005 | 技師接單 → 出發 | US-005 | 同上 |
| F-006 | 到場拍照 | US-006 | 同上 |
| F-007 | 材料申請 | US-007 | 同上 |
| F-008 | Scope Change | US-008 | 同上 |
| F-009 | 完工簽名 | US-009 | 同上 |
| F-010 | 改約 / 延遲 | US-010 | 同上 |
| F-011 | 消費者付款 V1.0 | US-011 | 同上 |
| F-012 | 技師月結撥款 V1.0 | US-012 | 同上 |
| F-013 | 對帳爭議雙簽 | US-013 | 同上 |
| F-014 | 退款流程 | US-014 | 同上 |
| F-015 | 保固申訴 | US-015 | 同上 |
| F-016 | SLA 紅色警報（2hr 到場）| US-016 | 同上 |
| F-017 | SOP 草稿審核 | US-017 | 同上 |
| F-018 | 客服接管對話 | US-018 | 同上 |
| F-019 | RBAC 動態調整 | US-019 | 同上 |
| F-020 | 稽核日誌 | US-020 | 同上 |
| F-021 | Dashboard / 報表 | US-021 | 同上 |
| F-022 | 消費者端工單追蹤 | US-022 | 同上 |
| F-023 | 錯誤頁 / 離線（cross-cutting）| US-023 | 同上 |

### 1.5.b BDD Features（F-1NN/F-2NN → FT-NNN）

| Legacy ID | 描述 | New ID（Phase 3 預留）| 推薦使用時機 |
|-----------|-----|-------------------|------------|
| F-101~F-109 | V1.0 BDD Features（9 個）| FT-101~FT-109 | 新 BDD Feature 編號用 FT- 前綴 |
| F-201~F-210 | V2.0 BDD Features（10 個）| FT-201~FT-210 | 同上 |
| F-110 | SLA Soft Alert（新增）| FT-110 | 已用新前綴（Phase 3 範例）|

### 1.5.c E5x Workflow / Module / Decision IDs

| Legacy ID | 描述 | New ID（Phase 3 預留）| 推薦使用時機 |
|-----------|-----|-------------------|------------|
| Flow 1-13 | E5x work-order Flows | UC-101~UC-113 | use case 編號 |
| G1-G4 | E5x admin governance | UC-G01~UC-G04 | 同上 |
| 模組 1-7 | E7x module spec | MOD-01~MOD-07 | module 規格編號 |
| Q1-Q10 | PM decisions | DEC-001~DEC-010 | 新決策直接用 DEC- |

### 1.5.d 新類型 ID（Phase 3 新增類別）

| 類型 | New ID 前綴 | 推薦使用時機 |
|------|------------|------------|
| Quality Attributes | QA-NNN | north-star-requirements.md 用 |
| Compliance | COM-NNN | 同上 |
| Acceptance Test | AT-NNN | v-model-right/ tests 用 |
| System Test | ST-NNN | 同上 |
| Integration Test | IT-NNN | integration-test-matrix.md 用 |
| Unit Test | UT-NNN | module spec test cases 用 |
| Performance Test | PT-NNN | performance-baseline.md 用 |
| Security Test | SEC-NNN | security-checklist.md 用 |

---

## 2. 反向缺口（BDD Feature 有但 E7x 沒列獨立流程）

對應 [[v-model-right/E7--bdd-scenarios#ⅲb-feature--e7x-流程編號對照f-101f-201--f-001f-023|E7 §Ⅲ.b]] 反向缺口：

| BDD Feature | 隱含於 / 屬性 | 修正動作 |
|------------|-------------|---------|
| F-103 三層解決機制 | 隱含於 F-001 / F-018 | 文件治理：在 F-001 / F-018 cross-ref 補 F-103 |
| F-106 安全防護 | Cross-cutting（E7x §6 安全閘門已涵蓋）| 不獨立列流程；於 F-001 / F-018 / F-007 各加 @F-106 註腳 |
| F-109 家族成員覆核 | V1.0 後段 | 若獨立 user flow → E7x 補 F-024；否則文件交叉註明 |
| F-203 標準化定價引擎 | 隱含於 F-008 | F-008 cross-ref 補 F-203 + module 8 PricingEngine |
| F-206 V1↔V2 資料串接 | Migration（implementation detail）| 不獨立列流程；於 release plan 文件處理 |

---

## 3. 對齊狀態彙總

```
總計 23 user flows（5/9 evening P0 bridge sprint 後）

  ✅ aligned    : 19 條  F-001/F-002/F-003/F-004/F-005/F-006/F-008/F-009/F-010/
                         F-013/F-015/F-016/F-017/F-018/F-019/F-020/F-021/F-022/F-023
                         （其中 11 條標 (impl complete)：
                           F-001/F-002/F-004/F-008/F-010/F-015/F-016/F-017/
                           F-018/F-019/F-021）
  ⚠ partial    :  2 條  F-007/F-014
  ⚠ blocked    :  2 條  F-011/F-012（全綁 Q7=B provider 選型）
  ❌ orphan     :  0 條

  PR #45-49 後：5 條從「spec-driven aligned」升「impl complete」：
    F-004 / F-008 / F-010 / F-016 / F-019（標 ✅(impl complete)）
    F-018 從 ⚠partial → ✅(impl complete)（PR #47 順手解 LINE Push real）

  5/9 evening P0 bridge sprint 後：
    F-001 / F-015 / F-017 從 spec-driven aligned 升 ✅(impl complete)
    F-014 從 ⚠blocked → ⚠partial（規則層 5/9 修完；金流回沖仍綁 Q7=B）

  5/10 morning（worktree 4-track sync）後：
    F-021 ⚠partial → ✅(impl complete)（T4 補 getKpiReport/getRevenueSummary
    start_date/end_date filter；commit `4c1d74b`）

歷程：
  - PR #38 (PM 拍板) ：✅10 / ⚠partial 8 / ⚠blocked 4 / ❌0
  - PR #40 (5-track)：✅15 / ⚠partial 5 / ⚠blocked 3 / ❌0  (+5 升 ✅)
  - PR #45-49 (impl)：✅16 / ⚠partial 4 / ⚠blocked 3 / ❌0  (+1 F-018 升 ✅，5 條從
                       spec-driven 升 impl complete)
  - 5/8 (matrix sync)：✅18 / ⚠partial 2 / ⚠blocked 3 / ❌0  (+2 升 ✅)
                          F-002（補模組 9 ProblemCardReviewEngine）
                          F-023（與 §4 row 211 PR #40 T4 結果同步）
  - 5/9 evening (P0 sprint) ：✅18 / ⚠partial 3 / ⚠blocked 2 / ❌0
                          (+1 F-014 blocked→partial；+3 F-001/F-015/F-017 升 impl complete)
  - 5/10 morning (4-track) ：✅19 / ⚠partial 2 / ⚠blocked 2 / ❌0
                          (+1 F-021 升 ✅(impl complete))

按阻塞類型（剩 4 條 ⚠/blocked）：
  Q7=B provider 選型可解 : 2 條（F-011/F-012）— F-014 規則層 5/9 已修，剩金流回沖等 provider
  外力 / TODO 可解        : 2 條（F-007 F-210 規格 / F-014 金流回沖）
```

---

## 4. 共通對齊缺口（多檔同問題）

| 缺口類型 | 影響檔 | 處理優先度 | 修正動作 | 狀態 |
|---------|-------|---------|---------|------|
| 3 個 E5x workflow 缺 F-XXX 引用 | work-order / dispatch / admin-governance | 🔴 HIGH | 各 Flow 標題後補「對應 F-NNN」（依本表第 1 節） | ✅ **本 PR 解**（work-order 16 Flow + dispatch §1-§9 + admin-governance G1-G4 全補）|
| 角色命名 6 vs 7（work-order vs admin-governance） | work-order §2.1 / admin-governance §1.1 | 🟡 MEDIUM | admin-governance §1.1 加「對應 work-order 角色」column | ✅ **本 PR 解**（既有 column 補 dispatcher Q1=A 拍板狀態 + 新增 operations_director 角色 + ROLE_HIERARCHY 階層說明）|
| Module spec 缺 F-101~F-109 對應 | E7x module-spec | 🟡 MEDIUM | 各模組 subheading 補「對應 BDD Feature: F-NNN」 | ✅ **本 PR 解**（模組 1-8 全補 BDD Feature + 流程引用）|
| F-107 情緒分流閾值 0.85 vs 0.90 不一致 | E7 line 767 / 802 | 🟡 MEDIUM | ~~統一為 0.90~~ → 釐清雙閾值設計（main 0.90 / edge 0.85，非衝突）| ✅ **本 PR 解**（Feature header 加 dual-threshold callout + inline note 強化）|
| Q1-Q10 §12 全部 ⬜待拍 | pm-alignment | 🔴 BLOCKING | 排 90 min PM 對齊會議（外力，本 PR 不解） | ✅ **PR #38 解**（10/10 全拍板 2026-05-07）|
| F-011/F-016/F-022 BDD 缺 | E7 BDD | 🟡 待 PM | 等 Q3/Q5/Q7 拍板後補 BDD Feature（外力）| ⚠ **部分解**：F-016 PR #40 T4 補 F-110 ✅ / F-022 Q3=C 拍板可寫但 BDD F-211 仍 TODO / F-011 仍綁 Q7=B provider |
| F-023 BDD 缺 | E7 BDD | 🟡 LOW | 建議新增 F-110 錯誤邊界 cross-cutting Feature | ✅ **PR #40 T4 解**（F-110 錯誤邊界 cross-cutting Feature + 4 scenarios 已建）|

---

## 5. 修正動作優先級（給 Phase 4）

### P0（本 PR 可做）
1. ✅ 在 3 個 E5x workflow 補「對應 F-NNN」cross-ref（F-001~F-023）
2. ✅ admin-governance §1.1 角色表加「對應 work-order 角色」column
3. ✅ E7 line 802 統一 confidence 閾值（0.85 → 0.90）+ 加註腳
4. ✅ E1x line 131 派工敘述補配重順序（對齊 F-202 + dispatch-weights）
5. ✅ E1x line 342 客訴 SLA 補分級（高 anger_level vs 一般）
6. ✅ Module spec 各模組 subheading 補「對應 BDD Feature: F-NNN」
7. ✅ 更新 _MOC.md 加入 _review-notes / _alignment-matrix 索引

### P1（後續 PR，不阻塞）
1. work-order §1.2 + §18 狀態圖合併（13 → 16 狀態單一圖）
2. dispatch §3 薪酬補實作公式 + Python 函數
3. dispatch §7 報表拆 3 endpoint
4. admin-governance §1.2 補全系統權限碼 catalogue
5. module-spec V2.0 模組 6-21 補 DbC 規格

### P2（外力解，本 PR 不做）
1. F-011 / F-014 金流 provider 整合（綁 PM Q7 + 商業決策）
2. F-012 撥款 API 整合（綁 財務 + 銀行）
3. F-016 SLA 賠償計算（綁 PM Q5 + 金流）
4. F-022 消費者端追蹤（綁 PM Q3）
5. F-018 LINE Push API 真實串接（外力 + 帳號）
6. PM Q1-Q10 對齊會議（外力 90 min）

---

## 6. Verification

對齊矩陣使用後驗證：

- [ ] 從任一 F-XXX 可在 1 分鐘內找到所有對應檔案位置
- [ ] 每個 ⚠ / ❌ row 都有具體「修正動作」（無 placeholder）
- [ ] PM 阻塞 column 與 [[decision-log/E7x--pm-alignment-Q1-Q10]] §12 追蹤表雙向一致
- [ ] 反向缺口（§2）每行都有歸宿（隱含 / cross-cutting / 補 F-024+）
- [ ] §5 P0 動作完成率 100% 視為 Phase 4 完成

---

## 7. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | Claude (assisted) | 初版：以 E7x F-001~F-023 為主鍵，整合 E1x / E5x×3 / E7 / E7x×3 共 8 維對應；標出 4 orphan + 10 partial + 8 aligned + 1 cross-cutting；建立 P0 / P1 / P2 修正優先序 |
| 2026-05-07 | PM + Claude (sync) | **PM Q1-Q10 全拍板同步**：10 row 中 9 row 的 PM Block column 從 `**Q-N**` → `✅ Q-N=X`；對齊狀態升級 — F-010 ⚠blocked→✅aligned, F-013 ⚠partial→✅aligned, F-011/F-012/F-014/F-022 ❌orphan→⚠blocked（待 Q7=B provider 選型 / Q3=C Web 匿名 token 實作）, F-016 ❌orphan→⚠partial（Q5=B Soft SLA）, F-004/F-008/F-019 ⚠blocked→⚠partial. 詳見 [[decision-log/E7x--pm-alignment-Q1-Q10#12-決策追蹤總表]]。 |
| 2026-05-07 | Claude (assisted) | **新增 §1.5 Legacy ID → New ID 對照表（Phase 3 漸進遷移第一步，alias 不改舊 ID）**：覆蓋 23 條 user flows（F→US）、19 個 BDD Features（F-1NN/F-2NN→FT）+ F-110 新增、E5x Flows / Modules / Decisions（→UC/MOD/DEC）、新類型 QA/COM/AT/ST/IT/UT/PT/SEC。詳見 [[_RESTRUCTURE-PROPOSAL#3-提案-b統一-id-系統|提案 §3.1]]。 |
| 2026-05-07 | Claude (assisted) | **PR #40 5-track 解綁後狀態升級**：新增「立即可測 ✅」spec-driven 定義（規格 + test infra + PM 拍板齊備 → 可寫測試，不要求 production code 100%）。5 條流程升 ✅ aligned：F-004（T1 dispatcher seed）/ F-008（T2 Web token spec）/ F-016（T4 F-110 BDD）/ F-019（T1 dispatcher 角色）/ F-022（T2 getWorkOrderPublicStatus spec）。新統計：✅ 15 / ⚠ partial 5 / ⚠ blocked 3（全綁 Q7=B provider 選型）/ ❌ 0。 |
| 2026-05-08 | Claude (assisted) | **PR #45-49 production code 完成**：5 條 spec-driven aligned 升「impl complete」+ F-018 順手升 ✅。**PR #45** F-004 dispatcher RBAC 升級修補 P0 + 客服繞過 audit / **PR #46** F-008 HMAC 真實簽章 + scope_change_service real（CAS 防 race，27 test）/ **PR #47** F-010 3 reschedule/delay ops + LINE Push real（順手解 F-018 LINE Push integration TODO）/ **PR #48** F-016 SLA Soft alert + WS publish + dashboard 紅燈（Q5=B 合規驗證 — payload 0 賠償字串）/ **PR #49** F-019 updateRolePermissions API + ROLE_HIERARCHY + WS + RolePermissionsEditor UI。新統計：✅ 16 / ⚠ partial 4 / ⚠ blocked 3（仍綁 Q7=B）/ ❌ 0。 |
| 2026-05-08 | Claude (assisted) | **§4 共通對齊缺口收尾 4 項 ✅**：(1) E5x workflow 3 檔 F-NNN 引用補齊（work-order 16 Flow / dispatch §1-§9 / admin-governance G1-G4）；(2) admin-governance §1.1 角色表 dispatcher Q1=A 標已拍板 + 新增 operations_director（Q2=A）+ ROLE_HIERARCHY 階層說明；(3) E7x module-spec 模組 1-8 全補 BDD Feature + 流程引用；(4) E7 F-107 雙閾值設計釐清（Feature header callout 0.90 main / 0.85 edge 非衝突，calibration 變動需同步）。§4 表加狀態 column；剩 1 項 ⚠ 部分解（F-011 BDD 仍綁 Q7=B）。 |
| 2026-05-08 | Claude (assisted) | **F-002 / F-023 矩陣狀態 sync ✅**：(1) F-002 ⚠partial → ✅aligned — 在 `E7x--module-spec-v1-core.md` 補模組 9 ProblemCardReviewEngine（規格 9-1 review_problem_card / 9-2 create_work_order_from_problem_card，含 DbC 前置/後置/不變性 + 5 類測試情境輪廓），對齊 BDD F-105 admin V1.0；(2) F-023 ⚠partial → ✅aligned — 與 §4 row 211 早已記錄的 PR #40 T4 F-110 cross-cutting Feature + 4 scenarios 結果同步（先前 row 71 與 §4 不一致）。新統計：✅ 18 / ⚠ partial 2（F-007 / F-021）/ ⚠ blocked 3（F-011/012/014 全綁 Q7=B）/ ❌ 0。 |
| 2026-05-09 | Sunny + Claude | **F-002 production code 補完 ✅(impl complete)**：三層驗證發現 F-002「開 WO」這步在 production code **完全沒實作** — confirmProblemCard 只 UPDATE PC.status，無 side effect；work_order_service 全檔無 `create_*` 函式；dev 靠 seed data 看似 work，production 第一筆 confirmed PC 就會孤立，連帶 F-003~F-016 派工/技師/對帳/SLA 主幹斷鏈。本 PR 補：(1) `api/services/work_order_service.create_from_problem_card()` 含 SELECT FOR UPDATE 防 race + idempotency check + address fallback chain；(2) router `POST /problem-cards/{id}/convert-to-work-order` (`convertToWorkOrder` operationId) — 201 (new) / 200 (existing)；(3) OpenAPI spec 加 operation + `ConvertProblemCardToWorkOrderRequest` schema；(4) frontend 在 PC confirmed 狀態啟用「開單」按鈕；(5) 7 case integration test（happy/idempotent/state×2/address×2/tenant）；(6) `E7x--test-plan-and-readiness.md` row 88 wiring 修正 + 評等 🟡 → 🟢。F-002 SSOT row 50（模組規格）已於 5/8 標 ✅，本次同步 production code 至同層級。|
| 2026-05-09 evening | Sunny + Claude | **P0 bridge pattern sprint 完成 ✅**：ADR-009 D pattern 拍板採用 HTTP call from agent to admin API；4 條 P0 production blocker 修補（commit `44873f0` merged 到 dev）。F-001 ✅(impl complete) `createConversation` + agent webhook `_ensure_conversation_record` + 30 min cache；F-014 ⚠blocked→⚠partial（規則層補完 `createRefundRequest` dual-trigger + business unique key + auto dual-sign threshold；剩金流回沖綁 Q7=B）；F-015 ✅(impl complete) `createWarrantyClaim` dual-trigger；F-017 ✅(impl complete) `createSopDraft` + rating>=4 trigger skeleton。附帶 `Schema_doc_numbering.sql`（5 表 + sequences + ERP-style document_number XX-YYYYMMDD-NNNN + agent_outbox 表）。Backend 29/29 + Playwright 3/3 全 pass。新統計：✅ 18（含 10 個 impl complete）/ ⚠ partial 3（F-007/F-014/F-021）/ ⚠ blocked 2（F-011/F-012 全綁 Q7=B 金流 provider）/ ❌ 0。 |
| 2026-05-10 morning | Sunny + Claude | **4-track worktree 平行 sync ✅**：4 條 deferred items 平行收尾 — (T1) SSOT + test-plan 矩陣 sync 5/9 evening sprint 結果（commit `a8111ae`）；(T2) agent H_INTENT + H_PC layer 整合（commit `ef567d0`，15/15 unit test pass，新增 `harness/intent_handler.py` + `harness/pc_creator.py`，stage 4.5 + 7.5 接入 orchestrator）；(T3) 5 detail/list page 顯示 ERP `document_number`（commit `d636553`）；(T4) F-021 `getKpiReport` + `getRevenueSummary` 加 `start_date` / `end_date` query params（commit `4c1d74b`）→ **F-021 ⚠partial → ✅aligned (impl complete)**。新統計：✅ 19（含 11 個 impl complete）/ ⚠ partial 2（F-007/F-014）/ ⚠ blocked 2（F-011/F-012）/ ❌ 0。剩外力解 4 條：F-007 F-210 規格（PM+BE）+ F-011/F-012/F-014 金流 Q7=B provider 選型會議。|
