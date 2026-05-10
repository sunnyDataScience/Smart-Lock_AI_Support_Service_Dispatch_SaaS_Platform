---
id: SF-WO-11
title: customer not onsite (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-010 / F-016
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 11
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-11 — customer not onsite

> Work Order BF 的子流程 11 of 13。

## 19. Flow 11：客戶不在場 — 對應 F-010 / F-016

> **Endpoints:** `reportCustomerAbsent`（Week 4）, `proposeReschedule`（T11）
> **Events Out:** `customer.absent.reported`, `work_order.reschedule.proposed`
> **Idempotency:** Required on 回報不在場與改期
> **Error codes:** `RESCHEDULE_RSVP_EXPIRED`, `RESCHEDULE_LIMIT_EXCEEDED`
> **Related pages:** T3 → **T11 改期日曆** + 客戶 LINE Flex RSVP（19 T1.4 閉環）


> **Gap ID**：OP-03 — 技師到場但客戶不在家的處理流程

### 19.1 觸發條件

- 技師到場 GPS 打卡後，無法聯繫到客戶 (門鈴無人應答、電話未接)
- 工單狀態從 `accepted` 準備轉為 `in_progress` 時觸發

### 19.2 參與角色

Technician, Customer, Admin, Finance

### 19.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant DB as PostgreSQL
    participant TechApp as 技師 Web App
    actor Technician as 技師
    participant SLA as SLA 計時器
    participant Admin as 管理員面板
    actor AdminUser as 管理員

    Note over Technician: 技師到達客戶地址，按門鈴無人回應

    Technician->>TechApp: GPS 到場打卡 + 回報「客戶不在場」
    TechApp->>DB: INSERT customer_absence_log<br/>(work_order_id, arrived_at=NOW(), gps_coords)
    TechApp->>DB: UPDATE work_orders SET substatus=customer_absent

    Note over SLA: 啟動 15 分鐘等待計時器

    SLA->>LINE: 第 1 次推播 (T+0min)
    LINE->>Customer: 「技師已到達您的地址，請開門」<br/>+「如有特殊情況請立即回覆」<br/>+ 技師電話一鍵撥打按鈕

    Technician->>Customer: 撥打客戶電話 (第 1 次)
    Note over Technician: 電話未接通

    SLA->>SLA: 等待 5 分鐘

    SLA->>LINE: 第 2 次推播 (T+5min)
    LINE->>Customer: 「技師仍在您的門口等候中」<br/>+「請盡快前來開門或回覆訊息」

    Technician->>Customer: 撥打客戶電話 (第 2 次)
    Note over Technician: 電話仍未接通

    SLA->>SLA: 等待 5 分鐘

    SLA->>LINE: 第 3 次推播 (T+10min)
    LINE->>Customer: 「⚠ 最後提醒：技師將再等候 5 分鐘」<br/>+「若無法聯繫，將收取出場費 NT$300」<br/>+ [我馬上到] [改期] [取消] 按鈕

    SLA->>SLA: 等待 5 分鐘

    Note over SLA: T+15min — 等待時間到期

    alt 15 分鐘內客戶回應 — 「我馬上到」
        Customer->>LINE: 點擊 [我馬上到] / 電話回覆
        LINE->>TechApp: 客戶確認趕來中
        TechApp->>Technician: 「客戶表示馬上到達」
        Note over Technician: 額外等候 (最多再 15 分鐘)

        Customer->>Technician: 客戶到場
        Technician->>TechApp: UPDATE work_orders SET status=in_progress
        Note over Technician: 正常施工流程 (→ Flow 1 §4 階段四)

    else 15 分鐘內客戶回應 — 「改期」
        Customer->>LINE: 點擊 [改期]
        LINE->>Customer: 「請選擇新的預約時段」
        Customer->>LINE: 選擇新時段
        LINE->>DB: UPDATE work_orders SET status=cancelled,<br/>cancel_reason=customer_absent_reschedule
        LINE->>DB: INSERT work_orders (新工單, 新時段,<br/>absence_fee=300, linked_order_id)
        LINE->>Customer: 「已為您重新安排 [新時段]」<br/>+「本次出場費 NT$300 將計入下次帳單」
        LINE->>TechApp: 通知技師返回
        TechApp->>Technician: 「客戶已改期，請返回」

    else 15 分鐘內客戶回應 — 「取消」
        Customer->>LINE: 點擊 [取消]
        LINE->>DB: UPDATE work_orders SET status=cancelled,<br/>cancel_reason=customer_absent_cancel
        LINE->>DB: INSERT invoices<br/>(type: absence_fee, amount: 300, status: pending)
        LINE->>Customer: 「已取消本次服務」<br/>+「出場費 NT$300 將另行通知付款方式」
        LINE->>TechApp: 通知技師返回
        TechApp->>Technician: 「客戶取消服務，請返回」

    else 15 分鐘無任何回應
        SLA->>DB: UPDATE work_orders SET status=cancelled,<br/>cancel_reason=customer_no_show
        SLA->>DB: INSERT invoices<br/>(type: absence_fee, amount: 300, status: pending)
        SLA->>LINE: 最終通知
        LINE->>Customer: 「技師已等候 15 分鐘，無法聯繫到您」<br/>+「工單已暫停，出場費 NT$300 將另行收取」<br/>+「如需重新預約請回覆本訊息」
        SLA->>TechApp: 通知技師離場
        TechApp->>Technician: 「客戶未到場，工單暫停，請返回」
        SLA->>Admin: 通知管理員
        Admin->>AdminUser: 客戶不在場案件 (需後續跟進)
    end

    Note over DB: === 技師考核 ===
    Note over DB: 客戶不在場不計入技師負面記錄<br/>(not_technician_fault = true)
    DB->>DB: UPDATE customer_absence_log<br/>SET resolution, technician_penalty=false
```

### 19.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | `accepted` | `accepted` (substatus: customer_absent) | 技師到場但客戶不在 |
| 2a | customer_absent | `in_progress` | 客戶在 15 分鐘內到場 |
| 2b | customer_absent | `cancelled` + `created` (新單) | 客戶選擇改期 |
| 2c | customer_absent | `cancelled` | 客戶取消 / 15 分鐘無回應 |

### 19.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| T+0 min (到場) | LINE Push + 電話 | Customer | 技師到達通知 + 一鍵撥打 |
| T+5 min | LINE Push + 電話 | Customer | 第 2 次提醒 |
| T+10 min | LINE Flex + 電話 | Customer | 最後提醒 + 出場費告知 + 選項按鈕 |
| T+15 min (超時) | LINE Push | Customer | 工單暫停 + 出場費收取通知 |
| T+15 min (超時) | Web Alert | Admin | 客戶不在場案件需跟進 |
| 任意時刻客戶回覆 | Web Push | Technician | 客戶回應 (趕來/改期/取消) |

### 19.6 業務規則

| 編號 | 規則 | 說明 |
|------|------|------|
| BR-F11-001 | 等待時間上限 15 分鐘 | 含 3 次 LINE 推播 (5 分鐘間隔) |
| BR-F11-002 | 出場費 NT$300 | 不論取消或改期，均收取出場費 |
| BR-F11-003 | 技師不受負面記錄 | `technician_penalty = false`，客戶不在場非技師責任 |
| BR-F11-004 | 改期時出場費計入下次帳單 | 不另開帳單，隨下次工單合併收取 |
| BR-F11-005 | 客戶說「我馬上到」額外等候上限 15 分鐘 | 超過再次觸發本流程 |
| BR-F11-006 | 單一客戶 3 個月內 2 次不在場 | 標記為高風險客戶，後續工單要求預付訂金 |

---
