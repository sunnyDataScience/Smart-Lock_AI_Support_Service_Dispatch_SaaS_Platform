# 頁面規格對應表 (Page Specification Mapping)

> **用途：** 作為 `docs/02-design/E5x--frontend-information-arch.md`（IA 48 頁定義）與本目錄 `web_design_spec_prompt_pipeline/pages/*.md`（19 份 page spec）之間的**雙向對照索引**。
> **維護原則：** IA 新增/刪除頁面時同步更新本檔；pipeline 新增 spec 檔時新增對應列。
>
> **最後更新：** 2026-04-23 · **版本：** v1.1 · **對應 IA 版本：** v1.2 · **對應前端架構版本：** v1.2

---

## 1. 快速總覽

| 指標 | 數字 |
|:-----|:----|
| IA 定義頁面總數 | **52 頁**（Admin 38 + Technician 12 + Global 2，V1.1 新增 A37/G1/G2/T11） |
| Pipeline spec 檔數 | **22 份**（`page_template.md` 不計） |
| 平均每份 spec 覆蓋頁數 | 2.4 頁 |
| 已覆蓋頁面 | 52 / 52 ✅ |
| V1.0 頁面 | 11 頁 / 已覆蓋 11 |
| V2.0 頁面 | 37 頁 / 已覆蓋 37（含驗證閘新增 A37/G1/T11）|
| V3.0 頁面 | 3 頁 / 已覆蓋 3 |
| V1.1 新增（plan §S 驗證閘）| A37、G1、T11（Global 類另增 G2 保留）|

---

## 2. IA 頁面 → Pipeline spec 檔（Forward Mapping）

### 2.1 Admin Panel（37 頁）

| IA # | 路徑 | 頁面名稱 | 版本 | Pipeline 檔 | Section 位置 |
|:-----|:-----|:---------|:-----|:------------|:-------------|
| A0 | `/login` | 管理員登入 | V1.0 | `14_auth_and_settings.md` | A0 子段 |
| A1 | `/dashboard` | 營運儀表板 | V1.0 | `02_admin_dashboard.md` ¹ | 主要 |
| A2 | `/conversations` | 對話列表 | V1.0 | `03_admin_conversations.md` | 列表段 |
| A3 | `/conversations/[id]` | 對話詳情 | V1.0 | `03_admin_conversations.md` | 詳情段 |
| A4 | `/problem-cards` | 問題卡列表 | V1.0 | `04_admin_problem_cards.md` | 列表段 |
| A5 | `/problem-cards/[id]` | 問題卡詳情 | V1.0 | `04_admin_problem_cards.md` | 詳情段 |
| A6 | `/knowledge-base/cases` | 案例庫 | V1.0 | `05_admin_knowledge_base.md` | Tab: 案例 |
| A7 | `/knowledge-base/cases/[id]` | 案例詳情/編輯 | V1.0 | `05_admin_knowledge_base.md` | `case_form_modal` |
| A8 | `/knowledge-base/manuals` | 手冊管理 | V1.0 | `05_admin_knowledge_base.md` | Tab: 手冊 |
| A9 | `/knowledge-base/sop-drafts` | SOP 審核佇列 | V1.0 | `05_admin_knowledge_base.md` | Tab: SOP 草稿 |
| A10 | `/knowledge-base/sop-drafts/[id]` | SOP 審核面板 | V1.0 | `05_admin_knowledge_base.md` | SOP 審核區 |
| A11 | `/work-orders` | 工單列表 | V2.0 | `06_admin_work_orders.md` | 列表視圖 |
| A12 | `/work-orders/[id]` | 工單詳情 | V2.0 | `07_admin_work_order_detail.md` | 主要 |
| A13 | `/technicians` | 技師管理 | V2.0 | `08_admin_technicians.md` | 列表段 |
| A14 | `/technicians/[id]` | 技師詳情 | V2.0 | `08_admin_technicians.md` | 詳情段 |
| A15 | `/accounting` | 帳務管理 | V2.0 | `09_admin_accounting.md` | 主要 |
| A16 | `/settings` | 系統設定 | V1.0 | `14_auth_and_settings.md` | A16 子段（4 Tabs） |
| A17 | `/admin/refunds` | 退款審批 | V2.0 | `10_admin_advanced.md` | 子頁 1 |
| A18 | `/admin/roles` | RBAC 管理 | V2.0 | `10_admin_advanced.md` | 子頁 6 |
| A19 | `/admin/inventory` | 庫存管理 | V2.0 | `10_admin_advanced.md` | 子頁 2 |
| A20 | `/admin/audit-events` | 稽核日誌 | V2.0 | `10_admin_advanced.md` | 子頁 5 |
| A21 | `/admin/warranty-claims` | 保固索賠 | V2.0 | `10_admin_advanced.md` | 子頁 3 |
| A22 | `/admin/disputes` | 爭議仲裁 | V2.0 | `10_admin_advanced.md` | 子頁 4 |
| A23 | `/admin/customers` | 客戶主檔 | V2.0 | `15_admin_customers_and_diagnostics.md` | A23 子段 |
| A24 | `/admin/customers/[id]` | 客戶詳情 | V2.0 | `15_admin_customers_and_diagnostics.md` | A24 子段（5 Tabs） |
| A25 | `/admin/technicians/[id]/schedule` | 技師排班 | V2.0 | `16_admin_technician_detail.md` | A25 子段 |
| A26 | `/admin/technicians/[id]/skills` | 技師技能認證 | V2.0 | `16_admin_technician_detail.md` | A26 子段 |
| A27 | `/admin/technicians/[id]/settlements` | 技師結算明細 | V2.0 | `16_admin_technician_detail.md` | A27 子段 |
| A28 | `/admin/dispatch-queue` | 派工佇列監控 | V2.0 | `17_admin_dispatch_queue_and_reports.md` | A28 子段 |
| A29 | `/admin/reports/kpi` | KPI 儀表板 | V2.0 | `17_admin_dispatch_queue_and_reports.md` | A29 子段 |
| A30 | `/admin/reports/technician-ranking` | 技師排行榜 | V2.0 | `17_admin_dispatch_queue_and_reports.md` | A30 子段 |
| A31 | `/admin/reports/revenue` | 營收報表 | V2.0 | `17_admin_dispatch_queue_and_reports.md` | A31 子段 |
| A32 | `/admin/diagnostics/[conversation_id]` | AI 診斷推理檢視 | V2.0 | `15_admin_customers_and_diagnostics.md` | A32 子段 |
| A33 | `/admin/knowledge-base/sop-performance` | SOP 績效儀表板 | V2.0 | `15_admin_customers_and_diagnostics.md` | A33 子段 |
| A34 | `/admin/settings/tenant` | 租戶設定 | V3.0 | `18_admin_multi_tenant.md` | A34 子段（5 Tabs） |
| A35 | `/admin/settings/tenant/brand` | 品牌客製 | V3.0 | `18_admin_multi_tenant.md` | A35 子段 |
| A36 | `/admin/super/*` | 超管平台 | V3.0 | `18_admin_multi_tenant.md` | A36 子段 |
| **A37** | `/admin/dispatch-manual` | **派工人工介入** | V2.0 ² | `20_admin_dispatch_manual.md` | 主要 |

> ¹ **注意：** `01_dashboard.md` 已於 2026-04-23 清理（commit `f42ee65`）。
> ² **V1.1 新增：** A37 由 plan §S 驗證閘補入，覆蓋 Flow 2 技師 3 次拒單後的人工派工情境。

### 2.2 Technician Web App（11 頁）

| IA # | 路徑 | 頁面名稱 | 版本 | Pipeline 檔 | Section 位置 |
|:-----|:-----|:---------|:-----|:------------|:-------------|
| T0 | `/tech-login` | 技師登入 | V2.0 | `14_auth_and_settings.md` | T0 子段 |
| T1 | `/pool` | 案件池 | V2.0 | `11_tech_pool.md` | 主要 |
| T2 | `/my-orders` | 我的工單 | V2.0 | `12_tech_my_orders.md` | 列表段 |
| T3 | `/my-orders/[id]` | 工單詳情/完工回報 | V2.0 | `12_tech_my_orders.md` | 詳情段 |
| T4 | `/account` | 帳戶中心 | V2.0 | `13_tech_account.md` | 主要 |
| T5 | `/my-orders/[id]/scope-change` | 範圍變更申請 | V2.0 | `19_tech_workorder_subflows.md` | T5 子段 |
| T6 | `/my-orders/[id]/material-request` | 缺料回報 | V2.0 | `19_tech_workorder_subflows.md` | T6 子段 |
| T7 | `/my-orders/[id]/delay` | 延遲通知 | V2.0 | `19_tech_workorder_subflows.md` | T7 子段 |
| T8 | `/my-orders/[id]/door-check` | 門面外觀檢核 | V2.0 | `19_tech_workorder_subflows.md` | T8 子段 |
| T9 | `/my-orders/[id]/signature` | 雙方電子簽章 | V2.0 | `19_tech_workorder_subflows.md` | T9 子段 |
| T10 | `/account/schedule` | 我的排班 | V2.0 | `19_tech_workorder_subflows.md` | T10 子段 |
| **T11** | `/my-orders/[id]/reschedule` | **改期日曆** | V2.0 ² | `22_reschedule_calendar.md` | 主要 |

### 2.3 Global Pages（跨角色，V1.1 新增）

| IA # | 路徑 | 頁面名稱 | 版本 | Pipeline 檔 | Section 位置 |
|:-----|:-----|:---------|:-----|:------------|:-------------|
| **G1** | `/notifications` | **全域通知中心** | V2.0 ² | `21_global_notifications.md` | 主要 |
| G2 | `/offline` | 離線狀態頁 | V2.0 ² | `23_global_offline.md` | 主要 |

> ³ G2 spec 於 2026-04-23 驗證閘 Stage 3 末期建立（commit `b409c8a`）。

---

## 3. Pipeline spec 檔 → IA 頁面（Reverse Mapping）

| # | Pipeline 檔 | 行數 | 覆蓋 IA 頁 | 主題 |
|:---|:---|---:|:---|:---|
| ~~01~~ | ~~`01_dashboard.md`~~ | — | — | 已清理（commit `f42ee65`） |
| 02 | `02_admin_dashboard.md` | — | **A1** | Admin 營運儀表板 |
| 03 | `03_admin_conversations.md` | — | **A2, A3** | 對話列表 + 詳情 |
| 04 | `04_admin_problem_cards.md` | — | **A4, A5** | 問題卡列表 + 詳情 |
| 05 | `05_admin_knowledge_base.md` | — | **A6, A7, A8, A9, A10** | 知識庫 3 Tabs（案例/手冊/SOP） |
| 06 | `06_admin_work_orders.md` | — | **A11** | 工單列表 + 派工看板 |
| 07 | `07_admin_work_order_detail.md` | — | **A12** | 工單詳情 |
| 08 | `08_admin_technicians.md` | — | **A13, A14** | 技師列表 + 詳情 |
| 09 | `09_admin_accounting.md` | — | **A15** | 帳務管理 |
| 10 | `10_admin_advanced.md` | 624 | **A17, A18, A19, A20, A21, A22** | 進階管理（6 合 1） |
| 11 | `11_tech_pool.md` | — | **T1** | 技師案件池 |
| 12 | `12_tech_my_orders.md` | — | **T2, T3** | 我的工單 |
| 13 | `13_tech_account.md` | 382 | **T4** | 帳戶中心 |
| **14** | `14_auth_and_settings.md` | **766** | **A0, T0, A16** | 認證 + 系統設定 |
| **15** | `15_admin_customers_and_diagnostics.md` | **862** | **A23, A24, A32, A33** | 客戶主檔 + AI 診斷治理 |
| **16** | `16_admin_technician_detail.md` | **735** | **A25, A26, A27** | 技師詳細管理 |
| **17** | `17_admin_dispatch_queue_and_reports.md` | **871** | **A28, A29, A30, A31** | 派工監控 + 報表群 |
| **18** | `18_admin_multi_tenant.md` | **835** | **A34, A35, A36** | 多租戶管理（V3.0） |
| **19** | `19_tech_workorder_subflows.md` | **1,004** | **T5, T6, T7, T8, T9, T10** + Flow 11 客戶 RSVP | 工單子流程 + T1.4 RSVP 補強 |
| **20** | `20_admin_dispatch_manual.md` | **297** | **A37** | 派工人工介入（V1.1 新增） |
| **21** | `21_global_notifications.md` | **324** | **G1** | 全域通知中心（V1.1 新增） |
| **22** | `22_reschedule_calendar.md` | **318** | **T11** | 改期日曆（V1.1 新增） |
| **23** | `23_global_offline.md` | **265** | **G2** | 離線狀態頁（V1.1 新增） |

粗體（14-19）為 2026-04-23 新增；20-23 為 2026-04-23 驗證閘（plan §S）補入。

粗體為 2026-04-23 新增。

---

## 4. 主題分群視圖

### 4.1 認證層（2 頁 / 1 檔）
| IA | Pipeline |
|:---|:---|
| A0 `/login`、T0 `/tech-login` | `14_auth_and_settings.md` |

### 4.2 V1.0 客服閉環（10 頁 / 5 檔）
| IA | Pipeline |
|:---|:---|
| A1 儀表板 | `02_admin_dashboard.md` |
| A2, A3 對話 | `03_admin_conversations.md` |
| A4, A5 問題卡 | `04_admin_problem_cards.md` |
| A6–A10 知識庫 | `05_admin_knowledge_base.md` |
| A16 系統設定 | `14_auth_and_settings.md` |

### 4.3 V2.0 派工閉環（6 頁 / 4 檔）
| IA | Pipeline |
|:---|:---|
| A11 工單列表 | `06_admin_work_orders.md` |
| A12 工單詳情 | `07_admin_work_order_detail.md` |
| A13, A14 技師管理 | `08_admin_technicians.md` |
| A28 派工佇列監控 | `17_admin_dispatch_queue_and_reports.md` |

### 4.4 V2.0 財務與治理（8 頁 / 2 檔）
| IA | Pipeline |
|:---|:---|
| A15 帳務管理 | `09_admin_accounting.md` |
| A17 退款、A18 RBAC、A19 庫存、A20 稽核、A21 保固、A22 爭議 | `10_admin_advanced.md` |

### 4.5 V2.0 客戶與 AI 診斷（4 頁 / 1 檔）
| IA | Pipeline |
|:---|:---|
| A23, A24 客戶主檔、A32 診斷推理、A33 SOP 績效 | `15_admin_customers_and_diagnostics.md` |

### 4.6 V2.0 技師詳細管理（3 頁 / 1 檔）
| IA | Pipeline |
|:---|:---|
| A25 排班、A26 技能、A27 結算 | `16_admin_technician_detail.md` |

### 4.7 V2.0 報表中心（3 頁 / 1 檔）
| IA | Pipeline |
|:---|:---|
| A29 KPI、A30 排行、A31 營收 | `17_admin_dispatch_queue_and_reports.md` |

### 4.8 V3.0 多租戶（3 頁 / 1 檔）
| IA | Pipeline |
|:---|:---|
| A34 租戶設定、A35 品牌客製、A36 超管平台 | `18_admin_multi_tenant.md` |

### 4.9 V2.0 技師端 Mobile-First（11 頁 / 4 檔）
| IA | Pipeline |
|:---|:---|
| T1 案件池 | `11_tech_pool.md` |
| T2, T3 我的工單 | `12_tech_my_orders.md` |
| T4 帳戶 | `13_tech_account.md` |
| T5 範圍變更、T6 缺料、T7 延遲、T8 門面、T9 簽章、T10 排班 | `19_tech_workorder_subflows.md` |

---

## 5. 關鍵互動路徑與檔案對照（主要使用者旅程）

### 5.1 管理員 — 知識庫管理閉環（V1.0）
```
14 登入 → 02 儀表板 → 05 SOP 草稿審核 → 05 案例庫確認
```

### 5.2 管理員 — 派工 Happy Path（V2.0）
```
02 儀表板 → 06 工單列表 → 07 工單詳情 → 08 技師指派
                            ↓
                   17 派工佇列監控（異常時）
```

### 5.3 管理員 — 退款/爭議治理（V2.0）
```
02 儀表板告警 → 10 退款審批（雙簽）
             → 10 爭議仲裁（證據對比）
             → 10 稽核日誌（事後追溯）
             → 15 診斷推理（AI 決策追溯）
```

### 5.4 管理員 — V3.0 租戶管理
```
18 超管 → 租戶列表 → 18 租戶詳情 → 18 品牌客製（即時預覽）
       → 18 API 金鑰（B2B 開通）
```

### 5.5 技師 — Happy Path（V2.0）
```
14 技師登入 → 11 案件池 → 12 接單 → 12 工單詳情 → 12 完工回報
                                                ↓
                                      19 T9 雙方電子簽章
```

### 5.6 技師 — 非 Happy Path 子流程（V2.0）
```
12 工單詳情（in_progress）
  ├─ 19 T5 範圍變更（Flow 3）
  ├─ 19 T6 缺料回報（Flow 4）
  ├─ 19 T7 延遲通知（Flow 5）
  ├─ 19 T8 門面檢核（Flow 10）
  └─ 19 T9 雙方簽章
```

---

## 6. 共用元件與 Pipeline 對應

> 對齊 `E5x--frontend-architecture.md §3.3` 的組件庫清單，標記每個業務元件在哪些 page spec 被引用。

| 元件 | 來源檔 | 被引用 pipeline |
|:-----|:-------|:----------------|
| `ConversationTimeline` | features/customer_service | 03, 04 |
| `ProblemCardViewer` | features/customer_service | 04, 07 |
| `SOPReviewPanel` | features/knowledge_base | 05 |
| `WorkOrderKanban` | features/dispatch | 06 |
| `QuotationBuilder` | features/accounting | 07, 09 |
| `CompletionReportForm` | features/dispatch | 07, 12, 19 |
| `CasePoolCard` | features/dispatch | 11 |
| `DispatchAttemptTimeline` | features/dispatch | 17 |
| `RefundApprovalWorkflow` | features/accounting | 10 |
| `AuditEventRow` | features/audit | 10 |
| `PermissionMatrix` | features/rbac | 10 |
| `InventoryLowStockBanner` | features/inventory | 10 |
| `DisputeEvidencePanel` | features/dispute | 10 |
| `DiagnosticTraceViewer` | features/agent-harness | 15 |
| `SignaturePad` | features/e-signature | 10 (refund), 19 (T9) |
| `TechnicianScheduleCalendar` | features/dispatch | 16 (A25), 19 (T10) |
| `SkillCertificationForm` | features/dispatch | 16 (A26) |
| `SettlementBreakdown` | features/accounting | 16 (A27), 09 |
| `KPIFunnelChart` | features/reports | 17 (A29) |
| `TechnicianRankingTable` | features/reports | 17 (A30) |
| `TenantSwitcher` | features/multi-tenant | 18 (A36 上部全域) |
| `BrandPreviewSandbox` | features/multi-tenant | 18 (A35) |
| `OfflineQueueIndicator` | infrastructure | 19 (技師端全域) |

---

## 7. WebSocket 頻道與 Pipeline 對應

> 對齊 `E5x--frontend-architecture.md §2.4` 的 10 個 WS 頻道，標記訂閱頁面。

| 頻道 | 訂閱頁面（IA） | Pipeline |
|:-----|:----------------|:---------|
| `/realtime/work-orders/{id}` | A12, T3 | 07, 12 |
| `/realtime/dispatch-queue` | A28 | 17 |
| `/realtime/pool/{tech_id}` | T1 | 11 |
| `/realtime/refunds` | A17 | 10 |
| `/realtime/disputes` | A22 | 10 |
| `/realtime/sla-alerts` | A1, A29 | 02, 17 |
| `/realtime/rbac` | 全域（所有 session） | 全部 |
| `/realtime/inventory/low-stock` | A19 | 10 |
| `/realtime/diagnostics/{conv_id}` (SSE) | A32 | 15 |
| `/realtime/notifications/{user_id}` | **G1 + 全域 header bell** | **21** + 全部 |

> **新增：** G1 通知中心是 `/realtime/notifications/{user_id}` 的主要消費頁（21_global_notifications.md）。

---

## 7.5 Flow × Page 覆蓋矩陣（2026-04-23 驗證閘新增）

> 對齊 `E5x--work-order-interaction-flows.md` 13 個 Flow + 新增 Flow 14、`flows-admin-governance.md` G1-G4、`flows-multi-tenant.md` MT1-MT5。

### 工單互動 Flow（14 個）

| Flow | 主題 | 涉及頁面（IA） | Pipeline |
|:---|:---|:---|:---|
| Flow 1 | Happy Path | T1 → T3 → T9 | 11, 12, 19 |
| Flow 2 | 拒單重派 | A11, A12, **A37**, T1 | 06, 07, **20**, 11 |
| Flow 3 | 範圍變更 | T3, T5, A12 | 12, 19, 07 |
| Flow 4 | 缺料處理 | T3, T6, A12, A19 | 12, 19, 07, 10 |
| Flow 5 | 延遲通知 | T3, T7, **T11** | 12, 19, **22** |
| Flow 6 | 退款雙簽 | A17（含雙簽 pad）| 10 |
| Flow 7 | 保固爭議 | A21, A22, A32 | 10, 15 |
| Flow 8 | 二次派工 | A12, A13, A28 | 07, 08, 17 |
| Flow 9 | 客訴生命週期 | A12, A22, **A37 升級** | 07, 10, 20 |
| Flow 10 | 門面變更 | T3, T8, T9 | 12, 19 |
| Flow 11 | 客戶不在場 | T3, **T11**, 客戶 LINE Flex RSVP | 12, **22**, **19 T1.4 補強** |
| Flow 12 | 金流與支付 | A9 帳務、客戶 LINE 支付頁 | 09 |
| Flow 13 | 帳款異常 EX5 | A9, A20 | 09, 10 |
| **Flow 14** | **技師排班衝突** | **T10, A25, A28, A37** | **19, 16, 17, 20** |

### 管理員治理 Flow（4 個）

| Flow | 主題 | 涉及頁面（IA） | Pipeline |
|:---|:---|:---|:---|
| G1 | RBAC 角色生命週期 | A18 | 10 |
| G2 | 稽核查詢匯出 | A20 | 10 |
| G3 | 庫存低警報補貨 | A19, **G1 通知** | 10, **21** |
| G4 | 爭議仲裁 | A22, A17, A12 | 10, 07 |

### V3.0 多租戶 Flow（5 個）

| Flow | 主題 | 涉及頁面（IA） | Pipeline |
|:---|:---|:---|:---|
| MT1 | 租戶開通 | A36 | 18 |
| MT2 | 品牌客製審核 | A34, A35, A36 | 18 |
| MT3 | 超管跨租戶 | A36 | 18 |
| MT4 | B2B API Key | A34 子 Tab | 18 |
| MT5 | 租戶退場 | A34, A36 | 18 |

### 全站橫切

| 橫切功能 | 涉及所有頁面 | Pipeline |
|:---|:---|:---|
| 全域通知 | 任一頁 bell → **G1** | **21** |
| 全域登入／登出 | A0, T0 | 14 |
| 全域導航規範 | 48+ 頁 | `E5x--frontend-navigation-matrix.md` 本表外 |

---

## 8. API 端點與 Pipeline 對應（摘要）

> 詳細 endpoint 清單見 `E5x--frontend-information-arch.md §9.1`。此處僅列主要 Bounded Context 對應。

| 後端 Context | API Base | 主要 Pipeline |
|:-------------|:---------|:--------------|
| `auth` | `/api/v1/auth/*` | 14 |
| `user_management` | `/api/v1/users/*`, `/api/v1/roles/*` | 14, 10 |
| `customer_service` | `/api/v1/conversations/*`, `/api/v1/problem-cards/*` | 03, 04 |
| `knowledge_base` | `/api/v1/knowledge-base/*` | 05, 15 (sop-performance) |
| `dispatch` | `/api/v1/work-orders/*`, `/api/v1/technicians/*`, `/api/v1/customers/*` | 06, 07, 08, 15, 16, 17, 19 |
| `accounting` | `/api/v1/accounting/*`, `/api/v1/refunds/*`, `/api/v1/disputes/*` | 09, 10, 16 |
| `inventory` | `/api/v1/inventory/*` | 10 |
| `audit` | `/api/v1/audit-events/*` | 10 |
| `reports` | `/api/v1/reports/*` | 17 |
| `agent-harness` | `/api/v1/diagnostics/*` | 15 |
| `multi-tenant` | `/api/v1/tenants/*`, `/api/v1/super/*` | 18 |
| `e-signature` | `/api/v1/signatures/*` | 10 (refund dual-sign), 19 (T9) |
| `dispatch (manual)` | `/api/v1/dispatch/candidates`, `/work-orders/{id}/assign` | **20, 07** |
| `notifications` | `/api/v1/notifications/*` | **21** |
| `reschedule` | `/api/v1/work-orders/{id}/reschedule`, `/technicians/me/availability` | **22, 19 T1.4** |

---

## 9. 驗證檢查清單

- [x] 所有 IA 頁面（52）都有對應 pipeline 檔（含 V1.1 新增 A37/G1/T11；G2 保留）
- [x] 所有 pipeline 檔都能對應回 IA 頁面
- [x] V1.0 / V2.0 / V3.0 版本標記一致
- [x] 每個多檔共用的元件（如 `SignaturePad`）都追溯到源 spec
- [x] WebSocket 頻道清單覆蓋所有即時需求
- [x] 重複檔（`01_dashboard.md` vs `02_admin_dashboard.md`）已於 commit `f42ee65` 清理
- [x] Flow × Page 矩陣建立（§7.5，含 Flow 1-14 + G1-G4 + MT1-MT5）
- [x] G2 `/offline` spec 檔（`23_global_offline.md`，驗證閘 Stage 3 完成）
- [ ] （待辦）若 IA 後續新增頁面，同步更新本檔

---

## 10. 變更記錄

| 日期 | 版本 | 變更摘要 |
|:-----|:-----|:---------|
| 2026-04-23 | v1.0 | 初版：對應 IA v1.2（48 頁）與 pipeline 19 份 spec 檔；建立 Forward / Reverse / 主題分群 / 使用者旅程 / 元件 / WS / API 多維對照 |
| 2026-04-23 | v1.1 | 驗證閘（plan §S）補完：註冊 A37 派工人工介入、G1 通知中心、T11 改期日曆；新增 §2.3 Global Pages 類；§7.5 Flow × Page 覆蓋矩陣（Flow 1-14 + G1-G4 + MT1-MT5）；清理 01_dashboard.md；新增 dispatch(manual) / notifications / reschedule API 對應 |
