---
id: CR-0037
title: "Change Impact Analysis — 師傅拆帳規則主檔（esales sheet 21 mock seed）+ 剩餘 esales 誠實分流"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-19
target-release: TBD（補洞優先）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0037: 師傅拆帳規則主檔

> **Tier**: 4-exploration → CIA（per-change）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 Domain model / DB schema）
> **驅動來源**: 業主「一起做」剩餘 esales 資料。盤點（remaining-esales-scout）後**誠實分流**：唯一有真草稿資料且可 mock-first 建的＝師傅拆帳（sheet 21）。
> **🛑 mock-first（決議 5）：sheet 21 值當 mock seed，正式值待業主 Q-09 師傅分潤；NOT wired 進 reconciliation 重算（Phase II）。**

---

## 1. Change Statement

**As-is**：esales sheet 21「Technician Payout Rule」有 69 筆師傅拆帳草稿（23 服務 × A/B/C 級別 + 夜間/急件加成率），但 code 拆帳硬編 80%（ADR-0041），與服務/等級無關。無 `technician_payout_rule` 表。

**To-be**：建 `technician_payout_rule` 主檔（仿 CR-0034 catalog）+ 69 筆 mock seed + 查詢 service + 後台 API（base_payout RBAC 遮蔽）。**不接** reconciliation 重算（拆帳 × 0.8 → 查表）。

**Driver**：把 sheet 21 既有草稿值灌為可查的拆帳主檔，為 Phase II 拆帳重算備好資料（structure-first，同 CR-0034 catalog → CR-0032 引擎的先後）。

## 2. 剩餘 esales 誠實分流（盤點結論）

| 項目 | 狀態 | 處置 |
|---|---|---|
| **師傅拆帳 sheet 21** | 69 筆真草稿 | ✅ **本 CR 建** |
| 服務/材料價 Q-01/02 | CR-0034 已 seed 完整（值+decision_status） | 已完成，無 gap |
| 加價 Q-03~06 | CR-0034 surcharge_rule 已 seed 值 | seed 完成；**套用引擎** deferred（待 Q-03~06 算法決策） |
| 退款 tier | ADR-0040 已實作 | 已完成，不重做 |
| 客戶報價文字 Q-12 | esales **真無值**（同稅 Q-07） | ❌ defer（無 source 不捏造，待客服主管） |
| AR/AP Ledger / Brand Settlement / 佣金引擎（sheet 27-31） | 各 1 sample 列，依賴金流代收代付（會議 Phase 2） | ❌ defer（無 payment 基建硬建低價值） |
| 品牌/SKU/供應商/BOM（sheet 15-22） | 結構草稿 | ❌ defer（無即時 consumer，另 CR） |

## 3. Affected API

| API | Endpoint | Action |
|---|---|---|
| 拆帳規則列表 | `GET /tenants/{tid}/payout-rules`（base_payout RBAC 遮蔽）| New（掛 catalog_v2，M12 tag）|

## 4. Affected Data

| Entity | Action |
|---|---|
| `technician_payout_rule`（新表，migration 045）| rule_id / service_code / service_name / level_id(LV-A/B/C) / base_payout（內部成本）/ night·urgent_surcharge_pct / currency / effective·expiry_date / decision_status / is_mock / tenant_id；69 筆 seed（ON CONFLICT 冪等）|

> **不接**：`reconciliation.technician_payout` 重算（目前硬編 80%）→ Phase II（需 work_orders 夜間/急件旗標 + Q-09）。

## 5. Affected Test

seed 69 筆可讀；get_rule(service×level) 取值；compute_payout 純計算（夜間/急件疊乘）；API RBAC（base_payout 僅後台）。

## 6. Affected Architecture

| Concern | Notes |
|---|---|
| 新 ADR？ | 否（複用 CR-0034 catalog 模式 + RBAC）；reconciliation 重算改查表時再評估是否 supersede ADR-0041 |
| 複用 | CR-0034 catalog RBAC（include_cost）、catalog_v2 router |

## 7. Human Decisions Required（§8）

| # | Question | mock（sheet 21）| Status |
|---|---|---|---|
| 1 | 拆帳基礎值（Q-09 師傅分潤）| 69 筆草稿（A/B=draft、C 需覆核）| open |
| 2 | reconciliation 重算是否改用此表（取代 ADR-0041 硬編 80%）| 暫不接（Phase II）| open |
| 3 | 夜間/急件旗標來源（work_orders 加欄）| 暫無（重算前需）| open |

## 8. Suggested Implementation Order

1. migration 045：technician_payout_rule + 69 seed（人工轉寫自 sheet 21）
2. payout_rule_service：list_rules（RBAC）/ get_rule / compute_payout（純）
3. API：GET /payout-rules（catalog_v2）
4. Tests / 三同步 / registry

## 9. Risks & Rollback

| Risk | Mitigation |
|---|---|
| 草稿值當正式 | is_mock + decision_status；正式待 Q-09 |
| 拆帳成本外洩 | base_payout RBAC 遮蔽（include_cost，同 catalog unit_price）|

**Rollback**：新表可逆；無既有邏輯被改（reconciliation 未接）。

## 10. Out of Scope

reconciliation 拆帳重算、AR/AP/Brand/佣金引擎、品牌/SKU/BOM 主檔、加價套用引擎、客戶報價文字、稅務 → follow-up / Phase II（見 §2 分流）。

## 11. 實作進度

- ✅ **實作（`feat/cr-0037-payout-rules`）**：migration `045`（technician_payout_rule + 69 筆 mock seed，python 轉寫自 sheet 21）+ `payout_rule_service`（list_rules RBAC / get_rule / compute_payout 純）+ `GET /tenants/{tid}/payout-rules`（catalog_v2，base_payout RBAC 遮蔽）。
- ⏳ **待 migration 045 套 dev DB**：`test_cr_0037_payout_rules.py`（seed 69 / get_rule / RBAC）；純計算測試已 pass。
- ✅ **對抗式審查（安全/正確/治理 3 lens，治理 clean）後修正**：
  - **tenant 隔離**（CRITICAL/HIGH，多 lens）：`list_rules`/`get_rule` 加 `tenant_id` 參數 + `(tenant_id IS NULL OR tenant_id=%s)` 過濾（仿 CR-0034），router 傳 tenantId。seed 全 NULL = **全域共享主檔**（單租戶；未來租戶自訂插非 NULL）。
  - **get_rule base_payout 外洩**（HIGH）：加 `include_cost`（預設 False），僅 True 才回 base_payout/base_payout_raw（Phase II recalc 內部帶 True）。
  - 靜態 WHERE 參數化（解 SQL-injection 樣式）+ 排序/轉寫/tenant 語意 docstring·COMMENT。
- **已知（不在本 CR 改）**：`_COST_VISIBLE_ROLES` 散在 catalog_v2/quote_v2（同值），中央化 refactor 另案。
- 分支：`feat/cr-0037-payout-rules`
