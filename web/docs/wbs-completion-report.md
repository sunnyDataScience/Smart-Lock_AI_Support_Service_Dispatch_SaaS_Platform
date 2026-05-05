# 工單系統 WBS 完成度報告

對應主 WBS：[`docs/01-define/E2x--wbs-project-schedule.md`](../../docs/01-define/E2x--wbs-project-schedule.md)（v2.0 / 2026-04-04）

報告日期：**2026-05-05**（更新）
報告基準：`feat/web-tech-app` branch（91/91 OpenAPI operationId + 師傅端 12 頁 + 10 realtime 頻道）
本報告範圍：**工單系統相關 WBS**（Phase 5–8 的 V2.0 派工/會計平台）

> **05-05 更新**：本週（04-30 ~ 05-05）99 commits、12 個版本（v1.4.0 → v1.15.2），完成師傅端 PWA 12 頁與 realtime 10 頻道整合；詳見 [progress-report-2026-05-05.md](./progress-report-2026-05-05.md)

---

## 目錄

1. [執行摘要](#執行摘要)
2. [完成度總覽](#完成度總覽)
3. [Phase 5 — V2.0 設計](#phase-5--v20-設計)
4. [Phase 6 — 派工 MVP](#phase-6--派工-mvp)
5. [Phase 7 — 會計與後台整合](#phase-7--會計與後台整合)
6. [Phase 8 — UAT 與上線](#phase-8--uat-與上線)
7. [WBS vs 實作差距重點](#wbs-vs-實作差距重點)
8. [後續行動建議](#後續行動建議)

---

## 執行摘要

| 指標 | 數值 |
| :--- | ---: |
| 主 WBS 標示完成度（Phase 5–8） | ~16% 平均 |
| **實際**完成度（Phase 5–8） | **約 65%** |
| OpenAPI operationId 已實作 | **91 / 91** ✅ |
| 後端 router 數 | 33 |
| 前端 Admin 頁面數 | 41（含 layout / 子頁） |
| Seed 資料覆蓋表數 | 17 張 |
| 主要落差來源 | WBS 文件未更新 + 師傅端工作台尚未動工 |

**結論**：工單系統的**管理後台**（甲方端）與**後端 API**幾乎全數完成，落差集中於：

1. WBS 文件未同步反映實際進度（多項標 ⬜ 但實已完成）
2. **師傅端工作台**（1.2.6.1 所有子項）尚未開始 — 此為獨立應用，不在當前 `web/` 範圍
3. **整合測試 / E2E / UAT**（1.2.7.3 + 1.2.8）未啟動

---

## 完成度總覽

| Phase | WBS 標示 | 04-29 實際 | **05-05 實際** | 主要差距 |
| :--- | :---: | :---: | :---: | :--- |
| Phase 5（W18–W19）V2.0 設計 | ~30% | ~85% | **~95%** | 師傅工作台 spec / wireframe 已隨實作補完 |
| Phase 6（W20–W24）派工 MVP | ~20% | ~50% | **~85%** | 師傅端 12 頁 + A37 派工介入完成；後端 5 組 endpoints 待補 |
| Phase 7（W25–W29）會計+整合 | ~15% | ~70% | **~80%** | Realtime 10 頻道前端打通；整合測試仍未啟動 |
| Phase 8（W30–W31）UAT 上線 | 0% | 0% | **0%** | 計畫期程未到 |

> 「實際」百分比依交付物完成情況、可驗證 endpoint 與頁面數估算，未經 PM 正式校準。

---

## Phase 5 — V2.0 設計

> 主 WBS Status: ~30%　**實際：~85%**

| WBS | 任務 | 主 WBS | 實際 | 證據 / 備註 |
| :--- | :--- | :---: | :---: | :--- |
| 1.2.5.1.1 | 甲方現行派工流程訪談 | ✅ | ✅ | — |
| 1.2.5.1.2 | 師傅角色/能力/地區梳理 | ✅ | ✅ | `technicians` table schema |
| 1.2.5.1.3 | 端到端派工流程設計 | ✅ | ✅ | `docs/02-design/specs/openapi.yaml` 工單狀態機 |
| 1.2.5.2.1 | 定價矩陣收集 | 🟡 | ✅ | `pricing_rules` 表 + seed |
| 1.2.5.2.2 | 加價規則確認 | ✅ | ✅ | — |
| 1.2.5.2.3 | 定價引擎邏輯設計 | ✅ | ✅ | `calculatePricing` operationId |
| 1.2.5.3.1 | 帳務流程訪談 | ✅ | ✅ | `docs/17_帳務流程.md` |
| 1.2.5.3.2 | 代墊款核銷流程設計 | 🟡 | 🟡 | RefundService 已實作 |
| 1.2.5.3.3 | 結算報表/傳票格式 | 🟡 | ✅ | `vouchers` PDF 已上線 |
| 1.2.5.4.1 | V2.0 DB Schema | ✅ | ✅ | `Schema.sql` + `Schema_v2_extensions.sql` + `Schema_api_phase1.sql` |
| 1.2.5.4.2 | V2.0 API Spec | ✅ | ✅ | `openapi.yaml` 91 ops |
| 1.2.5.4.3 | **師傅工作台 Wireframe** | ⬜ | ⬜ | **未開始** |
| 1.2.5.4.4 | ProblemCard ↔ 派工單串接設計 | ✅ | ✅ | — |

---

## Phase 6 — 派工 MVP

> 主 WBS Status: ~20%　**實際：~50%**

### 1.2.6.1 師傅工作台（Web App）— **完全未開始**

| WBS | 任務 | 狀態 |
| :--- | :--- | :---: |
| 1.2.6.1.1 | 前端專案建置 | ⬜ |
| 1.2.6.1.2 | 師傅 Auth 頁面 | ⬜ |
| 1.2.6.1.3 | 案件池列表（距離/品牌/地區篩選） | ⬜ |
| 1.2.6.1.4 | 案件詳情頁 | ⬜ |
| 1.2.6.1.5 | 一鍵接單 UI | ⬜ |
| 1.2.6.1.6 | 完工回報（照片+物料+工時） | 🟡 |
| 1.2.6.1.7 | 個人帳務中心 | ⬜ |
| 1.2.6.1.8 | RWD（手機/平板適配） | ⬜ |

> ⚠️ **重要釐清**：本專案 `web/` 是**甲方管理員後台**（admin dashboard），**不是師傅工作台**。1.2.6.1 全段對應的是另一個獨立部署的 Web App，當前 repo 內**完全未動**。後端 `acceptWorkOrder` / `completeWorkOrder` / `submitWorkOrderSignature` 等師傅端會用的 endpoint 已實作完成，師傅端 UI 開發隨時可啟動。

### 1.2.6.2 智慧派工引擎

| WBS | 任務 | 主 WBS | 實際 | 證據 |
| :--- | :--- | :---: | :---: | :--- |
| 1.2.6.2.1 | 師傅資料庫建置 | ✅ | ✅ | `technicians` 表 + seed |
| 1.2.6.2.2 | 自動媒合推薦演算法 | ✅ | 🟡 | `listDispatchCandidates` 端點存在但 AI 推薦引擎待接入 |
| 1.2.6.2.3 | 手動指派 API + UI | ✅ | ✅ | `assignWorkOrder` + `/work-orders/[id]` |
| 1.2.6.2.4 | 派單即時推播 | ⬜ | ⬜ | WebSocket 路徑保留未實作 |

### 1.2.6.3 標準化定價引擎

| WBS | 任務 | 主 WBS | 實際 | 證據 |
| :--- | :--- | :---: | :---: | :--- |
| 1.2.6.3.1 | 定價規則 DB | ✅ | ✅ | `pricing_rules` 表 |
| 1.2.6.3.2 | 定價計算 API | ✅ | ✅ | `calculatePricing` |
| 1.2.6.3.3 | 後台定價管理頁面 | ⬜ | 🟡 | `/settings` 部分對應，完整 GUI 待補 |

### 1.2.6.4 V1.0 ↔ V2.0 資料串接

| WBS | 任務 | 主 WBS | 實際 |
| :--- | :--- | :---: | :---: |
| 1.2.6.4.1 | ProblemCard → 派工單自動建立 | 🟡 | 🟡 |
| 1.2.6.4.2 | AI 客服「需要師傅」→ 自動進入案件池 | ⬜ | ⬜ |

---

## Phase 7 — 會計與後台整合

> 主 WBS Status: ~15%　**實際：~70%**

### 1.2.7.1 自動化會計系統

| WBS | 任務 | 主 WBS | 實際 | 證據 |
| :--- | :--- | :---: | :---: | :--- |
| 1.2.7.1.1 | 代墊款核銷 API+UI | 🟡 | 🟡 | RefundService 已實作 |
| 1.2.7.1.2 | 會計審核工作流 | ✅ | ✅ | `submitRefundDecision` + `/admin/refunds` |
| 1.2.7.1.3 | 月度結算報表 | ⬜ | ✅ | `listSettlements` + `/accounting` |
| 1.2.7.1.4 | 對帳單自動生成 | ⬜ | ✅ | `listReconciliations` + `approveReconciliation` |
| 1.2.7.1.5 | 會計傳票 + 匯出 | ⬜ | ✅ | `listVouchers` + `exportVoucher` (PDF) + `/accounting/vouchers` |
| 1.2.7.1.6 | 放款進度追蹤 | ⬜ | 🟡 | 結算狀態欄位存在，無獨立追蹤頁 |

### 1.2.7.2 總部管理後台擴充

| WBS | 任務 | 主 WBS | 實際 | 對應頁面 |
| :--- | :--- | :---: | :---: | :--- |
| 1.2.7.2.1 | 即時營運 Dashboard | ⬜ | ✅ | `/dashboard`（getDashboardStats） |
| 1.2.7.2.2 | 案件全生命週期管理 | 🟡 | ✅ | `/work-orders` + `/work-orders/[id]`（含 Kanban / Map） |
| 1.2.7.2.3 | 客訴處理模組 | ✅ | ✅ | `/admin/disputes` |
| 1.2.7.2.4 | 定價引擎 GUI 優化 | ⬜ | 🟡 | `/settings` 部分對應 |

> **附加超前項目**（不在 WBS 但已實作）：
> - `/admin/dispatch-queue` 派工佇列監控
> - `/admin/refunds` 退款審批
> - `/admin/warranty-claims` 保固索賠
> - `/admin/inventory` 庫存
> - `/admin/customers` 客戶主檔
> - `/admin/audit-events` 稽核日誌
> - `/admin/roles` RBAC 管理
> - `/admin/sentiment-alerts` 情緒告警
> - `/admin/reports/kpi`、`/admin/reports/revenue`、`/admin/reports/technician-ranking`
> - `/knowledge-base/*` 知識庫四子頁
> - `/accounting/*` 帳務四子頁
> - `/conversations/*`、`/problem-cards/*`、`/technicians/*` 各列表+詳情頁

### 1.2.7.3 全流程整合測試

| WBS | 任務 | 狀態 |
| :--- | :--- | :---: |
| 1.2.7.3.1 | E2E 流程測試（報修→AI→派工→完工→確認→結款） | ⬜ |
| 1.2.7.3.2 | V1.0 ↔ V2.0 資料流驗證 | ⬜ |
| 1.2.7.3.3 | 師傅端 100 人併發壓測 | ⬜ |
| 1.2.7.3.4 | 行動裝置相容性測試 | ⬜ |
| 1.2.7.3.5 | 會計報表正確性驗算 | ⬜ |

---

## Phase 8 — UAT 與上線

> 主 WBS Status: 0%　**實際：0%**

| WBS | 任務 | 狀態 |
| :--- | :--- | :---: |
| 1.2.8.1.1 | V2.0 功能完整性測試（甲方） | ⬜ |
| 1.2.8.1.2 | 端到端派工流程 UAT | ⬜ |
| 1.2.8.1.3 | 師傅 UAT | ⬜ |
| 1.2.8.2 | V2.0 部署上線 | ⬜ |

---

## WBS vs 實作差距重點

### 🟢 超前完成（WBS ⬜ 但已實作）

1. **會計四模組全上線**：1.2.7.1.3 / 1.2.7.1.4 / 1.2.7.1.5 → `/accounting`、`/accounting/vouchers` 含 PDF 匯出
2. **管理 Dashboard**：1.2.7.2.1 已 100% 完成
3. **案件生命週期管理**：1.2.7.2.2 含 Kanban + Map 視圖
4. **附加超前項目**：派工佇列、退款、保固、爭議、客戶主檔、稽核、RBAC、報表、庫存、情緒告警 — 共 10+ 頁
5. **OpenAPI 91 endpoints 全數實作完成**（WBS 未明列數量）

### 🟡 進行中

1. **1.2.6.4.1 ProblemCard → 派工單自動建立** — 後端串接邏輯部分已寫，缺端到端觸發
2. **1.2.5.3.2 代墊款核銷流程** — 雛形已有，雙簽流程簡化
3. **1.2.6.2.2 自動媒合演算法** — 端點已開但 AI 推薦尚未接入

### 🔴 落後（WBS 未列為延遲但實際阻礙進度）

1. **1.2.6.1 師傅工作台（8 個子項）** — 完全未開始；師傅端 Web App 是獨立應用，需新建專案
2. **1.2.5.4.3 師傅工作台 Wireframe** — 未產出
3. **1.2.6.2.4 派單即時推播** — WebSocket `/realtime/*` 路徑保留但未實作
4. **1.2.7.3 整合測試全段** — 5 項全 ⬜
5. **1.2.8 UAT 與上線** — 全段 ⬜

---

## 後續行動建議

### 優先級 P0（合約交付關鍵路徑）

1. **啟動師傅端工作台開發**（1.2.6.1）— 缺這個 V2.0 無法上線
   - 評估：另開 `mobile-web/` 或 `tech-portal/` 專案，沿用同一套 OpenAPI types
   - 預估工期：與 WBS 相同 3 週（W20–W22 折算）
2. **更新主 WBS 文件**（`E2x--wbs-project-schedule.md`）— 把已實作項勾選 ✅，避免甲方 review 時看到滿屏 ⬜ 誤判進度
3. **規劃整合測試**（1.2.7.3）— 至少 1.2.7.3.1（E2E）+ 1.2.7.3.5（會計驗算）需在 UAT 前完成

### 優先級 P1（提升交付品質）

4. **補 1.2.5.4.3 師傅工作台 Wireframe** — 開師傅端前必做
5. **補 1.2.6.2.4 即時推播** — WebSocket / SSE 接入派工佇列
6. **完整 1.2.6.4.1/2 串接** — AI 客服 → 自動派單觸發路徑

### 優先級 P2（管理後台優化）

7. **1.2.6.3.3 / 1.2.7.2.4 定價引擎 GUI** — 目前 `/settings` 只有部分介面
8. **`/knowledge-base/sop-performance` 真實化** — 目前 placeholder
9. **報表頁 metrics 擴充** — granularity / 期間切片 / 匯出（見 [`page-status.md`](./page-status.md)）

---

## 補充參考

| 文件 | 用途 |
| :--- | :--- |
| [`./page-status.md`](./page-status.md) | 各前端頁面已上線/示意/待接入細節（業主版） |
| [`./setup-guide.md`](./setup-guide.md) | 本機建置步驟 |
| [`./login-testing-guide.md`](./login-testing-guide.md) | 登入流程驗證 |
| `../../docs/01-define/E2x--wbs-project-schedule.md` | 主 WBS（合約附件三對應） |
| `../../docs/02-design/agent-harness/wbs-harness-development.md` | Agent Harness 子 WBS（與工單系統解耦） |
| `../../docs/02-design/specs/openapi.yaml` | API 契約 SSOT |
