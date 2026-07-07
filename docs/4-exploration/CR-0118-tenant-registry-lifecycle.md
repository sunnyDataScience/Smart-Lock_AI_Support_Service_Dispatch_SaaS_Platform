---
id: CR-0118
title: 租戶 registry 與生命週期管理(SuperAdmin 大後台「租戶管理」;CR-0113 方案 A P3 收尾)
status: draft
created: 2026-07-06
owner: sunny
tier: 4
related: [CR-0113, CR-0114, CR-0116, 20260702 會議記錄 §二.3]
---

# CR-0118 — 平台 console「租戶管理」:已開站租戶 registry + 生命週期

## §1 觸發背景

- **20260702 §二.3(Sunny 口述)**:「SuperAdmin 可從大後台管理所有租戶 Admin」。
- **盤點(2026-07-06)**:CR-0114 platform console 目前只有「品牌**申請**審核」(開站
  *前*的關卡)+ 師傅審核 + 廠商 + 維運監控。**核准後的品牌並未被登錄成「已開站
  租戶」**——SuperAdmin 缺一個「我有哪幾家品牌在營運、各自狀態如何、開站資訊為何」
  的正典檢視面。這是 CR-0113 方案 A「P3 SuperAdmin console」尚未落地的最後一塊拼圖。

## §2 現況事實(2026-07-06 查證,精準到檔案)

| # | 事實 | 證據 |
|---|---|---|
| 1 | 平台庫(lock_platform)僅 4 表:`users` / `revoked_jti` / `brand_applications` / `monitor_target`,**無租戶 registry** | `SQL/platform/Schema_platform.sql` |
| 2 | 核准品牌申請 = 標 `status='approved'` + 定 `slug` + 回開站指引文字;**不建租戶列、不追蹤開站後狀態** | `brand_application_service.approve` |
| 3 | `monitor_target.brand` 只是 health URL 的分組字串(CR-0116),非租戶正典(無狀態/接洽人/部署資訊) | `Schema_platform.sql:101-115` |
| 4 | `platform_admin_service` 只有 auth(login/refresh/logout/me),無租戶管理 | `api/services/platform_admin_service.py` |
| 5 | 架構分叉早已定案:SuperAdmin = 跨專案**外層 console**,**不進各品牌 DB 改帳號**(品牌 admin 帳號在各品牌庫,平台不跨庫寫) | CR-0113 §5 方案 A + §8 裁決 |

## §3 範圍

**IN(本 CR):**

- 平台庫新表 `tenant`:已開站租戶正典(slug / company / status / 接洽人 / 部署 metadata / 溯源 application_id)。
- 核准品牌申請成功後,自動登錄/連結一列 `tenant`(approved → 進入營運名冊)。
- platform console 新分頁「租戶管理」:列出所有租戶 + 狀態徽章 + 開站資訊;連到該租戶的監控 health。
- 租戶生命週期(**平台層標示**):`active` / `suspended` / `terminated` + 備註(平台側註記,實際品牌庫動作仍手動,符合 CR-0114 裁決 2「開站純手動」)。
- 端點(全 `/api/v1/platform` 前綴,`require_platform_admin`):`GET /platform/tenants`(?status=)、`GET /platform/tenants/{id}`、`POST .../{id}:suspend`、`POST .../{id}:reactivate`。

**OUT(維持 CR-0113 方案 A 邊界,不在本 CR):**

- 直連各品牌庫 CRUD 品牌 admin 帳號(重設密碼 / 停用登入)——跨品牌 DB 深水,方案 A 明言「外層 console 不進各專案 DB 切 tenant」;短期走各品牌後台的 Lock AI 維運帳號。
- 多品牌工單 / 資料聚合(CR-0112 已知殘留)。

## §4 影響面(CIA 七面向)

| 面向 | 影響 | 破壞性 |
|---|---|---|
| **User/Business flow** | 新增「SuperAdmin 檢視/管理已開站租戶」流;品牌申請核准流末端自動多一步「登錄為租戶」 | 否(additive) |
| **API contract** | 新增 4 端點;`approveBrandApplication` 回應 additive 加 `tenant_id` | 否 |
| **Domain model** | 新增 `Tenant`(平台視角的已開站租戶名冊);與品牌庫 `saas.tenant`(該品牌自我描述那 1 筆)概念區隔 | 否 |
| **DB schema** | 平台庫新表 `tenant`(Schema_platform.sql 追加,IF NOT EXISTS);`brand_applications` 可加 `tenant_id` 反向連結(選填) | 否(新表) |
| **External integration** | 無 | — |
| **Test plan** | 新增 `test_platform_tenants`(registry + 核准連動 + gate);`test_api_surface` / `test_platform_surface` 端點集更新 | — |
| **Architecture boundary** | platform console 能力擴充,**不跨品牌庫寫**(維持方案 A);registry 為平台單庫本地資料,不引新 infra | 否 |

## §5 設計方案

**表 `tenant`(lock_platform):**
`id` / `slug`(unique) / `company_name` / `contact_name` / `contact_email` / `contact_phone` /
`status`(active/suspended/terminated,CHECK)/ `plan`(選填)/ `application_id`(→ brand_applications,溯源)/
`deploy_note`(開站 metadata 文字)/ `created_at` / `updated_at` / `status_changed_at` / `status_changed_by`。

**服務 `platform_tenant_service`:**
`list` / `get` / `create_from_application`(approve 內呼叫,idempotent by slug)/ `set_status`(suspend/reactivate/terminate,寫 status + status_changed_by/at)。

**router `platform_tenants`:** 4 端點,`require_platform_admin`。

**前端 `web/src/app/platform/tenants/{page,[id]}.tsx`:** 清單(狀態徽章 + 搜尋)+ 詳情(開站資訊 + 生命週期動作 + 連監控);platform layout 導航加「租戶管理」。

**approve 連動:** `brand_application_service.approve` 成功後呼叫 `create_from_application`(**fail-soft**:registry 建立失敗不擋核准,loud log)。

## §6 落地(規模小,可單輪或雙輪;比照 CR-0116 節奏)

| 輪 | 內容 |
|---|---|
| R1(後端) | migration + service + router + main 掛載 + approve 連動 + tests |
| R2(前端) | tenants 清單/詳情 + 導航 + i18n |

## §7 風險 / 取捨

1. **registry 與品牌庫 `saas.tenant` 雙記**:平台 `tenant` 是跨品牌名冊、品牌 `saas.tenant` 是該品牌自身描述,語意不同不衝突;文件需註明避免誤解。
2. **生命週期 `suspended` 平台層僅標示**,不自動停該品牌服務(需手動 gcloud / 各品牌後台)——與方案 A 一致,console 文案須明示「平台層標示,實際停站走維運」。
3. **slug 唯一性**:approve 已定 slug;registry 沿用同 slug 當 key。

## §8 Human Decisions Required 🛑

1. **是否此輪落地租戶 registry?**（建議:**是**——§二.3 唯一還沒做的功能面,且只碰
   platform 站 :3003,不動 Johnson UAT 面(:3000 派工 / :3001 師傅),風險低)。
2. **生命週期動作範圍**：MVP 先「檢視 + 平台層 suspend/reactivate 標示」（建議），
   或連「terminate + 開站精靈(brands/*.env 產生器)」一起做?
3. **稽核粒度**：先最小(`status_changed_by/at` 欄位，建議)，或建 `tenant_lifecycle_event`
   事件表(比照師傅生命週期)?建議先最小、事件表後置。

### 進度

- **2026-07-06**:立案(CIA)。現況查證(平台庫 4 表無 registry)+ CR-0113 方案 A 邊界
  確認(不跨品牌庫寫)+ registry 設計 + 七面向影響。🛑 待業主裁決 §8。
- **2026-07-07**:業主裁決 §8——Q1 做 MVP、Q2 檢視+平台層 suspend/reactivate 標示、
  Q3 稽核先最小欄位(不建事件表)。**單輪落地**(branch `feat/cr-0118-tenant-registry`):
  `tenant` 表(Schema_platform.sql)+ `platform_tenant_service` + `platform_tenants` router
  四端點 + main 掛載 + `brand_application_service.approve` 連動(fail-soft)+ 前端 `/platform/tenants`
  + `TenantsPanel` + 導航。驗證:`test_platform_tenants.py` 10 測、**全套 1663 passed**
  (隔離 scratch DB)、tsc 0、瀏覽器端到端(核准品牌申請→自動登錄→停用→恢復)。
  已重建本機 platform api+web、5435 套 `tenant` 表。merge `012a10e7`(--no-ff)。
