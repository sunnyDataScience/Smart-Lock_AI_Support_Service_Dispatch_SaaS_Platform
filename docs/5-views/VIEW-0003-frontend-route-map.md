---
title: Frontend Route Map (AI-AUTO)
tier: 5
status: active
last_regenerated: 2026-05-10
generator: manual (Phase 8 後改 router config scan); from `find web/src/app -name page.tsx`
DO_NOT_EDIT: |
  Tier 5 = AI-AUTO 視圖。手動編輯會在下次 regen 被覆寫。
related:
  - "../2-contracts/pages/INDEX.md"
  - "../1-decisions/module-boundary/ARCH-0004-module-boundary-web.md"
  - "../1-decisions/frontend-tech-stack.md"
---

# Frontend Route Map

> 從 Next.js 15 App Router (web/src/app/) 自動 derive 出的 61 個 page.tsx route。
> 每個 route 對應 `2-contracts/pages/<IA-id>-*.md` 的 page-contract。

## Admin Panel routes (38 active + few extras)

| Route | File | IA | Page Contract |
| :-- | :-- | :-- | :-- |
| `/login` | `web/src/app/login/page.tsx` | A0 | `2-contracts/pages/A0-管理員登入.md` |
| `/dashboard` | `web/src/app/dashboard/page.tsx` | A1 | `2-contracts/pages/A1-營運儀表板.md` |
| `/conversations` | `web/src/app/conversations/page.tsx` | A2 | `2-contracts/pages/A2-對話列表.md` |
| `/conversations/[id]` | `web/src/app/conversations/[id]/page.tsx` | A3 | `2-contracts/pages/A3-對話詳情.md` |
| `/problem-cards` | `web/src/app/problem-cards/page.tsx` | A4 | `2-contracts/pages/A4-問題卡列表.md` |
| `/problem-cards/[id]` | `web/src/app/problem-cards/[id]/page.tsx` | A5 | `2-contracts/pages/A5-問題卡詳情.md` |
| `/knowledge-base` | `web/src/app/knowledge-base/page.tsx` | (root) | — (route group root) |
| `/knowledge-base/cases` | `web/src/app/knowledge-base/cases/page.tsx` | A6 | `2-contracts/pages/A6-案例庫.md` |
| `/knowledge-base/cases/new` | `web/src/app/knowledge-base/cases/new/page.tsx` | A7-new | (variant of A7) |
| `/knowledge-base/cases/[id]` | `web/src/app/knowledge-base/cases/[id]/page.tsx` | A7 | `2-contracts/pages/A7-案例詳情-編輯.md` |
| `/knowledge-base/cases/[id]/edit` | `web/src/app/knowledge-base/cases/[id]/edit/page.tsx` | A7-edit | (variant of A7) |
| `/knowledge-base/manuals` | `web/src/app/knowledge-base/manuals/page.tsx` | A8 | `2-contracts/pages/A8-手冊管理.md` |
| `/knowledge-base/sop-drafts` | `web/src/app/knowledge-base/sop-drafts/page.tsx` | A9 | `2-contracts/pages/A9-SOP-審核佇列.md` |
| `/knowledge-base/sop-drafts/[id]` | `web/src/app/knowledge-base/sop-drafts/[id]/page.tsx` | A10 | `2-contracts/pages/A10-SOP-審核面板.md` |
| `/knowledge-base/family-reviews` | `web/src/app/knowledge-base/family-reviews/page.tsx` | (extra) | — (V2 family review，無 IA) |
| `/work-orders` | `web/src/app/work-orders/page.tsx` | A11 | `2-contracts/pages/A11-工單列表.md` |
| `/work-orders/[id]` | `web/src/app/work-orders/[id]/page.tsx` | A12 | `2-contracts/pages/A12-工單詳情.md` |
| `/work-orders/kanban` | `web/src/app/work-orders/kanban/page.tsx` | (extra) | — (額外視圖) |
| `/work-orders/map` | `web/src/app/work-orders/map/page.tsx` | (extra) | — (額外視圖) |
| `/technicians` | `web/src/app/technicians/page.tsx` | A13 | `2-contracts/pages/A13-技師管理.md` |
| `/technicians/[id]` | `web/src/app/technicians/[id]/page.tsx` | A14 | `2-contracts/pages/A14-技師詳情.md` |
| `/accounting` | `web/src/app/accounting/page.tsx` | A15 | `2-contracts/pages/A15-帳務管理.md` |
| `/accounting/invoices` | `web/src/app/accounting/invoices/page.tsx` | A15-i | (sub-tab) |
| `/accounting/revenue` | `web/src/app/accounting/revenue/page.tsx` | A15-r | (sub-tab) |
| `/accounting/vouchers` | `web/src/app/accounting/vouchers/page.tsx` | A15-v | (sub-tab) |
| `/settings` | `web/src/app/settings/page.tsx` | A16 | `2-contracts/pages/A16-系統設定.md` |
| `/admin/refunds` | `web/src/app/admin/refunds/page.tsx` | A17 | `2-contracts/pages/A17-退款審核.md` |
| `/admin/roles` | `web/src/app/admin/roles/page.tsx` | A18 | `2-contracts/pages/A18-RBAC-管理.md` |
| `/admin/inventory` | `web/src/app/admin/inventory/page.tsx` | A19 | `2-contracts/pages/A19-庫存管理.md` |
| `/admin/audit-events` | `web/src/app/admin/audit-events/page.tsx` | A20 | `2-contracts/pages/A20-稽核日誌.md` |
| `/admin/warranty-claims` | `web/src/app/admin/warranty-claims/page.tsx` | A21 | `2-contracts/pages/A21-保固索賠.md` |
| `/admin/disputes` | `web/src/app/admin/disputes/page.tsx` | A22 | `2-contracts/pages/A22-爭議仲裁.md` |
| `/admin/customers` | `web/src/app/admin/customers/page.tsx` | A23 | `2-contracts/pages/A23-客戶主檔.md` |
| `/admin/customers/new` | `web/src/app/admin/customers/new/page.tsx` | A23-new | (variant) |
| `/admin/customers/[id]` | `web/src/app/admin/customers/[id]/page.tsx` | A24 | `2-contracts/pages/A24-客戶詳情.md` |
| `/admin/customers/[id]/edit` | `web/src/app/admin/customers/[id]/edit/page.tsx` | A24-edit | (variant) |
| `/admin/dispatch-queue` | `web/src/app/admin/dispatch-queue/page.tsx` | A28 | `2-contracts/pages/A28-派工佇列監控.md` |
| `/admin/dispatch-manual` | `web/src/app/admin/dispatch-manual/page.tsx` | A37 | `2-contracts/pages/A37-派工人工介入.md` |
| `/admin/reports/kpi` | `web/src/app/admin/reports/kpi/page.tsx` | A29 | `2-contracts/pages/A29-KPI-儀表板.md` |
| `/admin/reports/technician-ranking` | `.../page.tsx` | A30 | `A30-技師排行榜.md` |
| `/admin/reports/revenue` | `.../page.tsx` | A31 | `A31-營收報表.md` |
| `/admin/knowledge-base/sop-performance` | `.../page.tsx` | A33 | `A33-SOP-績效儀表板.md` |
| `/admin/sentiment-alerts` | `.../page.tsx` | (extra) | — |
| `/admin/schedule-requests` | `.../page.tsx` | (extra) | — |
| `/admin/api-status` | `.../page.tsx` | (extra) | — (admin debug) |

> 缺：A25-A27 (technician detail subroutes), A32 (diagnostic view), A34-A36 (V3 multi-tenant) — page-contract 已建，UI 未實作。

## Technician Web App routes (11 + extras)

| Route | File | IA | Page Contract |
| :-- | :-- | :-- | :-- |
| `/tech-login` | `web/src/app/tech-login/page.tsx` | T0 | `2-contracts/pages/T0-技師登入.md` |
| `/pool` | `web/src/app/pool/page.tsx` | T1 | `2-contracts/pages/T1-案件池.md` |
| `/my-orders` | `web/src/app/my-orders/page.tsx` | T2 | `2-contracts/pages/T2-我的工單.md` |
| `/my-orders/[id]` | `web/src/app/my-orders/[id]/page.tsx` | T3 | `2-contracts/pages/T3-工單詳情-完工回報.md` |
| `/my-orders/[id]/scope-change` | `.../page.tsx` | T5 | `T5-範圍變更申請.md` |
| `/my-orders/[id]/material-request` | `.../page.tsx` | T6 | `T6-缺料回報.md` |
| `/my-orders/[id]/delay` | `.../page.tsx` | T7 | `T7-延遲通知.md` |
| `/my-orders/[id]/door-check` | `.../page.tsx` | T8 | `T8-門面外觀檢核.md` |
| `/my-orders/[id]/signature` | `.../page.tsx` | T9 | `T9-雙方電子簽章.md` |
| `/my-orders/[id]/reschedule` | `.../page.tsx` | (variant) | — (改約變體) |
| `/account` | `web/src/app/account/page.tsx` | T4 | `T4-帳戶中心.md` |
| `/account/schedule` | `web/src/app/account/schedule/page.tsx` | T10 | `T10-我的排班.md` |

## Global / Cross-cutting routes

| Route | File | IA | Page Contract |
| :-- | :-- | :-- | :-- |
| `/notifications` | `web/src/app/notifications/page.tsx` | G1 | `G1-全域通知中心.md` |
| `/scope-change/[token]` | `.../page.tsx` | (consumer-public) | (消費者公開 token UI) |
| `/track/[token]` | `.../page.tsx` | (consumer-public) | (消費者工單追蹤 / FR-0022) |
| `/` | `web/src/app/page.tsx` | (root) | (root redirect to /login or /dashboard) |

> 缺：G2 (offline), G3 (error-boundary as Next.js error.tsx), G4 (reschedule calendar) — 多為 Next.js convention 而非 page.tsx，不在本表。

## 統計

- Total page.tsx files: 61
- 對應到 IA: ~52
- 額外 (knowledge-base root group, kanban/map 視圖, customers new/edit, sentiment-alerts, schedule-requests, api-status, root, [token] consumer-public, my-orders/[id]/reschedule): ~9

## Auth / RBAC mapping

| Route prefix | Required role |
| :-- | :-- |
| `/login`, `/tech-login`, `/`, `/scope-change/[token]`, `/track/[token]` | public |
| `/dashboard`, `/conversations*`, `/problem-cards*`, `/knowledge-base*`, `/work-orders*`, `/technicians*`, `/accounting*`, `/settings`, `/notifications` | admin (任何 admin role) |
| `/admin/*` | admin (含 ops_director / ops_manager / dispatch_officer / support_agent / auditor 視子路由) |
| `/pool`, `/my-orders*`, `/account*` | technician |

詳見 `2-contracts/modules/MC-0015-rbac.md` 7 角色 × 8 權限矩陣。

## 變更紀錄

| 日期 | 變更 |
| :--- | :--- |
| 2026-05-10 | 初版 — 從 `find web/src/app -name page.tsx` 整理，含 IA mapping |
