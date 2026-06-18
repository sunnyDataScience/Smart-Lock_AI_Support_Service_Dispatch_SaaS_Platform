---
id: CR-0034
title: "Change Impact Analysis — 報價基礎主檔（service/material/surcharge，esales mock seed）"
status: built
tier: 4-exploration
owner: HYBRID
created: 2026-06-18
target-release: TBD（補洞優先 S4）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0034: 報價基礎主檔（Phase A）

> **Tier**: 4-exploration → CIA（per-change）
> **Mandated by**: `.claude/rules/change-governance.md`（DB schema + Domain model）
> **驅動來源**: 20260617 gap-audit S4 + esales 報價資料庫（決議 5「報價數字當 mock 灌進系統」）
> **依賴**: CR-0027 quote_line_items（將參照本主檔）；CR-0032 報價引擎上游

---

## 1. Change Statement

**As-is**：報價基礎主檔（服務/材料/加價規則）在 code 完全缺；報價只能裸打數字。

**To-be**：`service_catalog`(29 服務) + `material_catalog`(20 材料) + `surcharge_rule`(12 規則) 三表，並依**決議 5** 把 esales xlsx 結構 + 草稿值灌為 **mock（is_mock=TRUE）**；內部成本 RBAC 遮蔽。正式價待業主回 esales Q-01~Q-12 後從 mock 轉正式。

**Driver**：報價引擎(CR-0032)/金流(CR-0035) 的上游主檔；會議「報價成本架資料庫沒建」。

## 2-7. 影響摘要

- **Data**：migration 040 三新表 + seed（ON CONFLICT idempotent）；tenant_id 預留。
- **API**：`GET /tenants/{tid}/quote-catalog`（service/material/surcharge；internal cost 依角色遮蔽 `_COST_VISIBLE_ROLES`）。
- **Domain**：service_type(inspection/emergency/replacement/repair)、material_class、surcharge rule_type（區域/急件/夜間/假日/取消費）。
- **不可信來源處置**：數值人工轉寫自 esales（非自動 copy），全 `is_mock=TRUE`、`decision_status` 保留原「待填價/待決策/已知規格」。區域+取消費=已知規格(ADR-0102)；急件/夜間/假日/S5=待決策(esales Q-03~Q-06)。
- **Test**：`test_cr_0034_quote_catalog.py` 2 案（seed 數量 + 全 mock + 取消費已知/急件待決策；internal cost RBAC 遮蔽）。

## 8. Human Decisions Required（mock→正式價時才需，不擋本 CR）

| # | esales Q | 待決策 | 狀態 |
|---|---|---|---|
| 1 | Q-01/02 | 服務/材料正式價（現為 mock 草稿）| open（mock 先上）|
| 2 | Q-03/04/05 | 急件/夜間/假日加價：固定額 vs 百分比 + 時段/適用日 | open |
| 3 | Q-06 | S5 取消費計算方式（現「50% from final quote」mock）| open |
| 4 | Q-09 | 師傅分潤拆帳（→ CR-0034 Phase B technician_payout_rule）| open |

> 本 CR Phase A 只建「服務/材料/加價規則」核心主檔 + mock；**Phase B**（brand/sku/supplier/BOM/technician_payout_rule/finance_config）另接。

## 9. 實作進度

- ✅ migration 040（service_catalog 29 / material_catalog 20 / surcharge_rule 12 + seed mock）；套 dev DB 驗證
- ✅ `quote_catalog_service`（list/get + internal cost RBAC 遮蔽）+ `catalog_v2` router（GET /quote-catalog）+ main.py 註冊
- ✅ `test_cr_0034_quote_catalog.py` 2 pass + py_compile
- ⏳ 前端報價主檔檢視頁（admin）— 下一步
- ⏳ Phase B：BOM / 拆帳 / 供應商 / finance_config；mock→正式價（待 esales Q-01~Q-12）
- 分支：`feat/cr-0034-quote-catalog`

## 10-11. Risks / Out of Scope

- 風險：mock 當正式價 → `is_mock` 欄 + decision_status 標記 + API note；UI 顯示「預估值待覆核」。
- Out of scope：CR-0032 報價引擎（quote 主表/核准/snapshot）；Phase B 主檔；金流（CR-0035）。

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主）| Sunny | 2026-06-17 | ✅ 決議 5 授權 mock seed |
