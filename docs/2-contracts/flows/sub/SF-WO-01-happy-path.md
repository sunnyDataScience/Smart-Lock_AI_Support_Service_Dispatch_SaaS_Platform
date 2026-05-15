---
id: SF-WO-01
title: happy path (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-001 / F-002 / F-005 / F-006 / F-009
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 1
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-01 — happy path

> Work Order BF 的子流程 1 of 13。

## 4. Flow 1：正常路徑 (Happy Path) — 對應 F-001 / F-002 / F-005 / F-006 / F-009

> **Endpoints:** `openapi#operationId=listConversations`, `getConversation`, `listProblemCards`, `listWorkOrderPool`, `acceptWorkOrder`, `getWorkOrder`, `completeWorkOrder`, `submitWorkOrderSignature`
> **Events In:** `work_order.available`（WS `/realtime/pool/{tech_id}`）, `work_order.assigned`
> **Events Out:** `work_order.status.changed` (pending → assigned → accepted → in_progress → completed → confirmed), `work_order.completed`
> **Idempotency:** Required on `acceptWorkOrder`, `completeWorkOrder`, `submitWorkOrderSignature`（Step 5/11/14）
> **Error codes:** `WORK_ORDER_CONFLICT`（接單競爭）, `WORK_ORDER_STATUS_INVALID`, `SIGNATURE_ALREADY_SIGNED`
> **Related pages:** T1（11_tech_pool）→ T3（12_tech_my_orders）→ T9（19 簽章段）

### 4.1 觸發條件

工單建立有三種觸發路徑：

**路徑 A — 診斷推理引擎觸發** (自動)：
- `task_decompose` 輸出 `diagnosis_status = "recommend_dispatch"`（診斷推理超過 3 輪未收斂、或 LLM 判斷需到府）
- 詳見 `diagnostic-intelligence-architecture.md` §4 PDCA Loop

**路徑 B — 品牌錯誤碼直接觸發** (自動，跳過遠端嘗試)：
以下 7 個信號直接觸發派工，不進入遠端排查：

| 品牌 | 錯誤信號 | 失效模式 | 原因 |
|---|---|---|---|
| dormakaba | 紅燈閃 4 次 | FM-MECH-002 馬達異常 | 需更換馬達模組 |
| dormakaba | 紅燈常亮 | FM-ELEC-002 系統錯誤 | 需主機板檢測 |
| Philips | 紅燈閃 3 次 | FM-MECH-003 離合器異常 | 需更換離合器 |
| Kaadas | 紅燈閃 5 次 | FM-MECH-004 馬達堵轉 | 需鎖體檢查 |
| Milre | 面板全亮後熄滅 | FM-ELEC-001 主機板異常 | 需更換主機板 |
| 所有品牌 | 門扇反弓 | FM-MECH-005 | 需專業調整門/門框 |
| 所有品牌 | 承接板嚴重偏位 | FM-MECH-006 | 需重新校正安裝 |

> 來源：`SOP-DISPATCH-001.json` check_dispatch_signals + `SOP-HW-001.json`

**路徑 C — 管理員手動建立** (人工)：
- 管理員從 Admin Panel 建立工單（客訴升級、電話接單等）

### 4.2 參與角色

Customer, AI_System, Dispatch_Engine, Technician, Admin, Finance

### 4.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant AI as AI 系統
    participant DB as PostgreSQL
    participant Dispatch as 派工引擎
    participant Maps as Google Maps API
    participant Pricing as 報價引擎
    participant TechApp as 技師 Web App
    actor Technician as 技師
    participant LINE as LINE Messaging API
    participant Finance as 財務系統

    Note over Customer, AI: === 階段一：問題診斷與工單建立 ===

    Customer->>AI: 報修訊息 (LINE Text/Image)
    AI->>AI: ProblemCard 建立<br/>(brand, model, symptoms, urgency)
    AI->>AI: L1 向量搜尋 (cosine >= 0.85)
    AI->>AI: L1 未命中 → L2 RAG 生成
    AI->>AI: L2 未解決 → 觸發 L3 升級

    Note over AI: L3 升級前收集客戶聯絡資訊

    AI->>LINE: 請求客戶提供地址與電話
    LINE->>Customer: 「為了安排技師上門服務，請提供您的地址和聯絡電話」
    Customer->>LINE: 提供地址與電話
    LINE->>AI: 客戶聯絡資訊
    AI->>DB: UPDATE users SET phone, address
    AI->>DB: INSERT work_orders (status: created, priority: normal)
    AI->>LINE: 通知客戶「已安排技師服務」
    LINE->>Customer: 「您的報修已受理，正在為您匹配最合適的技師」

    Note over Dispatch, Maps: === 階段二：智能派工 ===

    Dispatch->>DB: 查詢 ProblemCard (brand, model, location, urgency)
    Dispatch->>DB: 查詢可用技師列表<br/>(capabilities, service_regions, status=active)

    Note over Dispatch: 多因子加權匹配演算法：<br/>技能匹配 (40%) × 距離 (25%)<br/>× 評分 (20%) × 可用性 (15%)

    Dispatch->>Maps: 批次計算各技師到客戶距離
    Maps-->>Dispatch: 距離矩陣 + 預估行車時間
    Dispatch->>Dispatch: 排序候選技師 → 選出 Top 1
    Dispatch->>DB: UPDATE work_orders SET status=assigned, technician_id
    Dispatch->>TechApp: 推播工單通知 (含 ProblemCard 摘要)
    TechApp->>Technician: 顯示新工單 (客戶地址、問題描述、預估報價)

    Note over Technician, TechApp: === 階段三：技師接單與到場 ===

    Technician->>TechApp: 點擊「接受工單」
    TechApp->>DB: UPDATE work_orders SET status=accepted, accepted_at=NOW()
    TechApp->>LINE: 通知客戶技師資訊
    LINE->>Customer: 「技師 王師傅 已接單<br/>預計 14:30 到達，聯絡電話 09xx-xxx-xxx」

    Note over Technician: 技師出發前往客戶地址

    Technician->>TechApp: GPS 到場打卡
    TechApp->>DB: UPDATE work_orders SET status=in_progress, started_at=NOW()
    TechApp->>LINE: 通知客戶技師已到場
    LINE->>Customer: 「技師已到達您的地址，即將開始服務」

    Note over Technician: === 階段四：現場作業 ===

    Note over Technician: 拍攝施工前照片 (依拍攝規範)
    Note over Technician: 執行維修/安裝作業
    Note over Technician: 拍攝施工後照片 + 功能測試影片

    Technician->>TechApp: 提交完工報告<br/>(照片、零件用量、工時、服務摘要)
    TechApp->>Pricing: 自動計價<br/>(brand × lock_type × difficulty + modifiers)
    Pricing-->>TechApp: 報價明細 (工資 + 車馬費 + 零件 + 加價)
    TechApp->>DB: UPDATE work_orders SET status=completed,<br/>completed_at=NOW(), final_price
    TechApp->>DB: INSERT invoices (status: issued)

    Note over Customer, LINE: === 階段五：客戶確認與帳務 ===

    TechApp->>LINE: 完工通知 + 帳單明細 (Flex Message)
    LINE->>Customer: 「維修完成！請確認服務品質」<br/>+ 帳單明細 + 滿意度調查

    Customer->>LINE: 點擊「確認完工」+ 評分 5 星
    LINE->>DB: UPDATE work_orders SET status=confirmed,<br/>confirmed_at=NOW(), rating=5
    DB->>DB: UPDATE technicians SET rating (加權平均),<br/>completed_orders += 1
    LINE->>Customer: 「感謝您的確認！服務已完成」

    Note over Finance: === 階段六：帳務結算 ===

    Finance->>DB: 月底批次對帳<br/>(confirmed 工單 → reconciliations)
    Finance->>DB: 計算技師應領金額<br/>(總收款 - 平台費 - 材料費)
    Finance->>DB: INSERT settlements (status: pending)
    Finance->>DB: UPDATE work_orders SET status=archived
```

### 4.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 | 耗時預估 |
|------|----------|----------|----------|----------|
| 1 | — | `created` | AI 系統建立工單 | < 1 秒 |
| 2 | `created` | `assigned` | 派工引擎匹配完成 | < 5 分鐘 |
| 3 | `assigned` | `accepted` | 技師接受工單 | < 15 分鐘 |
| 4 | `accepted` | `in_progress` | 技師到場打卡 | 依預約時間 |
| 5 | `in_progress` | `completed` | 技師提交完工報告 | 30 分鐘 ~ 2 小時 |
| 6 | `completed` | `confirmed` | 客戶確認 / 48 小時自動確認 | < 48 小時 |
| 7 | `confirmed` | `archived` | 月底帳務結清 | 月結週期 |

### 4.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| L3 升級 | LINE Flex | Customer | 「已安排技師服務，正在匹配中」 |
| 技師接單 | LINE Flex | Customer | 技師姓名、預計到達時間、聯絡電話 |
| 技師接單 | Web Push | Technician | 工單詳情、客戶地址、導航連結 |
| 技師到場 | LINE Push | Customer | 「技師已到達」 |
| 完工回報 | LINE Flex | Customer | 帳單明細 + 確認按鈕 + 滿意度調查 |
| 客戶確認 | Web Push | Technician | 「客戶已確認完工」 |
| 帳務結算 | Web Push | Technician | 月結對帳單 |

---
