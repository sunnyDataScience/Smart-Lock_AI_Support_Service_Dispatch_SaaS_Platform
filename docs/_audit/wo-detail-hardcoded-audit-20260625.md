---
title: 工單詳情頁 /work-orders/[id] 寫死資料盤點報告
status: active
tier: _audit
created: 2026-06-25
owner: 啟恆 / Sunny 裁決
method: 11-區塊 fan-out + 對抗式驗證 workflow（31 agents），以 file:line 實查前端顯示值 vs WorkOrder schema / DB work_orders 欄位 / 既有端點，逐筆判定「真寫死 / 有接但沒資料 / 誤判」；主 agent 另獨立讀 code 雙重確認頭號項目
sources:
  - web/src/app/work-orders/[id]/page.tsx（3195 行，admin 工單詳情頁）
  - web/src/components/work-orders/{WorkOrderDetailSidebar,DispatchOrderView,EventTimeline}.tsx
  - web/types/api.generated.ts（WorkOrder schema 欄位）
  - public.work_orders DB 欄位（本地實查）
---

> ⚠️ 本文件為 `_audit` 稽核軌跡：盤點「畫面顯示值是否真實接資料」。判定基準＝該值能否對應到 WorkOrder schema 欄位 / DB 欄位 / 既有端點。實作修正前個別後端新欄位仍須走 CIA。狀態反映 2026-06-25 當下 codebase（branch `fix/wo-detail-real-data` 基礎）。

# 工單詳情頁 `/work-orders/[id]` 寫死資料盤點報告

## 一、總體判斷

全頁 13 區塊：**真實接資料 8 區、寫死／假資料 5 區**。資訊骨架可信，但**頁面最顯眼的頂部「SLA 進度時間軸」與「完工報告」整段是假的** —— 正好是業主用來判斷「工單進度與品質」的兩個地方。

| 判定 | 區塊 |
|---|---|
| ✅ 真實接資料（可信） | WorkTimeline（`buildEvents(order)` 衍生）、ProblemCardSummary、LineMediaGallery、ConversationThread、各 Modal 表單群、DispatchOrderView 主體、WorkOrderDetailSidebar 主體、Detail Header 本體 |
| ❌ 寫死／假資料 | **SlaTimeline（整段假）**、**CompletionReport 完工報告（整段假）**、ExceptionRecords 例外紀錄（空殼 stub）、設備面板遙測三格（誠實佔位「示意」）、DispatchOrderView 簽名狀態（用 `status` 推斷，非查簽名紀錄） |

> **一句話結論**：能信的是「這張單是誰、什麼鎖、聊了什麼、報價多少」；**不能信**的是「現在進度到哪、SLA 剩多久、完工驗收結果、有沒有異常」—— 後者全是每張工單長一模一樣的假畫面。

## 二、寫死項目主表（依嚴重度排序，已去重）

| 功能 | 區塊 | 寫死了什麼 | 該接什麼（資料源在?） | 影響 | 嚴重度 |
|---|---|---|---|---|---|
| SLA 進度時間軸（元件不接 props） | SlaTimeline | `SlaTimeline()` 無參數渲染，整段 mock | `order` 時間戳 / `GET /work-orders/{id}/events`（**已存在**，EventTimeline 在用） | 頂部最顯眼元件，每張單同一條假時間軸，SLA 監控失真 | **CRITICAL** |
| 完工功能測試（指紋✓/密碼✓/電池✗） | CompletionReport | `FUNC_TESTS` 常數，電池恆 fail | service_report / data 需**新增結構化欄位**（後端無） | 每張單恆顯示「電池失敗」，完工驗收失稽核意義，誤導品管 | **CRITICAL** |
| 完工報告（元件不接 props） | CompletionReport | `CompletionReport()` 無參數，標題「（示意）」 | `order.completion_time` / `summary` / `completion_status`（**已存在**） | 任一工單（含未完工）都顯示同一份假報告 | **HIGH** |
| 各階段時間戳與完成狀態 | SlaTimeline | `SLA_NODES` 固定 09:00/09:15/09:32/10:45、前三綠點、第四 active | created_at / events / accepted_at / started_at / completion_time / confirmed_at（**已存在**） | 已完工或剛建單的工單都顯示「施工中」 | **HIGH** |
| SLA 剩餘倒數「02:15」 | SlaTimeline | `t("remaining",{time:"02:15"})` 固定 | 節點時間有源；**但 SLA deadline 欄位缺失**，需後端補政策 | 每張單永遠「剩 2 小時 15 分」，無法辨識逾時單 | **HIGH** |
| 進度條 60% | SlaTimeline | `w-[60%]` 固定 | 已完成節點數 ÷ 總節點數動態算（**資料源存在**） | 進度永遠 60%，與真實進度無關 | **HIGH** |
| 完工提交時間「—」 | CompletionReport | i18n `submittedAt`=「提交時間：—」無插值 | `order.completion_time` / DB `completed_at`（**已存在**，WorkTimeline 已在用） | 看不到真實完工時刻 | **HIGH** |
| 異常紀錄清單（空殼） | ExceptionRecords | `ExceptionRecords()` 無 props、無 fetch、永遠空虛線框 | `GET /tenants/{tid}/exception-cases`（**後端已存在**，/admin/exceptions 在用；需補 work_order_id 篩選） | 工單有拒單/缺料/糾紛也一筆不顯示，誤導「此工單無異常」 | **HIGH／MEDIUM** |
| 簽名完成狀態 | DispatchOrderView | 由 `order.status` 推斷，非查 `digital_signatures` | 簽名紀錄端點（已存在；今日 fix/signature-response-500 已處理同源問題） | 狀態與真實簽名紀錄可能脫鉤 | **MEDIUM** |
| 設備面板－電量 | WorkOrderDetailSidebar | 固定「—」，標「電量（示意）」 | 智慧鎖遙測（**後端無此欄位**，需新整合） | 已誠實標「示意」、整塊淡化，誤導風險低 | **LOW** |
| 設備面板－連線 | WorkOrderDetailSidebar | 固定灰燈＋「—」，標「連線（示意）」 | 同上，需設備連線端點（**後端無**） | 同上，誠實佔位 | **LOW** |
| 設備面板－最近操作 | WorkOrderDetailSidebar | 固定「—」，標「最近操作（示意）」 | 同上，需 IoT 裝置遙測（**後端無**） | 同上，誠實佔位 | **LOW** |

## 三、分類小結：純前端工 vs 全端工

### A. 該接但寫死 —— 資料源已存在，純前端沒接（**只需前端工**）

修這些**不用動後端**，把元件改成接 `order` 或呼叫既有端點即可：

- **SLA 時間軸全部節點時間戳、完成狀態、進度條** → `order` 既有時間戳，或 `GET /work-orders/{id}/events`（已存在，EventTimeline.tsx:239 正在用）
- **完工提交時間／摘要／完工狀態** → `order.completion_time` / `order.summary` / `order.completion_status`
- **異常紀錄清單** → `GET /tenants/{tid}/exception-cases`（後端已存在；需補一個 `work_order_id` query 篩選，屬小改；或前端撈清單後本地過濾）

### B. 該接但後端根本沒這資料 —— 要新端點／新欄位（**全端工，須走 CIA**）

短期無法純前端修好，需後端先建欄位：

- **功能測試逐項結果（指紋／密碼／電池 pass-fail）** → WorkOrder type 與 DB 皆無結構化欄位，需後端在 `service_report` / `data` 增 `function_tests` 結構或開新端點。**且需產品決定：測哪些項、由誰於何時填**（技師完工時填）
- **SLA 剩餘倒數的「期限」** → 無 SLA deadline 欄位，需後端依 urgency / service_category 補 SLA 政策才能算倒數
- **設備面板電量／連線／最近操作** → 純智慧鎖 IoT 遙測，後端完全無此整合，需新端點（**且已誠實標「示意」，非欺騙性 mock，可暫緩**）

## 四、建議優先修的 3 項

**第 1 優先 —— SLA 進度時間軸（業主口中的「進度」，真相在此）**
真相：它 **100% 是假的**。每一張工單詳情頁頂部都顯示同一條寫死時間軸——建立 09:00、派工 09:15、接單 09:32、施工中 10:45、剩餘 02:15、進度條 60%——**無論工單實際是剛建立、已完工還是已取消，畫面永遠顯示「施工中、還剩 2 小時 15 分」**。這不是裝飾，是會直接誤導派工調度與 SLA 催件決策的假儀表板。
修法：**純前端工**。資料源 `order` 時間戳已在頁面載入（同頁 `buildEvents` 已在消費），把 SlaTimeline 改接 `order` 即可；剩餘倒數因無 SLA 期限欄位，先隱藏、其餘照修。

**第 2 優先 —— 完工報告 + 功能測試結果**
任一工單（含未完工）都顯示同一份假報告：提交時間恆「—」、功能測試恆「指紋✓ 密碼✓ 電池✗」。**「電池恆失敗」最危險**——品管可能誤判每張單都有電池問題，或對真有問題的單視而不見，完工驗收完全失去稽核意義。
修法：**半前端半全端**。提交時間／摘要／完工狀態是純前端（接 `order.completion_time` 等既有欄位）；功能測試逐項結果需後端先補結構化欄位——**上線前此區應改空狀態或隱藏，絕不可繼續顯示假固定結果**。

**第 3 優先 —— 異常紀錄清單**
工單頁的異常區塊是永遠空的示意框，但後端 M15 例外框架（`exception-cases`）已實際在記錄拒單／缺料／糾紛等異常。管理員在工單頁看到空框會誤判「此工單無異常」，被迫跳 /admin/exceptions 另頁交叉比對。
修法：**幾乎純前端工**。端點已存在且 /admin/exceptions 已在用，只需把 ExceptionRecords 改接 `workOrderId` 並呼叫 `GET /exception-cases`，後端僅需補一個 `work_order_id` 篩選參數（小改）。

> 設備面板三格遙測雖也是寫死，但已誠實標「示意」、整塊淡化、按鈕標 comingSoon，**誤導風險低，可排在最後或待 IoT 整合再做**，不應佔用前三優先順位。

## 五、後續動作

- **A 類（純前端）**：本輪於 `fix/wo-detail-real-data` 實作 SlaTimeline 真實化、完工報告時間/摘要真實化、ExceptionRecords 接 exception-cases；功能測試與 SLA 倒數的假顯示一併改為誠實空狀態。
- **B 類（後端新欄位）**：`function_tests` 結構化欄位、SLA deadline 政策觸及 DB schema + API contract + domain model → 須先走 `sunnydata-change-impact-analysis` 產 CIA、業主裁決 §8（測哪些項、SLA 政策參數）後再實作。
