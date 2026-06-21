---
id: CR-0090
title: "技師與廠商可共用同一 email（email 唯一性改每角色唯一）"
status: implemented
tier: 4-exploration
owner: HYBRID
created: 2026-06-21
target-release: dev_new_arch
product-version: null
supersedes: null
superseded-by: null
---

# CR-0090: 技師與廠商可共用同一 email

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md`（觸發：Domain model — 改變 email 唯一性不變式）
> **背景**: 業主逐頁測試時，同一人想同時當師傅（接案）與廠商（發案），但註冊回 `EMAIL_TAKEN (409)`。

## 1. Change Statement

**As-is**: `email` 在 `users` 表「全域唯一」（register_technician / register_vendor 皆 `WHERE email = %s` 檢查）→ 同 email 無法同時註冊技師與廠商。

**To-be**: email 唯一性放寬為「**每角色唯一**」—— 同 email 可同時為技師 + 廠商（兩列 users，role 各異），但同一角色內仍唯一。

**Driver**: 業主裁決「師父跟廠商 email 改成可以用同一個」。平台轉外包仲介後，同一自然人兼具接案/發案身分為常見情境。

## 2. Affected Flow / Spec

| ID | Action | Description |
|---|---|---|
| `UF-技師註冊 / UF-廠商註冊` | Modified | 唯一性檢查由全域改為角色限定 |
| email 唯一性 invariant | Modified | global-unique → unique-per-role |

## 3. Affected API

| API | Action | Breaking? |
|---|---|---|
| registerTechnician / registerVendor | 行為放寬（同 email 跨角色不再 409） | 否（更寬鬆，不破既有 caller）|

錯誤訊息更精確：`...already registered as a technician / a vendor`。

## 4. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `users` | **無 schema 變更** | ❌ |

> 關鍵：`users.email` **本來就無 UNIQUE 約束**（僅 `line_user_id` UNIQUE + PK；`idx_users_email_tenant` 為非唯一索引）。DB 早允許重複 email，故零 migration。

## 5. 登入分辨（為何不衝突）

`_find_user_by_email(email, role_in)` 為 `WHERE email = %s AND role IN (...)`；
`/technicians/login` 帶 `["technician"]`、`/vendors/login` 帶 `["vendor"]` →
同 email 兩列各自由對應端點 + 各自密碼登入，天然分辨。兩帳號為**獨立 users 列**
（獨立 password_hash / status / profile）。

## 6. Affected Test

| Test | Action |
|---|---|
| `test_cr_0090_cross_role_email` | New（component）：同 email 技師+廠商皆成功、同角色仍 409、兩帳號各自 role 登入 |
| `test_cr_0029_registration` | Unchanged（vendor 單路徑仍 409 行為不變）|

## 7. Affected Architecture

無模組邊界變更；無新 ADR。

## 8. Human Decisions Required

✅ **業主已裁決：技師與廠商可共用 email。**

| # | 問題 | 決策 |
|---|---|---|
| 1 | 共用粒度 | **每角色唯一**（同 email 一技師帳 + 一廠商帳；同角色內不可重複）|
| 2 | 帳號模型 | **兩列獨立 users**（各自密碼/狀態/profile），非單列多角色 |
| 3 | 密碼重設（admin/self）以 email 比對遇重複 email 之歧義 | **Phase II**：目前 `admin_reset_password` 以 email+tenant `LIMIT 1` 取一列（歧義邊角），待 reset 流程改 role-aware；本 CR 不擋（reset 為管理員手動、低頻）|

## 9. Implementation（已完成）

1. ✅ register_technician 檢查 → `WHERE email = %s AND role = 'technician'`
2. ✅ register_vendor 檢查 → `WHERE email = %s AND role = 'vendor'`
3. ✅ 錯誤訊息標明角色
4. ✅ test_cr_0090 4/4（component）+ 回歸 267 unit；實機：技師201→廠商同email 201→技師同email再註冊 409；DB 同 email 兩列 technician+vendor

## 10. Risks & Rollback

| Risk | 緩解 |
|---|---|
| 密碼重設遇重複 email 歧義 | §8-3 列 Phase II；目前 LIMIT 1 取一列、reset 為手動低頻 |
| 下游若假設 email 全域唯一 | 已查：登入 role 過濾、profile 由 user_id 取；無其他全域唯一假設 |

Rollback：純 service 檢查放寬，改回 `WHERE email = %s` 即復原（無 schema/資料變更）。

## 11. Out of Scope

- 單列多角色（一個帳號同時是技師+廠商）— 採兩列獨立帳號
- 密碼重設 role-aware 化（Phase II）
- 帳號合併 / 跨身分 SSO

## 12. Sign-off

| Role | Date | Approved? |
|---|---|---|
| Product / 業主 | 2026-06-21 | ✅（逐頁測試裁決）|
