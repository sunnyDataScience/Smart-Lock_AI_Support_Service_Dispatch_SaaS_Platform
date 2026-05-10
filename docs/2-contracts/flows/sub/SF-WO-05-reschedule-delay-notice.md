---
id: SF-WO-05
title: reschedule delay notice (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-010
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 5
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-05 — reschedule delay notice

> Work Order BF 的子流程 5 of 13。

## 8. Flow 5：延遲通知與改期 — 對應 F-010

> **Endpoints:** `postDelayNotification`（Week 4）, `getTechnicianAvailability`, `proposeReschedule`（T11）
> **Events Out:** `work_order.delay.notified`, `work_order.reschedule.proposed`, `work_order.reschedule.confirmed_by_customer`
> **Idempotency:** Required on 延遲通知 + 改期提案
> **Error codes:** `DELAY_NOTIFICATION_LIMIT_EXCEEDED`, `RESCHEDULE_LIMIT_EXCEEDED`, `RESCHEDULE_SLOT_TAKEN`, `RESCHEDULE_RSVP_EXPIRED`
> **Related pages:** T7（19 延遲）→ **T11 改期日曆** → 客戶 LINE Flex RSVP（19 T1.4 補強）


### 8.1 觸發條件

- 技師預計無法在預約時段內到達
- 維修作業時間超出預估
- 交通或天氣等外部因素導致延遲

### 8.2 參與角色

Technician, Customer, Admin

### 8.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant DB as PostgreSQL
    participant TechApp as 技師 Web App
    actor Technician as 技師
    participant SLA as SLA 監控
    participant Admin as 管理員面板
    actor AdminUser as 管理員

    Note over Technician: 技師在前往途中遇到交通壅塞

    Technician->>TechApp: 回報延遲<br/>(原因：交通壅塞，新 ETA：15:00)
    TechApp->>DB: INSERT delay_notification<br/>(reason, original_eta, new_eta)
    TechApp->>DB: UPDATE work_orders SET status=delayed

    TechApp->>SLA: 計算延遲嚴重度

    alt 輕微延遲 (<=15 分鐘)
        SLA->>SLA: 記錄但不通知
        Note over SLA: 在 ±30 分鐘容許範圍內

    else 中度延遲 (15~30 分鐘)
        SLA->>LINE: 自動通知客戶
        LINE->>Customer: 「技師因交通狀況稍有延遲」<br/>+「新的預計到達時間：15:00」<br/>+「造成不便敬請見諒」

    else 嚴重延遲 (>30 分鐘)
        SLA->>LINE: 通知客戶 + 提供選項
        LINE->>Customer: 「技師因交通狀況延遲超過 30 分鐘」<br/>+ 新 ETA<br/>+ [繼續等待] [改期] [取消] 按鈕

        SLA->>Admin: 觸發管理員警報
        Admin->>AdminUser: 顯示延遲警報 (工單 + 延遲時間)

        alt 客戶選擇繼續等待
            Customer->>LINE: 點擊 [繼續等待]
            LINE->>DB: 記錄客戶確認等待

            Note over DB: 業務規則：<br/>嚴重延遲 → 自動產生補償方案<br/>(如：車馬費減免 $100)

            LINE->>Customer: 「感謝您的耐心等候」<br/>+「將為您減免車馬費 $100 作為補償」

        else 客戶選擇改期
            Customer->>LINE: 點擊 [改期]
            LINE->>Customer: 「請選擇新的預約時段」
            Customer->>LINE: 選擇新時段

            LINE->>DB: UPDATE work_orders SET status=cancelled,<br/>cancel_reason=rescheduled
            LINE->>DB: INSERT work_orders (新工單，新時段)
            LINE->>TechApp: 通知技師本次工單取消
            TechApp->>Technician: 「客戶已改期，請返回」
            LINE->>Customer: 「已為您重新安排 [新時段]」

        else 客戶選擇取消
            Customer->>LINE: 點擊 [取消]
            LINE->>DB: UPDATE work_orders SET status=cancelled,<br/>cancel_reason=delay_cancellation

            Note over DB: 業務規則：<br/>因技師延遲導致客戶取消 → 不收費<br/>技師記錄延遲扣分

            LINE->>Customer: 「已取消本次服務，不收取任何費用」
            LINE->>TechApp: 通知技師工單取消
            TechApp->>Technician: 「客戶已取消，請返回」
            Admin->>DB: UPDATE technicians 延遲記錄 +1
        end
    end

    Note over SLA: === 作業中延遲 ===

    alt 作業時間超出預估
        Note over Technician: 維修進行中，發現問題比預期複雜

        Technician->>TechApp: 回報作業延遲<br/>(原因：問題複雜度高，預計加時 1 小時)
        TechApp->>DB: UPDATE delay_notification (作業延遲)
        TechApp->>LINE: 通知客戶
        LINE->>Customer: 「維修作業需要更多時間處理」<br/>+「預計額外需要 1 小時」
    end
```

### 8.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | `accepted` / `in_progress` | `delayed` | 技師回報延遲 |
| 2a | `delayed` | `in_progress` | 輕微延遲 → 技師到場 |
| 2b | `delayed` | `cancelled` + `created` | 客戶改期 → 取消舊單 + 建新單 |
| 2c | `delayed` | `cancelled` | 客戶取消 |

### 8.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 中度延遲 (15~30 min) | LINE Push | Customer | 延遲說明 + 新 ETA |
| 嚴重延遲 (>30 min) | LINE Flex | Customer | 延遲說明 + 繼續/改期/取消 選項 |
| 嚴重延遲 (>30 min) | Web Alert | Admin | 延遲警報 + 工單資訊 |
| 客戶確認等待 | — | — | 自動產生補償方案 |
| 客戶改期 | Web Push | Technician | 本次工單取消，客戶已改期 |
| 作業延遲 | LINE Push | Customer | 預計額外所需時間 |

### 8.6 補償規則

| 延遲程度 | 補償方案 | 自動/人工 |
|----------|----------|-----------|
| 15~30 分鐘 | 無補償 (在 SLA 容許範圍) | — |
| 30~60 分鐘 | 車馬費減免 $100 | 自動 |
| > 60 分鐘 | 車馬費全免 + $200 折扣碼 | 自動 |
| 技師未到 (no-show) | 全額免費 + $500 折扣碼 + 優先重派 | 自動 + 人工跟進 |

---
