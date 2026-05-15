---
id: MC-0004
title: "Data Export"
tier: 2-contracts
status: active
owner: HYBRID
last-reviewed: 2026-05-15
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
---

# Data Export / Portability 規格書

> GAP #14 -- 資料匯出與可攜性  
> 合約條款 Contract 9-3 資料可攜權  
> 狀態: Draft  
> 最後更新: 2026-04-04

---

## 1. 概述

本規格定義 Smart Lock AI Support SaaS Platform 的資料匯出功能。依據合約第 9-3 條之資料可攜權要求，平台必須提供使用者及管理員以標準格式匯出其資料的能力。匯出作業採非同步處理，產生的檔案於 72 小時後自動過期刪除。

---

## 2. Export Scopes (匯出範圍)

| Scope 識別碼 | 說明 | 包含內容 | 權限要求 |
|---|---|---|---|
| `conversations` | 使用者對話紀錄 | LINE 聊天訊息、AI 回應、timestamp、session metadata | 使用者本人或 admin |
| `work_orders` | 服務工單紀錄 | 工單基本資料、狀態變更歷程 (status history)、技師指派紀錄、完工報告 | 使用者本人或 admin |
| `financial` | 財務資料 | invoices、payments、refunds、金額明細、付款方式 | 僅限 admin + finance role |
| `personal_data` | 個人資料 (GDPR-style portability) | 使用者 profile、PII 欄位 (姓名、電話、地址、身分證號)、偏好設定 | 使用者本人或 admin |

---

## 3. Export Formats (匯出格式)

| Format | Content-Type | 適用情境 |
|---|---|---|
| CSV | `text/csv` | 表格式資料，適合 Excel / Google Sheets 匯入 |
| JSON | `application/json` | 完整結構化資料，保留物件關聯 (relationships) |
| PDF | `application/pdf` | 格式化報表，適合列印與歸檔 |

### 格式限制

- `financial` scope 的 PDF 格式包含公司抬頭與合規聲明。
- CSV 格式將巢狀結構扁平化 (flatten)，以 dot notation 命名欄位。
- JSON 格式保留完整的 foreign key 關聯與 nested objects。

---

## 4. PII Masking (個資遮罩)

匯出請求可附帶 `mask_pii=true` 旗標，啟用後系統將對以下欄位進行遮罩處理:

| 欄位類型 | 原始值範例 | 遮罩後範例 |
|---|---|---|
| phone | 0912-345-678 | 0912-***-678 |
| email | user@example.com | u***@example.com |
| address | 台北市信義區松仁路100號 | 台北市信義區****** |
| id_number | A123456789 | A1*****789 |

遮罩演算法保留首尾辨識字元，中間以 `*` 取代。此機制適用於所有 scope 中包含 PII 的欄位。

---

## 5. API Endpoints

### 5.1 建立匯出請求

```
POST /api/v1/exports
```

**Request Body:**

```json
{
  "scope": "work_orders",
  "format": "json",
  "filters": {
    "date_from": "2026-01-01",
    "date_to": "2026-03-31",
    "status": "completed"
  },
  "mask_pii": false
}
```

**Response (202 Accepted):**

```json
{
  "id": "exp_abc123",
  "status": "pending",
  "scope": "work_orders",
  "format": "json",
  "created_at": "2026-04-04T10:00:00Z",
  "expires_at": "2026-04-07T10:00:00Z"
}
```

### 5.2 查詢匯出狀態

```
GET /api/v1/exports/{id}
```

**Response (200 OK):**

```json
{
  "id": "exp_abc123",
  "status": "completed",
  "scope": "work_orders",
  "format": "json",
  "file_size_bytes": 245760,
  "created_at": "2026-04-04T10:00:00Z",
  "expires_at": "2026-04-07T10:00:00Z"
}
```

**status 可能值:** `pending`, `processing`, `completed`, `failed`, `expired`

### 5.3 下載匯出檔案

```
GET /api/v1/exports/{id}/download
```

**Response:** 檔案二進位串流，附帶 `Content-Disposition: attachment` header。

僅在 `status=completed` 且未過期時可下載，否則回傳 `404 Not Found` 或 `410 Gone`。

---

## 6. Authorization (授權規則)

| 角色 | conversations | work_orders | financial | personal_data |
|---|---|---|---|---|
| line_user | 僅自己 | 僅自己 | 不可 | 僅自己 |
| technician | 僅自己 | 僅自己 | 不可 | 僅自己 |
| admin | 任意使用者 | 任意使用者 | 需 finance role | 任意使用者 |
| super_admin | 任意使用者 | 任意使用者 | 可 | 任意使用者 |

- 一般使用者只能匯出自己的資料，系統自動以 JWT 中的 `user_id` 過濾。
- `financial` scope 需要 `finance` 權限，即使是 admin 也必須具備此 role permission。

---

## 7. Rate Limiting (頻率限制)

- 每位使用者每小時最多 1 筆匯出請求。
- 超過限制時回傳 `429 Too Many Requests`，response header 包含 `Retry-After` 秒數。
- admin 帳號的限制放寬至每小時 5 筆。

---

## 8. File Lifecycle (檔案生命週期)

1. 匯出請求建立後，狀態為 `pending`。
2. Worker 取得任務後轉為 `processing`。
3. 處理完成後轉為 `completed`，檔案寫入 `./data/exports/` 目錄。
4. 檔案自 `created_at` 起算 72 小時後標記為 `expired`。
5. 排程任務 `cleanup_expired()` 定期掃描並刪除過期檔案與對應的資料庫紀錄。

```
pending --> processing --> completed --> expired (72h TTL)
                |
                +--> failed (可重試)
```

---

## 9. 技術實作要點

- 匯出作業以 async background task 執行，避免阻塞 API response。
- 大量資料採 streaming write，避免記憶體溢出。
- 檔案儲存路徑: `./data/exports/{export_id}.{format}`。
- 資料庫連線透過環境變數 `POSTGRES_URI` 取得。
- CSV 寫入使用 Python `csv` module；JSON 使用 `json` module；PDF 可選用 `reportlab` 或 `weasyprint`。

---

## 10. 相關文件

- 合約第 9-3 條: 資料可攜權
- GAP #14: Data Export / Portability
- `agent/services/export/exporter.py`: 實作模組

---

## §11 測試情境與案例 (DataExport)

<!-- TC-ID: IT-0081 -->
#### 情境 1: 正常路徑 — 使用者匯出自己對話 JSON
*   **Arrange**: u-001 過去 30 天有 50 筆 conversation。
*   **Act**: POST /exports，scope=conversations、format=json、actor=u-001。
*   **Assert**: 回 202 + job_id；非同步完成後可下載；JSON 含 50 筆 + nested session metadata；audit `export.requested` + `export.completed`。

<!-- TC-ID: IT-0082 -->
#### 情境 2: 正常路徑 — admin 匯出 financial PDF 含合規聲明
*   **Arrange**: admin u-admin-001，財務模組過去 1 年 200 筆 invoice。
*   **Act**: POST /exports，scope=financial、format=pdf。
*   **Assert**: PDF 第一頁含公司抬頭 + 合規聲明（per §3 格式限制）；audit 含 actor=admin。

<!-- TC-ID: IT-0083 -->
#### 情境 3: 邊界 — 72 小時後匯出檔案自動刪除
*   **Arrange**: export job 完成於 T 時刻，produced_at=T，retention=72h。
*   **Act**: T+73h 嘗試 GET /exports/{id}/download。
*   **Assert**: 回 410 Gone + 訊息「檔案已過期，請重新發起匯出」；GCS object 已 delete；audit `export.expired_cleanup`。

<!-- TC-ID: IT-0084 -->
#### 情境 4: 邊界 — CSV flatten 巢狀資料 dot notation
*   **Arrange**: work_order 含 nested customer.address.city。
*   **Act**: 匯出 CSV。
*   **Assert**: header 含 `customer.address.city` 欄位；row 值正確；陣列欄位（如 status_history）用 JSON string 包覆。

<!-- TC-ID: IT-0085 -->
#### 情境 5: 異常 — 非 financial role 嘗試匯出 financial scope
*   **Arrange**: technician u-tech-001 沒 financial 權限。
*   **Act**: POST /exports，scope=financial。
*   **Assert**: 回 403 `forbidden.scope`；job 不建立；audit `rbac.denied` 含 denied_scope=financial。

<!-- TC-ID: IT-0086 -->
#### 情境 6: 業務規則 — personal_data scope GDPR 必含所有 PII 但須加密
*   **Arrange**: u-001 申請 personal_data export。
*   **Act**: 完成 export。
*   **Assert**: 檔案 ZIP 加密（密碼透過 LINE 推播分開傳）；內容含姓名/電話/地址/身分證；不含他人 PII；audit `gdpr.export` 含 contract_clause=9-3。
