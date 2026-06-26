---
id: CR-0103
title: 技師管理「編輯 / 停權 / 復權」前端接線 + admin 編輯端點
status: implemented
tier: 4-exploration
created: 2026-06-26
author: Claude (Opus 4.8) + 業主裁決
relates:
  - FR-0044  # technician lifecycle（approve/reject/suspend/reactivate/terminate）
  - CR-0094  # 完整角色系統（list 頁核准按鈕）
---

# CR-0103 — 技師管理「編輯 / 停權 / 復權」前端接線 + admin 編輯端點

## 1. 動機（業主回報）

業主在 `/technicians`（→ 詳情頁 `/technicians/[id]`）發現「操作沒有作用」，
問「原本是打算做什麼」。

## 2. 診斷（查證結果）

- **詳情頁「編輯」「停權」是 `disabled` 佔位鈕**（`title="即將推出"`），無 onClick → 點了沒反應。
- **停權/復權/終止後端早已實作可用**：`technician_lifecycle_v2` 的 `:suspend` / `:reactivate` /
  `:terminate`（+ `technician_lifecycle_service.suspend/reactivate/approve/reject`，須 `X-Initiator`
  header + `{reason, notes}`，有 audit）。典型「後端做了前端沒接」假綠（同 CR-0091/0094）。
- **死碼 bug**：`technicians_v2.py` 另有重複的 `:suspend` **501 stub**，因 main.py include 順序
  （`tech_lifecycle_v2_router` 先註冊）被遮蔽、永遠跑不到 → misleading dead route。
- **「編輯」後端真缺**：只有技師改自己的 `updateMyProfile`（PATCH /technicians/me），
  **無 admin 改任意技師的端點**。
- 詳情頁「技能矩陣/本週排班/佣金/獎懲」為寫死示意（已有誠實 disclaimer，本 CR 不動）。

## 3. 觸發面向（CIA gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| API contract | ✅ | 新增 `PATCH /tenants/{tid}/technicians/{techId}`（updateTechnicianV2）；移除未實作的 501 stub |
| User flow | ✅（弱）| 技師詳情頁新增可用的編輯/停權/復權操作 |
| Domain model | ❌ | 不新增欄位（沿用 technicians 既有 name/phone/email/capabilities/service_regions）|
| DB schema | ❌ | 無 migration |

## 4. §8 Human Decisions Required（已裁決）

| # | 決策 | 業主選擇 |
|---|---|---|
| D1 | 範圍 | **編輯 + 停權/復權一起做**（編輯需補後端端點）|
| D2 | 可編輯欄位 | **姓名 / 電話 / 技能(品牌) / 服務區域**（Option B preview 指定；email 不在 Technician 回應 schema，本 CR 不納）|
| D3 | 停權/復權 | 接既有 `technician_lifecycle_v2`（須 reason，UI prompt 收集；有 audit）|
| D4 | 501 死碼 | 移除 technicians_v2 重複的 `:suspend` stub |

## 5. 實作

**後端**
- `technician_service.update_technician(*, tenant_id, technician_id, patch)` — 與 `update_my_profile`
  同 SET 邏輯（name/phone/email/capabilities/regions 部分更新），改以 technician_id 定位、
  get_technician 守門（404/跨租戶）。
- `technicians_v2.py`：新 `PATCH /tenants/{tenantId}/technicians/{techId}`（updateTechnicianV2，
  `_TechnicianUpdateRequest` 全選填、None 不更新；DISPATCH_ROLES + cross-tenant guard）。
  **移除**重複未實作的 `:suspend` 501 stub（連帶清 `JSONResponse` import）。
- 狀態變更（停權/復權）**不新增端點**，沿用 `technician_lifecycle_v2` 既有可用端點。

**前端 `/technicians/[id]/page.tsx`**
- 「編輯」→ 開 modal（姓名/電話/技能/區域，逗號分隔轉陣列）→ `api.patch` updateTechnicianV2 → refetch。
- 「停權」（status=active）/「復權」（status=suspended）依 onboarding 狀態切換；prompt 收 reason →
  `api.post :suspend/:reactivate`（帶 `X-Initiator`）→ refetch。
- mutation 後 `cacheInvalidate("GET:")`（清 30s GET 快取，否則 refetch 取到舊狀態 — 比照列表頁核准）。

## 6. 範圍與限制

- 編輯不含 email（Technician 回應 schema 無此欄，無法預填）/ rating / 狀態（狀態走停權復權）。
- 「終止」(:terminate) 為不可逆，本 CR 不掛 UI（另議）。
- 詳情頁示意資料（技能矩陣/排班/佣金/獎懲）維持現狀（已有 disclaimer）。

## 7. 測試

- API `test_technicians_v2_endpoint.py` +3：PATCH 部分更新（name/phone/capabilities/regions，
  未帶 email 不變）、404、cross-tenant 403 → 與 lifecycle/onboard 合計 38 passed。
- Live UI（Playwright，丁啟恆）：編輯鈕啟用 → modal 預填 → 改技能存檔 → DB 持久化（已還原）；
  停權→復權→停權 round-trip 按鈕正確切換（cache 修正後）；測試 lifecycle events 已清。

## 8. 進度

✅ S1 done（branch `feat/technician-admin-edit`，疊於 phone 分支）：service update_technician +
PATCH updateTechnicianV2 + 移除 501 死碼 stub；前端編輯 modal + 停權/復權接線 + cache 修正；
API 38 passed；Playwright 全流程驗證。**待部署 api+web**。
