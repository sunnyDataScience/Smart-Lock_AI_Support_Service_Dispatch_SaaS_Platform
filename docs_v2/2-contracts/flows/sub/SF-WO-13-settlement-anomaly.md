---
id: SF-WO-13
title: settlement anomaly (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-013 / F-014 / F-021
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 13
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-13 — settlement anomaly

> Work Order BF 的子流程 13 of 13。

## 21. Flow 13：帳款異常 EX5 — 對應 F-013 / F-014 / F-021

> **Endpoints（Week 4 補完）：** `flagBillingException`, `reopenInvoice`, `issueAllowance`, `retryPayment`
> **Webhook（inbound）:** 金流三平台 `payment.failed` / `payment.refund.failed`
> **Events Out:** `invoice.voided`, `invoice.allowance.issued`, `billing.exception.flagged`
> **Idempotency:** Required on 發票重開 / 折讓 / 重試付款
> **Error codes:** `INVOICE_VOID_WINDOW_EXPIRED`, `INVOICE_DUPLICATE_NUMBER`, `WEBHOOK_AMOUNT_MISMATCH`, `PAYMENT_ALREADY_PROCESSED`
> **Related pages:** A9 帳務 / A20 稽核 + webhook-spec §4 發票規範


> **Gap ID**：OP-02 — 原文件缺少付款失敗、金額不符、發票錯誤的處理流程

### 21.1 觸發條件

- EX5-A：客戶/技師回報金額與帳單不符
- EX5-B：線上付款失敗 (卡號錯誤、餘額不足、交易逾時)
- EX5-C：電子發票開立錯誤 (品項、金額、載具錯誤)

### 21.2 參與角色

Customer, Finance, Admin, Technician

### 21.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant DB as PostgreSQL
    participant Billing as 帳務系統
    participant Payment as 金流服務商
    participant Invoice as 電子發票<br/>(財政部 API)
    participant Admin as 管理員面板
    actor AdminUser as 管理員
    actor FinUser as 財務人員

    Note over Billing: === EX5-A：金額不符 ===

    alt EX5-A 金額不符
        Customer->>LINE: 「帳單金額跟技師說的不一樣」
        LINE->>Billing: 金額爭議通知

        Billing->>DB: SELECT final_price, breakdown<br/>FROM work_orders WHERE id = ?
        Billing->>Billing: 計算差額<br/>|客戶聲稱金額 - 帳單金額|

        alt 差額 < NT$100 (自動修正)
            Billing->>DB: UPDATE invoices SET amount = corrected_amount,<br/>correction_reason, auto_corrected=true
            Billing->>Invoice: 作廢原發票 + 重新開立
            Invoice-->>Billing: 新發票號碼
            Billing->>LINE: 通知客戶已修正
            LINE->>Customer: 「帳單金額已修正為 NT$X,XXX」<br/>+ 新發票資訊

        else 差額 >= NT$100 (人工審核)
            Billing->>Admin: 建立金額爭議案件
            Admin->>AdminUser: 顯示爭議明細<br/>(帳單金額 vs 客戶聲稱 vs 技師回報)

            AdminUser->>DB: 調閱完工報告 + 報價記錄
            AdminUser->>AdminUser: 核對實際工項與收費

            alt 帳單金額正確
                AdminUser->>LINE: 說明帳單計算依據
                LINE->>Customer: 費用明細說明 + 計算邏輯
            else 帳單金額有誤
                AdminUser->>Billing: 修正帳單金額
                Billing->>DB: UPDATE invoices SET amount = corrected
                Billing->>Invoice: 作廢原發票 + 重新開立
                Billing->>LINE: 通知客戶已修正
                LINE->>Customer: 「帳單已修正，造成不便敬請見諒」
            end
        end
    end

    Note over Billing: === EX5-B：付款失敗 ===

    alt EX5-B 付款失敗
        Payment-->>Billing: Webhook: payment_failed<br/>(errorCode, errorMessage)
        Billing->>DB: INSERT payment_attempts<br/>(invoice_id, attempt=1, status=failed, error)
        Billing->>DB: UPDATE invoices SET payment_status=retry_pending

        Billing->>LINE: 付款失敗通知
        LINE->>Customer: 「付款未成功，請確認卡片資訊」<br/>+ 錯誤原因 (餘額不足/卡號錯誤/逾時)<br/>+ [重新支付] 按鈕

        loop 重試最多 3 次 (間隔 24hr)
            Customer->>LINE: 點擊 [重新支付]
            LINE->>Payment: 重新發起付款
            Payment-->>Billing: payment_result

            alt 第 N 次重試成功
                Billing->>DB: UPDATE invoices SET status=paid
                Billing->>DB: UPDATE work_orders SET status=archived
                Billing->>LINE: 付款成功
                LINE->>Customer: 「付款完成！」
            else 第 N 次重試仍失敗
                Billing->>DB: UPDATE payment_attempts<br/>(attempt=N, status=failed)
            end
        end

        Note over Billing: 3 次付款失敗後

        Billing->>DB: UPDATE invoices SET payment_status=manual_collection
        Billing->>Admin: 轉人工催款
        Admin->>FinUser: 建立催款案件<br/>(客戶聯絡資訊 + 帳單 + 失敗記錄)
        FinUser->>Customer: 電話聯繫付款事宜
    end

    Note over Invoice: === EX5-C：發票錯誤 ===

    alt EX5-C 發票錯誤
        Customer->>LINE: 「發票資訊有誤，需要修改」
        LINE->>Billing: 發票更正請求

        Billing->>DB: 查詢原發票資訊
        Billing->>Invoice: 作廢原發票<br/>(void API, reason: correction)
        Invoice-->>Billing: void_result (success/fail)

        alt 作廢成功
            Billing->>Invoice: 重新開立正確發票<br/>(corrected items, carrier, amount)
            Invoice-->>Billing: new_invoice_number
            Billing->>DB: UPDATE invoices SET<br/>invoice_number=new, correction_count+=1
            Billing->>LINE: 通知客戶新發票
            LINE->>Customer: 「發票已更正」<br/>+ 新發票號碼 + 明細
        else 作廢失敗 (已逾作廢期限)
            Billing->>Admin: 通知財務人員手動處理
            Admin->>FinUser: 需開立折讓單
            FinUser->>Invoice: 開立折讓 + 重新開立
            FinUser->>LINE: 通知客戶處理結果
            LINE->>Customer: 「發票已透過折讓方式更正」
        end

        Note over Billing: SLA：發票更正 2 小時內完成
    end
```

### 21.4 狀態轉換表

| 步驟 | 異常類型 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|----------|
| 1a | EX5-A | `billed` | `billed` (修正) | 差額 < $100 自動修正 |
| 1b | EX5-A | `billed` | `disputed` | 差額 >= $100 人工審核 |
| 2a | EX5-B | `billed` | `billed` (retry) | 付款失敗 → 重試 |
| 2b | EX5-B | `billed` | `billed` (manual) | 3 次失敗 → 人工催款 |
| 3 | EX5-C | `billed` / `archived` | 不變 | 發票作廢 + 重開 |

### 21.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 金額不符 (自動修正) | LINE Push | Customer | 帳單已修正 + 新發票 |
| 金額不符 (人工審核) | Web Alert | Admin | 金額爭議案件 |
| 付款失敗 | LINE Flex | Customer | 失敗原因 + 重新支付按鈕 |
| 3 次失敗 | Web Alert | Finance | 轉人工催款 |
| 發票更正完成 | LINE Push | Customer | 新發票號碼 + 明細 |
| 發票更正超時 | Web Alert | Finance | 超過 2hr SLA |

### 21.6 業務規則

| 編號 | 規則 | 閾值 | 動作 |
|------|------|------|------|
| BR-EX5-001 | 金額不符自動修正閾值 | 差額 < NT$100 | 系統自動修正 + 重開發票 |
| BR-EX5-002 | 金額不符人工審核閾值 | 差額 >= NT$100 | 建立爭議案件 → 人工核對 |
| BR-EX5-003 | 付款重試次數上限 | 3 次 | 超過轉人工催款 |
| BR-EX5-004 | 付款重試間隔 | 24 小時 | 每 24hr 發送一次付款提醒 |
| BR-EX5-005 | 發票更正 SLA | 2 小時 | 超時升級至財務主管 |
| BR-EX5-006 | 單一工單發票修正次數上限 | 3 次 | 超過需財務主管審核 |

---
