# Brand OEM 資料上傳 API 規格書 (GAP #21)

## 1. 概述

本 API 提供品牌 OEM 合作夥伴上傳產品相關資料的標準介面，包含產品手冊、故障碼表、韌體更新紀錄、保固條款等文件。上傳的資料經過驗證與處理後，自動整合至平台知識庫，供 AI 診斷引擎與客服系統使用。

### 設計目標

- 標準化品牌資料匯入流程，取代人工整理
- 自動觸發知識庫更新 pipeline（RAG embedding、fault tree merge 等）
- 透過 RBAC 確保只有授權的品牌帳號可操作（依賴 GAP #16 角色權限）

---

## 2. 資料類型定義

| 類型識別碼 | 說明 | 目標儲存 | 允許格式 |
|---|---|---|---|
| `manual_pdf` | 產品安裝/維修手冊 | `manuals` table + RAG vector store | PDF |
| `fault_code_table` | 品牌專屬故障碼對照表 | `knowledge/fault_trees/` | JSON, CSV, XLSX |
| `firmware_changelog` | 韌體版本更新紀錄 | `case_entries` references | JSON, CSV, PDF |
| `warranty_policy` | 品牌保固條款與條件 | warranty verification pipeline | PDF, JSON |

### 2.1 manual_pdf

產品手冊上傳後進入既有的 PDF 解析 pipeline：拆分段落、embedding 生成、寫入 vector store，使 AI agent 可透過 RAG 檢索手冊內容。

### 2.2 fault_code_table

品牌專屬故障碼表，包含 fault code、description、severity、recommended actions 等欄位。上傳後與 `knowledge/fault_trees/` 目錄下的現有故障樹合併，擴充 L1 diagnostic engine 的判斷能力。

### 2.3 firmware_changelog

韌體更新紀錄，記錄各版本的功能變更、已知問題修復、相容性資訊。處理後建立索引，供 case_entries 查詢參照。

### 2.4 warranty_policy

品牌保固條款文件，定義保固範圍、期限、排除條件等。匯入後供 warranty verification pipeline 自動比對保固資格。

---

## 3. API Endpoints

Base path: `/api/v1/brands/{brand_id}/uploads`

### 3.1 上傳檔案

```
POST /api/v1/brands/{brand_id}/uploads
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

**Request Parameters:**

| 欄位 | 類型 | 必填 | 說明 |
|---|---|---|---|
| `file` | binary | Y | 上傳的檔案 |
| `upload_type` | string | Y | 資料類型（見第 2 節） |
| `description` | string | N | 檔案描述 |

**Response (201 Created):**

```json
{
  "id": "uuid",
  "brand_id": "uuid",
  "upload_type": "manual_pdf",
  "filename": "XYZ-Lock-Manual-v2.pdf",
  "file_size_bytes": 2048576,
  "status": "pending",
  "uploaded_by": "user-uuid",
  "created_at": "2026-04-04T10:00:00Z"
}
```

### 3.2 列出上傳紀錄

```
GET /api/v1/brands/{brand_id}/uploads
Authorization: Bearer <token>
```

**Query Parameters:**

| 欄位 | 類型 | 必填 | 說明 |
|---|---|---|---|
| `upload_type` | string | N | 篩選特定資料類型 |
| `status` | string | N | 篩選狀態（pending, processing, completed, failed） |
| `page` | integer | N | 分頁頁碼，預設 1 |
| `page_size` | integer | N | 每頁筆數，預設 20 |

**Response (200 OK):**

```json
{
  "items": [
    {
      "id": "uuid",
      "brand_id": "uuid",
      "upload_type": "fault_code_table",
      "filename": "fault-codes-v3.json",
      "file_size_bytes": 15360,
      "status": "completed",
      "uploaded_by": "user-uuid",
      "processed_at": "2026-04-04T10:05:00Z",
      "created_at": "2026-04-04T10:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

### 3.3 查詢單筆上傳狀態

```
GET /api/v1/brands/{brand_id}/uploads/{id}
Authorization: Bearer <token>
```

**Response (200 OK):**

```json
{
  "id": "uuid",
  "brand_id": "uuid",
  "upload_type": "warranty_policy",
  "filename": "warranty-terms-2026.pdf",
  "file_size_bytes": 524288,
  "status": "processing",
  "error_message": null,
  "uploaded_by": "user-uuid",
  "processed_at": null,
  "created_at": "2026-04-04T10:00:00Z"
}
```

### 3.4 刪除上傳紀錄

```
DELETE /api/v1/brands/{brand_id}/uploads/{id}
Authorization: Bearer <token>
```

**Response (204 No Content)**

刪除同時移除磁碟上的實體檔案。已完成處理並整合至知識庫的資料不會被回溯移除（需透過知識庫管理介面操作）。

---

## 4. 處理 Pipeline

上傳檔案的處理流程：

```
Upload -> Validate -> Store -> Process -> Integrate
```

### 4.1 Validate

- 檢查檔案大小（上限 100 MB）
- 驗證副檔名與 upload_type 的對應關係
- 基本格式檢查（PDF header、JSON syntax、CSV structure）

### 4.2 Store

- 檔案儲存至 `./data/uploads/brands/{brand_id}/` 目錄
- 檔名格式：`{upload_id}_{original_filename}`
- 建立 `brand_uploads` 資料庫紀錄，狀態設為 `pending`

### 4.3 Process

依 upload_type 分派至對應的處理器：

| upload_type | 處理器 | 處理內容 |
|---|---|---|
| `manual_pdf` | `_process_manual_pdf` | PDF 解析、段落拆分、embedding 生成 |
| `fault_code_table` | `_process_fault_codes` | 解析 JSON/CSV、合併至 fault_trees |
| `firmware_changelog` | `_process_firmware_changelog` | 解析版本紀錄、建立索引 |
| `warranty_policy` | `_process_warranty_policy` | 解析條款、寫入 warranty_policies |

處理過程中狀態為 `processing`，完成後更新為 `completed` 或 `failed`。

### 4.4 Integrate

處理完成的資料自動寫入對應的知識庫表與索引：

- PDF 手冊 → `manuals` table + pgvector embedding
- 故障碼 → `knowledge/fault_trees/` JSON 檔案
- 韌體紀錄 → `case_entries` 可查詢的參照資料
- 保固條款 → `warranty_policies` table

---

## 5. 認證與授權

### 5.1 認證

所有 endpoint 需攜帶有效的 Bearer token。Token 由平台 auth service 簽發。

### 5.2 授權

需具備 `brand_oem` 角色（依賴 GAP #16 RBAC 機制）。品牌帳號只能存取自己 `brand_id` 下的資料，跨品牌操作會回傳 `403 Forbidden`。

### 5.3 角色權限矩陣

| 操作 | `brand_oem` | `platform_admin` | 其他角色 |
|---|---|---|---|
| POST upload | 限自身 brand | 全部 | 禁止 |
| GET list/detail | 限自身 brand | 全部 | 禁止 |
| DELETE | 限自身 brand | 全部 | 禁止 |

---

## 6. Rate Limiting

| 限制項目 | 上限 |
|---|---|
| 上傳頻率 | 10 次/小時/brand |
| 單檔大小 | 100 MB |
| 並行處理 | 3 個/brand |

超出限制時回傳 `429 Too Many Requests`，response header 包含 `Retry-After` 秒數。

---

## 7. 支援格式

| 格式 | MIME Type | 說明 |
|---|---|---|
| PDF | `application/pdf` | 產品手冊、保固條款、韌體紀錄 |
| JSON | `application/json` | 故障碼表、保固條款（結構化）、韌體紀錄 |
| CSV | `text/csv` | 故障碼表、韌體紀錄 |
| XLSX | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | 故障碼表 |

---

## 8. 錯誤回應

所有錯誤回應遵循統一格式：

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Extension '.docx' is not allowed for upload type 'manual_pdf'. Allowed: ['.pdf']"
  }
}
```

| HTTP Status | Error Code | 說明 |
|---|---|---|
| 400 | `VALIDATION_FAILED` | 檔案驗證失敗 |
| 401 | `UNAUTHORIZED` | Token 無效或過期 |
| 403 | `FORBIDDEN` | 角色權限不足或跨品牌操作 |
| 404 | `NOT_FOUND` | 上傳紀錄不存在 |
| 413 | `FILE_TOO_LARGE` | 檔案超過 100 MB |
| 429 | `RATE_LIMITED` | 超出上傳頻率限制 |
| 500 | `PROCESSING_ERROR` | 處理 pipeline 內部錯誤 |

---

## 9. 資料庫 Schema

```sql
CREATE TABLE brand_uploads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id        UUID NOT NULL REFERENCES brands(id),
    upload_type     VARCHAR(50) NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    file_path       TEXT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message   TEXT,
    uploaded_by     UUID NOT NULL REFERENCES users(id),
    processed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_upload_type CHECK (
        upload_type IN ('manual_pdf', 'fault_code_table',
                        'firmware_changelog', 'warranty_policy')
    ),
    CONSTRAINT chk_status CHECK (
        status IN ('pending', 'processing', 'completed', 'failed')
    )
);

CREATE INDEX idx_brand_uploads_brand_id ON brand_uploads(brand_id);
CREATE INDEX idx_brand_uploads_status ON brand_uploads(status);
```
