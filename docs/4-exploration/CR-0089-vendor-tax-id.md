---
id: CR-0089
title: "廠商註冊新增統一編號 + 公司名必填"
status: implemented
tier: 4-exploration
owner: HYBRID
created: 2026-06-21
target-release: dev_new_arch
product-version: null
supersedes: null
superseded-by: null
---

# CR-0089: 廠商註冊新增統一編號 + 公司名必填

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md`（觸發：DB schema + API contract）
> **背景**: 業主逐頁測試廠商註冊時，先遇 404（路徑缺 `/api/v1`，已由 `fix/register-path-and-fields` cherry-pick 修復），再評估「是否需更多資訊」。

## 1. Change Statement

**As-is**: 廠商（發案者：品牌商/鎖店/經銷商）註冊收 7 欄（類型/聯絡人/公司名(選填)/手機/Email/密碼/地址）。`vendors` 表無統一編號欄位。

**To-be**: 新增「統一編號」（必填，8 碼）+ 公司名改必填。台灣 B2B 對廠商開立發票/對帳/簽約需統編。

**Driver**: 業主裁決（逐頁測試 AskUserQuestion）「加統一編號 + 公司名必填」。研究 B2B 供應商 onboarding 慣例（tax ID 為核心）。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `UF-廠商註冊`（CR-0029 衍生） | Modified | 廠商分頁新增統編欄、公司名改必填 |

## 3. Affected Spec

| Spec ID | Action | Description |
|---|---|---|
| `FR-vendor-register`（CR-0029） | Modified | 註冊欄位 +tax_id（必填 8 碼）、company_name 改必填 |

## 4. Affected API

| API | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| registerVendor | `POST /api/v1/vendors/register` | Schema tighten | 局部 | `VendorRegisterBody` +tax_id(`^\d{8}$` 必填)、company_name 由 optional 改 min_length=1。唯一 caller 為註冊頁，已同步；舊請求缺 tax_id/company_name → 422 |

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `vendors` | +`tax_id VARCHAR(8)` | **migration 076**（ADD COLUMN IF NOT EXISTS，既有列 NULL 向後相容、不回溯，idempotent）|

無 state machine 影響。無唯一性約束（同公司可多聯絡人；未來如需以 tax_id 去重另議）。

## 6. Affected Test

| Test | Action | Description |
|---|---|---|
| `test_cr_0089_vendor_tax_id` | New | VendorRegisterBody 驗證：統編 8 碼必填、公司名必填（9 案，pytest unit）|
| `test_cr_0029_registration` | Unchanged | 走 service 層（繞 Pydantic），tax_id nullable → 不破；service INSERT 已含 tax_id |

## 7. Affected Architecture

無模組邊界變更；無新 ADR。

## 8. Human Decisions Required

✅ **業主已裁決（2026-06-21，逐頁測試）：加統一編號 + 公司名必填。**

| # | 問題 | 決策 |
|---|---|---|
| 1 | 廠商欄位範圍 | **加統一編號 + 公司名必填**（不含負責人/職稱/銀行/營登上傳，列 Phase II）|
| 2 | 統編格式/必填 | 必填、8 碼數字（`^\d{8}$`）；既有列允許 NULL（不回溯）|
| 3 | 統編唯一性 | MVP 不設 UNIQUE（同公司多聯絡人情境）；未來如需另議 |

## 9. Implementation（已完成）

1. ✅ migration 076 `vendors +tax_id`（套 dev + 記 schema_migrations 076）
2. ✅ `VendorRegisterBody` +tax_id 必填 + company_name 必填
3. ✅ `register_vendor` INSERT/return 含 tax_id
4. ✅ 前端註冊頁廠商分頁加統編欄(required pattern \d{8}) + 公司名 required + i18n（taxId/taxIdHint 中英）
5. ✅ test_cr_0089 9/9 + 回歸 267 unit 全綠
6. ✅ 實機：帶統編 201 落庫、缺統編 422、非 8 碼 422

## 10. Risks & Rollback

| Risk | 緩解 |
|---|---|
| 既有 caller 缺欄 422 | 唯一 caller=註冊頁，已同步；無其他外部 caller |
| 既有 vendors 列無統編 | 欄位 nullable，不回溯；僅新註冊強制 |

Rollback：欄位 nullable 純加法可逆；前端/Pydantic 變更可單獨 revert。

## 11. Out of Scope

- 負責人 / 聯絡人職稱 / 銀行帳戶 / 營業登記證上傳（Phase II）
- 統編真實性驗證（財政部 API 勾稽）
- 對既有廠商回填統編

## 12. Sign-off

| Role | Date | Approved? |
|---|---|---|
| Product / 業主 | 2026-06-21 | ✅（逐頁測試裁決）|
