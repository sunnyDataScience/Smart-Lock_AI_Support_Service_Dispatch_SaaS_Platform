---
id: CR-0021
title: "5 角色帳號 + 前端 route 權限隔離（Change Impact Analysis）"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-12
target-release: Phase 8 上線前
product-version: null
supersedes: null
superseded-by: null
---

# CR-0021: 5 角色帳號 + 前端 route 權限隔離

> **Mandated by**: `.claude/rules/change-governance.md`（觸發：User flow / API contract / Architecture boundary）
> 🛑 §8 未裁決前不動 code。

---

## 1. Change Statement

**As-is**：
- 權限**強制在 API 層**完整（`role_required` / `require_keeper`；A3 已用 20 條 pytest 矩陣證明）。
- 但 **前端 `AuthGuard` 只檢查 token、無 route-level role gating**：非 admin 角色持有效 token 仍可在瀏覽器**載入** `/admin/*` 頁（API 會 403，頁面顯示空/錯誤）。
- **admin web 登入端點 `/auth/login` 只收 `admin` / `reviewer`**；dispatcher/operations_manager/customer_service 等後台角色**登不進** admin web。
- 可登入帳號只 seed 了 admin / dispatcher / technician。

**To-be**（會議 2026-06-10 決議 #9「5 種角色帳號權限上線前完成測試」）：
- 5 個操作角色各有可登入帳號;admin web 登入收這些後台角色;前端依角色 gate 路由（看不到也進不去無權限頁）。

**Driver**：會議決議 #9 + Iron 要以各角色點 UI 給反饋（Action #3）。

## 2. Affected Flow

| Flow | Action | Description |
|---|---|---|
| 登入流程 | Modified | admin web 登入放寬收後台角色;技師仍走 tech-login |
| 後台導覽 | Modified | sidebar 依角色隱藏無權限項;直接打 URL 也被 gate |

## 3. Affected Spec

| Spec | Action | Description |
|---|---|---|
| RBAC route policy（新）| New | role → 可存取的 nav section 對應表（前端 gate 依據;與後端 role_required 對齊）|

## 4. Affected API

| API | Action | Breaking? | Notes |
|---|---|---|---|
| `POST /api/v1/auth/login`（loginAdmin）| `allowed_roles` 擴充 | No | 由 `["admin","reviewer"]` 加入後台角色（見 §8-Q2）。對既有 admin/reviewer 無影響 |

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `users`（seed）| New rows | 補缺角色登入帳號（reviewer / operations_manager / customer_service…）；密碼沿用 demo bcrypt(changeme123) |

## 6. Affected Test

| Test | Action | Description |
|---|---|---|
| pytest `test_login_roles` | New | 各放寬角色可 `/auth/login` 取 token;technician 仍被 admin login 擋 |
| Playwright `role-ui-isolation` | New | 以各角色登入 → 驗 sidebar 只顯示有權限項、直接打無權限 URL 被導開 |
| 既有 `rbac.spec.ts`（@wip mock）| Replace/Update | 改真實登入 + 真隔離（取代 mock 假 JWT）|

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| 前端 AuthGuard | Extend | 加 route→role gate（token-only → token+role）。demo 風險：對應表猜錯會誤擋 → §8-Q3 須明確 |
| 角色真相源 | Decide | 前端 route policy 與後端 role_required 須對齊;避免前端比後端寬/嚴造成 confusing UX |
| 登入端點安全 | Review | 放寬 admin login 收後台角色 = 擴大可取得 admin-web token 的角色集（仍受後端 per-endpoint guard 保護）|

## 8. Human Decisions Required

🛑 **每列裁決後才動 code。**

| # | 問題 | 選項 | 建議 |
|---|---|---|---|
| 1 | 哪 5 個角色？ | (a) admin / operations_manager / dispatcher / customer_service / technician (b) 系統正典 admin/reviewer/technician/brand_oem/line_user (c) 自訂 | **(a)** — 操作面最有區隔、最貼合後台 demo（technician 走手機端）|
| 2 | admin web 登入放寬收哪些角色？ | (a) admin/reviewer/operations_manager/dispatcher/customer_service (b) 只加 operations_manager (c) 維持現狀只 admin/reviewer | **(a)** 收齊後台角色;technician 維持 tech-login |
| 3 | 前端 route→role 對應（gate 依據）| 見下表「建議對應」 | 照下表;未列到的頁預設 admin/ops 才可 |
| 4 | 無權限時行為 | (a) 導向 /dashboard (b) 顯示「無權限」頁 (c) 404 | **(a)** 導 /dashboard + sidebar 隱藏該項（最不打斷 demo）|
| 5 | seed 帳號密碼 | (a) 全用 changeme123(demo) (b) 各角色不同 | **(a)** demo 一致好記;email 如 ops@example.com / cs@example.com / reviewer@example.com |

### 建議 route→role 對應表（Q3）

| Nav section / 路由 | admin | operations_manager | dispatcher | customer_service |
|---|:--:|:--:|:--:|:--:|
| dashboard | ✅ | ✅ | ✅ | ✅ |
| conversations / problem-cards | ✅ | ✅ | ✅ | ✅ |
| knowledge-base | ✅ | ✅ | ➖ | ✅ |
| work-orders / dispatch-queue / material-requests | ✅ | ✅ | ✅ | ➖(唯讀) |
| technicians | ✅ | ✅ | ✅ | ➖ |
| customers | ✅ | ✅ | ➖ | ✅ |
| accounting（settlements/vouchers/refunds/warranty/disputes）| ✅ | ✅ | ➖ | ➖ |
| inventory | ✅ | ✅ | ➖ | ➖ |
| reports（kpi/ranking/revenue/sop-perf）| ✅ | ✅ | ➖ | ➖ |
| admin（audit-events / roles）| ✅ | ➖ | ➖ | ➖ |

> technician：完全不進 admin web（走 /pool /my-orders 手機端）。

## 9. Suggested Implementation Order（§8 裁決後）

1. **後端**：`/auth/login` allowed_roles 擴充（Q2）+ pytest 登入角色測試
2. **Seed**：補缺角色登入帳號（Q1/Q5）
3. **前端**：route→role policy（常數表）+ AuthGuard gate（Q3/Q4）+ sidebar 依角色過濾
4. **Tests**：Playwright role-ui-isolation（各角色 sidebar + URL gate）;更新/取代 rbac.spec.ts
5. **Docs**：CHANGELOG + 完成度文件;ADR（前端 route gating policy 與後端對齊原則）

## 10. Risks & Rollback

- **風險**：前端對應表與後端 role_required 不一致 → 前端讓進但 API 403（confusing）或前端誤擋（demo 中斷）。緩解：對應表以後端 guard 為準、列清楚、Playwright 覆蓋。
- **風險**：放寬 admin login 收後台角色 = 更多角色可拿 admin-web token;但每個 endpoint 仍受後端 guard，real security 不變。
- **Rollback**：前端 gate 為 additive（移除即回 token-only）;登入 allowed_roles 可縮回;seed 帳號可刪。低風險。
