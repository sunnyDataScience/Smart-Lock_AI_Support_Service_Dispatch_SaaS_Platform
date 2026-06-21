---
title: "前後端落差 + RBAC 權限稽核報告（回應業主盤點要求）"
tier: 4-exploration
created: 2026-06-21
owner: AI-audit
related: [CR-0038, CR-0091, CR-0092]
method: "37-agent workflow（14 塊 router 權限矩陣 + 23 CR 前後端對照），逐端點/逐 CR 讀 code 實證"
---

# 前後端落差 + RBAC 權限稽核報告

> **觸發**: 業主「幫我盤點一下前幾天的修改，是不是很多只改後端沒改前端，我看連權限設定都沒改好」。
> **方法**: 多 agent 稽核 —— 14 塊涵蓋 96 router 共 **407 端點**逐一分類授權；23 個近期 CR 逐一比對後端 vs 前端實際落地（讀 code，非讀文件）。

## TL;DR — 兩個直覺都成立，且已量化

1. **權限沒做好** ✅：407 端點中 **80 個敏感寫入零角色檢查**（只 `require_tenant`，任何登入者含 technician/vendor 可寫金流/設定/派工）。
2. **只改後端沒改前端** ✅：23 個近期 CR 中 **11 個後端 done 但前端 missing/partial**（5 個 HIGH）。但**非全面** —— 8 個 CR 前後端完全同步，證明做得好是做得到的。

---

## 一、權限稽核（80 個 HIGH 無角色守衛）

`require_tenant` 只驗「登入 + 同租戶」，**不檢查角色**。`role_required` 才檢查。407 端點分類：

| 風險 | 數量 | 說明 |
|---|---|---|
| **HIGH** | **80** | 敏感寫入只用 require_tenant → 任何角色可寫 |
| MED | 193 | 多為敏感讀取 / cross-role-read（Phase II 評估）|
| OK/LOW | 134 | 已 role_required / self-scoped / consumer-public / webhook |

HIGH 分布（按資源）：

| Category | 數 | 代表端點（任何登入者皆可寫）|
|---|---|---|
| accounting | 45 | brand-b2b 結算 generate/submit/approve/**mark-paid**、dispatcher-commission、月結、對帳、退款、技師對帳單 |
| admin-only | 14 | m18 config draft/**start-rollout**/rollback、deprecation reset、GDPR legal-hold/**hard-delete** |
| pricing | 10 | pricing-rules、quote 核准/送出 |
| dispatch | 5 | **auto-match**、技師 onboard/suspend/terminate 生命週期 |
| data-correction | 2 | data-correction approve/reject |
| role-mgmt | 2 | roles、rbac |
| audit | 1 | audit log 寫入 |

> **最危險**：`brand-b2b-statements:mark-paid`（標記金流已付）、`m18 rollback`（任意回滾設定上線）、`gdpr hard-delete`（永久刪資料）—— 技師/廠商 token 全部打得進去。掛 `_require_initiator`/`_require_sod_two` 的端點只檢查 header 是否存在/相異，**填任意字串即繞過**，非真守衛。

**補充洞察（來自 CR-0040）**：`brand_oem` / `accounting` 兩個後端有用到的角色，**不在前端 `rolePolicy.ts` 任何路由清單** → 這些角色就算建了帳號也登不進任何頁。呼應業主「5 種角色只有 admin」—— 不只缺帳號建立，連既有角色都進不來。

→ **修復**: [CR-0092](CR-0092-rbac-hardening.md)（本輪硬化 80 HIGH）。

---

## 二、前後端對照（23 CR 逐一實證）

| CR | 後端 | 前端 | 嚴重 | 落差摘要 |
|---|---|---|---|---|
| **CR-0026** | done | partial | **HIGH** | 工單欄位 setter + RBAC 都有，**前端零編輯 UI**；serial/door/warranty/service_category 在後台根本無法輸入 |
| **CR-0035** | done | missing | **HIGH** | 報價→應收發票三條寫入路徑全做完，**前端發票頁仍純唯讀**、無「開立發票/觸發月結」按鈕 |
| **CR-0036** | done | missing | **HIGH** | 訂金/佣金/月結灌進 config，但**前端無 config 治理 UI**，且 deposit_required「只寫不讀」（API 不回傳）|
| **CR-0039** | done | missing | **HIGH** | 完工三道硬閘 + 技師正規端點全做完，**前端完全沒接**；技師完工頁仍打後台 override 端點 → 撞 403 guard，**主完工流程實質壞掉** |
| **CR-0040** | done | partial | **HIGH** | 角色過濾 evidence 完整，但**被保護角色 brand_oem/accounting 不在 rolePolicy 無法登入**；角色感知元件是死碼從未掛載 |
| CR-0029 | done | partial | MED | 廠商註冊/核准做完，但**登入後到不了任何廠商頁**（rolePolicy 不含 vendor，無廠商專區）→ deferred CR-0031 |
| CR-0037 | done | missing | MED | 拆帳規則主檔 + API + 69 筆 seed，**前端零消費**（無頁/無入口）|
| CR-0042 | done | partial | MED | 轉單 422 結構化缺漏欄位 + override，前端丟棄結構化錯誤、**無 override UI** |
| CR-0043 | done | partial | MED | PATCH fields / reopen 端點完整，**前端無編輯表單/無 reopen 按鈕**（CR-0026 缺口寫入面複製）|
| CR-0046 | done | missing | MED | company_profile/discount_policy 入 config + CRUD API，**前端無檢視/編輯 UI** |
| CR-0047 | done | partial | MED | 輸入序號自動算保固後端全做，前端**只唯讀顯示、無編輯 UI 可觸發** |
| CR-0044 | done | missing | LOW | 取消費/有效期入 config，前端無檢視（CR 本就 scope out UI）|
| CR-0045 | done | partial | LOW | tax_policy 可動態改但前端無調稅 UI |
| CR-0033 | done | partial | LOW | 免責簽署頁完整，但**同意連結未派送給客戶**、operator 端無同意狀態（後者本輪 CR-0091 補）|
| CR-0028 | done | n/a | LOW | LINE 推播修復，消費端是 LINE 非後台，無前端缺口 |
| CR-0022/0024 | done | done | LOW | 完整同步，僅測試覆蓋/Phase 2 尾巴 |
| **CR-0021/0027/0030/0032/0034/0041** | done | done | NONE | **前後端完全同步**（罕見好案例）|

### 共通病灶
1. **「DB/API 有、UI 沒接」反覆出現**（CR-0026/0035/0036/0037/0043/0046/0047）—— 欄位與端點建好，但後台沒有對應的輸入表單或動作按鈕。
2. **config 治理零 UI**（CR-0036/0044/0045/0046）—— 多個 CR 把參數搬進 M18 config governance，但前端只有 legacy SystemConfigForm（rag/llm/resolution/line_bot 四段），業主無法自助改值。
3. **角色設計斷層**（CR-0029/0040）—— 後端有角色概念，前端 rolePolicy 漏列 → 角色帳號登不進對應頁。

---

## 三、本輪修復範圍 vs 留待後續

| 項目 | 狀態 |
|---|---|
| i18n 66 個 raw key（quotes/quoteCatalog/vendorApprovals/工單詳情）| ✅ 本輪修（commit a34e0de7）|
| RBAC 硬化 80 HIGH 端點 | 🔧 本輪（CR-0092）|
| 派工單 6 模組視圖 + admin 免責同意 GET | 🔧 本輪（CR-0091；後端 GET ✅，前端視圖建置中）|
| CR-0026/0043/0047 工單欄位「編輯 UI」 | ⏳ 併入 CR-0091 派工單 inline edit（部分覆蓋）|
| CR-0035/0036 發票/config 治理前端 | 📋 Phase II（範圍大，獨立 CR）|
| CR-0039 技師完工頁接正規端點（含 403 撞牆修復）| 📋 Phase II（HIGH，建議優先排）|
| CR-0040 角色補進 rolePolicy + CR-0029 廠商專區 | 📋 Phase II |
| MED 193 端點收緊 | 📋 Phase II（避免過度收緊合法 cross-role 讀取）|

> 完整逐端點矩陣留存於稽核產物（perm_matrix.json，80 HIGH + 193 MED 逐筆 path/category/fix）。
