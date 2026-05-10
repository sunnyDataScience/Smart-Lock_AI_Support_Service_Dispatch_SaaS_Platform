---
id: MOD-V1-04
title: knowledge-base-manager — V1.0 Core Module
tier: 2
status: accepted
last-synced-with: pending
sync-source: doc
source-paths:
  - agent/...
  - api/...
synced-at: 2026-05-10
related:
  - "../flows/business/_pending-split_BF-work-order.md"
  - "../functional-requirements/"
  - "../../1-decisions/module-boundary/{agent,api}.md"
legacy_id: V1-Module-4
extracted_from: _pending-split-v1-core-modules.md (lines 696-901)
---

# knowledge-base-manager — V1.0 Core Module Contract

> 從 `_pending-split-v1-core-modules.md` (V1.0 5-9 module spec) 模組 4 抽出。
> 待重構為 VibeCoding `module-contract.template.md` 的 pre/post conditions 結構。

## 模組 4: KnowledgeBaseManager — 對應 BDD Feature: F-104 / 流程 F-001（RAG）/ F-017（SOP 草稿前置）

### SearchCaseLibraryUseCase / IngestManualUseCase

**所在路徑**: `backend/src/smart_lock/application/knowledge_base/use_cases.py`
**對應領域層**: `backend/src/smart_lock/domains/knowledge_base/entities.py`
**對應 BDD Feature**: `docs/03_behavior_driven_development.md#feature-自進化知識庫`
**對應資料庫表**: `case_entries`, `manuals`, `manual_chunks`

**模組描述**: KnowledgeBaseManager 負責知識庫的讀寫操作。SearchCaseLibraryUseCase 提供案例庫的向量搜尋能力（供 L1 使用）；IngestManualUseCase 處理 PDF 手冊的上傳、解析（PyMuPDF）、切片、向量化（text-embedding-004）及入庫流程（供 L2 RAG 使用）。

---

### 規格 4-1: `search_case_library`

**描述 (Description)**: 將查詢文字向量化後，對 `case_entries` 表執行 pgvector cosine similarity 搜尋，回傳匹配的案例清單。

**函式簽名**:
```python
async def search_case_library(
    self,
    query: KBSearchQueryDTO,
) -> KBSearchResultDTO:
```

其中 `KBSearchQueryDTO` 包含:
```python
class KBSearchQueryDTO:
    query_text: str          # 搜尋文字
    brand: str | None        # 品牌過濾 (optional)
    lock_type: str | None    # 鎖型過濾 (optional)
    top_k: int = 3           # 回傳筆數上限
    threshold: float = 0.85  # 相似度閾值
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `query.query_text` 不可為空字串，長度不超過 2000 字元。
    2. `query.top_k` 範圍為 `1 ~ 10`。
    3. `query.threshold` 範圍為 `0.0 ~ 1.0`。
    4. Embedding Service 可用。
    5. PostgreSQL + pgvector 連線可用。

*   **後置條件 (Postconditions)**:
    1. 回傳的 `KBSearchResultDTO` 包含 `results`（案例清單）與 `total_found`（符合閾值的總數）。
    2. `results` 中每筆的 `similarity_score >= threshold`，按 score 降序排列。
    3. `results` 最多 `top_k` 筆。
    4. 每筆結果包含 `case_entry_id`, `title`, `problem_description`, `solution`, `similarity_score`, `brand`, `lock_type`, `difficulty`。
    5. 搜尋耗時（含 embedding 生成 + pgvector 查詢）記錄於回傳 DTO 的 `search_duration_ms`。

*   **不變性 (Invariants)**:
    1. 只搜尋 `is_active = true` 的案例。
    2. Embedding 維度為 768。
    3. 搜尋操作為唯讀，不修改任何資料（`hit_count` 更新由 ThreeLayerResolver 負責）。

---

### 規格 4-2: `ingest_manual`

**描述 (Description)**: 接收管理員上傳的 PDF 手冊檔案，執行非同步處理流程：PDF 解析 -> 文本切片 -> Embedding 向量化 -> 入庫。

**函式簽名**:
```python
async def ingest_manual(
    self,
    file: UploadFile,
    brand: str,
    model: str | None = None,
    uploaded_by: uuid.UUID | None = None,
) -> ManualIngestResponseDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `file` 必須為有效的 PDF 檔案（MIME type 為 `application/pdf`）。
    2. `file` 大小不超過 50MB。
    3. `brand` 不可為空字串。
    4. `uploaded_by`（若提供）必須對應一個存在且 `role` 為 `"admin"` 或 `"reviewer"` 的使用者。

*   **後置條件 (Postconditions)**:
    1. `manuals` 表新增一筆記錄，`status = "processing"`。
    2. 非同步背景任務已啟動，執行以下 Pipeline：
        a. PDF 解析（PyMuPDF）：提取文本與頁碼。
        b. 文本切片：按章節 + 固定 Token 數（約 512 tokens/chunk，重疊 50 tokens）切割。
        c. 向量化：對每個 chunk 呼叫 Embedding Service 生成 768 維向量。
        d. 入庫：所有 chunks 批次寫入 `manual_chunks` 表。
    3. Pipeline 完成後：`manuals.status` 更新為 `"completed"`，`total_chunks` 更新為實際切片數。
    4. Pipeline 失敗時：`manuals.status` 更新為 `"failed"`，`error_message` 記錄失敗原因。
    5. 回傳的 `ManualIngestResponseDTO` 包含 `manual_id` 與 `status = "processing"`（非同步處理中）。

*   **不變性 (Invariants)**:
    1. 每個 `manual_chunks` 的 `embedding` 維度始終為 768。
    2. `manual_chunks.chunk_index` 在同一 `manual_id` 下連續且唯一（從 0 開始）。
    3. `manual_chunks.token_count` 不超過切片上限（預設 512 + 50 重疊 = 562）。
    4. PDF 處理流程不阻塞 API 回應（全程非同步）。

---

### 測試情境與案例 (KnowledgeBaseManager)

#### 情境 1: 正常路徑 — 向量搜尋命中高相似度案例

*   **測試案例 ID**: `TC-KBM-001`
*   **描述**: 搜尋 "Yale YDM-7116 密碼鍵盤無回應"，案例庫中有完全匹配的案例。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 在 `case_entries` 表中預置一筆案例：`title = "Yale YDM-7116 密碼鍵盤無回應"`，`embedding` 已計算。
        - Mock Embedding Service 為搜尋文字生成對應的 768 維向量。
    2.  **Act**: 呼叫 `search_case_library(KBSearchQueryDTO(query_text="Yale YDM-7116 密碼鍵盤沒反應", brand="Yale", top_k=3, threshold=0.85))`。
    3.  **Assert**:
        - 驗證 `results` 至少包含 1 筆記錄。
        - 驗證第一筆結果的 `similarity_score >= 0.85`。
        - 驗證 `solution` 欄位非空。
        - 驗證 `search_duration_ms` 為正整數。

#### 情境 2: 正常路徑 — 搜尋無命中（所有結果低於閾值）

*   **測試案例 ID**: `TC-KBM-002`
*   **描述**: 搜尋一個案例庫中完全沒有相關資料的問題，回傳空結果。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - `case_entries` 表中只有與 Yale 相關的案例。
        - 搜尋文字為 `"未知品牌 XYZ-999 型號的全新問題"`。
    2.  **Act**: 呼叫 `search_case_library(KBSearchQueryDTO(query_text="未知品牌 XYZ-999 的問題", threshold=0.85))`。
    3.  **Assert**:
        - 驗證 `results` 為空列表。
        - 驗證 `total_found` 為 0。

#### 情境 3: 正常路徑 — PDF 手冊上傳與切片處理

*   **測試案例 ID**: `TC-KBM-003`
*   **描述**: 管理員上傳一份 Samsung SHP-DP609 的操作手冊 PDF，系統應完成解析、切片與向量化。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 準備一份測試用 PDF 檔案（10 頁，約 5000 字）。
        - Mock Embedding Service 的 batch embedding API。
    2.  **Act**: 呼叫 `ingest_manual(file=test_pdf, brand="Samsung", model="SHP-DP609", uploaded_by=admin_user_id)`。
    3.  **Assert**:
        - 驗證 `manuals` 表新增一筆記錄，`brand = "Samsung"`, `model = "SHP-DP609"`。
        - 驗證回傳的 `status` 為 `"processing"`。
        - 等待非同步任務完成後：
            - 驗證 `manuals.status` 為 `"completed"`。
            - 驗證 `manual_chunks` 表中新增了多筆記錄（每筆 `token_count <= 562`）。
            - 驗證每筆 chunk 的 `embedding` 維度為 768。
            - 驗證 `chunk_index` 從 0 開始連續遞增。

#### 情境 4: 邊界情況 — 品牌過濾縮小搜尋範圍

*   **測試案例 ID**: `TC-KBM-004`
*   **描述**: 當指定 `brand` 過濾時，搜尋結果應優先展示該品牌的案例。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - `case_entries` 表中有兩筆相似案例：一筆 `brand = "Yale"`，一筆 `brand = "Samsung"`，問題描述相近。
    2.  **Act**: 呼叫 `search_case_library(KBSearchQueryDTO(query_text="密碼鍵盤無回應", brand="Yale"))`。
    3.  **Assert**:
        - 驗證結果中 Yale 品牌的案例排在 Samsung 之前（假設 similarity 相近時品牌匹配有加分）。

#### 情境 5: 無效輸入 — 上傳非 PDF 檔案

*   **測試案例 ID**: `TC-KBM-005`
*   **描述**: 管理員嘗試上傳一份 `.docx` 檔案，系統應拒絕。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: 準備一份 `.docx` 檔案。
    2.  **Act**: 呼叫 `ingest_manual(file=docx_file, brand="Yale")`。
    3.  **Assert**:
        - 預期系統拋出 `ValidationError`，訊息包含 `"PDF"` 或 `"file format"`。
        - 驗證 `manuals` 表未新增任何記錄。

#### 情境 6: 無效輸入 — 超過大小限制的 PDF

*   **測試案例 ID**: `TC-KBM-006`
*   **描述**: 管理員上傳超過 50MB 的 PDF 檔案，系統應拒絕。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: Mock 一份 55MB 的 PDF UploadFile。
    2.  **Act**: 呼叫 `ingest_manual(file=large_pdf, brand="Yale")`。
    3.  **Assert**:
        - 預期系統拋出 `ValidationError`，訊息包含 `"file size"` 或 `"50MB"`。

#### 情境 7: 業務規則 — 已停用的案例不出現在搜尋結果

*   **測試案例 ID**: `TC-KBM-007`
*   **描述**: 管理員將某案例的 `is_active` 設為 `false` 後，該案例不應出現在向量搜尋結果中。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - `case_entries` 表中有一筆高相似度案例，但 `is_active = false`。
    2.  **Act**: 呼叫 `search_case_library` 搜尋與該案例完全匹配的文字。
    3.  **Assert**:
        - 驗證搜尋結果中不包含該停用案例。

#### 情境 8: 業務規則 — PDF 處理失敗的錯誤記錄

*   **測試案例 ID**: `TC-KBM-008`
*   **描述**: PDF 內容損壞導致解析失敗，系統應記錄錯誤但不影響其他操作。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: Mock PyMuPDF 解析時拋出例外。
    2.  **Act**: 呼叫 `ingest_manual(file=corrupted_pdf, brand="Yale")`。
    3.  **Assert**:
        - 驗證 `manuals.status` 最終為 `"failed"`。
        - 驗證 `manuals.error_message` 非空，記錄了失敗原因。
        - 驗證 `manual_chunks` 表中無對應的切片記錄。
        - 驗證系統未拋出未捕獲的例外。

---

