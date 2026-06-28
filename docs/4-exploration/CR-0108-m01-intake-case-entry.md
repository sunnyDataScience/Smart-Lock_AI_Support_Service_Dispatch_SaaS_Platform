---
id: CR-0108
title: M01 進線 Case 入口 — 全渠道 Case/Inquiry 實體 + 報價前建 Case gate + first-response SLA
status: in-progress
tier: 4-exploration
created: 2026-06-28
author: Claude (Opus 4.8) + 業主裁決
decision_status: ✅ §8 已裁決（2026-06-28，見 §8.1）
relates:
  - phase1-gap-backlog-20260628   # Phase I backlog 批次 1
  - owner-spec-compliance-and-pending-decisions-20260627  # §五/§十一 M01 缺口
  - CR-0102   # LINE 進線電話自動帶入（M01 customer contact 薄片，已做）
  - CR-0096   # 同客多問題分卡（problem_cards per-issue）
---

# CR-0108 — M01 進線 Case 入口（全渠道 Case/Inquiry 實體）

> 🛑 **本檔為 CIA，停在 §8 等業主裁決後才動 code**（change-governance hard gate：
> 命中 Domain model + DB schema + User flow + API contract 四面向）。

## 1. Change Statement

**動機**：M01「客戶入口與案件建立」是 Phase I 完成度最低的模組（現況驗證 12%、評 missing），
也是業主核心目標「**接單從客服一路串到工單**」的最前端斷點。現況進線只走 LINE → problem_card
→ work_order，**沒有一個跨渠道、可追蹤的「Case / Inquiry」承載實體**，導致：
- 電話 / Web Chat / 熟客介紹等非 LINE 渠道進線**無建案入口**（客服無法代客建案）。
- 無「報價前先建 Case」流程 gate（規格 Q170）。
- 無「首次回應 SLA」計時（規格 M01 交付物 first SLA clock）。
- 無進線來源歸因（規格 8 渠道；現況 channel 僅 line/web/api 3 值且綁在 conversations）。

**範圍**：新增 Case/Inquiry domain entity + 表 + 客服多渠道建案 API/UI + first-response SLA
計時骨架 + 「凡報價/派工/客訴 inquiry 先有 Case」串接。

**現況證據**（2026-06-27 對 dev_new_arch HEAD 實查）：
- 全 schema 無進線 Case 表（`case_entries` 是 KB 案例庫、`exception_case` 是 M15 異常，皆非進線 Case）。
- `conversations.channel` 僅 line/web/api 3 值、DEFAULT line；`work_orders` 無 channel/source 欄。
- `quote`/`work_order` service 無 case_id 前置；grep first_response/sla_clock 零命中（現有 sla_policy 是工單完工 SLA）。
- CR-0102 已補 LINE 進線電話 → users.phone（M01 customer contact 之電話面向，唯一已落地薄片）。

## 2. Affected Flow

| Flow | 變更 |
|---|---|
| **UF 進線建案**（新）| 客服在後台選來源渠道 + 填客戶聯絡/需求摘要 → 建 Case（啟動 first-response SLA）|
| **BF 客服 → 工單** | 報價/派工/客訴前先有 Case；problem_card / work_order 連回 case_id |
| LINE 進線（既有）| AI escalation 建 problem_card 時，順帶 ensure/關聯一張 Case（source_channel=line）|

## 3. Affected Spec (FR / NFR)

- **BR-M01-01**（channel source 必填，8 渠道綁 Case）— 本 CR 落地 Phase I 子集（見 §8 D1）。
- **BR-M01-02 / Q006 / Q170**（報價前先建 Case）— 本 CR 落地（gate 強度見 §8 D3）。
- **G036**（lead source attribution）— 依附 source_channel，本 CR 建欄、彙整報表後續。
- **NFR first-response SLA** — 計時骨架本 CR 建；級距數值待業主（§8 D2）。
- **BR-M01-03 / G008 / Q003**（external partner portal 代客建案）— **Phase II/III 不在本 CR**（§11）。

## 4. Affected API

| 端點 | 動作 | 備註 |
|---|---|---|
| `POST /tenants/{tid}/cases` | 新增 | 客服建 Case（source_channel + customer contact + summary）|
| `GET /tenants/{tid}/cases` | 新增 | 列表（篩 source_channel / status / SLA 逾時）|
| `GET /tenants/{tid}/cases/{id}` | 新增 | 詳情（含關聯 problem_cards / work_orders / SLA 狀態）|
| `PATCH /tenants/{tid}/cases/{id}` | 新增 | 更新狀態 / 補資訊 / 關閉 |
| `POST …/problem-cards`、`create_quote`、工單建立 | 改 | 加 `case_id`（gate 強度見 §8 D3）|

全部 additive（不刪既有端點）；DISPATCH_ROLES/BACKOFFICE_ROLES 寫；cross-tenant guard。

## 5. Affected Data

- **新表 `saas.intake_case`**（暫名）：`id, tenant_id, case_number(可讀號?), source_channel,
  customer_id(nullable), customer_contact(phone/line/name), summary, status,
  first_response_due_at, first_responded_at, created_by, created_at, updated_at`。
- **關聯**：`problem_cards +case_id`、`work_orders +case_id`（nullable，漸進回填）。
- **migration**：新表 + 兩個 FK 欄 + 索引（per-tenant、source_channel、SLA due）。
- source_channel enum 值域 = §8 D1 裁決的 Phase I 渠道子集。

## 6. Affected Test

- 新 `test_intake_case_*`：建 Case（各渠道）/ 列表篩選 / SLA due 計算 / case_id gate（報價前無 Case → 422 或漸進放行依 D3）/ cross-tenant 403。
- 回歸：problem_card / quote / work_order 既有流程加 case_id 後不破。
- E2E：客服後台建 Case → 開問題卡/工單連回 → SLA 逾時標示。

## 7. Affected Architecture

- 新增 intake bounded context 的最小實體（Case 為 problem_card/work_order 的上游容器）。
- 不引入新 infra；沿用既有 v2 router + service + migration 慣例。
- 與 CR-0096（problem_cards per-issue）相容：一張 Case 可有多張 problem_card（多問題）。

## 8. 🛑 Human Decisions Required（請業主逐項裁決後我才動 code）

| # | 決策 | 選項 | 我的建議 |
|---|---|---|---|
| **D1** | **Phase I 要先接哪些進線渠道？** | (a) 僅 LINE + 電話 + Web + 熟客介紹（客服代建）；品牌/門市/經銷/建商 4 個 partner 渠道留 Phase II（隨 M14 Partner Portal）　(b) 一次全 8 渠道 | **(a)** —— partner 渠道屬會議定調第二階段（多租戶/Partner Portal），Phase I 先做客服可代建的 4 個 |
| **D2** | **first-response SLA 時效級距？**（建案後幾分鐘內要首次回應）| 例：一般 30 分 / 急件 10 分 / 夜間 次日 09:00 前？（你 + 客服定）| 工程骨架我先建（欄位+計時+逾時標示），**數值待你給**；可比照既有 sla_policy 入 M18 config 不寫死 |
| **D3** | **「報價前必先建 Case」gate 強度？** | (a) 硬擋（無 case_id 不能開報價/工單，422）　(b) 漸進（先 nullable 關聯、不強制，之後再硬擋）| **(b) 漸進** —— 避免一刀切破壞既有 LINE→problem_card→work_order 流程；先建關聯與後台建案，gate 之後另 CR 開硬擋 |
| **D4** | **Case 與既有 problem_card 的關係？** | (a) Case 為上游容器，一 Case 可含多 problem_card / work_order　(b) Case ≈ problem_card 同層改名 | **(a)** —— 與 CR-0096 多問題分卡相容、語意清楚（Case=一次進線事件，下可分多問題卡）|
| **D5** | **Case 要不要可讀編號？**（類似工單 TP-000001）| (a) 要（如 `C-TP-000001`，客服好溝通）　(b) 不要（內部 UUID 即可）| **(a)** —— 與工單可讀號一致，客服/客戶溝通好用 |
| **D6** | **客戶去重 key 確認**（既有三方不一致：你 Q008 裁「依地址」/ BR-M02-01「phone+LINE ID」/ code「phone」）| 重新裁定唯一鍵 | 建 Case 會碰客戶比對 → 需你定。建議 **phone + LINE ID 為主、地址輔助**（與多數實作一致），同步修文件 |

### 8.1 業主裁決（2026-06-28）

| # | 裁決 |
|---|---|
| **D1** | **LINE + 電話 + Web + 熟客介紹**（4 渠道，客服可代建）；品牌/門市/經銷/建商 4 個 partner 渠道留 Phase II |
| **D2** | SLA 計時骨架先建，數值入 config 標「暫定待業主確認」（暫定一般 30 分）—— 比照 CR-0106/0104 誠實假設模式 |
| **D3** | **漸進** —— problem_card/work_order 加 nullable case_id 先建關聯、不硬擋；硬擋之後另 CR |
| **D4** | **Case 為上游容器** —— 一 Case 可含多 problem_card/work_order（與 CR-0096 相容）|
| **D5** | **可讀號**（如 `C-TP-000001`，與工單一致）|
| **D6** | **phone + LINE ID 為主、地址輔助** —— 同步修正 Q008 文件（原裁「依地址」）|

## 9. Suggested Implementation Order（§8 裁決後）

1. migration：`saas.intake_case` 表 + `problem_cards/work_orders +case_id`（依 D1 定 source_channel enum）。
2. `intake_case_service`：建/列/詳/改 + first-response SLA due 計算（D2 數值入 config）。
3. `intake_cases_v2` router（4 端點，main.py 註冊）。
4. problem_card / quote / work_order 加 case_id 關聯（D3 漸進：先 nullable 不強制）。
5. 前端後台「進線建案」頁（選渠道 + 客戶聯絡 + 摘要）+ Case 列表（SLA 逾時標示）。
6. LINE escalation 順帶 ensure 一張 Case（source_channel=line）。
7. 測試（§6）+ 更新 traceability + 文件三同步。

## 10. Risks & Rollback

- **風險**：加 case_id 到 problem_card/work_order 若 D3 選硬擋，會破壞既有無 Case 的進線 → 故建議 D3 漸進。
- **回滾**：新表 + nullable 欄屬 additive，migration forward-only 可重套；前端新頁獨立可下架。

## 11. Out of Scope（明確不在本 CR）

- 品牌商 / 門市 / 經銷商 / 建商 4 個 partner 自助建案渠道（**Phase II/III**，隨 M14 Partner Portal + 三類租戶 multi-tenant）。
- lead source 行銷轉換分析報表（G036 彙整，建欄後另議）。
- 自動媒合 / 金流（Phase II）。

## 12. Sign-off

- [x] 業主裁決 §8 D1–D6（2026-06-28，見 §8.1）
- [x] 確認 §9 實作順序
- [ ] （實作後）更新 traceability matrix + doc-freshness

## 13. 進度

✅ **S1 後端核心 done**（branch `docs/cr-0108-m01-intake-cia`）：migration 085（`saas.intake_case`
+ 可讀號序列 + `problem_cards/work_orders +case_id` nullable）+ `intake_case_service`（建/列/詳/改
+ first-response SLA due 計算，渠道/狀態值域守門）+ `intake_cases_v2` router（4 端點，BACKOFFICE_ROLES
含客服、cross-tenant guard、POST idempotency，main.py 註冊）+ `[intake].first_response_sla_minutes`
config（暫定 30 待業主 D2）。API `test_intake_case` 5/5 + 全套 1459 passed 無回歸。**待部署 api（含 migration 085）**。

✅ **S2 前端 done**（branch `feat/cr-0108-intake-frontend`）：新頁 `web/src/app/admin/cases/page.tsx`
（客服代客建案：渠道 phone/web/referral + 客戶聯絡 + 摘要 → 建案發案號 + 啟動 SLA；Case 列表含狀態 /
SLA 逾時標示 / 標記處理中 / 結案）+ Sidebar「進線案件」入口（開單流程群組第 2 位）+ rolePolicy
`/admin/cases`（admin/ops/dispatcher/customer_service）+ i18n（中英 sidebar.nav.intakeCases）。
tsc 0 + 重建 api+web docker + **Playwright 實機驗證**（建案頁渲染、UI 建案 C-000006 即時入列、curl POST/GET
通；測試資料已清）。

⏳ **S3 待續**（小 follow-up）：LINE escalation 順帶 ensure 一張 Case（source_channel=line）讓 LINE 進線
也收斂到 Case 模型；客戶比對沿 D6（phone+LINE ID）。

> D6 裁決已記本檔 §8.1（BR-M02-01 既為 phone+LINE，與裁決一致；Q008 原「依地址」由本 CR D6 supersede，
> `docs/_source` 正典更新屬人工 tier-0 變更，另行處理，不由 AI 改源）。
