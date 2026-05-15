---
id: SF-WO-03
title: scope change (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-008
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 3
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-03 — scope change

> Work Order BF 的子流程 3 of 13。

## 6. Flow 3：範圍變更 — 對應 F-008

> **Endpoints（Week 4 補完）：** `createScopeChangeRequest`（`POST /work-orders/{id}/scope-change`）, `approveScopeChange`, `rejectScopeChange`
> **Events Out:** `work_order.scope.change_requested`, `work_order.scope.change_approved|rejected`
> **Idempotency:** Required on 新增 scope change（避免雙送報價）
> **Error codes:** `SCOPE_CHANGE_REJECTED`, `WORK_ORDER_STATUS_INVALID`（非 `in_progress` 不能改）
> **Related pages:** T5（19 範圍變更）→ A12 管理員審核 → 客戶 LINE Flex 確認


### 6.1 觸發條件

- 技師到場後發現現場狀況與 ProblemCard 描述不符
- 需要額外工序 (如：門扇加工、更換型號)
- 維修範圍擴大導致報價變動

### 6.2 參與角色

Technician, Customer, Admin, Dispatch_Engine

### 6.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant DB as PostgreSQL
    participant TechApp as 技師 Web App
    actor Technician as 技師
    participant Pricing as 報價引擎
    participant Admin as 管理員面板
    actor AdminUser as 管理員

    Note over Technician: 技師到場，工單狀態為 in_progress

    Technician->>Technician: 現場勘查：發現門扇為非標準厚度<br/>需額外切割加工
    Technician->>TechApp: 提交「範圍變更申請」<br/>(變更原因、新增工項、現場照片)

    TechApp->>DB: INSERT scope_change_request<br/>(original_scope, new_scope, reason, photos)
    TechApp->>DB: UPDATE work_orders SET status=scope_changed

    TechApp->>Pricing: 重新計價 (新增工項)
    Pricing-->>TechApp: 新報價明細<br/>(原報價 $1,800 → 新報價 $2,600)

    Note over TechApp: 業務規則：<br/>新報價 > 原報價 2 倍 → 需技術主管審核

    alt 報價差異 <= 2 倍
        TechApp->>LINE: 發送報價變更通知 (Flex Message)
        LINE->>Customer: 「現場勘查後發現需額外加工」<br/>+ 原報價 vs 新報價比較<br/>+ 變更原因說明 + 現場照片<br/>+ [核准] [拒絕] 按鈕
    else 報價差異 > 2 倍
        TechApp->>Admin: 提交技術主管審核
        Admin->>AdminUser: 顯示範圍變更審核單
        AdminUser->>Admin: 審核通過 / 調整報價
        Admin->>LINE: 發送審核後報價變更通知
        LINE->>Customer: 變更通知 (含主管審核標記)
    end

    Note over Customer: 客戶 24 小時內需回應

    alt 客戶核准新報價
        Customer->>LINE: 點擊 [核准]
        LINE->>DB: UPDATE scope_change_request SET status=approved
        LINE->>DB: UPDATE work_orders SET status=in_progress,<br/>estimated_price=new_price
        LINE->>TechApp: 通知技師「客戶已核准變更」
        TechApp->>Technician: 「客戶已同意新報價，請繼續作業」
        Technician->>Technician: 繼續施工

    else 客戶拒絕新報價
        Customer->>LINE: 點擊 [拒絕]
        LINE->>DB: UPDATE scope_change_request SET status=rejected

        Note over LINE: 提供替代方案

        LINE->>Customer: 「請選擇後續處理方式」<br/>+ [僅完成原始範圍] [取消並改期] [聯繫客服]

        alt 僅完成原始範圍
            Customer->>LINE: 選擇 [僅完成原始範圍]
            LINE->>DB: UPDATE work_orders SET status=in_progress
            LINE->>TechApp: 通知技師僅執行原始範圍
            TechApp->>Technician: 「客戶選擇原始範圍，請依原報價施工」
        else 取消並改期
            Customer->>LINE: 選擇 [取消並改期]
            LINE->>DB: UPDATE work_orders SET status=cancelled,<br/>cancel_reason=scope_change_rejected
            LINE->>Customer: 「已取消本次服務，客服將與您聯繫重新安排」
            LINE->>Admin: 通知管理員需重新安排
        else 聯繫客服
            Customer->>LINE: 選擇 [聯繫客服]
            LINE->>Admin: 轉接人工客服
            AdminUser->>Customer: 電話溝通協商方案
        end
    end
```

### 6.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | `in_progress` | `scope_changed` | 技師提交範圍變更 |
| 2a | `scope_changed` | `in_progress` | 客戶核准新報價 |
| 2b | `scope_changed` | `in_progress` | 客戶選擇僅完成原始範圍 |
| 2c | `scope_changed` | `cancelled` | 客戶拒絕且選擇取消 |

### 6.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 範圍變更提交 | LINE Flex | Customer | 原報價 vs 新報價 + 變更原因 + 照片 |
| 報價 > 2 倍 | Web Alert | Admin | 需技術主管審核 |
| 客戶核准 | Web Push | Technician | 客戶已同意新報價 |
| 客戶拒絕 | Web Push | Technician | 客戶選擇方案 (原範圍/取消/協商) |
| 24 小時未回應 | LINE Push | Customer | 提醒確認範圍變更 |
| 24 小時未回應 | Web Alert | Admin | 範圍變更超時未回應 |

---
