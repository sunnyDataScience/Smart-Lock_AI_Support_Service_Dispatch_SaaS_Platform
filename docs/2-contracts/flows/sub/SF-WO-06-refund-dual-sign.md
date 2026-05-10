---
id: SF-WO-06
title: refund dual sign (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-013 / F-014
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 6
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-06 — refund dual sign

> Work Order BF 的子流程 6 of 13。

## 9. Flow 6：退款審批與大額雙簽 — 對應 F-013 / F-014

> **Endpoints:** `openapi#operationId=submitRefundDecision`（Idempotency 必填）；待補：`listRefunds`, `getRefund`, `submitRefundSignature`（Week 3）
> **Events In:** `refund.requested`（客戶發起）
> **Events Out:** `refund.decision.made` (`/realtime/refunds`)，含 `dual_sign_pending=true`；完成後 `refund.completed`
> **Idempotency:** Required on `submitRefundDecision`（避免重覆審核）及第二簽核（Step 7-9）
> **Error codes:** `REFUND_DUAL_SIGN_REQUIRED`（金額 > 5000 或 100,000）, `REFUND_DECISION_LOCKED`
> **Dual-sign thresholds:** NT$ 5,000（第二簽核 `accountant`）; NT$ 100,000（升級 `tenant_admin`）
> **Related pages:** A17（10_admin_advanced 退款子頁）→ G4 爭議銜接

### 9.1 觸發條件

- 客戶透過 LINE 或客服申請退款
- 工單完成後客戶對服務品質/收費不滿
- 爭議處理結果為退款

### 9.2 參與角色

Customer, Admin, Finance

### 9.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant DB as PostgreSQL
    participant CSR as 客服人員
    participant Admin as 管理員面板
    actor CSRMgr as 客服主管
    actor OpsMgr as 營運主管
    actor FinMgr as 財務主管
    participant Finance as 財務系統

    Note over Customer: 客戶對收費有異議，申請退款

    Customer->>LINE: 「我要申請退款，收費不合理」
    LINE->>CSR: 轉接人工客服

    CSR->>DB: 調出工單記錄 + 帳單明細 + 對話歷史
    CSR->>Customer: 了解退款原因、核實情況

    CSR->>DB: INSERT refund_request<br/>(work_order_id, amount, reason, evidence)

    Note over CSR: === 退款金額分級審批 ===

    alt 金額 <= $10,000 (一般退款)
        Note over CSR: 層級 1：客服主管審批

        CSR->>Admin: 提交退款申請至客服主管
        Admin->>CSRMgr: 顯示退款申請 + 佐證資料

        alt 客服主管核准
            CSRMgr->>Admin: 核准退款
            Admin->>DB: UPDATE refund_request SET status=approved,<br/>approved_by=CSR_Mgr
            Admin->>Finance: 發送退款執行指令
        else 客服主管駁回
            CSRMgr->>Admin: 駁回 + 填寫理由
            Admin->>DB: UPDATE refund_request SET status=rejected
            Admin->>LINE: 通知客戶駁回原因
            LINE->>Customer: 退款申請結果 + 替代方案
        end

    else 金額 $10,001 ~ $100,000 (中額退款)
        Note over CSR: 層級 2：營運主管審批

        CSR->>Admin: 提交退款申請至營運主管
        Admin->>OpsMgr: 顯示退款申請 + 完整工單歷史

        alt 營運主管核准
            OpsMgr->>Admin: 核准退款
            Admin->>DB: UPDATE refund_request SET status=approved,<br/>approved_by=Ops_Mgr
            Admin->>Finance: 發送退款執行指令
        else 營運主管駁回
            OpsMgr->>Admin: 駁回 + 填寫理由
            Admin->>LINE: 通知客戶
            LINE->>Customer: 退款申請結果 + 申訴管道
        end

    else 金額 > $100,000 (大額退款 — 雙簽制度)
        Note over CSR: 層級 3：營運主管 + 財務主管 雙簽

        CSR->>Admin: 提交退款申請 (標記為大額)
        Admin->>OpsMgr: 第一簽：營運主管審核
        OpsMgr->>Admin: 第一簽核准 ✓

        Note over Admin: 第一簽完成，等待第二簽<br/>SLA：24 小時內完成雙簽

        Admin->>FinMgr: 第二簽：財務主管審核
        FinMgr->>Admin: 審核帳務影響 + 預算確認

        alt 雙簽通過
            FinMgr->>Admin: 第二簽核准 ✓
            Admin->>DB: UPDATE refund_request SET status=dual_approved,<br/>approver_1=Ops_Mgr, approver_2=Fin_Mgr
            Admin->>Finance: 發送退款執行指令

            Note over Finance: 大額退款需額外通知 CEO
            Finance->>DB: 記錄 CEO 通知已發送
        else 任一方駁回
            Admin->>DB: UPDATE refund_request SET status=rejected
            Admin->>LINE: 通知客戶 + 提供替代方案
            LINE->>Customer: 退款申請結果 + 協商管道
        end
    end

    Note over Finance: === 退款執行 ===

    Finance->>Finance: 確認退款帳戶資訊
    Finance->>DB: INSERT refund_transaction<br/>(amount, method, target_account)
    Finance->>Finance: 執行退款轉帳

    alt 退款成功
        Finance->>DB: UPDATE refund_request SET status=executed
        Finance->>DB: UPDATE invoices SET status=refunded (全額)<br/>或 adjustment (部分退款)
        Finance->>LINE: 通知客戶退款完成
        LINE->>Customer: 「退款 $X,XXX 已處理」<br/>+「預計 3~5 個工作日到帳」
    else 退款失敗
        Finance->>Admin: 退款執行失敗通知
        Admin->>CSR: 人工跟進處理
    end

    Note over Finance: === 審批逾時自動升級 ===

    alt 審批超過 48 小時未處理
        DB->>Admin: SLA 違反警報
        Admin->>OpsMgr: 自動升級至上級
    end
```

### 9.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | — | `refund_pending` | 客服建立退款申請 |
| 2a | `refund_pending` | `refund_approved` | 單簽核准 (<= $100K) |
| 2b | `refund_pending` | `refund_dual_approved` | 雙簽核准 (> $100K) |
| 2c | `refund_pending` | `refund_rejected` | 審批駁回 |
| 3 | `refund_approved` / `refund_dual_approved` | `refund_executed` | 財務完成退款 |
| 4 | `refund_executed` | `refund_failed` | 退款轉帳失敗 |

### 9.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 退款申請建立 | Web Alert | 審批人 (依金額) | 退款申請詳情 |
| 審批完成 | LINE Push | Customer | 審批結果 |
| 雙簽第一簽 | Web Alert | 財務主管 | 等待第二簽 |
| 退款執行完成 | LINE Flex | Customer | 退款金額 + 到帳預估 |
| 退款失敗 | Web Alert | Admin, Finance | 需人工跟進 |
| 審批超時 | Web Alert | 上級主管 | SLA 違反自動升級 |
| 大額退款 (> $100K) | Email | CEO | 大額退款通知 |

### 9.6 審批層級表

| 退款金額 | 審批層級 | 審批人 | SLA |
|----------|----------|--------|-----|
| <= $10,000 | 單簽 | 客服主管 | 24 小時 |
| $10,001 ~ $100,000 | 單簽 | 營運主管 | 24 小時 |
| > $100,000 | 雙簽 | 營運主管 + 財務主管 | 24 小時 (每簽) |
| > $100,000 (核准後) | 通知 | CEO | 知會 (不需核准) |

---
