---
id: CR-0092
title: "RBAC 硬化 — 80 個敏感寫入端點補後端角色守衛"
status: implementing
tier: 4-exploration
owner: HYBRID
created: 2026-06-21
target-release: dev_new_arch
product-version: null
supersedes: null
superseded-by: null
---

# CR-0092: RBAC 硬化 — 補後端角色守衛

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md`（觸發：Architecture boundary + API contract — 變更端點授權語意）
> **背景**: 業主「連權限設定都沒改好」。稽核 407 端點發現只有 ~36 用 `role_required`，其餘 `require_tenant`（**不檢查角色**）。

## 1. Change Statement

**As-is**: `require_tenant` 只驗 JWT + tenant，**完全不檢查 user.role**。407 端點中 **80 個敏感寫入**（accounting 45 / admin-only 14 / pricing 10 / dispatch 5 / data-correction 2 / role-mgmt 2 / audit 1 / cs 1）僅靠 `require_tenant` → **任何登入者（含 technician / vendor）可寫金流、設定、派工、結算、退款、技師生命週期**。部分端點掛 `_require_initiator` / `_require_sod_two`，但那些只檢查 `X-Initiator` header 是否存在/相異，**不檢查角色**，可任意填寫繞過。

**To-be**: 80 個 HIGH 端點改掛 `role_required(*ROLES)`（`role_required` 內部已含 `require_tenant`，drop-in 升級），角色集對齊既有 gated 端點 + 前端 `rolePolicy.ts`。

**Driver**: 安全漏洞（跨角色金流/設定寫入）+ 業主裁決「一起都做」。

## 2. 標準角色集合（core/deps.py，CR-0092）

集中於 `core/deps.py`，為「既有 `_BILLING_ROLES`/`_APPROVE_ROLES`/`_DISPATCH_ALLOWED_ROLES` 之超集 + super_admin」：

| 常數 | 角色 | 套用範圍 |
|---|---|---|
| `FULL_ACCESS_ROLES` | admin, tenant_admin, super_admin | config / roles / audit / GDPR / data-correction |
| `OPS_ROLES` | + operations_manager | accounting / billing / pricing / vendor-mgmt / warranty / 結算 / 退款 |
| `DISPATCH_ROLES` | + dispatcher | dispatch / auto-match / 技師生命週期 |
| `BACKOFFICE_ROLES` | + customer_service | 後台唯讀／一般操作 |

> **設計原則**：既有 gated 集合皆為新常數子集 → **不破既有存取**，只多放行 super_admin（修正其被誤擋的潛在 bug）。各 router 若已有合適 `_XXX_ROLES` 區域常數則沿用，否則 import 共用常數。

## 3. Affected API

| 範圍 | Action | Breaking? |
|---|---|---|
| 80 個 HIGH 寫入端點 | `require_tenant` → `role_required(*ROLES)` | **對 technician/vendor 為 breaking（本就不該有權限，故為修補非破壞）**；對後台角色不變 |
| 193 個 MED（多為讀取/cross-role-read）| **Phase II**（本 CR 不動，避免過度收緊合法跨角色檢視如 CS 讀工單）| — |

新增錯誤回應：非授權角色打這些端點由 200/寫入成功 → **403 FORBIDDEN**。

## 4. Affected Data / Architecture

- **無 schema 變更**；無新 ADR（沿用既有 `role_required` 機制，非新授權架構）。
- 影響模組：accounting / pricing / dispatch / config / rbac / gdpr / technician-lifecycle routers。

## 5. Affected Test

- 新增 `test_cr_0092_rbac_hardening.py`：technician/vendor token 打代表性 HIGH 端點（brand-b2b generate / dispatcher-commission approve / m18 config / data-correction approve / dispatch auto-match）→ **403**；admin/ops → 通過守衛。
- 回歸：全 unit/component suite 必須綠（既有後台角色測試會抓出過度收緊）。

## 6. Human Decisions Required

✅ 業主已裁決「一起都做」（blanket）。以下為實作決策（已採低風險預設，記錄供覆核）：

| # | 問題 | 決策 |
|---|---|---|
| 1 | 角色集 | 對齊既有 gated 端點 + super_admin（超集，不破既有）|
| 2 | MED 193 是否一起收緊 | **否**，Phase II 評估（避免過度收緊合法 cross-role 讀取）|
| 3 | SoD 雙簽（mark-paid/approve）是否強制 | 沿用現況（header SoD 留痕），雙簽角色強制列 Phase II |
| 4 | finance_manager / accountant 等稀有角色 | 不納入（程式碼僅 2-3 處用，非正典；對齊 rolePolicy 用 operations_manager）|

## 7. Implementation Order

1. ✅ `core/deps.py` 加 `FULL_ACCESS_ROLES / OPS_ROLES / DISPATCH_ROLES / BACKOFFICE_ROLES`。
2. 80 個 HIGH 端點逐一改 `role_required(*ROLES)`（依 category 選常數）。
3. `test_cr_0092` 角色隔離測試。
4. 全 suite 回歸綠。
5. 三處同步（CR §8 進度 / CHANGELOG / 完成度）。

## 8. Risks & Rollback

| Risk | 緩解 |
|---|---|
| 過度收緊擋到合法後台角色 | 常數為既有集超集；全 suite 回歸 + 角色隔離測試 |
| 漏改某 HIGH 端點 | 矩陣 80 筆逐一對照；保留 `perm_matrix.json` 稽核 |
| vendor/dispatcher self-scope 端點被誤當後台收緊 | self-scoped（commission self-dispute 等）標 Phase II 改 self-scope 比對，不在本 CR 一刀切 |

Rollback：純 dependency 替換，改回 `require_tenant` 即復原（無 schema/資料變更）。

## 9. 進度

- ✅ S1（deps 常數）done
