---
id: CR-0029
title: "Change Impact Analysis — 廠商/師傅雙路註冊（發案者 + 接案者）"
status: built
tier: 4-exploration
owner: HYBRID
created: 2026-06-18
target-release: TBD（Lite 版 / Beta 前）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0029: 廠商/師傅雙路註冊

> **Tier**: 4-exploration → CIA（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 User flow / Domain model / DB schema / API contract）
> **驅動來源**: 2026-06-17 會議 Action #3「加廠商/師傅註冊系統（發案者/接案者兩種路由，資料庫分開）」
> **依賴**: CR-0025 auth/password 基礎；single-tenant 可逆版（multi-tenant 三類租戶 → CR-0031）

---

## 1. Change Statement

**As-is**：僅師傅 self-register（`auth_service.register_technician` → users(role=technician) + technicians），無廠商/品牌商註冊路由與主表；前端無註冊頁。

**To-be**：發案者（品牌商/鎖店/經銷商）與接案者（師傅）兩路註冊。新增 `vendors` 主表 + `register_vendor` + vendor 獨立 login；`users.tenant_type`（requestor/technician/platform）預留三類租戶。前端單一 `/register` 頁含技師/廠商切換。**single-tenant 可逆版**（tenant_id 仍硬綁，tenant_type 預留）。

**Driver**：會議定調平台轉「外包仲介」，需兩端自助註冊。

## 2. Affected Flow / 3. Spec

| Flow / Spec | Action | Description |
|---|---|---|
| `UF` 廠商註冊 | New | /register 廠商分頁 → vendors 待審 |
| `UF` 師傅註冊 | Modified | 既有端點 + 新前端入口 |
| `FR` 註冊規則 | New | email 全域去重、vendor_type 列舉、pending_approval 待管理員核准 |

## 4. Affected API

| API | Endpoint | Action |
|---|---|---|
| `registerVendor` | `POST /vendors/register` | New（201，pending_approval）|
| `loginVendor` | `POST /vendors/login` | New（allowed_roles=['vendor']，**與後台角色隔離**，不入 `_ADMIN_WEB_ROLES`）|
| `registerTechnician` | `POST /technicians/register` | Unchanged（補寫 tenant_type='technician'）|

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `vendors`（新表）| New | migration 038：user_id FK / vendor_type(brand/locksmith/distributor) / name / company_name / phone / email / address / status(pending_approval…) / approved_by / tenant_id(預留) + 3 index |
| `users.tenant_type` | New 欄 | requestor/technician/platform（nullable，CR-0031 預留）+ backfill 既有（technician→technician、後台→platform、line_user→NULL）|

> vendors / tenant_type 比照既有 saas.* / users.tenant_id 慣例走 migration（base Schema.sql 不含 tenant 欄），不改 Schema.sql。

## 6. Affected Test

`test_cr_0029_registration.py`：register_vendor → users(role=vendor,tenant_type=requestor)+vendors；email dup→409；vendor_type 非法→422；vendor 可 vendors/login 但**不能登後台**。回歸 test_login_roles / test_auth_guards。

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| 角色隔離 | New role `vendor` | 獨立 `/vendors/login`，**不加進 `_ADMIN_WEB_ROLES`**（防 vendor 登後台）|
| Multi-tenant | 可逆準備 | tenant_type 預留三類；tenant_id 仍 single-tenant 硬綁；CR-0031 再轉 |
| 複用 | auth 基礎 | hash_password / email 去重 / transaction / idempotency / ApiError（CR-0025 交付）|

## 8. Human Decisions Required

✅ **會議授權用預設先做（Action #3 拍板）。** 採用：

| # | Question | Status | Decision（預設）|
|---|---|---|---|
| 1 | 「資料庫分開」 | ✅ 預設 | 本輪 single-tenant 可逆版（vendors/technicians 分表 + tenant_type 預留）；真正分庫屬 CR-0031 multi-tenant |
| 2 | email 多重身分（同人既技師又廠商）| ✅ 預設 | 本輪 email 全域唯一；多重身分待 CR-0031 |
| 3 | vendor 審核流程 | ✅ 預設 | status=pending_approval，管理員核准 UI 列 follow-up（approved_by/approved_at 欄已備）|
| 4 | 營業執照上傳 | ⏳ follow-up | 本輪不收檔（business_license 欄暫不建）；待業主確認需求 |

## 9. Implementation Order（已實作）

1. ✅ migration 038（vendors + users.tenant_type + backfill）
2. ✅ `auth_service.register_vendor` + register_technician 補 tenant_type
3. ✅ `auth.py` registerVendor + loginVendor 端點
4. ✅ `test_cr_0029_registration.py` 4 pass + auth 回歸
5. ✅ 前端 `/register`（技師/廠商切換）+ 登入頁註冊連結 + i18n
6. ⏳ Docs sync（commit 時）

## 10. Risks & Rollback

| Risk | Mitigation |
|---|---|
| vendor 登後台 | 獨立 /vendors/login，不加 `_ADMIN_WEB_ROLES`；測試驗證擋下 |
| 動 users INSERT 破壞 auth 測試 | 回歸 test_login_roles/test_auth_guards 全綠（14 pass）|
| 提前分庫=觸發 CR-0031 大重構 | 本輪只 single-tenant 可逆版 + tenant_type 預留 |

**Rollback**：新表 + nullable 欄 + 新端點，可逆。

## 11. Out of Scope

- Multi-tenant 三類租戶分庫（CR-0031）；vendor 審核 UI / 營業執照上傳；多重身分（同 email 多 role）。

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主）| Sunny | 2026-06-17 | ✅ 會議授權用預設先做 |

## 13. 實作進度

- ✅ migration 038 + register_vendor + vendor login + 前端 /register + 測試 4 pass + auth 回歸 + tsc 0；migration 038 套 dev DB 驗證
- ⏳ follow-up：vendor 審核 UI（approve/reject）、營業執照上傳、CR-0031 multi-tenant 分庫
- 分支：`feat/cr-0029-dual-registration`
