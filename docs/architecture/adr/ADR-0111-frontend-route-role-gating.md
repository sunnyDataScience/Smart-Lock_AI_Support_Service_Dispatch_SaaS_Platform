---
adr_id: ADR-0111
title: 前端 route-level role gating（對齊後端 role_required）
status: accepted
date: 2026-06-12
deciders: Sunny（業主）
related: [CR-0021]
tags: [rbac, frontend, auth, cr-0021]
---

# ADR-0111 — 前端 route-level role gating

## Context

權限**強制在 API 層**完整（`role_required` / `require_keeper`；A3 已用 20 條 pytest
矩陣證明）。但前端 `AuthGuard` 原本**只檢查 token、無 role gating**：非授權角色
持有效 token 仍可在瀏覽器**載入** `/admin/*` 頁（API 會 403，頁面顯示空/錯誤）。
會議決議 #9 要求 5 角色 UI 隔離 + Iron 以各角色點 UI（Action #3）。

## Decision

採 CR-0021 §8（Q1–Q5 照建議）：

1. **5 角色**：admin / operations_manager / dispatcher / customer_service / technician
   （technician 走 tech-login 手機端,不進 admin web）。
2. **admin web 登入放寬**：`/auth/login` allowed_roles 收
   admin/reviewer/operations_manager/dispatcher/customer_service。
3. **前端 route gating**：新增 `web/src/lib/rolePolicy.ts`（單一真相源）：
   - `canAccessRoute(pathname, role)`：route prefix → 允許角色,longest-prefix-wins。
   - `AuthGuard` 認證後再 gate;無權限 → 導 /dashboard（Q4）。
   - `Sidebar` 依角色過濾 nav（父項可存取或有可見子項才顯示）。
4. **對齊原則**：前端 policy **以後端 `role_required` 為準**,不比後端寬/嚴
   （避免「前端讓進但 API 403」或「前端誤擋」的 confusing UX）。
5. **安全定位**：前端 gating 是 **UX 層**,非安全邊界;真正強制仍在 API。
   admin/tenant_admin/super_admin 全放行;未列到的路由預設放行（demo 安全）。

## Consequences

- ✅ 各角色登入後只看到/進得去有權限的頁,符合 demo「5 角色隔離」需求。
- ✅ Playwright role-ui-isolation 4 角色覆蓋（route gate + sidebar 過濾）。
- ⚠️ 前端 policy 與後端 guard 須手動保持對齊（兩處維護）;以 ADR + Playwright 覆蓋降風險。
- ⚠️ 放寬 admin login 收後台角色 = 更多角色可取得 admin-web token;每 endpoint 仍受
  後端 guard,real security 不變。
- Rollback：前端 gate 為 additive（移除即回 token-only）;login allowed_roles 可縮回。
