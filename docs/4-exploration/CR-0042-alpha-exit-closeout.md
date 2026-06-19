---
title: CR-0042 Alpha Exit 收尾 — ProblemCard completeness gate（#1）+ 客戶 phone 去重（#6）
status: implemented
tier: 4-exploration
created: 2026-06-19
owner-decision: ✅ 2026-06-19 業主裁決 0.8 門檻 + 硬擋 + 主管 override（見 §8 / §10）
related: 階段2 test-plan §5 Alpha Exit 阻塞 #1/#6 / BR-M03 completeness / BR-M02-01 去重 / Q015
---

> 🛑 CIA，停 §8 等裁決後實作。階段2 測試計畫 §5 列的 **Alpha Exit 阻塞** 中零/低依賴兩項。

## 1. 動機
- **#1 completeness gate（Alpha 唯一硬阻塞）**：spec 要 ProblemCard 完整度達標才可轉 WO（test-plan §46 ≥0.85）；現況 `problem_card_service` `confidence_score` 永遠 None、convert-to-WO 無完整度 gate（只有 CR-0026 派工前必填欄 gate 在 WO 建立後）。
- **#6 phone 去重（P0 誤建風險）**：`customer_service.create_customer` 只查 line_user_id，phone 不去重 → 同人不同來源誤建雙主檔。

## 2. 觸發面向
API contract（convert 新增 422 / create_customer 新增 422）、Business rule（完整度門檻、去重鍵）、Test plan。無新表（completeness 即時算；phone 用既有欄）。

## 3. 現況（grounded）
- `problem_card_service.py:88` `confidence_score: None`；`problem_cards_v2.py:321` convert 直接呼 `create_from_problem_card`，無完整度檢查。PC 欄位：brand/model/symptom/urgency（建時必填）+ door_status/network_status/symptoms（選）+ address（convert 時帶）。
- `customer_service.py:313 create_customer` 只預查 line_user_id（無 phone）。

## 4. 契約變更
- `POST .../problem-cards/{id}/convert-to-work-order`：completeness < 門檻 → **422 `INCOMPLETE_PROBLEM_CARD`**（附缺漏欄位）。
- `POST .../customers`：phone 已存在 → **422 `DUPLICATE_CUSTOMER`**（同 line_user_id 既有行為一致）。

## 5. 設計
- **completeness_score** = 已填 key 欄 / key 欄總數。key 欄（建議）：brand, model, symptom, urgency, customer_address（convert 時）。門檻入 M18 config（仿 CR-0036/0039 不寫死）`problemcard_policy.min_completeness`。
- **phone 去重**：create_customer 加 phone 預查（normalize 後比對），重複 422。

## 6. 測試
`test_cr_0042_alpha_closeout.py`：completeness 足/不足→201/422 + 缺漏欄位；門檻 config fallback；phone 重複→422、不同 phone→201；line_user_id 既有路徑回歸。

## 7. 風險
- 門檻過嚴 → 卡住正常轉單（緩解：config 可調 + 主管 override）。
- phone normalize（空白/+886）→ 用簡單 strip + 去非數字 MVP。

---

## 8. 🛑 Human Decisions Required（僅 completeness）

| # | 決策 | 建議預設 | 業主裁決（2026-06-19）|
|:-:|---|---|---|
| **HD-1** | completeness 門檻 + 計分欄 | min_completeness=0.8（5 欄）| ✅ **0.8**（入 M18 config problemcard_policy）|
| **HD-2** | 不足時行為 | 硬擋 422 + 主管 override | ✅ **硬擋 422 + admin/ops override（帶 reason）**|

> phone 去重（#6）依 spec BR-M02-01 直接做（duplicate key=phone+LINE ID），無需裁決。

## 9. 實作順序（裁決後）
1. migration 051：M18 config `problemcard_policy`（min_completeness）seed。
2. `problem_card_service`：`compute_completeness(pc_row, address)` + convert 前 gate（讀 config + override）。
3. `customer_service.create_customer`：phone 預查去重。
4. `test_cr_0042` + 重跑 Alpha（component + unit）確認綠。

---

## 10. 進度

✅ **done（2026-06-19，branch `feat/cr-0042-alpha-exit-closeout`）**：
- **migration 051**：M18 config `problemcard_policy`（min_completeness=0.8 / key_fields 5 欄）。
- **`problem_card_service.assert_completeness`**：算完整度（已填 key 欄/總數）+ 讀 config 門檻 + 主管 override（admin/ops 帶 reason）；<門檻 → 422 `INCOMPLETE_PROBLEM_CARD`（附缺漏欄位）。
- **convert-to-WO v2 router**：轉單前呼 gate + `override_reason` query param。
- **`customer_service.create_customer`**：phone 去重（同租戶同電話 → 422 `DUPLICATE_CUSTOMER`，BR-M02-01）。
- **測試** `test_cr_0042` **6/6**（完整度 足/缺2擋/admin override/technician override無效 + phone 重複422/不同phone放行）+ 回歸 convert/PC/customer 37 + 全 Alpha **226 unit + 552 component 0 fail**。

⏳ **未做（誠實分流，非 Alpha 硬阻塞）**：#7 師傅 onboarding 寫 user_id（需接 CR-0029 註冊流程建 user → 寫 technician.user_id；中等改動，FR-0044 真表測試前置）；#8 對話可見性分流（M16，較大設計，先 CIA）；completeness 前端提示（後端已擋，前端顯缺漏欄位屬 polish）。
