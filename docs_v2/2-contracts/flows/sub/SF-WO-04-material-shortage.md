---
id: SF-WO-04
title: material shortage (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-007
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 4
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-04 — material shortage

> Work Order BF 的子流程 4 of 13。

## 7. Flow 4：缺料處理 — 對應 F-007

> **Endpoints（Week 4 補完）：** `createMaterialRequest`（`POST /work-orders/{id}/material-request`）, `getInventoryAvailability`
> **Events Out:** `work_order.material.requested`, `inventory.low_stock.alert`（若觸發閾值，走 G3）
> **Idempotency:** Required on 缺料申請
> **Error codes:** `MATERIAL_REQUEST_PENDING`, `INVENTORY_INSUFFICIENT`, `INVENTORY_PART_NOT_FOUND`
> **Related pages:** T6（19 缺料）→ A12 / A19 庫存 → G3 補貨流程（flows-admin-governance）


### 7.1 觸發條件

- 技師到場後發現所需零件未攜帶或庫存不足
- 零件型號與現場實際不符需特殊零件

### 7.2 參與角色

Technician, Customer, Admin, Dispatch_Engine

### 7.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant DB as PostgreSQL
    participant TechApp as 技師 Web App
    actor Technician as 技師
    participant Admin as 管理員面板
    actor AdminUser as 管理員
    participant Dispatch as 派工引擎

    Note over Technician: 技師到場，工單狀態為 in_progress

    Technician->>Technician: 現場診斷：需更換馬達模組<br/>但未攜帶該型號零件
    Technician->>TechApp: 提交「缺料報告」<br/>(缺件名稱、型號、數量、是否可替代)

    TechApp->>DB: INSERT material_request<br/>(part_name, part_model, qty, is_substitutable)
    TechApp->>DB: UPDATE work_orders SET status=material_pending

    TechApp->>Admin: 通知管理員缺料狀況
    Admin->>AdminUser: 顯示缺料工單 + 零件資訊

    AdminUser->>Admin: 查詢零件庫存 / 供應商

    alt 方案 A：部分修復 + 後續回訪
        Note over Technician: 可先執行部分修復<br/>(如：臨時供電恢復基本功能)

        Technician->>TechApp: 提交部分完工報告<br/>(已完成項目 + 待完成項目)
        TechApp->>LINE: 通知客戶部分修復完成
        LINE->>Customer: 「技師已完成臨時修復」<br/>+「零件到貨後將安排回訪」<br/>+ 預估備料時間

        AdminUser->>Admin: 確認零件到貨 ETA
        Admin->>DB: INSERT work_orders (新工單，linked_work_order_id)
        Admin->>DB: 原工單添加 linked_orders 關聯

        Note over Dispatch: 零件到貨後

        AdminUser->>Admin: 確認零件到位
        Admin->>Dispatch: 觸發回訪工單派工
        Dispatch->>TechApp: 推播回訪工單<br/>(優先派原技師)
        TechApp->>Technician: 回訪工單通知

    else 方案 B：暫停等待零件
        Note over Technician: 無法執行任何修復<br/>需等待零件到貨

        Technician->>TechApp: 回報現場無法作業
        TechApp->>LINE: 通知客戶需等待零件
        LINE->>Customer: 「所需零件需特別調貨」<br/>+ 預估到貨時間<br/>+ [接受等待] [取消服務] 按鈕

        alt 客戶接受等待
            Customer->>LINE: 點擊 [接受等待]
            LINE->>DB: 記錄客戶確認等待
            LINE->>Customer: 「零件到貨後將第一時間通知您」

            Note over Admin: 備料到位 (72 小時內)

            AdminUser->>Admin: 確認零件到位
            Admin->>LINE: 通知客戶零件已到
            LINE->>Customer: 「零件已到貨，請選擇回訪時段」
            Customer->>LINE: 選擇時段
            Admin->>Dispatch: 安排回訪派工

        else 客戶取消服務
            Customer->>LINE: 點擊 [取消服務]
            LINE->>DB: UPDATE work_orders SET status=cancelled,<br/>cancel_reason=material_shortage
            LINE->>Customer: 「已取消本次服務，不收取任何費用」
            LINE->>Admin: 通知管理員客戶取消

            Note over DB: 業務規則：<br/>因缺料取消不收取任何費用<br/>(含車馬費全額免除)
        end
    end
```

### 7.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | `in_progress` | `material_pending` | 技師回報缺料 |
| 2a | `material_pending` | `completed` (部分) | 部分修復完成 + 建立回訪工單 |
| 2b | `material_pending` | `material_pending` | 等待零件到貨 |
| 3a | `material_pending` | `in_progress` | 備料到位 → 繼續作業 |
| 3b | `material_pending` | `cancelled` | 客戶不願等待取消 |
| 回訪 | `created` (新工單) | ... | 備料完成後建立新工單 |

### 7.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 缺料回報 | Web Alert | Admin | 缺件名稱、型號、工單編號 |
| 缺料回報 | LINE Push | Customer | 缺料狀況說明 + 預估備料時間 |
| 部分修復完成 | LINE Flex | Customer | 已完成項目 + 回訪時程 |
| 零件到位 | LINE Push | Customer | 零件到貨通知 + 預約回訪 |
| 零件到位 | Web Push | Technician | 回訪工單通知 |
| 72 小時未到貨 | Web Alert | Admin | 備料超時警報 |

---
