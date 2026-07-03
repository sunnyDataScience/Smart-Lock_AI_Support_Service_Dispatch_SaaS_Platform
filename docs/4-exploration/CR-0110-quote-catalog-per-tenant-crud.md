---
id: CR-0110
title: "報價主檔 per-tenant CRUD（各租戶自有價碼）"
status: implemented
tier: 4-exploration
owner: HYBRID
created: 2026-07-01
target-release: go-live
product-version: null
supersedes: null
superseded-by: null
---

# CR-0110: 報價主檔 per-tenant CRUD（各租戶自有價碼）

> **Tier**: 4-exploration → Change Impact Analysis（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（觸發面向：API contract / Domain model / DB schema / Architecture boundary）
> **CIA 產出**：手動依 `VibeCoding_Workflow_Templates/4-exploration/CIA-0000-*.template.md`（原 `sunnydata-change-impact-analysis` skill 已不在 registry）

---

## 1. Change Statement

**As-is**：報價主檔頁（`/admin/quote-catalog`）為**唯讀**——`GET /tenants/{tid}/quote-catalog` → `quote_catalog_service.get_catalog` 讀 `service_catalog`(32) / `material_catalog`(20) / `surcharge_rule`(12) 三表。三表 **PK 只在 code 上**（`service_code` / `material_code` / `rule_code`），`tenant_id` 欄存在但目前全庫共用一份 global 樣板（多為 `tenant_id IS NULL`、`is_mock=TRUE`、`decision_status='待填價'`）。無任何寫入端點。

**To-be**：**每個租戶可維護自己的一套價碼**——三類目（服務 / 材料 / 加價規則）提供 Create / Update / Delete，租戶隔離，報價試算引擎依租戶取正確價。

**Driver**：業主需求——不同租戶（鎖匠加盟店 / 品牌商）有各自的成本結構與收費，不能共用單一 global 價目；需自助 CRUD 而非改 seed。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| 報價主檔管理流程（新 BF/UF，尚未編號） | New | admin 新增/編輯/刪除本租戶服務·材料·加價規則 |
| 報價試算流程（`quote_engine_service.add_line`） | Modified | 加報價明細時，catalog 查價須改為 tenant-scoped（見 §7）|
| 現場追加價 / 客戶報價單 | Unchanged（資料源變） | 讀的仍是 catalog，但取值改租戶版 |

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| FR（catalog 管理，新） | New | 服務/材料/加價規則 CRUD 契約與驗證（code 唯一性、必填欄、金額 ≥ 0）|
| FR（catalog 查價，改） | Modified | 查價由「code 唯一」改為「(tenant, code) 解析 + fallback 規則」|
| NFR（租戶隔離） | Modified | catalog 讀寫皆須 cross-tenant guard（對齊 ADR-0030）|

## 4. Affected API

| API | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `getQuoteCatalogV2` | `GET /tenants/{tid}/quote-catalog` | Response 可能加欄 | No | 若加 `id`/`editable`/`source(global/tenant)` 為 additive |
| 新 | `POST /tenants/{tid}/quote-catalog/services` | New | No | 新增服務項目 |
| 新 | `PATCH /tenants/{tid}/quote-catalog/services/{code}` | New | No | 編輯（價、名稱、狀態）|
| 新 | `DELETE /tenants/{tid}/quote-catalog/services/{code}` | New | No | 刪除（軟/硬見 §8-5）|
| 新 | `POST/PATCH/DELETE …/materials/{code}` | New | No | 材料同上 |
| 新 | `POST/PATCH/DELETE …/surcharges/{code}` | New | No | 加價規則同上 |

全部走 v2 tenant-scoped path + cross-tenant guard + idempotency（POST）。CRUD 端點對既有 GET 呼叫者非破壞。

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `service_catalog` | PK `service_code` → 需支援 (tenant, code) 唯一（見 §8-2）| **需 migration**：改複合唯一鍵或加 surrogate `id` + `UNIQUE(tenant_id, service_code)` |
| `material_catalog` | 同上（`material_code`）| 同上 |
| `surcharge_rule` | 同上（`rule_code`）| 同上 |
| 三表 | `is_mock` / `decision_status` 於租戶編輯後語意（見 §8-6）| App-level；可能加 `deleted_at`（軟刪，§8-5）+ `updated_by` |

**核心約束**：目前 PK = code，同一 `SVC-RES-001` 全庫只能存一列 → **無法讓兩租戶各有不同價**。這是本 CR 的根本 schema 決策點。

## 6. Affected Test

| Test | Action | Description |
|---|---|---|
| `test_cr_0034_quote_catalog`（既有） | Update | GET 回應含租戶版/新欄位 |
| catalog CRUD（新） | New | 建立/編輯/刪除 happy-path × 3 類目 |
| 租戶隔離（新） | New | cross-tenant 建立/讀取/刪除 → 403 CROSS_TENANT_*；A 租戶看不到 B 的價 |
| code 唯一性（新） | New | 同租戶重複 code → 409；跨租戶同 code 允許 |
| quote_engine tenant 取價（新/改） | New | `add_line` 對有租戶覆寫的 code 取到租戶價、無覆寫取 global（依 §8-1 fallback）|

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| **報價試算引擎（重大）** | **必改** | `quote_engine_service.add_line` 現以 `WHERE service_code=%s` / `material_code=%s` **無 tenant_id** 查價（api/services/quote_engine_service.py:132,137）→ per-tenant 價導入後**這裡不 tenant-scope 就會抓錯價 / PK 不再唯一**，等於租戶各自價碼在「真正開報價」時失效。須改為依 (tenant, code) 解析 + fallback。 |
| Module boundary | Unchanged | 仍在 quote/catalog bounded context |
| 新 ADR？ | **需要** | ADR 記錄 §8-1 資料模型（global+override vs 全獨立 copy）與 §8-2 唯一鍵方案 |
| pricing_matrix（sheet 04）/ pricing_rule_service | 待界定 | 第一版價格矩陣是否也 per-tenant？（§8-9 範圍邊界）|

## 8. Human Decisions Required

🛑 **CIA 阻擋 code 變更，直到每列都有裁決。**

> **2026-07-03 裁決落地（20260702 會議 + 業主 AskUserQuestion）**：
> 20260702 會議拍板「一品牌一 GCP 專案 + 獨立 DB」（會議記錄 §三/§五）——
> 單品牌 DB 內 code 天然唯一 → **§8-1（資料模型）、§8-2（唯一鍵）、§8-4 之跨租戶顧慮、
> §8-7（code 產生）、§8-8（fallback）、§8-9（矩陣邊界）全數失效或大幅簡化**，
> 不做 global+override、不改複合鍵、quote_engine.add_line 按 code 查價不變。
> 業主 2026-07-03 裁決殘餘三項：**§8-3=(a) 三類目一次做**；**§8-5=(a) 軟刪 deleted_at**
> （migration 087；同 code 重建=復活該列）；**§8-6=(a) 租戶編輯後 is_mock=FALSE +
> decision_status='已確認'**。RBAC 沿用 pricing_rules_v2 慣例（OPS_ROLES）。
> 實作：branch `feat/quote-catalog-crud`（9 端點 create/update/delete × 三類目、
> 前端報價主檔頁新增/編輯/刪除 modal、test_quote_catalog_crud 9 測試）。


| # | 問題 | 選項 | Owner | Status | Decision |
|---|---|---|---|---|---|
| 1 | **資料模型** | (a) global 樣板(tenant NULL) + 租戶覆寫，查價「租戶列優先、否則 global」 (b) 每租戶完整 copy 一份、無 global fallback (c) 純租戶、無 global 概念（onboarding 給空白或選填樣板）| 業主+架構 | open | — |
| 2 | **唯一鍵 / PK 方案** | (a) 改複合主鍵 `(tenant_id, code)` (b) 加 surrogate `id` PK + `UNIQUE(tenant_id, code)`（外鍵較穩）| 架構 | open | — |
| 3 | **CRUD 範圍** | (a) 服務+材料+加價規則三類一次做 (b) 先服務、其餘後續 CR | 業主 | open | — |
| 4 | **RBAC** | 哪些角色能 CRUD 報價主檔？(a) 僅 admin (b) admin + 新「定價管理」角色 (c) 含客服主管 | 業主+安全 | open | — |
| 5 | **刪除語意** | (a) 軟刪 `deleted_at`（可復原/稽核） (b) 硬刪。租戶能否「刪/隱藏」global 預設，或只能刪自己建立的列？| 業主 | open | — |
| 6 | **is_mock / decision_status** | 租戶填了自己的價後：(a) `is_mock` 翻 FALSE、`decision_status` 標「已確認」 (b) 這兩欄僅屬 global 樣板、租戶列不沿用（改記 `updated_by`/`updated_at`）| 業主 | open | — |
| 7 | **code 產生規則** | 新增項目時 code 由 (a) 使用者自填（驗唯一） (b) 系統自動產生（如 `SVC-{tenantSlug}-NNN`）。唯一性範圍＝租戶內 | 架構+業主 | open | — |
| 8 | **quote_engine fallback** | `add_line` 取價：確認「租戶列優先 → 無則 global」是否符合業務（承 §8-1）；global 也無時該報錯還是價 0 | 架構 | open | — |
| 9 | **範圍邊界** | 本 CR 是否含「04 第一版價格矩陣 / pricing_rule」per-tenant，或僅本頁三類基礎主檔？矩陣另立 CR？| 業主 | open | — |

## 9. Suggested Implementation Order

§8 全數裁決後，依相依序實作：

1. **ADR** → 記錄 §8-1 資料模型 + §8-2 唯一鍵 + §8-8 fallback 決策
2. **Schema migration** → 三表唯一鍵改造（+ 視 §8-5 加 `deleted_at`、§8-6 欄位語意）
3. **Service（讀）** → `quote_catalog_service.get_catalog` 查價改 (tenant, code) 解析 + fallback
4. **Service（寫）** → catalog CRUD service（三類目 create/update/delete + 驗證 + cross-tenant guard）
5. **報價引擎** → `quote_engine_service.add_line` 取價改 tenant-scoped（§7 重點、避免價碼失效）
6. **API** → 新 POST/PATCH/DELETE 端點（openapi + generated model）+ 既有 GET 加 additive 欄
7. **Tests** → CRUD happy-path + 租戶隔離 403 + code 唯一 409 + 引擎取價（TDD）
8. **UI** → 報價主檔頁加新增/編輯/刪除（表格行內編輯或 modal）
9. **Traceability + doc-freshness** → 更新 TM、確認 tier-2 contract 同步

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 唯一鍵 migration 撞既有外鍵/引用（quote_line_items 以 code 記價來源）| Medium | High | 先盤 code 被誰參照；採 surrogate id 方案降風險（§8-2b）|
| 報價引擎漏改 tenant-scope → 租戶價不生效卻無報錯 | Medium | High | §9-5 明列為必做；加「引擎取價」測試守門 |
| 既有 global mock 列與新租戶列混淆（is_mock 語意）| Medium | Medium | §8-6 先定義；migration 標記來源 `source=global/tenant` |
| 刪除破壞既有報價明細的價來源可追溯性 | Low | Medium | 傾向軟刪（§8-5a）保稽核 |

**Rollback**：CRUD 端點以 feature-flag / 路由層可關；schema 採「加 surrogate id + 新唯一鍵」為 additive、可保留舊 code 唯一性一段時間並行；引擎取價改動以「租戶無覆寫時等價於舊行為」保後相容。

## 11. Out of Scope

- 04 第一版價格矩陣 / pricing_rule per-tenant（除非 §8-9 裁決納入 → 另 CR）
- 正式價填寫（Q-01~Q-12 業務決策，屬 CR-0034 脈絡、非本 CR）
- 報價單 PDF 版型 / 稅務顯示（另 CR）
- 跨租戶價目複製 / 匯入匯出工具（後續增強）

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| 業主 | | | |
| 架構 | | | |
| 工程 Lead | | | |
| QA Lead | | | |
