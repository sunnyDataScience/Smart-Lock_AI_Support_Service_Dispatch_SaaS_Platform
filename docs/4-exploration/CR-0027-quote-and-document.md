---
id: CR-0027
title: "Change Impact Analysis — 報價成本明細 + 客戶版電子工單"
status: built
tier: 4-exploration
owner: HYBRID
created: 2026-06-18
target-release: TBD（Lite 版 / Beta 前）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0027: 報價成本明細 + 客戶版電子工單

> **Tier**: 4-exploration → CIA（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 Domain model / DB schema / API contract）
> **驅動來源**: 2026-06-17 會議「報價成本明細沒做」+ 決議 4（後台看成本、客戶看電子工單只露最終價、含關防）+ 決議 5（報價 mock 打 8 成）+ §4.1（電子化 PDF 回 LINE）
> **依賴**: CR-0026（`work_orders.customer_final_amount` / service_category）+ CR-0028（outbox 推送）
> **來源素材（不可信，僅引語意、數值當 mock）**: esales 報價 xlsx + 派工單 PDF（計費核銷模組）

---

## 1. Change Statement

**As-is**：報價只有 `work_orders.estimated_price/final_price` 兩個裸 FLOAT + `invoices.line_items`(JSONB 無結構)，無法做欄位級成本遮蔽、無結構化拆項、無客戶電子工單。

**To-be**：(a) `quote_line_items` 表記錄成本拆項（`unit_price` 內部成本**僅後台可讀**、`customer_price` 對外）；(b) 對外總額落 `work_orders.customer_final_amount`；(c) 客戶版電子工單 PDF（只露 customer_price/最終價 + 關防，**結構上不含 unit_price**）；(d) 完工推 LINE 通知客戶（決議 4/§4.1）。**數值一律 `is_mock=true` 待財務覆核（決議 5）。**

**Driver**：會議「報價成本明細沒做、成本架資料庫沒建」。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF`（報價成本） | New | 後台建成本拆項 → 重算對外總額 |
| `BF`（完工出單） | Modified | 完工 → 開立電子工單 + 推 LINE 通知最終金額 |
| `UF`（後台成本面板） | New | 詳情側邊欄成本明細（含 unit_price，RBAC） |

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `NFR`（安全/RBAC） | New | unit_price server 端遮蔽（非僅前端隱藏）；客戶版 PDF 結構不接觸成本欄 |

## 4. Affected API

| API | Endpoint | Action | Breaking? |
|---|---|---|---|
| `listQuoteItemsV2` | `GET .../work-orders/{id}/quote-items` | New | No（unit_price 依角色遮蔽）|
| `addQuoteItemV2` | `POST .../work-orders/{id}/quote-items` | New | No（後台管理角色）|
| `getWorkOrderDocumentV2` | `GET .../work-orders/{id}/document` | New | No（回 application/pdf）|

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `quote_line_items`（新表） | New | migration 037：work_order_id FK / tenant_id（預留）/ item_name / category(labor/material/other) / **unit_price（後台）** / quantity / **customer_price（對外）** / is_mock(預設 TRUE) + 2 index |
| `work_orders.customer_final_amount` | Reuse | CR-0026 已建；本 CR 每次拆項異動重算 = Σ(customer_price × quantity) |

## 6. Affected Test

`test_cr_0027_quote_document.py`：add_line_item 重算總額；list include_cost True/False（RBAC 遮蔽 unit_price）；render_document 回 %PDF + customer view 結構不含 unit_price；cross-tenant 404。`test_cr_0028_wo_push.py`：work_order_document builder 只露最終價。

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| 成本遮蔽 | RBAC | `_COST_VISIBLE_ROLES={admin,operations_manager,tenant_admin}`；`work_order_document_service` 只 SELECT customer-facing 欄、結構隔離 unit_price |
| PDF 產生 | 複用 | `report_export_service` reportlab + STSong-Light CID 中文字型；關防 placeholder（env `WORK_ORDER_SEAL_IMAGE`）|
| 完工推送 | 複用 | CR-0028 outbox + 新 `work_order_document` push_kind |
| 新 ADR？ | 建議 | 報價快照不可變 / 稅務含未稅 / 訂金規則（Phase II）—— 本輪未立，列 follow-up |

## 8. Human Decisions Required

✅ **會議授權用預設先做（決議 4/5）。** 本輪採用：成本僅後台（admin/ops_manager/tenant_admin）；客戶版只露最終價；數值 `is_mock=true` 待財務覆核；關防用可配置 placeholder（待業主提供章圖）。

| # | Question | Status | Decision（預設）|
|---|---|---|---|
| 1 | 客戶版列品項 vs 只露總價 | ✅ 預設 | PDF 列品項但**只露 customer_price**、總額；絕不含 unit_price |
| 2 | 關防/章圖來源 | ⏳ | 先 placeholder（env 可配）；待業主提供章圖 |
| 3 | 成本可見角色（八角色 vs 五角色） | ✅ 預設 | 沿用五角色；成本僅 admin/ops_manager/tenant_admin；八角色另案 |
| 4 | mock 數值 seed 來源 | ✅ 預設 | app seed、`is_mock=true`；**不抄 esales xlsx 原值**（sourcing rule）|

## 9. Suggested Implementation Order（已實作）

1. ✅ Schema → migration 037 `quote_line_items`
2. ✅ Service → `quote_service`（CRUD + RBAC 遮蔽 + 重算）+ `work_order_document_service`（PDF，結構隔離成本）
3. ✅ API → quote-items GET/POST（RBAC）+ document GET（PDF）
4. ✅ 完工推送 → `complete_order` enqueue `work_order_document` + builder
5. ✅ Tests → `test_cr_0027_quote_document.py`（3）+ builder（2）
6. ✅ UI → 後台詳情成本明細面板（unit_price RBAC）+ i18n
7. ⏳ Docs sync → CHANGELOG / system-completion-status（commit 時）

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 成本外洩客戶端 | Low | High | server 端 RBAC（非僅前端）；document_service 只 SELECT customer 欄、結構隔離；測試斷言客戶 view 無 unit_price |
| 來源汙染（抄 xlsx 數值）| Medium | High | app seed、`is_mock=true`、待財務覆核；migration 註解標來源不貼值 |
| mock 當正式價 | Medium | High | `is_mock` 欄 + UI「預估值待覆核」badge |

**Rollback plan**：新表 + 新端點，移除即回原狀；work_orders 不破壞。

## 11. Out of Scope（follow-up）

- ✅ ~~客戶端 track 頁 PDF 下載~~ —— **已於 `feat/cr-0027-document-followup` 補完**（public `getConsumerWorkOrderDocumentV2` token 端點 + track 頁完工後下載連結）。
- ✅ ~~後台 PDF 下載按鈕~~ —— **已補完**（側邊欄成本面板「下載電子工單 PDF」，走 `api.download` authed）。
- service_catalog / material_catalog / 完整報價引擎、Phase II 財務結算（esales sheet 24-33）。
- 報價快照不可變 ADR / 稅務含未稅 / 訂金規則。

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主）| Sunny | 2026-06-17 | ✅ 會議授權用預設先做 |

## 13. 實作進度

- ✅ migration 037 + quote_service + work_order_document_service + 3 端點 + 完工推送 + 後台成本面板
- ✅ **follow-up 補完（`feat/cr-0027-document-followup`）**：public `getConsumerWorkOrderDocumentV2` token 端點 + track 頁完工後 PDF 下載連結 + 後台側邊欄「下載電子工單 PDF」按鈕
- ✅ `test_cr_0027_quote_document.py` 4 pass（含 consumer doc 端點）+ builder 2 pass + tsc 0 error + 套 migration 037 至 dev DB 驗證
- ⏳ 仍 follow-up：報價引擎完整版 / service_catalog / Phase II 財務結算
- 分支：`feat/cr-0027-quote-and-document` → `feat/cr-0027-document-followup`（接 CR-0026 之後）
