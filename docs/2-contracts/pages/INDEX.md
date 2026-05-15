---
title: Page Contracts Index — 10 anchor pages
tier: 2
status: active
last_updated: 2026-05-10
related:
  - "../../1-decisions/module-boundary/ARCH-0004-module-boundary-web.md"
  - "../frontend-design-system/"
  - "../../5-views/VIEW-0003-frontend-route-map.md (full IA → route mapping)"
---

# Page Contracts Index

> 10 個 **anchor page-contracts**，覆蓋 V1.0 主要 user flow 入口。
> 每 page-contract = thin spec（route / auth / FR trace）。
> **完整 52 頁 IA 對照** + **route → page.tsx 映射**見 [`5-views/VIEW-0003-frontend-route-map.md`](../../5-views/VIEW-0003-frontend-route-map.md)。
>
> **Why anchor-only**: 大部分頁面為 CRUD / list / detail 樣板，frontend code (`web/src/app/<route>/page.tsx`) 即為 source of truth。Anchor pages 涵蓋有特殊 auth / multi-step flow / cross-cutting behavior 的關鍵入口。

## Admin Panel anchors (4)

| ID | Route | 說明 |
| :-- | :-- | :-- |
| [`A0-管理員登入`](./A0-管理員登入.md) | `/login` | Auth flow 入口 |
| [`A1-營運儀表板`](./A1-營運儀表板.md) | `/dashboard` | Admin 主入口 |
| [`A12-工單詳情`](./A12-工單詳情.md) | `/work-orders/[id]` | V2 核心：工單 lifecycle 全功能介面 |

## Technician Web App anchors (3)

| ID | Route | 說明 |
| :-- | :-- | :-- |
| [`T0-技師登入`](./T0-技師登入.md) | `/tech-login` | 技師 auth |
| [`T1-案件池`](./T1-案件池.md) | `/pool` | 技師主入口 / 接單 |
| [`T3-工單詳情-完工回報`](./T3-工單詳情-完工回報.md) | `/my-orders/[id]` | 技師核心 flow（出發 → 到場 → 完工）|

## Global / Cross-cutting anchors (4)

| ID | Route | 說明 |
| :-- | :-- | :-- |
| [`G1-全域通知中心`](./G1-全域通知中心.md) | `/notifications` | 跨 actor 通知 |
| [`G2-離線狀態頁`](./G2-離線狀態頁.md) | `/offline` | PWA offline UX |
| [`G3-錯誤邊界`](./G3-錯誤邊界.md) | error.tsx / 404 / 500 | Next.js error boundary 慣例 |
| [`G4-改約-calendar`](./G4-改約-calendar.md) | reschedule UI | calendar widget |

## frontmatter 標準

```yaml
---
id: PAGE-XX
route: /path/to/page
version: V1.0 | V2.0 | V3.0
access_role: admin | technician | any
trace_to_fr: FR-NNNN-...
---
```

## 新增 page contract 時機

只在以下情況新增 anchor：
1. 跨多 user flow 的入口（如 dashboard）
2. 含特殊 auth / RBAC 規則
3. multi-step flow 的核心步驟
4. cross-cutting global behavior（error / offline / notification）

CRUD list / detail 不需新建 contract — `web/src/app/<route>/page.tsx` + frontend-route-map 已涵蓋。
