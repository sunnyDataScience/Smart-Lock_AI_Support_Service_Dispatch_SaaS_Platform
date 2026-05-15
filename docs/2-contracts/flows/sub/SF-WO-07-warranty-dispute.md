---
id: SF-WO-07
title: warranty dispute (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-015
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 7
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-07 — warranty dispute

> Work Order BF 的子流程 7 of 13。

## 10. Flow 7：保固爭議 — 對應 F-015

> **Endpoints（Week 4 補完）：** `createWarrantyClaim`, `verifyWarrantyPeriod`, `proposeDiscountCompromise`
> **Events Out:** `warranty.claim.created`, `warranty.claim.resolved`, `warranty.out_of_period.declined`
> **Idempotency:** Required on 建立索賠
> **Error codes:** `WARRANTY_OUT_OF_PERIOD`, `DISPUTE_SLA_OVERDUE`
> **Related pages:** A21 保固索賠 → A22 爭議（升級）→ G4 爭議仲裁（flows-admin-governance §5）
> **Note:** 與 G4 分界 — 本 Flow 處理「保固認定 + 修復」；G4 處理「金額賠償裁決」


### 10.1 觸發條件

- 客戶宣稱產品在保固期內故障
- 保固起算日認定有爭議 (常見：點交日 vs 入住日)
- 保固期邊界案件

### 10.2 參與角色

Customer, AI_System, Admin

### 10.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant AI as AI 系統
    participant DB as PostgreSQL
    participant Admin as 管理員面板
    actor AdminUser as 管理員/客服
    participant ProjectDB as 建案資料庫
    participant Dispatch as 派工引擎

    Customer->>LINE: 「我的電子鎖壞了，還在保固期內」
    LINE->>AI: 客戶訊息

    AI->>AI: 偵測「保固」關鍵詞<br/>→ 標記為高風險案件

    Note over AI: 業務規則（鐵律）：<br/>涉及建案/保固期案件<br/>AI 嚴禁報價，必須轉真人

    AI->>DB: 查詢客戶地址關聯的建案資訊

    alt 非建案客戶 (一般零售)
        AI->>DB: 查詢 purchase_date / warranty_start_date
        AI->>AI: 計算保固到期日<br/>(warranty_start_date + warranty_period)

        alt 保固期內 (明確)
            AI->>LINE: 回覆客戶
            LINE->>Customer: 「經查您的產品保固至 YYYY-MM-DD」<br/>+「保固期內免費維修」<br/>+「正在為您安排技師」

            AI->>DB: INSERT work_orders<br/>(warranty_repair=true, price=0)
            AI->>Dispatch: 觸發免費維修派工

        else 保固已過期 (明確)
            AI->>LINE: 回覆客戶
            LINE->>Customer: 「您的產品保固已於 YYYY-MM-DD 到期」<br/>+ 保固條款說明<br/>+「提供維修 8 折優惠」<br/>+ [預約付費維修] [聯繫客服]

        else 保固期邊界 (±30 天內)
            Note over AI: 邊界案件 → 轉真人處理
            AI->>Admin: 轉接人工：保固期邊界案件
            Admin->>AdminUser: 顯示案件 + 保固資訊
            AdminUser->>Customer: 人工判斷處理
        end

    else 建案客戶 (社區/建商專案)
        Note over AI: 建案案件鐵律：<br/>保固起算日 = 建商點交日<br/>（非住戶入住日）

        AI->>Admin: 強制轉人工處理
        Admin->>AdminUser: 顯示案件：建案保固查詢

        AdminUser->>ProjectDB: 查詢建案資料<br/>(社區名稱, 建商, 點交日, 保固期限)
        ProjectDB-->>AdminUser: 建案資料<br/>(點交日: 2025-01-15, 保固: 1 年)

        AdminUser->>AdminUser: 計算保固到期日<br/>(2025-01-15 + 1 年 = 2026-01-15)

        alt 保固有效
            AdminUser->>LINE: 回覆客戶
            LINE->>Customer: 「經查貴社區保固至 2026-01-15」<br/>+「將安排免費維修」
            AdminUser->>Dispatch: 派工 (warranty_repair=true)

        else 保固已過期，客戶無異議
            AdminUser->>LINE: 回覆客戶
            LINE->>Customer: 「貴社區保固已於 2026-01-15 到期」<br/>+ 保固條款<br/>+「提供維修 8 折優惠」

        else 保固已過期，客戶有異議
            Note over AdminUser: 客戶堅持「住進來才半年」<br/>保固起算日有爭議

            AdminUser->>LINE: 回覆客戶
            LINE->>Customer: 說明保固條款<br/>「保固自建商點交日起算」<br/>+ 出示書面依據

            alt 客戶接受
                Customer->>LINE: 接受付費維修
                AdminUser->>Dispatch: 派工 (付費)
            else 客戶不接受 → 正式爭議
                Customer->>LINE: 「我不接受，要投訴」
                LINE->>DB: INSERT complaint<br/>(type=warranty_dispute)
                AdminUser->>Admin: 建立爭議案件
                AdminUser->>AdminUser: 收集證據<br/>(購買合約、點交記錄、保固書)

                Note over AdminUser: 爭議處理流程<br/>→ 參見 Flow 9 客訴生命週期

                AdminUser->>LINE: 提供折衷方案
                LINE->>Customer: 「考量您的情況，提供維修費 5 折」
            end
        end
    end
```

### 10.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | — | `created` | 保固查詢 → 確認免費維修 → 建立工單 |
| 2 | — | — | 保固過期 → 客戶選擇付費維修 → 建立工單 |
| 3 | — | `disputed` | 保固認定爭議 → 進入爭議流程 |

### 10.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 保固關鍵詞觸發 | Web Alert | Admin | 高風險案件：保固查詢 |
| 建案案件 | Web Alert | Admin | 強制轉人工：建案保固 |
| 保固確認 (有效) | LINE Flex | Customer | 保固期限 + 免費維修安排 |
| 保固確認 (過期) | LINE Flex | Customer | 到期日 + 優惠方案 |
| 爭議建立 | Web Alert | Admin | 保固爭議案件 |

### 10.6 業務規則

| 規則 | 說明 |
|------|------|
| 保固起算日 | 建案客戶 = 建商點交日；零售客戶 = 購買日 |
| AI 報價禁令 | 涉及建案/保固案件，AI 嚴禁自動報價 |
| 邊界案件 | 保固到期前後 30 天內的案件一律轉人工 |
| 善意折讓 | 保固剛過期 (< 90 天) 可提供 8 折優惠 |
| 證據保存 | 所有保固認定需保留書面查詢記錄 |

---
