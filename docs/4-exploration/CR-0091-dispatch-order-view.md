---
id: CR-0091
title: "標準化派工單 6 模組視圖（前端組裝既有欄位 + admin 免責同意顯示）"
status: implementing
tier: 4-exploration
owner: HYBRID
created: 2026-06-21
target-release: dev_new_arch
product-version: null
supersedes: null
superseded-by: null
---

# CR-0091: 標準化派工單 6 模組視圖

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md`（觸發：User flow — 新增派工單檢視/編輯流程）
> **背景**: 業主指「開單頁面的欄位沒有按照 `電子鎖安裝與維修派工單整合分析報告.pdf` 做」。該 PDF 整合 Chatlock + dormakaba 兩大品牌派工單，歸納出 6 大模組標準欄位。

## 1. Change Statement

**As-is**: 工單詳情頁（`web/src/app/work-orders/[id]/page.tsx`）有 SLA/問題卡/媒體/時間軸/對話/完工/異常等區塊，但**沒有按 PDF 6 模組組織的結構化派工單視圖**；多數規格欄位（brand/model/serial/door/warranty/billing）已存在 DB 卻未在前端呈現或編輯。

**To-be**: 新增「派工單」結構化視圖，依 PDF 6 模組呈現 + 可內嵌編輯（既有 `PATCH /work-orders/{id}/fields`），模組 4 免責同意顯示客戶同意狀態（補 admin 端唯讀 GET），模組 5 計費沿用 quote-items，模組 6 簽認讀 digital_signatures。

**Driver**: 業主裁決「option 1：完整派工單視圖 + 可內嵌編輯 + 補免責同意端點 + 地址結構化輸入不動 schema」。

## 2. 關鍵發現 —— 這是「後端做了前端沒跟」的典型

PDF 6 模組欄位 vs 現有 `work_orders` 欄位對照（**幾乎全部已存在**，CR-0026/CR-0043 加的）：

| PDF 模組 | PDF 欄位 | DB 欄位 | 狀態 |
|---|---|---|---|
| 1 基礎案件 | 客戶名稱/電話/地址/施工日期 | customer_name/phone/address（base）、scheduled_at | ✅ 有（地址為單欄，結構化用前端解析顯示，不動 schema）|
| 2 設備環境 | 產品型號/序號/購買地點/安裝日期/環境遮雨/門扇材質門厚 | model、serial_number、dealer、install_date、rain_exposure、door_type+door_thickness+is_interior_door、brand | ✅ 全有 |
| 3 工單類型狀態 | 服務類別/維修原因/完工狀態 | service_category、problem_type、completion_status+status_reason、warranty_status+warranty_expiry_date | ✅ 全有 |
| 4 施工免責合規 | 特殊門型加價/3 段法律同意簽名 | special_door_surcharge；consent → `work_order_consents`（consent_service 三型 new_installation/lock_destruction/personal_data）| ⚠️ 後端有但 **admin 端無 GET** |
| 5 多維度計費 | 出勤/安裝/特殊費/零件明細/總計 | customer_final_amount、payment_method/proof、materials_used；明細 → quote-items | ✅ 有 |
| 6 雙方簽認 | 工程師簽名/客戶驗收簽名 | digital_signatures 表 | ✅ 有 |

**結論**：6 模組所需資料 + 編輯端點（`patchWorkOrderFieldsV2`，已 role_required）**後端早就齊備**，唯一缺口是**前端沒有對應視圖** + 模組 4 缺 admin 唯讀 GET。完全坐實業主「只改後端沒改前端」的觀察。

## 3. Affected API

| API | Action | Breaking? |
|---|---|---|
| `GET /tenants/{tid}/work-orders/{id}/consents` | **New**（admin/staff 唯讀顯示客戶三段同意狀態，沿用 consent_service.get_consents）| 否（新增）|
| `PATCH /tenants/{tid}/work-orders/{id}/fields` | 既有，沿用（role_required(_DISPATCH_ALLOWED_ROLES)）| 否 |
| `GET /tenants/{tid}/work-orders/{id}/quote-items` | 既有，沿用（模組 5）| 否 |

> 新 GET 走 `role_required(*_DISPATCH_ALLOWED_ROLES)`（後台角色），對齊 fields PATCH。**不**新增寫入端點（客戶同意走既有 consumer `/consumer/consents/{token}`）。

## 4. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `work_orders` / `work_order_consents` / `digital_signatures` | **無 schema 變更** | ❌ |

> 地址結構化（縣市/鄉鎮/路街/巷弄號樓）：**不動 schema**，前端對既有 `address` 單欄做顯示層解析，必要時以「結構化輸入框 → 合併寫回單欄」呈現（業主裁決）。

## 5. Affected Architecture / Test

- 無模組邊界變更；無新 ADR。
- 新增 component test：admin consents GET 回傳三型 + accepted 狀態。
- 前端：新增 `DispatchOrderView`（6 模組）+ inline edit；以現有 Playwright smoke 驗證渲染無 raw key / 無 crash。

## 6. Human Decisions Required

✅ 業主已裁決（前次對話）：

| # | 問題 | 決策 |
|---|---|---|
| 1 | 範圍 | option 1：完整 6 模組視圖 + 可內嵌編輯 |
| 2 | 免責同意 | 補 admin 端唯讀 GET（顯示客戶同意狀態），客戶簽署仍走 consumer LIFF |
| 3 | 地址 | 結構化輸入但**不動 schema**（前端解析/合併既有單欄）|

## 7. Implementation Order

1. 後端：新增 admin `GET /work-orders/{id}/consents`（薄包 consent_service.get_consents）+ component test。
2. 前端：`DispatchOrderView` 6 模組（讀既有 WorkOrderEnvelope 欄位）+ inline edit（PATCH fields）+ 模組 4 串新 GET + 模組 5 串 quote-items + 模組 6 串 signatures。
3. 掛進工單詳情頁（新分頁/區塊）。
4. i18n key（全繁中）+ Playwright smoke。

## 8. Risks & Rollback

| Risk | 緩解 |
|---|---|
| 地址單欄無法乾淨拆解 | 顯示層 best-effort 解析，原始單欄永遠保留為真相源 |
| inline edit 誤改既有欄位語意 | 只送 `exclude_unset` 變更欄位（patch 既有行為），唯讀模組（4/6）不開編輯 |

Rollback：前端視圖為新增區塊，移除即復原；admin GET 為唯讀新端點，無副作用。
