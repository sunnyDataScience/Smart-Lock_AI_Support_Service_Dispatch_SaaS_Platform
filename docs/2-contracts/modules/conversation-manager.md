---
id: MOD-V1-01
title: conversation-manager — V1.0 Core Module
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
legacy_id: V1-Module-1
extracted_from: _pending-split-v1-core-modules.md (lines 61-263)
---

# conversation-manager — V1.0 Core Module Contract

> 從 `_pending-split-v1-core-modules.md` (V1.0 5-9 module spec) 模組 1 抽出。
> 待重構為 VibeCoding `module-contract.template.md` 的 pre/post conditions 結構。

## 模組 1: ConversationManager (ProcessMessageUseCase) — 對應 BDD Feature: F-101 / 流程 F-001 / F-002 / F-018

**所在路徑**: `backend/src/smart_lock/application/conversation/use_cases.py`
**對應領域層**: `backend/src/smart_lock/domains/conversation/entities.py`
**對應 BDD Feature**: `docs/03_behavior_driven_development.md#feature-line-bot-ai-客服對話`
**對應 API 端點**: `POST /api/v1/webhook/line` (LINE Webhook Handler 內部呼叫)

**模組描述**: ConversationManager 是 LINE Bot 客服對話的核心編排器。負責接收使用者訊息後，執行意圖辨識、NER 實體擷取、對話狀態機轉換、ProblemCard 更新，並在資訊收集完成後觸發三層解決機制。此模組必須在 LINE Webhook 的 1 秒回應限制下，將 LLM 呼叫 (2-10 秒) 委派至非同步任務處理。

---

### 規格 1-1: `process_message`

**描述 (Description)**: 接收一則來自 LINE 使用者的訊息，根據當前對話狀態執行相應的業務邏輯（意圖辨識、資訊擷取、狀態轉換），並產生 AI 回覆訊息。

**函式簽名**:
```python
async def process_message(
    self,
    line_user_id: str,
    message_content: str,
    content_type: str = "text",
    metadata: dict | None = None,
) -> ConversationResponseDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `line_user_id` 不可為空，且格式必須為 `U` + 32 位十六進位字元（共 33 字元）。
    2. `message_content` 不可為空字串（text 類型時）。
    3. `content_type` 必須為 `"text"`, `"image"`, `"location"` 之一。
    4. LINE Webhook 簽章驗證已通過（由上層 Webhook Controller 確保）。
    5. Redis 連線可用（用於讀寫對話 Session Cache）。

*   **後置條件 (Postconditions)**:
    1. 使用者訊息已持久化至 `messages` 表，`role` 為 `"user"`。
    2. AI 回覆訊息已持久化至 `messages` 表，`role` 為 `"assistant"`。
    3. 所屬 `conversations` 記錄的 `message_count` 已遞增。
    4. 對話上下文 (`conversations.context` JSONB) 已根據本輪對話更新（包含 `intent`, `collected_fields`, `missing_fields`, `turn_count`）。
    5. 若為新使用者首次訊息，則 `users` 表已建立對應記錄（呼叫 LINE Get Profile API 取得 `display_name`）。
    6. 若為新對話，則 `conversations` 表已建立新記錄，`status` 為 `"active"`，Redis Session Cache 已寫入。
    7. 回傳的 `ConversationResponseDTO` 包含 `reply_messages`（至少一則）與 `conversation_id`。
    8. 整個方法的同步部分（排除 LLM 呼叫）在 500ms 以內完成，LLM 呼叫透過 `asyncio.create_task` 非同步執行。

*   **不變性 (Invariants)**:
    1. 一個 `conversations` 記錄最多關聯一張 `problem_cards` 記錄（1:1 UNIQUE FK）。
    2. 對話狀態只能依照狀態機規則轉換：`active -> collecting -> resolving -> resolved | escalated`，或 `active | collecting -> expired`。
    3. `conversations.message_count` 永遠等於其關聯的 `messages` 記錄總數。
    4. `users.last_active_at` 在每次互動後更新。

---

### 規格 1-2: `resume_expired_session`

**描述 (Description)**: 當使用者在對話超時（30 分鐘無互動）後發送新訊息時，恢復之前的對話上下文，從中斷處繼續收集資訊。

**函式簽名**:
```python
async def resume_expired_session(
    self,
    line_user_id: str,
    expired_conversation_id: uuid.UUID,
) -> ConversationResponseDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `expired_conversation_id` 對應的 `conversations` 記錄存在且 `status` 為 `"expired"`。
    2. 該對話的 `context` JSONB 中包含可恢復的上下文資料（`collected_fields` 不為空）。
    3. `line_user_id` 對應的使用者為該對話的擁有者（`conversations.user_id` 匹配）。

*   **後置條件 (Postconditions)**:
    1. 建立一個新的 `conversations` 記錄，`status` 為 `"collecting"`。
    2. 新對話的 `context` JSONB 從舊對話中繼承 `collected_fields`，`missing_fields` 重新計算。
    3. AI 回覆訊息包含之前已收集的資訊摘要，並詢問下一個缺失欄位。
    4. 舊對話記錄維持 `status = "expired"` 不變。

*   **不變性 (Invariants)**:
    1. 已收集的 ProblemCard 欄位資料不因超時而遺失。
    2. 新對話必須建立新的 `session_id` 並寫入 Redis。

---

### 測試情境與案例 (ConversationManager)

#### 情境 1: 正常路徑 — 新使用者首次發送問題訊息

*   **測試案例 ID**: `TC-CM-001`
*   **描述**: 一個從未互動過的 LINE 使用者發送第一則訊息，系統應建立使用者、建立對話、辨識意圖，並回覆問候語。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Mock `LINE Get Profile API` 回傳 `{"displayName": "王小明", "pictureUrl": "https://..."}`。
        - Mock `LLMGateway.classify_intent()` 回傳 `"lock_malfunction"`。
        - 資料庫中無 `line_user_id = "Uabc123...def"` 的使用者記錄。
    2.  **Act**: 呼叫 `process_message(line_user_id="Uabc123...def", message_content="我家的電子鎖打不開")`。
    3.  **Assert**:
        - 驗證 `users` 表新增一筆記錄，`display_name` 為 `"王小明"`，`role` 為 `"line_user"`。
        - 驗證 `conversations` 表新增一筆記錄，`status` 為 `"collecting"`。
        - 驗證 `messages` 表新增兩筆記錄（user + assistant）。
        - 驗證回傳的 `ConversationResponseDTO.reply_messages` 包含問候語且詢問品牌資訊。
        - 驗證 `conversations.context` 包含 `{"intent": "lock_malfunction", "collected_fields": {}, "missing_fields": ["brand", "model", "location", "door_status", "symptoms"]}`。

#### 情境 2: 正常路徑 — 多輪對話逐步收集 ProblemCard 資訊

*   **測試案例 ID**: `TC-CM-002`
*   **描述**: 使用者在已有的對話中回答品牌問題，系統應更新對話上下文中的 `collected_fields`。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 已存在 `conversations` 記錄，`status = "collecting"`，`context = {"intent": "lock_malfunction", "collected_fields": {}, "missing_fields": ["brand", "model", "location", "door_status", "symptoms"]}`。
        - Mock `LLMGateway.extract_entities()` 回傳 `{"brand": "Yale"}`。
    2.  **Act**: 呼叫 `process_message(line_user_id="Uabc123...def", message_content="品牌是 Yale")`。
    3.  **Assert**:
        - 驗證 `conversations.context.collected_fields` 更新為 `{"brand": "Yale"}`。
        - 驗證 `conversations.context.missing_fields` 不再包含 `"brand"`。
        - 驗證回覆訊息詢問下一個缺失欄位（型號）。
        - 驗證 `conversations.message_count` 遞增 2。

#### 情境 3: 正常路徑 — 資訊收集完成觸發三層解決機制

*   **測試案例 ID**: `TC-CM-003`
*   **描述**: 使用者提供最後一個缺失欄位後，系統應將對話狀態轉為 `"resolving"` 並觸發 ThreeLayerResolver。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 已存在 `conversations` 記錄，`status = "collecting"`，`context.collected_fields = {"brand": "Yale", "model": "YDM-7116", "location": "台北市信義區", "door_status": "closed_locked"}`，`context.missing_fields = ["symptoms"]`。
        - Mock `LLMGateway.extract_entities()` 回傳 `{"symptoms": "密碼鍵盤完全沒反應"}`。
        - Mock `ProblemCardEngine.generate_problem_card()` 回傳 ProblemCard with `status = "confirmed"`。
        - Mock `ThreeLayerResolver.resolve()` 回傳 `ResolutionResultDTO` with `resolution_layer = "L1"`。
    2.  **Act**: 呼叫 `process_message(line_user_id="Uabc123...def", message_content="密碼鍵盤完全沒反應，沒有燈光")`。
    3.  **Assert**:
        - 驗證 `conversations.status` 轉為 `"resolving"`，最終轉為 `"resolved"`。
        - 驗證 `problem_cards` 表已建立記錄，所有欄位填充完整。
        - 驗證 `ThreeLayerResolver.resolve()` 被呼叫。
        - 驗證回覆訊息包含解決方案內容。

#### 情境 4: 邊界情況 — 對話超時後恢復

*   **測試案例 ID**: `TC-CM-004`
*   **描述**: 使用者在對話超時（30 分鐘）後發送新訊息，系統應恢復先前的對話上下文。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 已存在 `conversations` 記錄，`status = "expired"`，`context.collected_fields = {"brand": "Gateman"}`。
        - 該使用者無其他 `active` 狀態的對話。
    2.  **Act**: 呼叫 `process_message(line_user_id="Uabc123...def", message_content="抱歉剛剛在忙")`。
    3.  **Assert**:
        - 驗證新建一筆 `conversations` 記錄，`status = "collecting"`。
        - 驗證新對話的 `context.collected_fields` 包含 `{"brand": "Gateman"}`。
        - 驗證回覆訊息包含 `"Gateman"` 品牌名稱，並詢問型號。

#### 情境 5: 無效輸入 — 使用者發送不相關訊息

*   **測試案例 ID**: `TC-CM-005`
*   **描述**: 使用者發送與電子鎖無關的訊息，系統應禮貌性導引回電子鎖問題。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 已存在 `conversations` 記錄，`status = "active"`。
        - Mock `LLMGateway.classify_intent()` 回傳 `"off_topic"`。
    2.  **Act**: 呼叫 `process_message(line_user_id="Uabc123...def", message_content="今天天氣不錯")`。
    3.  **Assert**:
        - 驗證 `conversations.status` 維持 `"active"` 不變（不進入 `"collecting"`）。
        - 驗證回覆訊息包含引導語，例如 `"我是電子鎖客服助手，請問您的電子鎖有什麼問題需要協助嗎？"`。
        - 驗證未建立 `problem_cards` 記錄。

#### 情境 6: 無效輸入 — LINE User ID 格式不合法

*   **測試案例 ID**: `TC-CM-006`
*   **描述**: 傳入格式不合法的 `line_user_id`，系統應拋出驗證例外。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: 無特殊前置。
    2.  **Act**: 呼叫 `process_message(line_user_id="invalid_id", message_content="test")`。
    3.  **Assert**:
        - 預期系統拋出 `ValidationError`，錯誤訊息包含 `"line_user_id"`。
        - 驗證資料庫未寫入任何記錄。

#### 情境 7: 業務規則 — LINE Webhook 非同步處理保證 1 秒內回應

*   **測試案例 ID**: `TC-CM-007`
*   **描述**: LLM 呼叫耗時 5 秒時，Webhook Handler 仍應在 1 秒內回傳 HTTP 200，LLM 結果透過非同步推播。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Mock `LLMGateway` 所有方法延遲 5 秒回傳。
        - 設定計時器追蹤 `process_message` 的同步回傳時間。
    2.  **Act**: 呼叫 `process_message(line_user_id="Uabc123...def", message_content="電子鎖打不開")`。
    3.  **Assert**:
        - 驗證方法的同步部分在 1000ms 以內回傳。
        - 驗證 LLM 呼叫已透過 `asyncio.create_task` 排入非同步佇列。
        - 驗證回傳的 DTO 包含 `processing = True` 標記（表示正在非同步處理）。

#### 情境 8: 業務規則 — 同一使用者並行對話限制

*   **測試案例 ID**: `TC-CM-008`
*   **描述**: 同一使用者不應同時擁有多個 `active` 或 `collecting` 狀態的對話。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 已存在 `conversations` 記錄，`status = "collecting"`，屬於使用者 `"Uabc123...def"`。
    2.  **Act**: 使用者發送新訊息，系統嘗試處理。
    3.  **Assert**:
        - 驗證系統不會建立新的 `conversations` 記錄。
        - 驗證訊息加入到既有的進行中對話。

---

