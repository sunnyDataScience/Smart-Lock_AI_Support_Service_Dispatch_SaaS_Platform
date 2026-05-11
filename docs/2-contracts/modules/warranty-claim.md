# 保固索賠與爭議處理規格書 (Warranty Dispute Specification)

> GAP #12 -- Smart Lock AI Support Service Dispatch SaaS Platform

---

## 1. 概述 (Overview)

本規格定義智慧門鎖服務派遣平台的保固索賠生命週期與爭議處理流程。
保固索賠涵蓋設備故障報修時的保固驗證、核准/拒絕決策、以及消費者對拒絕
結果提出爭議後的調解流程。

核心原則：

- 保固起算日以「交屋日」(handover date) 為準，非購買日期。
- AI 禁止自動報價保固案件，所有保固案件必須由人工處理。
- 保固外客戶可透過系統取得折扣報價。
- 爭議案件進入 `disputes` 表進行調解。

---

## 2. 商業規則 (Business Rules)

| 編號 | 規則 | 說明 |
|------|------|------|
| BR-WARRANTY-001 | 保固起算日為交屋日 | `warranty_start_date` 以建案資料庫中的交屋日為準，非 `purchase_date`。即使消費者提供購買憑證，系統仍以交屋日計算保固期間。 |
| BR-WARRANTY-002 | AI 禁止自動報價保固案件 | 任何涉及保固的工單，AI agent 不得自動生成報價。必須由客服人員 (CSM) 或技師手動報價。此規則透過 safety gate 強制執行。 |
| BR-WARRANTY-003 | 保固外客戶獲折扣報價 | 當 `is_within_warranty = FALSE` 時，系統根據過保天數計算折扣百分比，寫入 `discount_offered` 欄位。折扣邏輯見第 6 節。 |
| BR-WARRANTY-004 | 驗證來源優先順序 | 驗證保固資格時，資料來源優先順序為：`project_database` (建案資料庫) > `receipt` (收據) > `invoice` (發票)。優先採信建案資料庫中的交屋紀錄。 |
| BR-WARRANTY-005 | 拒絕後爭議進入調解 | 消費者對拒絕結果不服時，可提出爭議 (dispute)。系統於 `warranty_claims` 表標記 `status = 'disputed'`，同時在 `disputes` 表建立對應記錄，進入調解流程。 |

### 2.1 保固計算邏輯

```
is_within_warranty = (claim_date <= warranty_end_date) AND (claim_date >= warranty_start_date)
```

- `warranty_start_date`: 交屋日 (handover date)
- `warranty_end_date`: 保固到期日
- `claim_date`: 索賠日期，預設為 `CURRENT_DATE`

---

## 3. 狀態機 (State Machine)

```
               +--------+
               | filed  |
               +---+----+
                   |
             verify_claim()
                   |
                   v
             +-----------+
             | verified  |
             +-----+-----+
                   |
          +--------+--------+
          |                 |
    approve_claim()   reject_claim()
          |                 |
          v                 v
    +-----------+     +-----------+
    | approved  |     | rejected  |
    +-----------+     +-----+-----+
                            |
                   dispute_claim()  (customer contests)
                            |
                            v
                      +-----------+
                      | disputed  |
                      +-----------+
                            |
                   (enters disputes table
                    for mediation)
```

### 3.1 狀態轉換表

| 現狀態 (current) | 事件 (event) | 條件 (guard) | 目標狀態 (next) |
|---|---|---|---|
| `filed` | verify | `verification_source` 已提供 | `verified` |
| `verified` | approve | `is_within_warranty = TRUE` 或人工判定 | `approved` |
| `verified` | reject | 驗證不通過 | `rejected` |
| `rejected` | dispute | 消費者提出爭議理由 | `disputed` |

備註：`approved` 與 `disputed` 為終態或交由外部流程處理。`disputed` 狀態的
後續處理由 `disputes` 表的調解流程接管。

---

## 4. 與工單的整合 (Work Order Integration)

`warranty_claims.work_order_id` 為指向 `work_orders(id)` 的外鍵 (FK)。

整合規則：

- 保固索賠可在建立工單時同步建立，或事後補建。
- 當 `work_order_id` 不為 NULL 時，工單狀態更新須考慮保固狀態：
  - 保固案件核准 (`approved`) 後，工單可標記為免費服務。
  - 保固案件拒絕 (`rejected`) 後，工單轉為一般收費流程。
  - 保固案件爭議中 (`disputed`) 時，工單暫停計費直到調解完成。
- 一張工單最多對應一筆保固索賠。

---

## 5. 驗證流程 (Verification Flow)

```
                 收到索賠申請
                      |
                      v
         查詢建案資料庫 (project_database)
                      |
              +-------+-------+
              |               |
           找到            未找到
              |               |
              v               v
     以建案交屋日       查詢收據 (receipt)
     為 warranty_start    |
              |       +---+---+
              |       |       |
              |    找到    未找到
              |       |       |
              |       v       v
              |   以收據  查詢發票 (invoice)
              |   日期驗證    |
              |           +---+---+
              |           |       |
              |        找到    未找到
              |           |       |
              |           v       v
              |      以發票   驗證失敗
              |      日期驗證  (reject)
              |           |
              v           v
         計算 is_within_warranty
              |
       +------+------+
       |             |
    TRUE          FALSE
       |             |
       v             v
   可核准       計算折扣報價
   (approve)   (discount_offered)
```

### 5.1 驗證來源優先順序

| 優先順序 | 來源 | `verification_source` 值 | 信賴度 |
|----------|------|-------------------------|--------|
| 1 | 建案資料庫 | `project_database` | 最高 |
| 2 | 收據 | `receipt` | 中 |
| 3 | 發票 | `invoice` | 低 |

---

## 6. 保固外折扣計算 (Out-of-Warranty Discount)

當 `is_within_warranty = FALSE` 時，系統根據過保天數與設備品牌計算折扣：

```
days_past_warranty = claim_date - warranty_end_date

if days_past_warranty <= 30:
    discount = 20%      # 剛過保，給予較高折扣
elif days_past_warranty <= 90:
    discount = 10%
elif days_past_warranty <= 180:
    discount = 5%
else:
    discount = 0%       # 過保超過 180 天，無折扣
```

折扣值寫入 `warranty_claims.discount_offered` 欄位。特定品牌可能有額外折扣
政策，由 `brand` 服務模組提供。

---

## 7. 資料表參考

對應 SQL Schema 中的 `warranty_claims` 表：

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | UUID PK | 索賠 ID |
| `work_order_id` | UUID FK | 關聯工單 |
| `customer_id` | UUID FK (NOT NULL) | 客戶 |
| `device_brand` | VARCHAR(100) | 設備品牌 |
| `device_model` | VARCHAR(100) | 設備型號 |
| `purchase_date` | DATE | 購買日期 (參考用) |
| `warranty_start_date` | DATE (NOT NULL) | 保固起算日 (交屋日) |
| `warranty_end_date` | DATE (NOT NULL) | 保固到期日 |
| `claim_date` | DATE | 索賠日期 |
| `is_within_warranty` | BOOLEAN (NOT NULL) | 系統計算 |
| `status` | VARCHAR(50) | 流程狀態 |
| `dispute_reason` | TEXT | 爭議理由 |
| `verification_source` | VARCHAR(100) | 驗證來源 |
| `resolution` | TEXT | 處理結果 |
| `discount_offered` | FLOAT | 保固外折扣百分比 |
| `created_at` | TIMESTAMPTZ | 建立時間 |
| `updated_at` | TIMESTAMPTZ | 更新時間 |

爭議案件同時關聯 `disputes` 表，`dispute_type = 'warranty'`。

---

## 8. Safety Gate 整合

BR-WARRANTY-002 由 `agent/harness/safety/gate.py` 強制執行：

- 當偵測到工單關聯保固索賠時，safety gate 必須攔截任何自動報價動作。
- 攔截後觸發人工轉接 (escalation) 流程。
- 對應的 audit event type 為 `safety_gate`，記錄攔截原因與觸發條件。

---

## §9 測試情境與案例 (WarrantyClaim)

<!-- TC-ID: IT-0129 -->
#### 情境 1: 正常路徑 — 保固期內 claim approved
*   **Arrange**: 建案資料庫 handover_date=2025-12-01，warranty 2 年；claim_date=2026-05-11 (5 個月)。
*   **Act**: 提交 claim。
*   **Assert**: warranty_claims status=approved；is_within_warranty=true；source=project_database (per BR-WARRANTY-004)；audit `warranty.approved`。

<!-- TC-ID: IT-0130 -->
#### 情境 2: 正常路徑 — 保固外客戶折扣報價
*   **Arrange**: handover=2023-01-01，warranty 2 年到 2025-01-01；claim=2026-05-11 (過保 16 個月)。
*   **Act**: 系統計算 discount。
*   **Assert**: is_within_warranty=false；status=denied；discount_offered (per §6 過保折扣公式，如過保 1 年內 70% 折)；不自動執行（仍需 CSM 確認）。

<!-- TC-ID: IT-0131 -->
#### 情境 3: 邊界 — claim_date = warranty_end_date 視為仍在保固
*   **Arrange**: warranty_end_date=2026-12-01；claim_date=2026-12-01。
*   **Act**: 計算。
*   **Assert**: is_within_warranty=true (per §2.1, ≤ end_date)；status=approved。

<!-- TC-ID: IT-0132 -->
#### 情境 4: 邊界 — 收據與建案資料庫衝突採信建案（BR-WARRANTY-004）
*   **Arrange**: 客戶提供收據 purchase_date=2025-09-01，建案資料庫 handover=2025-12-01。
*   **Act**: 驗證。
*   **Assert**: 採信 handover=2025-12-01；audit `warranty.source.project_database_used`，含 receipt_date 與 handover_date 兩值對照。

<!-- TC-ID: IT-0133 -->
#### 情境 5: 異常 — AI 自動報價保固案件被 safety gate 攔截 (BR-WARRANTY-002)
*   **Arrange**: ProblemCard 含 warranty_claim_id；AI agent 觸發 estimate_quote()。
*   **Act**: safety_gate 偵測。
*   **Assert**: gate 攔截，不執行 estimate；escalate 至 CSM；audit_logs event_type=safety_gate, reason=`warranty_no_ai_quote`。

<!-- TC-ID: IT-0134 -->
#### 情境 6: 業務規則 — Denied 後消費者爭議進 disputes 表
*   **Arrange**: warranty_claim wc-001 status=denied。
*   **Act**: 消費者提交爭議。
*   **Assert**: warranty_claims status=disputed；disputes 表新增 1 筆，linked to wc-001；通知 operations_manager；audit `warranty.disputed`。
