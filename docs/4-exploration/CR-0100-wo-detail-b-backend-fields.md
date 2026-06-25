---
title: "CR-0100 — 工單詳情頁 B 類後端欄位（SLA deadline + 完工摘要 + 功能測試）"
status: draft
tier: 4-exploration
created: 2026-06-25
owner: 啟恆 / Sunny 裁決
trigger: API contract（WorkOrder envelope 新欄位 + completion 端點）+ DB schema（migration）+ Domain model（SLA 政策、功能測試）
related:
  - docs/_audit/wo-detail-hardcoded-audit-20260625.md（盤點來源，B 類＝後端無欄位需新建）
  - branch fix/wo-detail-real-data（A 類純前端已完成）
---

# CR-0100 — 工單詳情頁 B 類後端欄位

> 🛑 **本 CR 為 draft，動 DB schema / API contract 前須業主裁決 §8。** A 類（純前端）已於 `fix/wo-detail-real-data` 完成；本 CR 處理盤點報告中「後端根本沒這資料」的 B 類三項。

## 1. 背景 / 問題

工單詳情頁寫死資料盤點（`wo-detail-hardcoded-audit-20260625.md`）將假資料分兩類：A（資料源已存在、純前端沒接，已修）、**B（後端無欄位，需新建）**。業主 2026-06-25 裁決：B 全做。B 三項：

- **B2 SLA 倒數**：工單無 SLA deadline 欄位/政策 → 倒數無從算（A 已移除假「剩餘 02:15」）。業主裁決：**標準四級**。
- **B0 乾淨完工摘要**：`service_report` 是稽核串（`[ONSITE_COMPLETE] sig=… photos=[…] notes=<技師字>`），技師摘要埋在裡面，envelope 未曝露。
- **B1 功能測試逐項結果**：後端完全無結構化欄位（A 已移除假「指紋✓密碼✓電池✗」）。業主裁決：**做**（技師端逐項勾 + 後端 + admin 顯示）。

## 2. Affected Flow

- **UF 技師完工流程**（`/my-orders/[id]` 完工表單）：新增「功能測試逐項勾選」區（B1）；既有 notes 落 `completion_summary`（B0）。
- **UF admin 工單檢視**（`/work-orders/[id]`）：SLA 時間軸顯示倒數/逾時（B2）、完工報告顯示真實摘要（B0）+ 功能測試結果（B1）。
- **SF 派工/排程**：SLA deadline 計算起點與既有時間欄位關聯（見 §8 決策 1）。

## 3. Affected Spec

- 新 NFR：SLA 時效政策（四級時數）— M18 config 化，不寫死。
- M08 完工：完工報告資料模型擴充（summary + function_tests）。

## 4. Affected API

| 端點 | 變更 |
|---|---|
| `GET /tenants/{tid}/work-orders/{id}`（WorkOrder envelope） | **新增欄位**：`sla_deadline`（ISO，computed）、`completion_summary`（string）、`function_tests`（array） |
| `POST /tenants/{tid}/work-orders/{id}/onsite/completion` | 請求 body **新增**：`function_tests?`（array of {key, result}）；既有 `notes` 同步落 `completion_summary` |
| M18 config | 新 namespace `sla_policy`（四級時數） |

> 皆為 **additive**（新增欄位、新增可選參數），不破壞既有 caller。

## 5. Affected Data（DB migration）

| 表 | 變更 |
|---|---|
| `work_orders` | `+ completion_summary text`（B0）、`+ function_tests jsonb`（B1，預設 `'[]'`） |
| config（M18） | `sla_policy` namespace：`{ hours_by_urgency: {...} }`（B2，不寫死，比照 `completion_policy`） |

- `sla_deadline` **不落 DB 欄**：以 `created_at + sla_policy[urgency]` 在 service 讀時 computed（免 migration backfill；政策可調隨即生效）。
- migration 編號接續最新（078 後 → **079**）。

## 6. Affected Test

- `test_sla_policy`：四級時數讀 config、deadline 計算、逾時判定。
- `test_completion_summary`：完工 notes 落 `completion_summary` + envelope 曝露。
- `test_function_tests`：completion 接收 function_tests array、落 jsonb、envelope 回傳、非法 result 值 422。
- 回歸：completion gate（CR-0039）不受 function_tests 影響（見 §8 決策 4）。

## 7. Affected Architecture

無新模組/邊界。SLA 政策沿用 M18 config 機制；function_tests/summary 落既有 work_orders 表。

## 8. 🛑 Human Decisions Required（待業主裁決）

| # | 決策 | 選項 / 建議 |
|---|---|---|
| **1** | **SLA 計時起點** | 建議 `created_at`（工單建立起算，最直覺）。替代：派工時間 / 排程時間。 |
| **2** | **四級 vs 三級對齊** ⚠️ | 系統 `urgency` 實際只有 **3 級（low / medium / high）**，與你說的「四級」不符。建議二選一：<br>(a) **三級對齊**：high=8h、medium=24h、low=48h，「緊急 4h」保留給未來 emergency 旗標；<br>(b) **沿用四級但補 emergency**：先加一個 emergency 級（high→8h、medium→24h、low→48h、emergency→4h），需技師/派工端能設 emergency。 |
| **3** | **功能測試項目清單** | 建議預設 6 項（可勾 pass / fail / N/A）：指紋、密碼、卡片(RFID)、App/藍牙、機械鑰匙、電池電壓。請增刪。 |
| **4** | **功能測試是否為完工硬閘** | 建議**否**（選填，不擋完工，避免又卡關）。與 CR-0039 三道硬閘（照片≥3 / 簽名 / serial）脫鉤。 |
| **5** | **completion_summary 來源** | 建議：completion 的 `notes` 直接落 `completion_summary`（乾淨），`service_report` 維持稽核串不變。確認即可。 |

## 9. Suggested Implementation Order（待 §8 後）

1. **migration 079**：work_orders + completion_summary + function_tests；config 種 `sla_policy`。
2. **後端 service**：`work_order_service` completion 寫 completion_summary + function_tests；envelope builder 加 sla_deadline（computed）/completion_summary/function_tests。
3. **API 契約**：completion 端點 body 加 function_tests（Literal 驗證）；OpenAPI/型別重生。
4. **後端測試**（TDD）：上述三組測試先紅後綠。
5. **技師端 UI**（`/my-orders/[id]`）：完工表單加功能測試勾選區，送 function_tests。
6. **admin 顯示**（`/work-orders/[id]`）：SlaTimeline 加倒數/逾時、CompletionReport 顯示 summary + function_tests。
7. **更新** traceability + CHANGELOG + 本 CR status→active。

## 10. Risks & Rollback

- 風險低：全 additive。sla_deadline computed → 政策錯只需改 config，不需 migration 回滾。
- function_tests jsonb 預設 `[]` → 既有工單不受影響。
- Rollback：migration 079 down（drop 兩欄）+ 還原 envelope builder。

## 11. Out of Scope

- **B3 設備面板 IoT 遙測（電量/連線/最近操作）**：需智慧鎖硬體整合，本 CR 不含（盤點報告已標「可暫緩」，畫面已誠實標「示意」）。
- 歷史工單 function_tests 回填（無歷史資料，預設空）。

## 12. Sign-off

- [ ] 業主裁決 §8 五項
- [ ] 依 §9 實作
- [ ] 測試 + 部署（api migration 079 + web）
