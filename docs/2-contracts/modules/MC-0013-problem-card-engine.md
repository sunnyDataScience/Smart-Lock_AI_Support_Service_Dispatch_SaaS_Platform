---
id: MOD-PCE
title: problem-card-engine — V1.0 Canonical Module Contract
tier: 2
status: accepted
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: code
source-paths:
  - api/services/problem_card_service.py
  - agent/product_info/_common/troubleshoot.md
  - api/routers/problem_cards.py
synced-at: 2026-05-15
related:
  - "../flows/business/BF-0001-work-order-lifecycle.md"
  - "../flows/sub/SF-WO-01-happy-path.md"
  - "../functional-requirements/FR-0002-problem-card-triage.md"
  - "../../1-decisions/module-boundary/ARCH-0002-module-boundary-agent.md"
  - "../../4-exploration/agent-harness-v2/problem-card-spec.md (V2.0 future design)"
legacy_id: V1-Module-02 + 02-design/agent-harness/problem-card-spec.md
canonical_for: ProblemCard module
canonical_at: 2026-05-10
notice: |
  本檔為 ProblemCard module 的唯一 V1.0 canonical contract。
  原 problem-card-engine-v1.md 已 rename 為本檔。
  原 problem-card-engine.md (V2 design) 搬至 4-exploration/agent-harness-v2/problem-card-spec.md。
---

# problem-card-engine-v1 — V1.0 Core Module Contract

> 從 `_pending-split-v1-core-modules.md` (V1.0 5-9 module spec) 模組 2 抽出。
> 待重構為 VibeCoding `module-contract.template.md` 的 pre/post conditions 結構。

## 模組 2: ProblemCardEngine (GenerateProblemCardUseCase) — 對應 BDD Feature: F-102 / 流程 F-001 / F-002

**所在路徑**: `backend/src/smart_lock/application/problem_card/use_cases.py`
**對應領域層**: `backend/src/smart_lock/domains/problem_card/entities.py`
**對應 BDD Feature**: `docs/03_behavior_driven_development.md#feature-problemcard-智慧分診`
**對應資料庫表**: `problem_cards`

**模組描述**: ProblemCardEngine 負責從多輪對話中萃取結構化資訊，生成 ProblemCard 診斷卡。它使用 LLM 進行實體擷取（品牌、型號、位置、門況、網路狀態、症狀），計算欄位完整度分數，並在資訊不足時產生追問問題。ProblemCard 是三層解決機制的核心輸入。

---

### 規格 2-1: `generate_problem_card`

**描述 (Description)**: 從對話上下文與訊息記錄中，利用 LLM 提取結構化欄位，建立或更新 ProblemCard。

**函式簽名**:
```python
async def generate_problem_card(
    self,
    conversation_id: uuid.UUID,
    collected_fields: dict,
    conversation_messages: list[MessageDTO],
) -> ProblemCardResponseDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `conversation_id` 對應的 `conversations` 記錄必須存在。
    2. `collected_fields` 為字典，鍵為 ProblemCard 欄位名稱（`brand`, `model`, `location`, `door_status`, `network_status`, `symptoms`），值為字串或 null。
    3. `conversation_messages` 至少包含一則 `role = "user"` 的訊息。
    4. LLMGateway 服務可用。

*   **後置條件 (Postconditions)**:
    1. `problem_cards` 表中已建立或更新一筆記錄，`conversation_id` 外鍵指向傳入的對話。
    2. `completeness_score` 已根據關鍵欄位填充率重新計算（計算公式見規格 2-2）。
    3. `extracted_fields` JSONB 中記錄了 LLM 每個欄位的原始擷取結果與 confidence score。
    4. 若 `completeness_score >= 0.85`（合約要求 ProblemCard 必要欄位完整率 >= 85%），`status` 為 `"confirmed"` 或保持 `"incomplete"`（視是否有使用者確認）。
    5. 回傳的 `ProblemCardResponseDTO` 包含 `missing_fields` 列表與對應的 `follow_up_questions`。

*   **不變性 (Invariants)**:
    1. `completeness_score` 永遠在 `0.0` ~ `1.0` 之間。
    2. 一個 `conversations` 最多對應一張 `problem_cards`（UNIQUE FK 約束）。
    3. `symptoms` JSONB 欄位始終為陣列格式。

---

### 規格 2-2: `evaluate_completeness`

**描述 (Description)**: 根據 ProblemCard 的欄位填充情況計算完整度分數。

**函式簽名**:
```python
def evaluate_completeness(self, problem_card: ProblemCard) -> float:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `problem_card` 為合法的 ProblemCard 實體（非 None）。

*   **後置條件 (Postconditions)**:
    1. 回傳值為 `0.0` ~ `1.0` 之間的浮點數。
    2. 計算規則：`brand` 權重 0.25，`symptoms` 權重 0.25，`model` 權重 0.15，`location` 權重 0.15，`door_status` 權重 0.10，`network_status` 權重 0.10。
    3. 某欄位非空（非 None 且非空字串）時，獲得該權重的全部分數。

*   **不變性 (Invariants)**:
    1. 欄位權重之和始終等於 `1.0`。
    2. 此方法為純函式，不產生副作用。

---

### 測試情境與案例 (ProblemCardEngine)

<!-- TC-ID: IT-0017 | legacy: TC-PCE-001 -->
#### 情境 1: 正常路徑 — 所有欄位齊全時生成完整 ProblemCard

*   **測試案例 ID**: `TC-PCE-001`
*   **描述**: 對話中已收集到全部六個欄位，系統應生成 `completeness_score = 1.0` 的 ProblemCard。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 建立 `conversation_id` 對應的對話記錄。
        - 設定 `collected_fields = {"brand": "Samsung", "model": "SHP-DP609", "location": "新北市板橋區", "door_status": "closed_locked", "network_status": "wifi_connected", "symptoms": "指紋辨識失敗率突然升高"}`。
        - Mock LLMGateway 回傳與 `collected_fields` 一致的擷取結果。
    2.  **Act**: 呼叫 `generate_problem_card(conversation_id, collected_fields, messages)`。
    3.  **Assert**:
        - 驗證 `problem_cards` 表中記錄的 `brand` 為 `"Samsung"`、`model` 為 `"SHP-DP609"`。
        - 驗證 `completeness_score` 為 `1.0`。
        - 驗證 `status` 為 `"confirmed"`。
        - 驗證回傳 DTO 的 `missing_fields` 為空列表。

<!-- TC-ID: IT-0018 | legacy: TC-PCE-002 -->
#### 情境 2: 正常路徑 — 僅有品牌與症狀的最低限度 ProblemCard

*   **測試案例 ID**: `TC-PCE-002`
*   **描述**: 僅收集到 `brand` 和 `symptoms`，ProblemCard 達到觸發解決引擎的最低門檻。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 設定 `collected_fields = {"brand": "Yale", "symptoms": "鎖打不開"}`，其餘欄位為 null。
    2.  **Act**: 呼叫 `generate_problem_card(conversation_id, collected_fields, messages)`。
    3.  **Assert**:
        - 驗證 `completeness_score` 為 `0.5`（brand 0.25 + symptoms 0.25）。
        - 驗證 `missing_fields` 包含 `["model", "location", "door_status", "network_status"]`。
        - 驗證 `follow_up_questions` 非空，第一個問題詢問型號。

<!-- TC-ID: IT-0019 | legacy: TC-PCE-003 -->
#### 情境 3: 邊界情況 — 停產型號處理

*   **測試案例 ID**: `TC-PCE-003`
*   **描述**: 使用者的電子鎖型號已標記為停產，系統應在 ProblemCard 中標記並提供替代建議。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 設定 `collected_fields = {"brand": "Milre", "model": "MI-6800"}`。
        - 產品資料庫中 `MI-6800` 標記為 `discontinued = true`，替代型號為 `["MI-7800", "MI-8000"]`。
    2.  **Act**: 呼叫 `generate_problem_card(conversation_id, collected_fields, messages)`。
    3.  **Assert**:
        - 驗證 `extracted_fields` JSONB 中包含 `"discontinued_model": true`。
        - 驗證回傳 DTO 包含替代型號建議。
        - 驗證系統仍繼續處理（不因停產而中斷服務）。

<!-- TC-ID: IT-0020 | legacy: TC-PCE-004 -->
#### 情境 4: 邊界情況 — 重複生成 ProblemCard（冪等性）

*   **測試案例 ID**: `TC-PCE-004`
*   **描述**: 同一 `conversation_id` 重複呼叫 `generate_problem_card`，應更新既有記錄而非建立新記錄。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 已存在 `problem_cards` 記錄，`conversation_id` 對應，`brand = "Yale"`，`model = null`。
        - 新的 `collected_fields = {"brand": "Yale", "model": "YDM-7116"}`。
    2.  **Act**: 呼叫 `generate_problem_card(conversation_id, collected_fields, messages)`。
    3.  **Assert**:
        - 驗證 `problem_cards` 表中仍只有一筆記錄（未重複建立）。
        - 驗證 `model` 已更新為 `"YDM-7116"`。
        - 驗證 `completeness_score` 已重新計算。

<!-- TC-ID: IT-0021 | legacy: TC-PCE-005 -->
#### 情境 5: 無效輸入 — 空的對話訊息列表

*   **測試案例 ID**: `TC-PCE-005`
*   **描述**: 傳入空的 `conversation_messages`，系統應拋出驗證例外。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: 設定 `conversation_messages = []`。
    2.  **Act**: 呼叫 `generate_problem_card(conversation_id, {}, [])`。
    3.  **Assert**:
        - 預期系統拋出 `ValidationError`，訊息包含 `"conversation_messages"`。
        - 驗證 `problem_cards` 表未寫入任何記錄。

<!-- TC-ID: IT-0022 | legacy: TC-PCE-006 -->
#### 情境 6: 業務規則 — 優先度自動分類

*   **測試案例 ID**: `TC-PCE-006`
*   **描述**: 根據 `door_status` 與 `symptoms` 自動設定 ProblemCard 的 `urgency` 等級。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 測試案例 A: `door_status = "locked_out"`, `symptoms = "密碼鍵盤無回應"` => 預期 `urgency = "high"`。
        - 測試案例 B: `door_status = "locked_out"`, `symptoms = "人被鎖在門外"` => 預期 `urgency = "urgent"`。
        - 測試案例 C: `door_status = "normal"`, `symptoms = "WiFi 連線失敗"` => 預期 `urgency = "low"`。
    2.  **Act**: 分別呼叫 `generate_problem_card`。
    3.  **Assert**:
        - 驗證各案例的 `urgency` 欄位符合預期分類。

---

