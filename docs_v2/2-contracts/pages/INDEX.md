---
title: Page Contracts Index — 53 pages (38 Admin + 11 Tech + 4 Global)
tier: 2
status: active
last_updated: 2026-05-10
related:
  - "../../1-decisions/module-boundary/web.md"
  - "../frontend-design-system/"
  - "../../5-views/traceability-matrix.md (legacy IA mapping at appendix)"
  - "../../extras/web-frontend/pages-legacy/ (源 22 specs，作為深度參考)"
---

# Page Contracts Index

> 53 個 page contract 從 IA spec + pipeline 22 specs 拆分而成。
> 每個 page-contract 為 thin 包裝（route / auth / FR trace / source spec pointer）。
> 完整 UI / Component / Layout 規格在 `extras/web-frontend/pages-legacy/` 22 specs 內。

## Admin Panel (38 pages, A0-A37)

### V1.0 (11 pages)
- [`A0-管理員登入`](./A0-管理員登入.md) — `/login`
- [`A1-營運儀表板`](./A1-營運儀表板.md) — `/dashboard`
- [`A2-對話列表`](./A2-對話列表.md) — `/conversations`
- [`A3-對話詳情`](./A3-對話詳情.md) — `/conversations/[id]`
- [`A4-問題卡列表`](./A4-問題卡列表.md) — `/problem-cards`
- [`A5-問題卡詳情`](./A5-問題卡詳情.md) — `/problem-cards/[id]`
- [`A6-案例庫`](./A6-案例庫.md) — `/knowledge-base/cases`
- [`A7-案例詳情-編輯`](./A7-案例詳情-編輯.md) — `/knowledge-base/cases/[id]`
- [`A8-手冊管理`](./A8-手冊管理.md) — `/knowledge-base/manuals`
- [`A9-SOP-審核佇列`](./A9-SOP-審核佇列.md) — `/knowledge-base/sop-drafts`
- [`A10-SOP-審核面板`](./A10-SOP-審核面板.md) — `/knowledge-base/sop-drafts/[id]`
- [`A16-系統設定`](./A16-系統設定.md) — `/settings`

### V2.0 (24 pages)
- A11-A15: Work Order + 技師 + 帳務
- A17-A22: 進階管理（退款/RBAC/庫存/稽核/保固/爭議）
- A23-A33: 客戶 + 技師詳細 + 派工/報表
- A37: 派工人工介入

### V3.0 (3 pages, 多租戶)
- A34-A36: tenant settings + brand customization + super admin

## Technician Web App (11 pages, T0-T10)

- T0 登入 / T1 案件池 / T2-T3 我的工單 / T4 帳戶
- T5-T9 工單子流程（scope-change / material / delay / door-check / signature）
- T10 排班

## Global (4 pages, G1-G4)

- G1 通知中心 / G2 離線 / G3 錯誤邊界 / G4 改約 calendar

---

## frontmatter 標準

```yaml
---
id: PAGE-XX
route: /path/to/page
version: V1.0 | V2.0 | V3.0
access_role: admin | technician | any
trace_to_fr: FR-NNNN-... (對應 functional requirement)
source_spec_path: extras/web-frontend/pages-legacy/...
source_spec_section: 主要 / 列表段 / Tab: ... 等
---
```

## 待補完（Phase 8 / CR follow-up）

每個 page-contract 的 §4 Data Sources 與 §5 Component Map 目前為 TODO。
需從 source spec 抽 structured data（API endpoint list、components）。
建議：
1. 先實作頁面（web/src/app${route}/page.tsx）
2. 跑 `sunnydata-auto-regen` 從 router config 推 frontend-route-map
3. 補 Data Sources（從 generated/api.generated.ts 對照）
4. 補 Component Map（從實際 import 樹）

---

## Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | 初版 — 從 22 page spec 拆為 53 個 thin contract |
