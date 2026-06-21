---
id: CR-0094
title: "完整角色系統 — 後台員工帳號建立 + reviewer 三方對齊"
status: implemented
tier: 4-exploration
owner: HYBRID
created: 2026-06-21
target-release: dev_new_arch
related: [CR-0040, CR-0092, CR-0021]
---

# CR-0094: 完整角色系統

> **Mandated by**: 業主裁決「建完整角色系統」（回應「5 種角色只有 admin」+ CR-0040 角色登不進）。
> **背景**: 稽核發現角色三方不一致 + 無建立非-admin 帳號的路徑。

## 1. 問題（三方角色不一致 + 無建帳號）

| 來源 | 角色集 |
|---|---|
| `role_service._MATRIX`（RBAC 目錄）| admin / reviewer / technician / brand_oem / line_user（**5 個** = 會議「5 種角色」）|
| `auth._ADMIN_WEB_ROLES`（可登入後台）| admin / reviewer / operations_manager / dispatcher / customer_service |
| `rolePolicy.ts`（前端 gating）| admin / tenant_admin / super_admin / operations_manager / dispatcher / customer_service（**缺 reviewer**）|

且**無任何建立非-admin 角色帳號的端點/UI** → 實務上只有 admin（坐實業主觀察）。

## 2. 決策

以 **`_ADMIN_WEB_ROLES`（實際能登入後台者）為操作正典**建帳號；以 `role_service._MATRIX` 為權限意圖對齊後端守衛。brand_oem 為外部夥伴角色（媒體過濾 + partner_scope），需獨立夥伴入口（CR-0029 範疇），**不納入後台員工系統**。

## 3. 實作

| 層 | 變更 |
|---|---|
| **後端建帳號** | `auth_service.create_staff_user`（role ∈ operations_manager/dispatcher/customer_service/reviewer/admin；即時 active；email 角色限定去重）+ `list_staff_users` |
| **端點** | `POST /api/v1/staff`（建）+ `GET /api/v1/staff`（列），`role_required(*FULL_ACCESS_ROLES)` 守衛（僅 admin/tenant_admin/super_admin 可建員工）|
| **後端對齊 _MATRIX** | 新 `REVIEW_ROLES = OPS_ROLES + reviewer`；refunds/disputes/warranty 6 router 由 OPS_ROLES → REVIEW_ROLES（reviewer 於此三域可寫，對齊 _MATRIX）|
| **前端 gating** | `rolePolicy.ts` 補 reviewer（ALL_BACKOFFICE + /accounting + /admin/refunds/warranty-claims/disputes）+ 新 `/admin/staff` 路由（admin only）|
| **前端 UI** | 新 `/admin/staff` 員工管理頁（列表 + 建立表單，角色下拉）+ Sidebar audit 群組加「員工帳號」入口 + i18n |

## 4. Affected Data / Test

- **無 schema 變更**（users 表既有；staff = users 列 role∈集合 + tenant_type='platform'，已有 seed 樣本）。
- `test_cr_0094` 7/7：建帳號/非法角色 422/短密碼 422/重複 409/技師端點 403/admin 建+列/reviewer 可存取退款（對齊驗證）。
- 回歸全套件 **1393 passed / 0 fail**（含既有 RBAC 隔離測試）。

## 5. Out of Scope（Phase II）

- brand_oem / accounting / finance_manager 等非登入後台角色 → 夥伴入口（CR-0029）/ 角色模型再擴充
- 員工停用/改角色/改密碼（本 CR 只建立 + 列表）
- role_service._MATRIX 與端點守衛的逐資源完全對齊（本 CR 只對齊 reviewer 退款/保固/爭議三域）

## 6. Sign-off

| Role | Date | Approved? |
|---|---|---|
| Product / 業主 | 2026-06-21 | ✅（裁決「建完整角色系統」）|
