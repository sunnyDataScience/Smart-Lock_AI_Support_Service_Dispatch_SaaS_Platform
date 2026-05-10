---
id: SF-WO-12
title: payment flow (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-011 / F-012 (Q7=B)
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 12
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-12 — payment flow

> Work Order BF 的子流程 12 of 13。

## 20. Flow 12：金流與支付 — 對應 F-011 / F-012（V1.0，Q7=B 待 provider 選型）

> **Gap ID**：OP-01 — 原文件完全缺少付款階段，只有「帳務結清」一句帶過
>
> **Endpoints:** 待補（Week 3）：`createPayment`, `getPayment`, `issueInvoice`, `voidInvoice`；對應 schema `Invoice`（openapi.yaml#/components/schemas/Invoice）
> **Webhook（inbound）:** LINE Pay / 信用卡 / 現金（技師確認）— 帶 `X-Signature` + `Idempotency-Key`；失敗指數退避 1min → 24hr
> **Events In:** `work_order.billed`
> **Events Out:** `payment.confirmed`, `payment.failed`, `invoice.issued`, `invoice.voided`
> **Idempotency:** 所有金流 webhook 與 `createPayment` 強制 Idempotency-Key（24h 窗）
> **Error codes:** `PAYMENT_FAILED`, `PAYMENT_ALREADY_PROCESSED`, `INVOICE_ISSUE_FAILED`, `INVOICE_ALLOWANCE_INVALID`
> **Related pages:** A9（09_admin_accounting）+ 客戶 LINE 支付 Flex
> **SSOT schema:** `Invoice`（invoice_number 遵循 `^[A-Z]{2}\d{8}$` 格式、`category=service_fee|travel_fee|parts|other`、`status=pending|issued|allowance_pending|voided|reopened`）

### 20.1 觸發條件

- 工單狀態從 `confirmed` 轉為 `billed` (客戶確認完工後系統自動開帳)
- 人工補開帳單 (管理員手動觸發)

### 20.2 參與角色

Customer, Finance, Admin, Technician

### 20.3 支付方式矩陣

| 支付方式 | 金流服務商 | 手續費率 | 入帳時間 | 適用場景 |
|----------|-----------|---------|----------|----------|
| LINE Pay | LINE Pay API v3 | 2.75% | T+2 工作日 | LINE 內一鍵支付 (主推) |
| 信用卡 | 綠界 ECPay / 藍新 NewebPay | 2.5~3% | T+7 工作日 | 高單價工單 |
| 現金 | — | 0% | 即時 | 技師現場收款 (需回報) |

### 20.4 電子發票規格

| 項目 | 規格 | 說明 |
|------|------|------|
| 發票類型 | B2C 電子發票 | 財政部大平台 API |
| 載具 | 手機條碼 / 自然人憑證 / 會員載具 | 客戶 LINE 綁定時提供 |
| 格式 | 財政部 MIG 4.0 | JSON 格式上傳 |
| 發票時機 | 付款完成後 5 分鐘內 | 自動開立 |
| 保存期限 | 5 年 (依統一發票使用辦法) | — |

### 20.5 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant DB as PostgreSQL
    participant Billing as 帳務系統
    participant Payment as 金流服務商<br/>(LINE Pay / ECPay)
    participant Invoice as 電子發票<br/>(財政部 API)
    participant Admin as 管理員面板
    actor AdminUser as 管理員
    participant TechApp as 技師 Web App
    actor Technician as 技師

    Note over Billing: 工單 confirmed → 觸發帳務流程

    Billing->>DB: 查詢工單最終金額<br/>(final_price, breakdown)
    Billing->>DB: INSERT invoices<br/>(work_order_id, amount, status: issued)
    Billing->>DB: UPDATE work_orders SET status=billed

    Billing->>LINE: 發送帳單 Flex Message
    LINE->>Customer: 「請確認並支付服務費用」<br/>+ 帳單明細 (工資 / 車馬費 / 零件)<br/>+ 總金額 NT$X,XXX<br/>+ [LINE Pay 支付] [信用卡支付] [現場已付現金] 按鈕

    alt 選擇 LINE Pay
        Customer->>LINE: 點擊 [LINE Pay 支付]
        LINE->>Payment: 發起 LINE Pay Request API<br/>(orderId, amount, confirmUrl, cancelUrl)
        Payment-->>LINE: 付款頁面 URL
        LINE->>Customer: 跳轉 LINE Pay 付款畫面
        Customer->>Payment: 授權付款
        Payment->>Payment: Confirm API 確認扣款

        alt 付款成功
            Payment-->>Billing: Webhook: payment_confirmed<br/>(transactionId, amount)
            Billing->>DB: UPDATE invoices SET status=paid,<br/>payment_method=line_pay, transaction_id
            Billing->>DB: UPDATE work_orders SET status=archived

            Billing->>Invoice: 開立電子發票<br/>(buyer_identifier, amount, items)
            Invoice-->>Billing: invoice_number, invoice_date
            Billing->>DB: UPDATE invoices SET invoice_number

            Billing->>LINE: 付款成功通知
            LINE->>Customer: 「付款完成！」<br/>+ 電子發票資訊<br/>+ 交易編號

            Billing->>TechApp: 通知技師款項入帳
            TechApp->>Technician: 「工單 #xxx 客戶已付款」
        else 付款失敗
            Payment-->>Billing: Webhook: payment_failed<br/>(errorCode, errorMessage)
            Note over Billing: 觸發 EX5 帳款異常 (→ §21)
        end

    else 選擇信用卡
        Customer->>LINE: 點擊 [信用卡支付]
        LINE->>Payment: 建立綠界/藍新交易<br/>(MerchantTradeNo, TotalAmount, ReturnURL)
        Payment-->>LINE: 付款頁面 URL
        LINE->>Customer: 跳轉信用卡付款頁面
        Customer->>Payment: 輸入卡號完成付款

        alt 付款成功
            Payment-->>Billing: Webhook: payment_confirmed
            Billing->>DB: UPDATE invoices SET status=paid,<br/>payment_method=credit_card
            Billing->>DB: UPDATE work_orders SET status=archived
            Billing->>Invoice: 開立電子發票
            Billing->>LINE: 付款成功通知
            LINE->>Customer: 「信用卡付款完成！」+ 發票資訊
        else 付款失敗
            Payment-->>Billing: Webhook: payment_failed
            Note over Billing: 觸發 EX5 帳款異常 (→ §21)
        end

    else 現場已付現金
        Customer->>LINE: 點擊 [現場已付現金]
        LINE->>Billing: 現金付款聲明

        Billing->>TechApp: 請技師確認收款
        TechApp->>Technician: 「客戶聲明已付現金 NT$X,XXX，請確認」<br/>+ [確認已收款] [未收到款項]

        alt 技師確認收款
            Technician->>TechApp: 點擊 [確認已收款]
            TechApp->>DB: UPDATE invoices SET status=paid,<br/>payment_method=cash, confirmed_by=technician_id
            TechApp->>DB: UPDATE work_orders SET status=archived
            Billing->>Invoice: 開立電子發票
            Billing->>LINE: 付款確認 + 發票
            LINE->>Customer: 「現金收款確認完成！」+ 發票資訊
        else 技師未收到款項
            Technician->>TechApp: 點擊 [未收到款項]
            TechApp->>Admin: 通知管理員金額爭議
            Admin->>AdminUser: 金額爭議案件 (需人工確認)
            Note over Admin: 觸發 EX5-A 金額不符 (→ §21)
        end
    end
```

### 20.6 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 | 耗時預估 |
|------|----------|----------|----------|----------|
| 1 | `confirmed` | `billed` | 系統自動開立帳單 | < 1 秒 |
| 2a | `billed` | `archived` | LINE Pay / 信用卡 付款成功 | < 5 分鐘 |
| 2b | `billed` | `archived` | 現金付款 + 技師確認 | < 10 分鐘 |
| 2c | `billed` | `disputed` | 付款失敗 / 金額爭議 → EX5 | — |

### 20.7 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 帳單開立 | LINE Flex | Customer | 帳單明細 + 支付方式選擇 |
| 付款成功 | LINE Flex | Customer | 付款確認 + 電子發票 + 交易編號 |
| 付款成功 | Web Push | Technician | 款項入帳通知 |
| 付款失敗 | LINE Push | Customer | 付款失敗 + 重試選項 |
| 付款失敗 | Web Alert | Admin | 付款異常案件 |
| 帳單逾期 (7 天) | LINE Push | Customer | 付款提醒 |
| 現金確認請求 | Web Push | Technician | 確認現金收款 |

---
