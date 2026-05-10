# 退款審批流程規格書 (Refund Approval Specification)

> GAP #11 -- Smart Lock AI Support Service Dispatch SaaS Platform

---

## 1. 概述 (Overview)

本規格定義智慧門鎖服務派遣平台的退款審批流程。退款申請須經過
簽核鏈 (approval chain) 審批，依金額門檻區分為單簽與雙簽兩種路徑。
所有狀態變更皆記錄於 `approval_chain` JSONB 欄位，確保完整稽核軌跡。

---

## 2. 商業規則 (Business Rules)

| 編號 | 規則 | 說明 |
|------|------|------|
| BR-REFUND-001 | 金額 <= 100,000 TWD 時，採單簽流程 | `pending` -> `csm_approved` -> `executed` |
| BR-REFUND-002 | 金額 > 100,000 TWD 時，採雙簽流程 | `pending` -> `csm_approved` -> `ops_approved` -> `dual_signed` -> `executed` |
| BR-REFUND-003 | 任一階段被拒絕即終止流程 | 狀態直接轉為 `rejected`，不可回溯 |
| BR-REFUND-004 | 退款必須關聯至 work_order 或 complaint | 至少須提供 `work_order_id` 或 `complaint_id` 其中之一 |
| BR-REFUND-005 | 退款執行後觸發 LINE 通知 | 退款進入 `executed` 狀態時，透過 LINE Messaging API 通知客戶 |

### 2.1 金額門檻

```
DUAL_SIGN_THRESHOLD = 100,000 TWD
```

- `amount <= DUAL_SIGN_THRESHOLD` --> `requires_dual_sign = FALSE`
- `amount >  DUAL_SIGN_THRESHOLD` --> `requires_dual_sign = TRUE`

---

## 3. 狀態機 (State Machine)

```
                          +-----------+
                          | pending   |
                          +-----+-----+
                                |
                      CSM approve / reject
                       /                \
                      v                  v
              +---------------+    +-----------+
              | csm_approved  |    | rejected  |
              +-------+-------+    +-----------+
                      |
           +----------+----------+
           |                     |
     requires_dual_sign    !requires_dual_sign
           |                     |
           v                     v
   OPS approve / reject     execute_refund()
      /           \              |
     v             v             v
+--------------+ +----------+ +----------+
| ops_approved | | rejected | | executed |
+------+-------+ +----------+ +----------+
       |
       v
+-------------+
| dual_signed |
+------+------+
       |
  execute_refund()
       |
       v
  +----------+
  | executed |
  +----------+
```

### 3.1 狀態轉換表

| 現狀態 (current) | 事件 (event) | 條件 (guard) | 目標狀態 (next) |
|---|---|---|---|
| `pending` | CSM approve | -- | `csm_approved` |
| `pending` | CSM reject | -- | `rejected` |
| `csm_approved` | OPS approve | `requires_dual_sign = TRUE` | `ops_approved` |
| `csm_approved` | OPS reject | `requires_dual_sign = TRUE` | `rejected` |
| `csm_approved` | execute | `requires_dual_sign = FALSE` | `executed` |
| `ops_approved` | system auto | -- | `dual_signed` |
| `dual_signed` | execute | -- | `executed` |

---

## 4. Approval Chain JSONB 結構

`approval_chain` 欄位為 JSON 陣列，記錄每一位簽核者的決策：

```json
[
  {
    "role": "csm",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "decision": "approved",
    "comment": "客戶投訴合理，同意全額退款",
    "decided_at": "2026-04-04T10:30:00+08:00"
  },
  {
    "role": "ops",
    "user_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "decision": "approved",
    "comment": "",
    "decided_at": "2026-04-04T14:15:00+08:00"
  }
]
```

### 4.1 欄位定義

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| `role` | string | Y | 簽核角色：`csm` 或 `ops` |
| `user_id` | UUID string | Y | 簽核者 user ID |
| `decision` | string | Y | `approved` 或 `rejected` |
| `comment` | string | N | 簽核備註，拒絕時建議填寫原因 |
| `decided_at` | ISO 8601 | Y | 簽核時間，含時區 |

---

## 5. API 端點 (API Endpoints)

### 5.1 建立退款申請

```
POST /refunds
```

**Request Body:**

```json
{
  "work_order_id": "uuid | null",
  "invoice_id": "uuid | null",
  "complaint_id": "uuid | null",
  "requested_by": "uuid",
  "amount": 85000.00,
  "reason": "客戶反映鎖具安裝品質不佳，要求退款"
}
```

**Response:** `201 Created` -- 回傳完整 refund request 物件。

### 5.2 核准退款

```
PATCH /refunds/{id}/approve
```

**Request Body:**

```json
{
  "approver_id": "uuid",
  "role": "csm",
  "comment": "已確認客訴紀錄，同意退款"
}
```

**Response:** `200 OK` -- 回傳更新後的 refund request 物件。

### 5.3 拒絕退款

```
PATCH /refunds/{id}/reject
```

**Request Body:**

```json
{
  "approver_id": "uuid",
  "role": "csm",
  "reason": "退款金額與實際損失不符"
}
```

**Response:** `200 OK` -- 回傳更新後的 refund request 物件（status = `rejected`）。

### 5.4 查詢退款

```
GET /refunds/{id}
```

**Response:** `200 OK` -- 回傳完整 refund request 物件，包含 approval_chain。

---

## 6. SLA 規範

| 階段 | SLA |
|------|-----|
| CSM 簽核 (`pending` -> `csm_approved`) | 48 小時 |
| OPS 簽核 (`csm_approved` -> `ops_approved`) | 48 小時 |
| 退款執行 (`dual_signed` / `csm_approved` -> `executed`) | 24 小時 |

超過 SLA 時限時，系統應發送提醒通知給對應簽核者。

---

## 7. 稽核軌跡 (Audit Trail)

- 每一次狀態變更皆透過 `approval_chain` JSONB 欄位記錄。
- 資料表的 `updated_at` 欄位由 trigger 自動更新。
- 所有 API 呼叫應同時寫入 `audit_logs` 表（GAP #13），記錄：
  - 操作者 (`actor_id`)
  - 操作類型 (`action`: `refund.create`, `refund.approve`, `refund.reject`, `refund.execute`)
  - 變更前後狀態 (`before_state`, `after_state`)
  - 請求時間戳 (`timestamp`)

---

## 8. 資料表參考

對應 SQL Schema 中的 `refund_requests` 表：

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | UUID PK | 退款申請 ID |
| `work_order_id` | UUID FK | 關聯工單 |
| `invoice_id` | UUID FK | 關聯發票 |
| `complaint_id` | UUID FK | 關聯客訴 |
| `requested_by` | UUID FK (NOT NULL) | 申請者 |
| `amount` | FLOAT | 退款金額 (TWD) |
| `reason` | TEXT | 退款原因 |
| `status` | VARCHAR(50) | 流程狀態 |
| `approval_chain` | JSONB | 簽核鏈 |
| `requires_dual_sign` | BOOLEAN | 是否需要雙簽 |
| `executed_at` | TIMESTAMPTZ | 退款執行時間 |
| `created_at` | TIMESTAMPTZ | 建立時間 |
| `updated_at` | TIMESTAMPTZ | 更新時間 |
