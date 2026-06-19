---
id: CR-0043
title: "Change Impact Analysis — 公單欄位補完 Phase 2（對齊 20260617 派工單規格剩餘缺口）"
status: implemented
tier: 4-exploration
owner: HYBRID
created: 2026-06-19
target-release: Beta 前
supersedes: null
superseded-by: null
related: CR-0026（Phase 1 欄位骨架）/ CR-0033（免責同意）/ CR-0039（完工硬閘）/ wo-fields-vs-20260617 對抗式查證
---

# CR-0043: 公單欄位補完 Phase 2

> **Mandated by**: `.claude/rules/change-governance.md`（命中 API contract / Domain model / DB schema / Business rule / Test plan 多面向）
> **驅動來源**: 2026-06-19 對抗式 12-agent 逐欄查證（`20260617資料/電子鎖安裝與維修派工單整合分析報告.pdf` §三 6 模組 24 欄）—— CR-0026 補了 DB 骨架但 24 欄+3 優化僅 **7 符合 / 17 部分 / 3 缺**；本 CR 收口高 ROI 部分。
> **授權**: 沿用 CR-0026 §8「2026-06-17 會議授權用藍圖/PDF 語意當合理預設先做（業主 Sunny 同意，日後可微調）」+ 業主 2026-06-19「一起做」。

---

## 1. Change Statement

**As-is（對抗查證後真實態）**：
- **M1 客名/電話讀不出**：`work_orders.customer_name/customer_phone` 有寫入，但 `_WO_SELECT` 不撈、`WorkOrder` model 無欄、前端不顯示 → 工單詳情頁看不到客戶姓名電話。
- **service_category 死欄**：`create_from_problem_card` 把 `pc.category` 寫進 `problem_type`，`service_category` 永遠 NULL。
- **completion_status / parent_work_order_id 空殼**：CR-0026 建欄但全 codebase 零寫入；六段完工細狀態、返修連回未接線。
- **M5 計費**：除零件明細外，出勤費/夜間加成（`surcharge_rule` 表）0 處接進計算；安裝/破壞/拆除費無結構化費目；付款方式工單層無欄。
- **三段免責未綁完工 gate**：未同意仍可完工；「簽名」為 boolean 勾選。
- **全缺**：購買地點/經銷商、特殊門型加價確認、安裝環境遮雨三段。

**To-be（本 CR 四階）**：
1. **Tier ①（讀寫接線，無 schema）**：`customer_name/customer_phone` 接回 API+model+UI；修 `create_from_problem_card` 寫 `service_category`（pc.category → enum 映射）；新增 WO 欄位 `PATCH` 端點（補「寫入路徑稀薄」缺口，讓 service_category/serial/door/warranty 可被後台設定）。
2. **Tier ②（domain 寫入）**：完工流程逐步寫 `completion_status`（六段）；reopen 建子單寫 `parent_work_order_id`（BR-M05-02）。
3. **Tier ③（schema + 欄位，migration 052）**：補 `payment_method / dealer / install_date / rain_exposure / special_door_surcharge`；`quote_line_items` 費目語意擴充（dispatch/destruction/removal service code seed）；出勤費/夜間加成由 `surcharge_rule`+M18 config 驅動計入 quote total（**不寫死費率**）。
4. **Tier ④（合規 gate）**：完工硬閘加查三段 `work_order_consents`（M18 config `completion_policy.require_consents` 控）。

**邊界**：Phase II 完整財務結算（AR/AP/月結/退款 matrix）仍屬 P2 下輪；本 CR 只補**工單層欄位**與**出勤加成計入單筆 quote**，不建月結引擎。

## 2. Affected Flow / Spec

| Flow/Spec | Action | Description |
|---|---|---|
| BF WorkOrder lifecycle（M05 Q052） | Modified | 完工六段 `completion_status` 真實推進 |
| SF reopen/返修（BR-M05-02） | New | reopen 建子單連回 `parent_work_order_id` |
| BR-M09-XX 完工合規 | Modified | 完工 gate 加查三段免責（config 控） |
| FR 計費（M05） | Modified | 出勤費/夜間加成計入 quote（config 費率） |

## 3. Affected API

| Endpoint | Action | Breaking | Notes |
|---|---|---|---|
| `GET .../work-orders/{id}` | Response change | No | +customer_name/customer_phone/payment_method/dealer/install_date/rain_exposure |
| `PATCH .../work-orders/{id}/fields`（新） | New | No | 後台設 service_category/serial/door/warranty/payment 等欄位 |
| `POST .../work-orders/{id}/reopen`（新） | New | No | 建子單，parent 連回原單 |
| `POST .../work-orders/{id}/complete` | Behavior change | No | 加 consent gate（config 控，預設 off 避免回歸破壞）|

## 4. Affected Data（migration 052）

| Entity | Action |
|---|---|
| `work_orders` | +`payment_method`(cash/bank_transfer/credit_card/line_pay) / `dealer` / `install_date` / `rain_exposure`(indoor/outdoor_covered/outdoor_exposed) / `special_door_surcharge`(BOOLEAN) — 全 nullable 可逆 |
| `quote_line_items` | category 語意擴充：seed `service_catalog` 補 dispatch/destruction/removal SVC code（不改 schema，補 seed）|
| M18 config | `completion_policy.require_consents`（bool，預設 false）；`quote_policy.apply_surcharge`（bool，預設 false）+ 費率讀 `surcharge_rule` |

## 5. Affected Test

`test_cr_0043_wo_fields_phase2.py`：客名/電話 response 回傳；service_category create 寫入；PATCH 設欄位；completion_status 六段推進；reopen 建子單+parent；consent gate（config on/off）；payment_method/dealer/rain_exposure round-trip；surcharge config off 不影響既有總額。

## 6. Risks & Rollback

| Risk | Mitigation |
|---|---|
| consent gate 破壞既有完工回歸 | config `require_consents` 預設 **false**，明確開才擋 |
| surcharge 改動既有金額 | config `apply_surcharge` 預設 **false**，費率讀 `surcharge_rule` 不寫死 |
| PATCH 端點越權改欄 | RBAC：限 admin/ops；技師不可改 |
| 新欄位 NULL | 全 nullable、向後相容，舊 client 忽略 |

**Rollback**：新增欄位皆 nullable；新端點獨立；config 旗標可即時關閉。

## 7. Human Decisions（沿用會議授權，採 PDF 語意預設）

| # | 決策 | 預設（2026-06-19）|
|---|---|---|
| HD-1 | service_category 來源 | pc.category 映射（install/repair/warranty_in/warranty_out），無法判定 → `repair` 預設，可 PATCH 改 |
| HD-2 | consent gate 預設 | **off**（require_consents=false），避免回歸破壞；業主要強制再開 |
| HD-3 | surcharge 計算預設 | **off**（apply_surcharge=false），費率全讀 `surcharge_rule`（標 is_mock 待財務覆核）|
| HD-4 | reopen 子單 vs 改原單 | **建子單**（BR-M05-02 不覆蓋歷史）|
| HD-5 | M5 完整財務結算 | **不在本 CR**，P2 下輪 |

## 8. 實作順序

1. migration 052（5 欄 + config seed）
2. service：補 SELECT/model（客名電話+新欄）+ 修 service_category 寫入 + PATCH + reopen + completion_status 推進 + consent gate
3. router：PATCH/reopen 端點 + RBAC
4. 前端：sidebar 顯示客名電話/付款/門厚/遮雨 + 完工狀態
5. tests（TDD）+ 重跑回歸
6. docs sync（CHANGELOG / completion-status / 本檔進度）

## 9. 進度

✅ **done（2026-06-19，branch `feat/cr-0043-workorder-fields-phase2`）**：
- **Tier①**：`_WO_SELECT`/`_wo_row_to_dict` 接回 `customer_name`/`customer_phone`（index 28+，append-only）+ `WorkOrder` model + 前端 sidebar 顯示客名/電話/門厚/購買地點/安裝日期/遮雨/付款；修 `create_from_problem_card` 死欄 bug（加 `_map_service_category` 映射 enum，install/warranty_in/warranty_out/repair）；新增 `PATCH .../work-orders/{id}/fields`（`update_wo_fields` 白名單 18 欄 + enum 驗證，RBAC 限派工角色）。
- **Tier②**：`completion_status` 六段推進（accept→`pending_report`、complete→`pending_customer_confirm`、confirm→`closed`）；新增 `POST .../work-orders/{id}:reopen`（`reopen_order` 建子單複製設備/客戶欄 + `parent_work_order_id` 連回 + 發新公單號，BR-M05-02）。
- **Tier③**：**migration 052** `work_orders` +5 欄（dealer/install_date/rain_exposure/special_door_surcharge/payment_method）+ Schema.sql 同步 + `service_catalog` seed 3 計費費目；M18 config `quote_policy.apply_surcharge`（預設 false，費率讀 surcharge_rule 不寫死）。
- **Tier④**：`_enforce_completion_gate` 加查三段 `work_order_consents`（`_consents_satisfied`，config `completion_policy.require_consents` 控，預設 false 避免回歸破壞 → `CONSENTS_REQUIRED` 422）。
- **測試** `test_cr_0043` **17/17**（10 純函式映射/序列化 + 5 component：service_category 寫入、PATCH 設值/enum 驗證、reopen 子單連回、completion_status 推進、consent gate）+ 回歸 226 unit + 23 工單 component 檔全綠。migration 052 已套 dev + 記 schema_migrations。

⏳ **誠實分流（仍 P2 下輪，非工單欄位硬缺）**：
- M5 出勤費白天/夜間加成「自動計算」（surcharge_rule 接進 `quote_engine_service._recompute_total`）—— 屬完整財務結算，本 CR 只補欄位 + catalog 費目 + config 旗標（apply_surcharge 預設 off）。
- 簽名影像化（三段免責 boolean 勾選 → 真簽名影像寫 digital_signatures）。
- 保固序號動態回填（serial → 保固截止日 → 保內/外自動）—— warranty_service 引擎已存在但未接 work_order。
- 拍照存證前端上傳 UI（後端 photo_evidence gate 已在，前端 photos_before/after 仍寫死空陣列）。
- 結案 PDF Email 通道（目前只 LINE）。
</content>
</invoke>
