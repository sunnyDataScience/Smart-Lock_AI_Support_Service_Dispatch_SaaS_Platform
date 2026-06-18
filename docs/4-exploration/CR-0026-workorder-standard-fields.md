---
id: CR-0026
title: "Change Impact Analysis — 公單（WorkOrder）標準化欄位補洞"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-18
target-release: TBD（Lite 版 / Beta 前）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0026: 公單（WorkOrder）標準化欄位補洞

> **Tier**: 4-exploration → Change Impact Analysis（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 Domain model / DB schema / API contract 多面向）
> **Generated**: 手動（`sunnydata-change-impact-analysis` skill 未註冊，依 `VibeCoding_Workflow_Templates/4-exploration/CIA-0000` 模板產出，比照 CR-0025）
> **驅動來源**: 2026-06-17 lock-AI 會議 Action #1（補公單欄位）+ §十決議 3/4
> **來源素材（不可信，僅引 anchor 不抄內容）**: `docs/_source/01-workorder-erp.md`（#m03 / #m05 / #m08 + Q015-Q025）、`20260617資料/電子鎖安裝與維修派工單整合分析報告.pdf`（6 模組欄位標準化）、`20260617資料/AI_Blue_鎖匠ERP_報價資料庫_PhaseI_MarketLaunchCore_v1.xlsx`（成本資料模型，數值僅作 mock）

---

## 1. Change Statement

**As-is**：`work_orders` 表（`SQL/Schema.sql`）是**扁平最小結構**：只有 `customer_name/phone/address`、`service_report`、`photos`(JSONB)、`estimated_price/final_price`(兩個 FLOAT)、粗顆粒 `status`（created/assigned/accepted/in_progress/completed/confirmed/cancelled）。**缺**：設備辨識（品牌/型號/序號/門型/門厚）、服務類別（安裝/保內/保外/維修）、保固欄位、完工細狀態、狀態原因（status_reason）、返修連回原單（parent）、免責同意條款、雙方簽名、結構化成本拆項。

**To-be**：公單（WorkOrder）欄位標準化，對齊藍圖 M05/M08 與派工單分析報告 6 模組 —— 補上**設備辨識、服務類別、保固、完工細狀態機、狀態原因、返修 parent、免責簽名、雙簽名**；並確立「**客戶端電子工單只露最終價、成本明細僅後台**」的呈現邊界。結構化成本拆項（quote 模組）切到 **CR-0027** 另案處理，本 CR 只在 `work_orders` 保留 `customer_final_amount` 單一對外金額欄位。

**Driver**：會議當場點 UI 發現「公單畫面欄位有缺、Johnson 紙本工單對不上、報價成本明細沒做」；§十決議 3「公單欄位以 esales PDF 為對照、schema 先補前端才有資料」、決議 4「客戶端 LINE 只看最終電子工單（含關防、最終價），成本明細只在後台」。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF`（WorkOrder lifecycle，對 M05） | Modified | 公單生命週期補完工細狀態（待完工回報/待照片/待客戶確認/待客服審核/已完工/已結案）與狀態原因 gate |
| `UF`（後台公單畫面） | Modified | 公單編輯/檢視頁顯示新欄位（設備辨識/服務類別/保固/成本後台/簽名） |
| `UF`（客戶端電子工單） | New | 結案產出電子工單（含關防、品項、**只露最終價**）→ 對接 CR-0028 推 LINE/Email |
| `SF`（reopen/返修連回原單，對 BR-M05-02） | New | 返修必須連回原 WorkOrder、不覆蓋歷史 |

> 註：User Flow 正典 `docs/ux/user-flow-smart-lock-saas.md`（`status: draft`）目前無公單欄位層級 flow，需補。

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| 新 `FR`（ID 待配） | New | 公單必填/可後補/派工前必填三級欄位規則（對 M03 Q015）|
| 新 `FR`（ID 待配） | New | 完工包必備：photos + materials used + payment status + customer sign-off + teaching note（對 M08 BR-M08-03）|
| 新 `FR`（ID 待配） | New | 序號綁保固、保固期動態判定（輸序號自動帶保固截止 → 判保內/保外）|
| `NFR`（合規） | New | 免責條款（新機安裝同意/破壞鎖免責/個資）固定條款 + 客戶簽名留痕 |

> 註：現 codebase 無公單 FR 殼（work_order 直接實作於 `work_order_service.py`）。需補 FR 正典；本 CR 先列規則來源 anchor。

## 4. Affected API

| API | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| work-order create/update | `POST/PATCH .../work-orders` | Schema change | No（加欄位向後相容）| 新增設備/服務類別/保固/簽名欄位；舊 client 忽略多餘欄位 |
| work-order get/list | `GET .../work-orders/{id}` | Response change | No | 回傳新欄位；**成本明細欄位僅後台角色可見**（RBAC 過濾）|
| 電子工單產出 | `GET .../work-orders/{id}/document`（新，建議）| New | No | 產生客戶版電子工單（只露最終價）；實際推送走 CR-0028 |

需同步更新 `openapi-smart-lock-saas.yaml`（新增欄位 + 可能新 document endpoint）。

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `work_orders` | 加欄位 | 設備辨識：`brand` / `model` / `serial_number` / `door_type` / `door_thickness` / `is_interior_door`；服務類別：`service_category`(安裝/保內/保外/維修) / `problem_type`；保固：`warranty_status` / `purchase_date` / `invoice_no`；完工細狀態：`completion_status`（細分，補在粗 `status` 之下）；`status_reason`（cancel/reopen/reschedule/refund/dispute 必填，BR-M05-01）；`parent_work_order_id`(self-FK，返修連回，BR-M05-02)；`customer_final_amount`（對外單一金額）；**全表加 `tenant_id` 預設單租戶值**（multi-tenant 可逆準備）|
| `work_order_signatures`（新子表，建議） | New | `work_order_id` FK / `signer_type`(technician/customer) / `signature_ref` / `signed_at` —— 雙方簽認（PDF 模組 6）|
| `work_order_consents`（新子表，建議） | New | `work_order_id` FK / `consent_type`(新機安裝/破壞鎖免責/個資) / `accepted` / `accepted_at` —— 免責合規（PDF 模組 4）|
| `problem_cards` | 可能加欄位 | 三級必填分類落地（必填/可後補/派工前必填）—— 視 §8-Q3 裁決是否併入本 CR |
| 結構化成本拆項 | **不在本 CR** | `service_catalog`/`material_catalog`/`quote`/`quote_line_item` → **CR-0027**；本 CR `work_orders` 只留 `customer_final_amount` |

State machine impact：`work_orders` 完工段細狀態機（待完工回報→待照片→待客戶確認→待客服審核→已完工→已結案，對 M05 Q052）；返修經 `parent_work_order_id` 連回不覆蓋歷史。

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC`（新） | New | 公單建立帶完整設備/服務類別/保固欄位 → 正確儲存 |
| `TC`（新） | New | 三級必填驗證：缺「派工前必填」欄位 → 不可進 dispatch（對 BR-M05-03）|
| `TC`（新） | New | cancel/reopen/reschedule 未填 status_reason → 拒絕（BR-M05-01）|
| `TC`（新） | New | 返修建立 → `parent_work_order_id` 連回原單、原單歷史不變（BR-M05-02）|
| `TC`（新） | New | 序號 → 自動帶保固截止 → 判保內/保外 |
| `TC`（新） | New | RBAC：客戶版電子工單**不含**成本明細、只露 `customer_final_amount`；後台角色可見成本 |
| `TC`（新 E2E） | New | 後台填公單新欄位 → 客戶端電子工單顯示正確（Playwright）|

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module 邊界 | 釐清 | 公單（work_order 執行/完工文件）vs 報價成本（quote 模組）邊界：成本明細**不進 work_orders**，留 CR-0027 quote 模組；work_order 只持對外最終價 |
| 新 ADR？ | **Yes** | `ADR-NNNN`：(a) 成本明細與公單的邊界（客戶端只露最終價）；(b) 電子工單 PDF 產出與關防；(c) 序號綁保固動態判定 |
| External integration | 關聯 | 電子工單推 LINE/Email 屬 **CR-0028**（公單派出→回傳鏈路），本 CR 只產文件不負責推送 |
| Multi-tenant | 可逆準備 | 新欄位/子表一律帶 `tenant_id` 預設單租戶值，不寫死省略（為 CR-0031 預留）|
| 既有資產對齊 | 檢查 | `price_rules`(Schema.sql:493) 粗顆粒、`invoices.line_items`(JSONB) 與 esales 結構化模型不同 → CR-0027 處理，本 CR 不動 |

## 8. Human Decisions Required

✅ **以 2026-06-17 會議為主文件授權「用藍圖/PDF 語意當合理預設先做」（業主 Sunny 同意，日後可微調）。** 各項採用預設如下，code 標「預設值待業主確認」。

| # | Question | Owner | Status | Decision（預設，2026-06-18）|
|---|---|---|---|---|
| 1 | **成本明細邊界** | 業主/架構 | ✅ 預設 | **(a) 分兩 CR** —— 本 CR 只留 `customer_final_amount`，結構化拆項切 CR-0027 |
| 2 | **三級必填落地** | 業主 | ✅ 預設 | 派工前必填=品牌/型號/地址/問題類型（dispatch gate 已實作）；problem_cards 三級分類另案 |
| 3 | **免責條款內容** | 業主/法務 | ✅ 預設 | **(a) 先佔位** —— `work_order_consents` 暫不建、客戶版不出免責段（法務文字 follow-up，移 CR-0027 電子工單一併處理）|
| 4 | **客戶端電子工單呈現** | 業主 | ⏳ 留 CR-0027 | 屬 CR-0027 範圍（本 CR 只補欄位）|
| 5 | **完工細狀態機** | 業主/派工 | ✅ 預設 | **(a) 全做** —— M05 Q052 六段（app 層驗證 enum）|
| 6 | **報價數字來源** | 業主 | ✅ 預設 | **(a) mock seed、標待財務覆核**（CR-0027 落地）|
| 7 | **序號綁保固** | 業主 | ✅ 預設 | **(a) 本輪人工填 `warranty_status`**；序號自動判定規則另案 |

## 9. Suggested Implementation Order

§8 裁決後，依相依順序：

1. **Decisions** → 寫 `ADR-NNNN`（成本邊界 + 電子工單 + 序號綁保固）
2. **Schema** → migration：`work_orders` 加欄位 + `work_order_signatures` / `work_order_consents` 子表（+ tenant_id 預設值）
3. **Domain/Service** → `work_order_service` 補欄位驗證（三級必填、status_reason gate、返修 parent）
4. **API** → openapi 加欄位 + RBAC 過濾（成本欄位僅後台）+ 電子工單 document endpoint
5. **Tests** → 補 §6 TC（含三級必填、status_reason、RBAC 成本遮蔽；用 TDD）
6. **UI** → 後台公單畫面顯示新欄位 + 客戶版電子工單（只露最終價）
7. **Traceability** → 更新 traceability matrix（新 FR/API/TC）
8. **Docs sync** → 更新 user-flow + `system-completion-status` + CHANGELOG + 本 CR §13 進度

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 來源汙染：直接抄 PDF/xlsx 欄位/數字進 schema | Medium | High | 一律經 `docs/_source` anchor + 人工轉寫；數值標 mock 待覆核 |
| 與 CR-0020（編號）、CR-0022（LINE 轉換）schema 衝突 | Medium | Medium | migration 前先 grep 既有 work_orders 變更、協調欄位 |
| 成本明細誤入 work_orders → 客戶端外洩 | Low | High | 成本拆項切 CR-0027 quote 模組；work_order 僅 final price + RBAC 過濾 |
| 免責條款無法務背書即上線 | Medium | High | §8-Q3 裁決；先佔位不出客戶版 |
| 報價 mock 當正式價 | Medium | High | seed 標 mock、待財務覆核（會議共識）|

**Rollback plan**：新增欄位皆 nullable / 子表為新增（不動既有），可逆；客戶版電子工單掛 feature flag。

## 11. Out of Scope

- **結構化報價/成本資料模型**（service_catalog/material_catalog/quote/quote_line_item）→ **CR-0027**
- **LINE 公單派出→派工→報價回傳鏈路** → **CR-0028**
- **廠商/師傅註冊**、**派工模式切換**、**multi-tenant 三類租戶** → CR-0029 / CR-0030 / CR-0031
- Phase II 財務結算（訂金/AR/AP/月結，esales sheet 24-33）

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主）| Sunny | 2026-06-17 | ✅ 會議授權用預設先做 |
| Architect | | | |
| Engineering Lead | | | |
| QA Lead | | | |

## 13. 實作進度

- ✅ S2 Schema → migration `036-workorder-standard-fields.sql`（work_orders 16 欄 + scope_changes.tenant_id + backfill 84 列 + 3 index；Schema.sql 同步）
- ✅ S3 Domain/Service → `create_from_problem_card` 複製 brand/model/problem_type/photos + tenant_id；`assign_order` dispatch gate（BR-M05-03 `_assert_dispatch_ready`）；`cancel_order` status_reason 必填 gate（BR-M05-01）+ 寫結構化欄
- ✅ S4 API → `WorkOrder` pydantic model + TS 型別 + `_WO_SELECT`/`_wo_row_to_dict` 補 13 新欄（response 自動帶出）
- ✅ S5 Tests → `test_cr_0026_wo_fields.py` 4 pass（serializer 映射 ×3 + dispatch gate）；work_order 相關回歸 55 pass
- ✅ S6 UI → 後台詳情側邊欄「公單資訊」面板（服務類別/問題類型/保固/門型/完工狀態/狀態原因）+ 綁真實 S/N；tsc 0 error；i18n zh-TW/en
- ⏳ S1 ADR / S7 traceability matrix → 待補（後續）
- ⏳ 客戶端電子工單 + 結構化成本 → CR-0027（Phase 3）
- **採用預設**（§8）：免責先佔位、完工六段、保固人工填、成本切 CR-0027 —— 標「預設待業主確認」
