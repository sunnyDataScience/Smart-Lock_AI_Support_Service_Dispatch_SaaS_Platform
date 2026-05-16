---
id: MOD-V1-05
title: sop-generator — V1.0 Core Module
tier: 2
status: accepted
last-synced-with: dccfc0019fa897a3e5b37c4ae1130e6240190d6b
sync-source: code
source-paths:
  - api/services/sop_draft_service.py
  - agent/harness/sop_extractor.py
  - data/pipeline/silver_to_skill/
synced-at: 2026-05-16
related:
  - "../flows/business/_pending-split_BF-work-order.md"
  - "../functional-requirements/"
  - "../../1-decisions/module-boundary/{agent,api}.md"
legacy_id: V1-Module-5
extracted_from: _pending-split-v1-core-modules.md (lines 902-1102)
---

# sop-generator — V1.0 Core Module Contract

> 從 `_pending-split-v1-core-modules.md` (V1.0 5-9 module spec) 模組 5 抽出。
> 待重構為 VibeCoding `module-contract.template.md` 的 pre/post conditions 結構。

## 模組 5: SOPGenerator (DraftSOPUseCase) — 對應 BDD Feature: F-104（自進化）/ 流程 F-017

**所在路徑**: `backend/src/smart_lock/application/knowledge_base/use_cases.py`
**對應領域層**: `backend/src/smart_lock/domains/knowledge_base/entities.py` (SOPDraft)
**對應 BDD Feature**: `docs/03_behavior_driven_development.md#feature-自進化知識庫`
**對應資料庫表**: `sop_drafts`, `case_entries`

**模組描述**: SOPGenerator 是自演化知識庫的核心。當案件成功解決且使用者回饋為正面時，系統自動從對話記錄與 ProblemCard 中萃取解決模式，利用 LLM 生成結構化 SOP 草稿。草稿經管理員審核後，可一鍵發布為正式案例條目，使知識庫持續成長。

---

### 規格 5-1: `draft_sop`

**描述 (Description)**: 從已解決的案件中自動生成 SOP 草稿，包含標題、適用條件、步驟與注意事項。

**函式簽名**:
```python
async def draft_sop(
    self,
    conversation_id: uuid.UUID,
    problem_card_id: uuid.UUID,
) -> SOPDraftResponseDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `conversation_id` 對應的 `conversations` 記錄存在，且 `status` 為 `"resolved"`。
    2. `problem_card_id` 對應的 `problem_cards` 記錄存在，且 `resolution_layer` 不為 null。
    3. 對話中存在至少一則 `role = "assistant"` 的回覆，包含解決方案內容。
    4. 使用者回饋 (`conversations.user_feedback`) 為 `"helpful"`（僅對正面回饋的案件生成 SOP）。
    5. LLMGateway 服務可用。

*   **後置條件 (Postconditions)**:
    1. `sop_drafts` 表新增一筆記錄，`status = "pending_review"`。
    2. `title` 以 `"{brand} {model} {symptom_summary}"` 格式自動生成。
    3. `steps` JSONB 為有序陣列，每個元素包含 `step_number`, `description`, `notes`。
    4. `source_conversation_id` 與 `source_problem_card_id` 正確關聯。
    5. 若為 L3 人工解決的案件，SOP 草稿應區分 `temporary_fix` 與 `permanent_fix` 區段。
    6. 管理員通知已發送（Dashboard 通知或其他機制）。
    7. 回傳的 `SOPDraftResponseDTO` 包含 `sop_draft_id` 與完整草稿內容。

*   **不變性 (Invariants)**:
    1. SOP 草稿不可自動發布，必須經過管理員審核。
    2. `steps` 陣列至少包含 1 個步驟。
    3. 同一 `conversation_id` 不應重複生成 SOP 草稿。

---

### 規格 5-2: `check_duplicate`

**描述 (Description)**: 在提交 SOP 草稿供審核前，檢查知識庫中是否已存在高度相似的案例或 SOP，避免重複。

**函式簽名**:
```python
async def check_duplicate(
    self,
    sop_title: str,
    sop_steps_text: str,
    similarity_threshold: float = 0.90,
) -> DuplicateCheckResultDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `sop_title` 不可為空字串。
    2. `sop_steps_text` 不可為空字串（將 steps JSONB 序列化為純文字）。
    3. `similarity_threshold` 範圍為 `0.0 ~ 1.0`，預設 0.90。
    4. Embedding Service 可用。

*   **後置條件 (Postconditions)**:
    1. 回傳的 `DuplicateCheckResultDTO` 包含 `is_duplicate`（布林值）與 `similar_entries`（相似案例列表）。
    2. 若 `is_duplicate = True`，`similar_entries` 中至少有一筆 `similarity_score >= similarity_threshold` 的案例。
    3. `similar_entries` 包含 `case_entry_id`, `title`, `similarity_score`，按 score 降序排列。
    4. 同時搜尋 `case_entries` 與 `sop_drafts`（status 為 `"pending_review"` 或 `"approved"`）中的已有內容。

*   **不變性 (Invariants)**:
    1. 此方法為查詢操作，不修改任何資料。
    2. 重複檢查基於語義相似度（向量比對），而非精確文字比對。

---

### 測試情境與案例 (SOPGenerator)

<!-- TC-ID: IT-0023 -->
#### 情境 1: 正常路徑 — 從 L2 解決的案件生成 SOP 草稿

*   **測試案例 ID**: `TC-SOP-001`
*   **描述**: 一個透過 L2 RAG 成功解決的案件，使用者回饋為正面，系統應自動生成 SOP 草稿。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 已存在 `conversations` 記錄：`status = "resolved"`, `resolution_layer = "L2"`, `user_feedback = "helpful"`。
        - 已存在 `problem_cards` 記錄：`brand = "Samsung"`, `model = "SHP-DP609"`, `symptoms = ["wifi_connection_fail"]`, `resolution_layer = "L2"`。
        - 對話記錄包含 AI 生成的解決方案步驟。
        - Mock `LLMGateway` 從對話記錄中生成結構化 SOP。
    2.  **Act**: 呼叫 `draft_sop(conversation_id, problem_card_id)`。
    3.  **Assert**:
        - 驗證 `sop_drafts` 表新增一筆記錄。
        - 驗證 `title` 包含 `"Samsung"`, `"SHP-DP609"`, `"WiFi"` 相關語意。
        - 驗證 `steps` JSONB 為非空有序陣列。
        - 驗證 `status` 為 `"pending_review"`。
        - 驗證 `source_conversation_id` 與 `source_problem_card_id` 正確設定。

<!-- TC-ID: IT-0024 -->
#### 情境 2: 正常路徑 — 從 L3 人工解決的案件生成包含臨時/永久修復的 SOP

*   **測試案例 ID**: `TC-SOP-002`
*   **描述**: L3 人工客服解決的案件中，客服紀錄同時包含臨時修復與根本修復方案，SOP 應區分兩個區段。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - `conversations.resolution_layer = "L3"`, `user_feedback = "helpful"`。
        - 對話記錄中人工客服的解決方案包含 `"暫時解決"` 與 `"根本解決"` 兩部分。
    2.  **Act**: 呼叫 `draft_sop(conversation_id, problem_card_id)`。
    3.  **Assert**:
        - 驗證 `steps` JSONB 中包含 `"temporary_fix"` 和 `"permanent_fix"` 兩個區段。
        - 驗證 `notes` 中包含 `"requires_technician: true"` 標記（需派技師到場）。

<!-- TC-ID: IT-0025 -->
#### 情境 3: 邊界情況 — 重複檢測發現高相似度既有案例

*   **測試案例 ID**: `TC-SOP-003`
*   **描述**: 即將生成的 SOP 與已有案例的相似度 >= 0.90，系統應標記為重複並建議合併。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - `case_entries` 表中已有 `"Yale YDM-7116 密碼鍵盤無回應"` 的案例。
        - 準備生成一份幾乎相同問題的 SOP 草稿。
        - Mock Embedding Service 計算兩者向量的 cosine similarity 為 0.92。
    2.  **Act**: 呼叫 `check_duplicate(sop_title="Yale YDM-7116 按鍵沒反應", sop_steps_text="...")`。
    3.  **Assert**:
        - 驗證 `is_duplicate = True`。
        - 驗證 `similar_entries` 至少包含 1 筆，`similarity_score >= 0.90`。
        - 驗證相似案例的 `case_entry_id` 與 `title` 正確回傳。

<!-- TC-ID: IT-0026 -->
#### 情境 4: 邊界情況 — 同一對話不可重複生成 SOP

*   **測試案例 ID**: `TC-SOP-004`
*   **描述**: 同一 `conversation_id` 已生成過 SOP 草稿，再次呼叫應被拒絕。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - `sop_drafts` 表中已有一筆 `source_conversation_id` 匹配的記錄。
    2.  **Act**: 呼叫 `draft_sop(conversation_id, problem_card_id)`。
    3.  **Assert**:
        - 預期系統拋出 `ValidationError` 或回傳已存在的 SOP draft（而非建立新的）。
        - 驗證 `sop_drafts` 表中該 conversation 的記錄數仍為 1。

<!-- TC-ID: IT-0027 -->
#### 情境 5: 無效輸入 — 案件未解決即嘗試生成 SOP

*   **測試案例 ID**: `TC-SOP-005`
*   **描述**: 對話 `status` 不是 `"resolved"` 時嘗試生成 SOP，系統應拒絕。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - `conversations.status = "collecting"`（尚在收集資訊階段）。
    2.  **Act**: 呼叫 `draft_sop(conversation_id, problem_card_id)`。
    3.  **Assert**:
        - 預期系統拋出 `ValidationError`，訊息包含 `"conversation must be resolved"`。
        - 驗證 `sop_drafts` 表未新增記錄。

<!-- TC-ID: IT-0028 -->
#### 情境 6: 無效輸入 — 使用者回饋為負面時不生成 SOP

*   **測試案例 ID**: `TC-SOP-006`
*   **描述**: 使用者回饋 `user_feedback = "not_helpful"`，系統不應為負面回饋的案件生成 SOP。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - `conversations.status = "resolved"`, `user_feedback = "not_helpful"`。
    2.  **Act**: 呼叫 `draft_sop(conversation_id, problem_card_id)`。
    3.  **Assert**:
        - 預期系統拋出 `ValidationError`，訊息包含 `"positive feedback required"` 或類似語意。
        - 驗證 `sop_drafts` 表未新增記錄。

<!-- TC-ID: IT-0029 -->
#### 情境 7: 業務規則 — SOP 發布後自動轉為案例條目

*   **測試案例 ID**: `TC-SOP-007`
*   **描述**: 管理員審核通過並發布 SOP 後，系統應自動將其向量化並加入 `case_entries` 表。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 已存在 `sop_drafts` 記錄，`status = "approved"`。
        - Mock Embedding Service 為 SOP 內容生成 768 維向量。
    2.  **Act**: 呼叫 `adopt_sop_as_case(sop_draft_id)` （AdoptSOPAsCaseUseCase）。
    3.  **Assert**:
        - 驗證 `case_entries` 表新增一筆記錄。
        - 驗證新案例的 `source = "sop_approved"`。
        - 驗證新案例的 `embedding` 維度為 768。
        - 驗證新案例的 `is_active = true`。
        - 驗證 `sop_drafts.status` 更新為 `"published"`。
        - 驗證 `sop_drafts.published_as_case_entry_id` 指向新建的案例條目。
        - 驗證新案例在後續的 L1 向量搜尋中可被命中。

<!-- TC-ID: IT-0030 -->
#### 情境 8: 業務規則 — 管理員退回 SOP 時記錄回饋

*   **測試案例 ID**: `TC-SOP-008`
*   **描述**: 管理員審核退回 SOP 草稿並附上修訂意見，系統應記錄回饋並嘗試重新生成。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 已存在 `sop_drafts` 記錄，`status = "pending_review"`。
    2.  **Act**: 呼叫 `review_sop_draft(sop_draft_id, decision="reject", comment="步驟缺少安全提醒，需補充斷電注意事項")`。
    3.  **Assert**:
        - 驗證 `sop_drafts.status` 更新為 `"rejected"`。
        - 驗證 `sop_drafts.review_comment` 包含管理員的回饋。
        - 驗證 `sop_drafts.reviewed_by` 記錄審核者 ID。
        - 驗證 `sop_drafts.reviewed_at` 記錄審核時間。

---

