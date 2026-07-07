---
id: CR-0114
title: 平台方管理系統(platform console)與註冊/審核動線重構
status: accepted
created: 2026-07-05
owner: sunny
tier: 4
related: [CR-0112, CR-0113, CR-0094, CR-0060, ADR-0107, 20260702 會議記錄 §二/§三]
---

# CR-0114 — 平台方 console 與註冊/審核動線重構 Change Impact Analysis

## §1 變更請求

業主(2026-07-05)口述目標架構,把 CR-0112 雙 stack 拆分再推進一層:

1. **一頁式網站 = 純廣告導流**:師傅按鈕 → 師傅註冊;品牌廠商鎖店按鈕 →
   「成為品牌」的**平台申請**(不再打品牌 API `/vendors/register`)。
2. **師傅站台與品牌派工站台獨立**(前端+後端+DB)—— CR-0112 已落地,維持。
3. **師傅 DB 全平台唯一**(lock_tech);所有品牌都能讀它選師傅派工。
4. **各品牌派工 DB 各自獨立**(一品牌一套 stack,BRAND 參數化已完成)。
5. **新增平台方後台管理系統(platform console)**:Lock AI 自用(非師傅/品牌用),
   能看到師傅與品牌的所有註冊申請並管理。

實質採納 CR-0113 方案 A(品牌內兩層 + 平台外掛 console)並把 console 自 Phase 3 提前。

## §2 觸發面向

命中 CIA 六面向:**User/Business flow**(兩條註冊動線重構 + 新審核流)、
**API contract**(新 `/api/v1/platform/*` 前綴;品牌端 lifecycle 寫端點刪除)、
**Domain model**(brand_applications / staff_applications 新實體;platform_admin 新角色)、
**DB schema**(平台庫新建;品牌庫 staff_applications migration)、
**Test plan**(lifecycle 端點測試改寫 + 三個新測試檔)、
**Architecture boundary**(第四個 stack:platform-db/api/web)。

## §3 現況事實(2026-07-05 三路盤點,精準到行號)

| # | 事實 | 證據 |
|---|---|---|
| 1 | landing 品牌 modal 直打品牌 API `/vendors/register`,**送出即建 users(is_active=TRUE,pending 期間可登入)** | `VendorRegisterForm.tsx:44-53`、`auth_service.py:619-686` |
| 2 | 師傅審核在品牌後台:`technician_lifecycle_v2.py` 五寫端點(gate=DISPATCH_ROLES + 前端自報 `X-Initiator` header) | `technician_lifecycle_v2.py:24-169`、`technicians/page.tsx:66-84` |
| 3 | vendor 與 technician 審核**雙軌不一致**:vendor 無狀態機/無 audit 表;technician 有 `_ALLOWED_TRANSITIONS` 狀態機 + `saas.technician_lifecycle_event` audit + users.is_active 連動 | `vendor_service.py:82-116`、`technician_lifecycle_service.py:39-159` |
| 4 | 無任何平台層端點/頁面;`super_admin`/`tenant_admin` 為死角色(guard 收、無發 token 路徑) | `deps.py:173`、`auth.py:72-78`(CR-0113 §2) |
| 5 | 品牌端讀師傅一律讀**本地投影**,且 `technician_brand_authorization` 用於**過濾**候選 | `dispatch_service.py:192-345`、`technician_service.py:137-164` |
| 6 | mirror 機轉 = 拉 tech authority 現況寫入**當前行程的品牌 `_conn`**;fallback(TECH_POSTGRES_URI 未設)= 單庫,行為與拆分前相同 | `core/tech_mirror.py:52-92`、`core/db.py:136-147` |
| 7 | `technician_brand_authorization.brand` 語意 = **鎖品牌**(Yale 等),派工比對工單鎖品牌(CR-0060) | `dispatch_service.py:192-210` |
| 8 | compose 已四分天下的前三份:dispatch(每品牌一套,BRAND 參數化)/ tech(全品牌共用)/ landing(無後端) | `docker-compose.{dispatch,tech,landing}.yml` |

## §4 目標架構與設計

架構對照圖(業主已審):https://claude.ai/code/artifact/f600785f-c6ff-4481-a1cd-87d0f02f88eb

**設計總則**:同一 codebase + 第三個 surface/mode,複製 CR-0112 已驗證三件套
(`API_SURFACE` 路由過濾 + `NEXT_PUBLIC_APP_MODE` + 未設 env 即單庫 fallback);
`agent/`、`lockcore` 全程不動(ADR-0107 Architecture Lock)。

### 4.1 Platform stack(docker-compose.platform.yml)

- `platform-db`(5435,pgvector/pg17,database `lock_platform`,**獨立容器**——
  備份邊界、權限隔離、「一 instance 一 database」慣例);
  `platform-api`(8003,`API_SURFACE=platform`);`platform-web`(3003,`NEXT_PUBLIC_APP_MODE=platform`)。
- platform-api 三連線:`POSTGRES_URI`(主品牌庫,MVP mirror 落點)+ `TECH_POSTGRES_URI`
  + `PLATFORM_POSTGRES_URI`;**獨立 `API_JWT_SECRET_KEY`**(同名不同值 → token 與品牌互不通用)。
- 身分 = **新角色 `platform_admin`**(不活化 super_admin:那是品牌側萬能鑰匙,
  platform_admin 不在任何品牌 gate → deny-by-default);帳號存平台庫自己的
  users/revoked_jti,與品牌/師傅 user pool 物理分離。

### 4.2 品牌申請流(landing → platform)

平台庫新表 `brand_applications`(申請=意向書:**不收密碼、不建帳號**);
公開端點 per-IP in-memory 限流;核准 response 附 `onboarding_guide` 純文字
(以 `brands/locksmart.env` 為模板產建議值 + 手動步驟)——**只產文字不自動化**(裁決 2)。
`/vendors/register` 後端保留(pytest 依賴 + 未來品牌內協力廠商帳號路徑),前端入口全退場。

### 4.3 師傅審核搬遷

`/api/v1/platform/technicians` 六端點**復用 `technician_lifecycle_service` 零改動**;
initiator 語意升級:廢 `X-Initiator` header,改取已驗簽 token sub。
品牌端 `technician_lifecycle_v2.py` 刪五寫端點(留 GET lifecycle-events 唯讀),
品牌 technicians 頁唯讀化。mirror MVP = platform-api 帶主品牌 URI push;
終態(N 品牌)= pull-based(§4.4),新品牌上線零平台側改動。

### 4.4 品牌讀共用師傅庫

技師清單/派工候選改讀 tech conn(單庫 fallback 同顆連線,SQL 不改 → 行為不變);
authorization 由「過濾」改「**標示**」`brand_authorized`(裁決 3,鎖品牌語意=裁決 6);
**auto_match 維持只選已授權**(裁決 7)。FK 完整性靠 `ensure_technician_projection`
mirror-on-demand(assign/reassign/accept-claim/assign_dispatch/auto_match 五寫入點)。
佣金/對帳/月結等重 JOIN 面維持讀投影不動。

### 4.5 品牌員工帳號申請

品牌庫新表 `staff_applications`(**不預建 users 列**——placeholder role 會漏進
員工清單/角色統計,且 CR-0090 依角色去重無法定義);登入頁註冊 tab 換
`StaffRegisterForm`(無角色選擇);`admin/staff` 加待審區,核准時指派
**5 員工角色之一**(裁決 5 正典);`VendorRegisterForm.tsx` 兩入口清空後刪檔。

## §5 API contract 影響

| API | Action | Breaking? |
|---|---|---|
| `/api/v1/platform/auth/{login,logout}`、`/platform/me` | New | No(新前綴) |
| `/api/v1/platform/brand-applications`(POST 公開/GET/:approve/:reject) | New | No |
| `/api/v1/platform/technicians`(GET/五生命週期/:lifecycle-events) | New | No |
| `/tenants/{tid}/technicians/*` 五生命週期寫端點 | **Delete** | **Yes**(品牌前端同輪改) |
| `/api/v1/staff-applications`(POST 公開)+ `/tenants/{tid}/staff-applications*` | New | No |
| `/api/v1/vendors/register` | 保留(前端入口退場) | No |

## §6 DB 影響

- **新庫** `lock_platform`:users(平台管理員)/revoked_jti/brand_applications(`SQL/platform/Schema_platform.sql`,非 migration——全新庫)。
- **品牌庫 migration**:`staff_applications`(新表,無既有表變更)。
- **師傅庫零變更**(裁決 6 沿用鎖品牌授權語意)。

## §7 測試影響

改寫:`test_technicians_onboard_v2_endpoint.py`(→ platform 路徑)、
`test_technician_login_status_gate.py`、`test_api_surface.py`、`test_cr_0060_brand_auth.py`
(過濾→標示)。新增:`test_platform_surface.py`、`test_platform_auth.py`、
`test_platform_technician_lifecycle.py`、staff/brand applications、mirror-on-demand 測試。
**單庫 fallback 模式 pytest 全套必須維持全綠**。

## §8 Human Decisions Required(業主 2026-07-05 已全數裁決)

1. **師傅審核歸屬** → **移到 platform console**;品牌端唯讀。
2. **品牌開站** → **純手動**:console 只記錄申請/核准狀態 + 產開站指引文字。
3. **品牌選師傅可見範圍** → **全部啟用中可見 + 標示已授權/未授權**(過濾改標示)。
4. **品牌站內註冊 tab** → 改「**品牌員工帳號申請**」:員工申請 → 品牌 Admin 審核並指派角色。
5. **權限正典** → **UAT 版 7 角色**(`docs_html/20260709/角色與功能總覽-PPT素材.html`);
   子帳號可指派 5 員工角色(admin/operations_manager/dispatcher/customer_service/reviewer)。
6. **授權標示語意** → **鎖品牌授權**(沿用 technician_brand_authorization,零 schema 變更)。
7. **自動派工** → **仍只選已授權**;未授權者僅人工派工可選(畫面有標示)。

**殘餘開放問題**(不阻塞實作,記錄待後續):
- N 品牌時 platform-api 掛哪個品牌 network 的拓撲(MVP 掛主品牌 net)。
- 品牌內「協力廠商帳號」的 admin-gate 建立路徑(`/vendors/register` 降級後續 CR)。
- 多品牌工單聚合(tech-api 現綁單一品牌庫)—— 深水區,不在本 CR。

**§8 追補(2026-07-06 收斂輪盤查後新增,待業主裁決)**:
- **品牌 GDPR 被遺忘權對師傅身分列的處置權**:品牌端 `gdpr/forget-requests` 對
  `role=technician` subject 會 REDACT(soft-delete)/實體刪除(hard-delete)師傅
  權威庫身分列(`gdpr_forget_service.py` 技師分支,CR-0112 為 GDPR 完整性刻意
  設計,有稽核軌跡 + 30 天 cooldown)。依裁決 1 師傅身分歸平台方,但 platform
  console 目前**沒有任何 GDPR 端點**可承接 —— 單方收掉會造成師傅被遺忘權無處
  執行(法遵缺口)。收斂輪**維持現狀**,待裁決:(a) 平台 console 補 GDPR 流程後
  品牌端擋 technician subject;或 (b) 接受品牌端代執行(現狀)。
- **platform console 師傅管理功能缺口**(收斂輪把品牌端寫入全收掉後浮現):
  建立師傅(手動 onboard)/編輯主檔(姓名/技能/區域/等級 S-A-B-C)/認證管理
  (新增/編輯/刪除)/代重設師傅密碼 —— platform console 皆尚無對應功能,目前
  唯一入口=3001 /tech-register 自助註冊 + 3003 審核。屬後續輪。

### 進度

- 2026-07-05:三路現況盤點 + 設計書 + 業主七項裁決完成,本 CR 立案(status: accepted)。
- ✅ R0 done(merge `d7618172`):CR 立案 + CR-0113 §8 回寫 + CR-0112 補四 stack 拓撲節 + CHANGELOG Decisions。
- ✅ R1 done(merge `61bb1686`):platform console 骨架 —— 第四 stack(platform-db 5435 / platform-api 8003 / platform-web 3003)、新角色 `platform_admin`(隔離帳號池 + 獨立 JWT secret,品牌⇄平台 token 雙向 403)、`core/db.py` 第三連線 fallback。全套 1572 passed。
- ✅ R2 done(merge `883427d5`):品牌申請流 landing → platform console —— 平台庫 `brand_applications` 表 + `BrandApplyForm`(無密碼意向申請)取代 landing modal 的 VendorRegisterForm + console 審核頁(核准回開站指引純文字,裁決 2 純手動)。全套 1584 passed。
- ✅ R3 done(merge `de7d5f24`):師傅審核搬遷平台方(裁決 1)—— `platform_technicians` 六端點復用 lifecycle 狀態機零改動、品牌端刪 5 寫端點只留唯讀 audit、initiator 取 token sub 廢自報 X-Initiator。全套 1590 passed。
- ✅ R4 done(merge `6328a698`):品牌讀共用師傅庫(裁決 3/6/7)—— dispatch/technician service 改 `require_tech_conn()`、`list_dispatch_candidates` 授權由過濾改**標示** `brand_authorized`、`auto_match` 維持只選已授權、`ensure_technician_projection` mirror-on-demand 掛 3 寫入點保 FK。全套 1594 passed。
- ✅ R5 backend done(merge `9f845385`):品牌員工帳號申請後端(裁決 4)—— migration 088 `staff_applications`(不預建 users)、`staff_application_service`(submit 去重/approve transaction 內建 users 驗 role ∈ `_STAFF_ROLES`/reject)、全 tenant-scoped `routers/staff_applications.py`(無 /api/v1 前綴)。`test_staff_applications.py` 10 項,全套 1604 passed。
- ✅ 導流架構細化(merge `71ed1742`):業主回報「localhost:3000 點師父跳品牌」—— 實測師父 CTA 接線本身正確,真因是 3000 品牌 dispatch stack 的 `/` 誤渲染與 3002 重複的對外 landing。修 `crossModeRedirect` dispatch `/`→`/login` + landing 元件 dispatch build `return null`。Playwright 驗證。
- ✅ R5 frontend done(merge `e0557e06`):品牌員工帳號申請前端接線(裁決 4)—— `StaffRegisterForm`(無角色選擇,POST 公開 tenant-scoped 端點)取代登入頁註冊 tab、`admin/staff` 待審申請區(5 角色下拉 approve / prompt reason reject)、刪 `VendorRegisterForm`、i18n +staffApply 8 鍵(parity 2751)。tsc 0 + 重建 dispatch web/api + Playwright 端到端(申請→admin 核准指派派工員→新帳號登入 role=dispatcher)。
- **五輪 R0-R5 全數落地**;剩 5 輪收尾(docs_html regen、雲端部署含 migration 088、push 由業主執行)。
- ✅ 裁決 1 收斂輪 done(branch `fix/cr0114-brand-tech-readonly-closure`,2026-07-06):業主發現品牌後台仍可「新增技師」→ 多 agent 盤查(4 維度 29 發現、逆向驗證 22 確認/7 剔除)後把品牌端師傅職權全面收斂為唯讀 —— 刪品牌端 `POST createTechnician`/`PATCH updateTechnicianV2`(可寫技能+等級)/認證 CRUD 三寫端點(留 GET);`admin-reset-password` 對師傅帳號 403;新增 `API_SURFACE=dispatch` 剔除過濾(`/api/v1/platform/*` + `/api/v1/technicians/register` 不掛品牌 8001,杜絕 fallback「品牌庫幽靈師傅」);RBAC 矩陣 admin/supervisor 對 technicians 改唯讀;前端 3000 兩頁全唯讀(移除新增/編輯/認證維護 UI)+ dispatch build `/tech-register` 導 tech portal + 清死鍵死 props。全套 **1611 passed** 零回歸;`all` 模式(pytest/雲端單體)不過濾零變化。GDPR 師傅 subject 與 platform console 功能缺口記入 §8 追補待裁決。
- ✅ 品牌申請 + 廠商審核合併為「發案方審核」done(branch `feat/platform-merge-requestor-review`,2026-07-06):業主回饋「品牌跟廠商審核適合一起,都是發案的一方」→ 把 `/platform/brand-applications` 與 `/platform/vendors` 合成單一頁 `/platform/requestors`(nav 兩項併一項「發案方審核」)。**純前端整併,零後端改動**:兩頁 body 抽為 `components/platform/BrandApplicationsPanel.tsx` + `VendorsPanel.tsx`(移除各自 h1,改小字描述),新頁用分頁切換(品牌申請 / 廠商帳號)——兩者資料模型與審核動作不同(品牌申請核准填代號+出開站指引;廠商核准啟用帳號)故分頁不硬混清單。刪舊兩頁路由;API 端點不變。tsc 0;Playwright 驗(發案方審核頁兩分頁切換、各自審核動作正常)。**已部署本機 docker(platform web)**。

- ✅ 廠商審核移植 platform console done(branch `feat/platform-vendor-approvals`,2026-07-06):業主指示把品牌 `admin/vendor-approvals` 移到 `:3003/platform`(選項＝獨立「廠商審核」頁;後續 2026-07-06 併入「發案方審核」)。`vendors`＝發案方登入帳號(role=vendor,與 brand_applications 意向書是不同生命週期階段);審核職權自品牌移到平台統一管。**後端**:新 `platform_vendor_service`(cross-tenant list + `_resolve_tenant_id` 委派 vendor_service 狀態機)+ `platform_vendors.py` 3 端點(GET list / :approve / :reject,`require_platform_admin`);品牌 `vendors_v2` 刪 approveVendorV2/rejectVendorV2 寫端點(留 GET list + /vendors/me 唯讀)。**vendors.approved_by 有 FK→品牌 users,平台管理員住平台庫非品牌 user → 平台核准存 `approved_by=NULL`**(approved_at 記時間,「平台核准」隱含;approver_id 留參供未來平台 audit 表)。**前端**:新 `/platform/vendors`(狀態篩選 + 核准/拒絕,比照原品牌頁);nav 加「廠商審核」(第 3 項)。**品牌移除**:刪 `admin/vendor-approvals` 頁 + 側欄「廠商審核」項 + Store icon import + rolePolicy 死條目 + i18n(`sidebar.nav.vendorApprovals`/`admin.vendorApprovals.*`,parity 2654)。`/vendors/register` 公開註冊保留。測試 `test_platform_vendor_approvals.py` 5 項(RBAC 401/403、list→approve 冪等 409、reject、品牌 approve/reject 404);既有 `test_cr_0029_vendor_*` 打 service 層不受影響。全套 **1623 passed** 零回歸;tsc 0。**已部署本機 docker(platform api+web、dispatch web)**。

- ✅ 師傅管理移植 platform console done(branch `feat/platform-technician-management`,2026-07-06):§8 追補「platform console 補師傅建立/編輯/認證管理」收尾,業主指示把品牌 `/technicians` 完整移植到 `:3003/platform` 並完全移除品牌頁。**後端**:復原 `technician_service.create_technician`/`update_technician` + `technician_certification_service` 三個寫函式(師傅身分域服務,治理在 route 層),`platform_technician_service` 加 `_resolve_tenant_id` 包一層跨品牌 wrapper;`platform_technicians.py` 加 7 端點(`platformCreateTechnician`/`getPlatformTechnician`/`updatePlatformTechnician` + 認證 GET/POST/PATCH/DELETE),全 `require_platform_admin`。**前端**:新 `/platform/technicians`(清單+搜尋+新增師傅 modal+連詳情+保留生命週期動作)+ `/platform/technicians/[id]`(個人資料+編輯 modal 含等級+認證 CRUD+生命週期歷史);排班/獎懲屬品牌營運(per-brand 工單/財務)不搬。layout nav「師傅審核」→「師傅管理」;刪舊 `/platform/technician-approvals`。**品牌端移除**:刪 `/technicians` + `/technicians/[id]` + 側欄項 + 6 個孤兒元件(TechniciansTable/CertificationMatrix/ProfileCard/WeeklySchedule/TechnicianDetailSidebar/PenaltyBonusLog)+ rolePolicy 死條目 + 孤兒 i18n(parity 2666);品牌 `technicians_v2` GET 保留(customers 頁仍讀)。測試 `test_platform_technician_management.py` 7 項 + 更新 router 斷言,全套 **1618 passed** 零回歸;tsc 0。**已部署本機 docker(platform api+web、dispatch web)**。GDPR 師傅 subject 承接仍待裁決(另案)。

## §9 Suggested Implementation Order

| 輪 | branch | 內容 | 依賴 |
|---|---|---|---|
| R0 | `docs/cr-0114-platform-console` | 本 CR + CR-0113 §8 回寫 + CR-0112 補節 + CHANGELOG | — |
| R1 | `feat/platform-stack-skeleton` | platform 三件套(db/auth/deps/main)+ compose + Schema_platform + web platform 模式 + platform_auth | R0 |
| R2 | `feat/platform-brand-applications` | brand_applications 表/端點/console 頁 + landing 表單換裝 | R1 |
| R3 | `feat/platform-tech-approvals` | platform_technicians 六端點 + 品牌端 lifecycle 寫端點刪除 + 頁面唯讀化 | R1 |
| R4 | `feat/brand-read-tech-authority` | 讀 tech conn + 過濾改標示 + mirror-on-demand | R3 |
| R5 | `feat/staff-applications` | staff_applications + 登入頁 tab 換裝 + admin/staff 待審區 | R0(可與 R2-R4 並行) |
