---
id: MOD-V1-03
title: three-layer-resolver — V1.0 Core Module
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
legacy_id: V1-Module-3
extracted_from: _pending-split-v1-core-modules.md (lines 421-695)
---

# three-layer-resolver — V1.0 Core Module Contract

> 從 `_pending-split-v1-core-modules.md` (V1.0 5-9 module spec) 模組 3 抽出。
> 待重構為 VibeCoding `module-contract.template.md` 的 pre/post conditions 結構。

## 模組 3: ThreeLayerResolver (ResolveQueryUseCase) — 對應 BDD Feature: F-103 / 流程 F-001 / F-018

**所在路徑**: `backend/src/smart_lock/application/resolution/use_cases.py`
**對應領域層**: `backend/src/smart_lock/domains/resolution/strategies.py`
**對應 BDD Feature**: `docs/03_behavior_driven_development.md#feature-三層解決機制`
**對應資料庫表**: `conversations.resolution_layer`, `problem_cards.resolution_layer`

**模組描述**: ThreeLayerResolver 是系統的核心解決引擎，採用策略模式 (Strategy Pattern) 依序嘗試三層解決策略：L1 案例庫向量搜尋（CaseLibraryStrategy） -> L2 PDF 手冊 RAG（RAGStrategy） -> L3 人工轉接（HumanHandoffStrategy）。每一層有明確的信心分數閾值，未達標則自動降級至下一層。

---

### 規格 3-1: `resolve`

**描述 (Description)**: 接收一張已確認的 ProblemCard，依序執行三層解決策略，回傳最終解決結果。

**函式簽名**:
```python
async def resolve(
    self,
    problem_card: ProblemCardResponseDTO,
    conversation_id: uuid.UUID,
) -> ResolutionResultDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `problem_card` 的 `completeness_score >= 0.85`（合約要求必要欄位完整率 >= 85%；至少包含 `brand`、`symptoms`、`model`、`location`）。
    2. `problem_card.status` 為 `"confirmed"` 或 `"incomplete"`（至少滿足最低欄位需求）。
    3. `conversation_id` 對應的對話記錄存在且 `status` 為 `"resolving"`。

*   **後置條件 (Postconditions)**:
    1. 回傳的 `ResolutionResultDTO` 必須包含 `resolution_layer`（`"L1"`, `"L2"`, `"L3"` 之一）。
    2. 若 L1 或 L2 解決成功，`answer` 欄位包含解決方案文字，`source_references` 列出引用來源。
    3. 若最終升級至 L3，`needs_escalation = True`，`escalation_info` 包含人工轉接的相關資訊。
    4. `conversations.resolution_layer` 與 `problem_cards.resolution_layer` 已更新為最終解決層級。
    5. 每層嘗試的結果（包含 `layer`, `score`, `success`, `duration_ms`）記錄至日誌。

*   **不變性 (Invariants)**:
    1. 層級嘗試順序永遠為 L1 -> L2 -> L3，不可跳層或倒退。
    2. 若 L1 命中（score >= 0.85），不應再執行 L2 或 L3。
    3. L3 為最終 fallback，必定「成功」（定義為建立人工轉接請求）。

---

### 規格 3-2: CaseLibraryStrategy.search

**描述 (Description)**: L1 策略 — 將 ProblemCard 的問題描述向量化後，對 `case_entries` 表執行 pgvector cosine similarity 搜尋。

**函式簽名**:
```python
async def search(
    self,
    problem_description: str,
    brand: str | None = None,
    model: str | None = None,
    top_k: int = 3,
    threshold: float = 0.85,
) -> list[CaseSearchResultDTO]:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `problem_description` 不可為空字串。
    2. `top_k` 必須大於 0 且小於等於 10。
    3. `threshold` 必須在 `0.0` ~ `1.0` 之間。
    4. Embedding Service（text-embedding-004）可用。
    5. PostgreSQL + pgvector 連線可用。

*   **後置條件 (Postconditions)**:
    1. 回傳的列表長度在 `0` ~ `top_k` 之間。
    2. 列表中每個結果的 `similarity_score` 都 >= `threshold`。
    3. 列表按 `similarity_score` 降序排列。
    4. 每個結果包含 `case_entry_id`, `title`, `solution`, `similarity_score`, `brand`, `lock_type`。
    5. 若提供了 `brand` 和/或 `model`，搜尋結果應優先匹配相同品牌/型號的案例（但不排除其他）。
    6. 命中的 `case_entries` 記錄的 `hit_count` 遞增 1。

*   **不變性 (Invariants)**:
    1. 只搜尋 `is_active = true` 的案例條目。
    2. Embedding 向量維度始終為 768（text-embedding-004）。
    3. 搜尋使用 HNSW 索引（cosine similarity），不使用暴力搜尋。

---

### 規格 3-3: RAGStrategy.generate

**描述 (Description)**: L2 策略 — 基於 ProblemCard 的問題描述，從 `manual_chunks` 檢索相關段落，結合 Gemini 3 Pro 生成解決方案。

**函式簽名**:
```python
async def generate(
    self,
    problem_card: ProblemCardResponseDTO,
    top_k_chunks: int = 5,
    confidence_threshold: float = 0.70,
) -> RAGResultDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `problem_card` 至少包含 `brand` 和 `symptoms` 欄位。
    2. `top_k_chunks` 必須大於 0 且小於等於 20。
    3. `confidence_threshold` 必須在 `0.0` ~ `1.0` 之間。
    4. Embedding Service、LLMGateway（Gemini 3 Pro）、PostgreSQL + pgvector 連線均可用。

*   **後置條件 (Postconditions)**:
    1. 回傳的 `RAGResultDTO` 包含 `answer`（生成的解決方案文字）、`confidence_score`、`source_chunks`（引用的手冊段落列表）。
    2. 若 `confidence_score >= confidence_threshold`，`success = True`。
    3. `source_chunks` 中每個段落包含 `manual_chunk_id`, `source_pdf`, `page_number`, `chapter_title`, `relevance_score`。
    4. 生成的 `answer` 通過 Content Filter 驗證（無幻覺、無有害內容）。
    5. LLM 呼叫的 `token_usage` 與 `latency_ms` 記錄至 `messages.metadata` JSONB。

*   **不變性 (Invariants)**:
    1. RAG 檢索只搜尋 `status = "completed"` 的手冊對應的 `manual_chunks`。
    2. Prompt Template 使用 `configs/prompts/rag_answer.txt`，不可在程式碼中 hardcode。
    3. LLM 回應的 Token 總量不超過設定上限（防止成本失控）。

---

### 規格 3-4: HumanHandoffStrategy.escalate

**描述 (Description)**: L3 策略 — 當 L1 和 L2 均無法解決問題時，建立人工轉接請求，將 ProblemCard 與完整對話記錄轉交客服人員。

**函式簽名**:
```python
async def escalate(
    self,
    problem_card: ProblemCardResponseDTO,
    conversation_id: uuid.UUID,
    reason: str = "auto_escalation",
) -> EscalationResultDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `problem_card` 已存在且有有效的 `id`。
    2. `conversation_id` 對應的對話記錄存在。
    3. `reason` 為合法的升級原因字串（`"auto_escalation"`, `"user_request"`, `"content_filter_triggered"`）。

*   **後置條件 (Postconditions)**:
    1. `conversations.status` 更新為 `"escalated"`。
    2. `problem_cards.status` 更新為 `"escalated"`。
    3. `conversations.resolution_layer` 更新為 `"L3"`。
    4. 回傳的 `EscalationResultDTO` 包含 `ticket_id`（支援工單 ID）或 `work_order_id`（V2.0 派工單 ID）。
    5. 若在服務時間內（09:00-21:00），通知線上客服人員。
    6. 若在服務時間外，建立排程回撥（下一個營業日 09:00），並回傳預計聯繫時間。
    7. 使用者收到的 LINE 訊息包含案件編號與預估等待時間。

*   **不變性 (Invariants)**:
    1. ProblemCard 與完整對話記錄必須附加在轉接請求中。
    2. L3 升級不可失敗（即使無線上客服，也必須建立記錄並排程回撥）。

---

### 測試情境與案例 (ThreeLayerResolver)

#### 情境 1: 正常路徑 — L1 高信心命中直接解決

*   **測試案例 ID**: `TC-TLR-001`
*   **描述**: ProblemCard 的問題在案例庫中有高度匹配的解決方案（similarity >= 0.85），L1 直接解決。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 建立 ProblemCard: `brand = "Yale"`, `model = "YDM-7116"`, `symptoms = "密碼鍵盤無回應"`。
        - Mock `CaseLibraryStrategy.search()` 回傳 `[{similarity_score: 0.89, solution: "使用 9V 電池緊急供電..."}]`。
    2.  **Act**: 呼叫 `resolve(problem_card, conversation_id)`。
    3.  **Assert**:
        - 驗證回傳 `resolution_layer = "L1"`，`success = True`。
        - 驗證 `answer` 包含解決方案內容。
        - 驗證 `RAGStrategy.generate()` **未被呼叫**。
        - 驗證 `HumanHandoffStrategy.escalate()` **未被呼叫**。
        - 驗證 `conversations.resolution_layer` 更新為 `"L1"`。

#### 情境 2: 正常路徑 — L1 未命中，L2 RAG 成功解決

*   **測試案例 ID**: `TC-TLR-002`
*   **描述**: L1 搜尋結果低於閾值，自動降級至 L2 RAG，RAG 成功生成解決方案。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 建立 ProblemCard: `brand = "Samsung"`, `model = "SHP-DP609"`, `symptoms = "如何新增臨時密碼給訪客"`。
        - Mock `CaseLibraryStrategy.search()` 回傳空列表（最高 score 0.52，低於 0.85）。
        - Mock `RAGStrategy.generate()` 回傳 `{confidence_score: 0.82, answer: "在室內面板按下設定鍵..."}`。
    2.  **Act**: 呼叫 `resolve(problem_card, conversation_id)`。
    3.  **Assert**:
        - 驗證回傳 `resolution_layer = "L2"`，`success = True`。
        - 驗證 `answer` 包含步驟化解決方案。
        - 驗證 `source_references` 列出引用的手冊段落。
        - 驗證 `HumanHandoffStrategy.escalate()` **未被呼叫**。

#### 情境 3: 正常路徑 — L1 和 L2 均失敗，升級至 L3

*   **測試案例 ID**: `TC-TLR-003`
*   **描述**: L1 和 L2 均無法提供合格的解決方案，系統自動升級至 L3 人工轉接。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 建立 ProblemCard: `brand = "Gateman"`, `model = "WV-40"`, `symptoms = "鎖舌卡住完全無法轉動"`, `door_status = "locked_out"`, `urgency = "urgent"`。
        - Mock `CaseLibraryStrategy.search()` 回傳空列表（最高 score 0.41）。
        - Mock `RAGStrategy.generate()` 回傳 `{confidence_score: 0.38, success: False}`。
    2.  **Act**: 呼叫 `resolve(problem_card, conversation_id)`。
    3.  **Assert**:
        - 驗證回傳 `resolution_layer = "L3"`，`needs_escalation = True`。
        - 驗證 `escalation_info` 包含 `ticket_id` 與 `priority = "urgent"`。
        - 驗證 `conversations.status` 為 `"escalated"`。

#### 情境 4: 邊界情況 — L1 多個接近閾值的模糊匹配

*   **測試案例 ID**: `TC-TLR-004`
*   **描述**: L1 搜尋回傳多個 similarity score 接近的結果（例如 0.88, 0.86, 0.85），系統應提供候選清單讓使用者選擇。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 建立 ProblemCard: `brand = "Yale"`, `model = "YDR-323"`, `symptoms = "開門時發出異常聲音"`。
        - Mock `CaseLibraryStrategy.search()` 回傳三筆結果，scores 分別為 0.88, 0.86, 0.85。
    2.  **Act**: 呼叫 `resolve(problem_card, conversation_id)`。
    3.  **Assert**:
        - 驗證回傳 `resolution_layer = "L1"`。
        - 驗證 `answer` 包含三個候選方案，格式為可選擇的列表。
        - 驗證 `requires_user_selection = True`。

#### 情境 5: 邊界情況 — L1 閾值邊界值行為

*   **測試案例 ID**: `TC-TLR-005`
*   **描述**: 測試 similarity score 恰好等於閾值 0.85 的邊界行為。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Mock `CaseLibraryStrategy.search(threshold=0.85)` 回傳 `[{similarity_score: 0.85, ...}]`。
    2.  **Act**: 呼叫 `resolve(problem_card, conversation_id)`。
    3.  **Assert**:
        - 驗證 `resolution_layer = "L1"` （0.85 **包含在**閾值內，即 `>=` 而非 `>`）。
        - 驗證 `success = True`。

#### 情境 6: 無效輸入 — ProblemCard 未達最低完整度

*   **測試案例 ID**: `TC-TLR-006`
*   **描述**: 傳入 `completeness_score < 0.85` 的 ProblemCard（例如只有 `brand` + `symptoms`，缺其餘欄位），系統應拒絕處理並引導使用者補充資訊。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 建立 ProblemCard: `brand = "Yale"`, 其餘所有欄位為 null，`completeness_score = 0.25`。
    2.  **Act**: 呼叫 `resolve(problem_card, conversation_id)`。
    3.  **Assert**:
        - 預期系統拋出 `ValidationError`，訊息包含 `"completeness_score"` 或 `"symptoms"`。
        - 驗證三層策略均未被執行。

#### 情境 7: 業務規則 — L3 非營業時間升級

*   **測試案例 ID**: `TC-TLR-007`
*   **描述**: L3 升級發生在非營業時間（02:30 AM），系統應建立排程回撥而非即時轉接。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Mock 系統時間為 `02:30 AM`。
        - Mock `CaseLibraryStrategy` 與 `RAGStrategy` 均回傳失敗。
        - Mock 線上客服人員數量為 0。
    2.  **Act**: 呼叫 `resolve(problem_card, conversation_id)`。
    3.  **Assert**:
        - 驗證回傳的 `escalation_info` 包含 `scheduled_callback_at = "09:00"`（次日營業時間）。
        - 驗證 `conversations.status` 為 `"escalated"`，但實際處理時間為排程時間。
        - 驗證回覆訊息包含案件編號與 `"明天上班後第一時間聯繫您"` 語意。

#### 情境 8: 業務規則 — Embedding Service 不可用時的降級處理

*   **測試案例 ID**: `TC-TLR-008`
*   **描述**: Embedding Service 暫時不可用，L1 和 L2 均無法執行向量搜尋，系統應直接降級至 L3。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Mock `EmbeddingService` 拋出 `ExternalServiceError`。
    2.  **Act**: 呼叫 `resolve(problem_card, conversation_id)`。
    3.  **Assert**:
        - 驗證系統不拋出未捕獲的例外。
        - 驗證回傳 `resolution_layer = "L3"`，`needs_escalation = True`。
        - 驗證日誌中記錄 Embedding Service 失敗的警告。
        - 驗證 `escalation_info.reason` 包含 `"external_service_unavailable"`。

---

