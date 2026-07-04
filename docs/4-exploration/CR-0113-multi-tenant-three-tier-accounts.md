---
id: CR-0113
title: 多租戶三層帳號管理設計研究(SuperAdmin → 品牌 Admin → 子帳號+群組)
status: draft
created: 2026-07-04
owner: sunny
tier: 4
related: [CR-0112, CR-0111, CR-0031, 20260702 會議記錄 §二/§三, 18_admin_multi_tenant.md]
---

# CR-0113 — 多租戶三層帳號管理設計研究(AI-2,會議指定 7/4 交)

## §1 會議要求(20260702 §二,Sunny 口述)

1. 註冊時**不選角色**,一律先進場為**租戶 Admin**。
2. 租戶 Admin 自建**子帳號**並指派**權限群組**。
3. **SuperAdmin(Lock AI 端)**可從大後台管理所有租戶 Admin。
4. 子帳號登入走**同一個大後台入口**,帶「租戶+子帳號」進系統。
5. 參考 **GCP 帳號管理 UI** 模式(Sunny 自承「瞎猜的」,交辦研究業界做法)。

## §2 現況事實(2026-07-04 逐項查證,精準到行號)

| # | 事實 | 證據 |
|---|---|---|
| 1 | `saas.tenant` 只有最小骨架(id/name/created_at + dispatch_mode),全庫 1 筆 demo 租戶 | `SQL/migrations/004:41-51`、`039:16` |
| 2 | 註冊硬綁 demo 租戶:技師/廠商 register 寫死 `0000...0001` | `auth_service.py:490`、`:657` |
| 3 | `tenant_admin`/`super_admin` **登不進**(不在 `_ADMIN_WEB_ROLES` 5 角色) | `auth.py:72-78` |
| 4 | 兩角色**建不出**(不在 `_STAFF_ROLES`,註解明言「特殊不在此開放」) | `auth_service.py:527-529` |
| 5 | 兩角色**不在權限矩陣**(`_MATRIX` 12 角色無此二者)→ 矩陣管不到 | `role_service.py:110-279` |
| 6 | 但 guard 收它們:`FULL_ACCESS_ROLES=(admin,tenant_admin,super_admin)` 等散在各 router —— **有 token 就全通,卻沒有任何路徑發出這種 token**(死角色) | `deps.py:173`、`rbac_v2.py:43` |
| 7 | `X-Tenant-ID` 原樣採信:`resolve_tenant_id` 不驗 UUID、不查 `saas.tenant` 存在性(靠 JWT claim 比對擋跨租戶) | `core/tenant.py:16-25` |
| 8 | JWT 只有 `sub/role/tenant_id/type/iat/exp/jti`,**無群組/scope 概念** | `core/auth.py:67-75` |
| 9 | 「帳號群組」不存在;staff 頁只能建 5 個後台角色 | `staff/page.tsx:20-26` |
| 10 | `18_admin_multi_tenant.md` V3.0 spec(A34 租戶設定/A35 白牌/A36 超管平台 + TenantSwitcher)為**共用平台單庫多租戶**模型,端點未實作 | `docs/ui/.../18_admin_multi_tenant.md` |

## §3 關鍵設計張力:V3.0 spec 已被會議 §三推翻一半

18_admin_multi_tenant.md 假設**一套系統、單庫、邏輯多租戶**(TenantSwitcher 切租戶、
跨租戶快取隔離)。但同場會議 §三拍板「**一品牌一 GCP 專案 + 獨立 DB**」——
每品牌的 DB 內天然接近單租戶,「SuperAdmin 跨租戶」的實體從「同庫不同 tenant_id」
變成「**不同 GCP 專案的不同部署**」。三層帳號設計必須先回答:第三層(SuperAdmin)
跨的是什麼?

## §4 業界模式對照(會議指定參考 GCP)

| GCP IAM 概念 | 對應本系統 | 說明 |
|---|---|---|
| Organization | Lock AI(平台方) | SuperAdmin 的管轄範圍 |
| Project | **品牌(=一個 GCP 專案+獨立 DB)** | 會議 §三的部署單位 |
| Project Owner | 品牌租戶 Admin | 進場即為 Admin,管自己品牌 |
| IAM Member | 子帳號 | Admin 自建 |
| Predefined Roles | 現有 12 角色矩陣(CR-0111) | 已可配置 read/write/approve/delete |
| Custom Roles | **權限群組**(新概念) | 一組 permission codes 的命名集合 |
| Cloud Console(跨專案) | SuperAdmin 大後台 | 跨品牌運維視角 |

GCP 的做法印證:**「群組」本質是自訂角色**(權限碼集合),與預定義角色並存;
跨專案管理靠**外層 console**,不是進到每個專案的 DB 裡切 tenant。

## §5 設計提案

### 方案 A(推薦)—「品牌內兩層 + 平台外掛 SuperAdmin console」

對齊會議 §三獨立專案模式:

- **第 1 層 SuperAdmin(Lock AI)**:不是品牌系統內的角色,而是**跨專案運維
  console**(Phase 3;短期 = gcloud + Metrics Scope 監控 + 各品牌後台的
  Lock AI 維運帳號)。品牌 DB 內不需要 super_admin 可登入。
- **第 2 層 品牌租戶 Admin**:開專案時 provision(半自動化,landing「聯絡
  我們」模式)——`saas.tenant` 補完整欄位(slug/status/locale)寫入該品牌
  資訊 1 筆 + 建立第一個 `tenant_admin` 帳號。**進場不選角色、即為 Admin**
  (會議要求 1)。tenant_admin 補進 `_ADMIN_WEB_ROLES`/`_MATRIX`/`_ROLE_META`
  (消除死角色,rbac shadow 落差同時解掉)。
- **第 3 層 子帳號+群組**:staff 頁升級為「帳號與群組管理」——
  - MVP:子帳號指派**預定義角色**(現有 12 角色矩陣,already 可配 4 維權限)
  - Phase 2:**自訂群組** = `saas.account_group`(id/tenant_id/name/permission_codes[])
    + `users.group_id`(nullable);授權判定 = 角色矩陣 ∪ 群組 codes
    (`role_service.has_permission` 已存在,擴一個 union 即可,CR-0111 shadow 機制直接復用)
  - JWT 加 `group` claim(可選,或每請求查),登入入口**不變**(會議要求 4:
    同一大後台入口,tenant 由品牌部署天然決定——一品牌一網域,不需要 TenantSwitcher)

### 方案 B — 照 V3.0 spec 做單庫多租戶三層

保留 TenantSwitcher/跨租戶快取隔離。**與會議 §三矛盾**(已拍板獨立 DB),
且工程量最大(前端三層快取隔離 + 全 API 跨租戶測試)。不建議,除非
獨立專案模式翻案。

### 差異速覽

| | 方案 A | 方案 B |
|---|---|---|
| 與會議 §三一致 | ✅ | ❌(共用平台) |
| SuperAdmin 實體 | 跨專案 console(外層) | 同庫角色 + TenantSwitcher |
| tenant 表 | 每品牌 DB 1 筆(自我描述) | 單庫 N 筆 |
| 工程量 | 中(P1 約 1 輪、P2 約 1-2 輪) | 大(3+ 輪,前端隔離工程) |
| 18_admin_multi_tenant.md | 標 superseded(部分概念沿用) | 照做 |

## §6 落地階段(方案 A,UAT 後執行)

| 階段 | 內容 | 觸及 |
|---|---|---|
| **P1 品牌 Admin 進場**(1 輪) | tenant_admin 入登入集/矩陣/META;`saas.tenant` 補欄位(migration);provision 腳本(開品牌時建 tenant+Admin);register_vendor 註冊流程對齊「進場即 Admin」語意裁決 | api auth/role_service、SQL、scripts |
| **P2 子帳號+群組**(1-2 輪) | `saas.account_group` + users.group_id(migration);staff 頁 → 帳號與群組管理(建群組=勾權限碼);`has_permission` 加群組 union;先 shadow 後強制(復用 CR-0111 機制) | api/web/SQL |
| **P3 SuperAdmin console**(獨立專案) | 跨品牌運維面板(各品牌 health/用量/版本;結合 AI-12 Metrics Scope);品牌開站精靈(結合 AI-3 brands/*.env) | 新 app 或 gcloud 工具鏈 |

## §7 影響面(實作時各階段自帶 CIA)

- **API contract**:P1 登入集擴充(非破壞);P2 新增 group CRUD 端點。
- **DB**:P1 tenant 欄位補完;P2 account_group 表 + users.group_id(皆 migration)。
- **與 CR-0112 交互**:技師身分庫已拆分——群組/子帳號屬**品牌側帳號**
  (users 非技師列),不碰技師庫;SuperAdmin console 的跨品牌技師視角
  天然由「師傅平台全品牌共用」取得,不需要另做。

## §8 Human Decisions Required(業主)

1. **方案 A or B?**(A=品牌內兩層+外掛 console,推薦;B=單庫三層照 V3.0 spec)
2. **「註冊即租戶 Admin」的邊界**:現行 landing 廠商自助註冊(vendor)在獨立
   專案模式下還存在嗎?會議 §三說 landing 改「聯絡我們幫你部署」——
   若是,vendor 自助註冊降級為「品牌內的協力廠商帳號」而非租戶 Admin?
3. **群組 MVP 範圍**:P2 先做「指派預定義 12 角色」就好,還是一步到位自訂群組?
4. **排程**:P1 放 UAT 後第一輪?(P3 依賴品牌數 >1 才有意義,可後置)

### 進度

- 2026-07-04:設計研究完成(本文件),現況 10 項事實查證 + GCP 模式對照 +
  A/B 方案 + 三階段落地路線。🛑 待業主裁決 §8 後排實作輪(各階段自帶 CIA)。
