---
id: MOD-V1-06
title: sentiment-triage-engine — V1.0 Core Module
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
legacy_id: V1-Module-6
extracted_from: _pending-split-v1-core-modules.md (lines 1103-1234)
---

# sentiment-triage-engine — V1.0 Core Module Contract

> 從 `_pending-split-v1-core-modules.md` (V1.0 5-9 module spec) 模組 6 抽出。
> 待重構為 VibeCoding `module-contract.template.md` 的 pre/post conditions 結構。

## 模組 6: SentimentTriageEngine (AnalyzeSentimentUseCase) — 對應 BDD Feature: F-107 / 流程 F-016 / F-018

**模組職責**: 即時分析消費者訊息的情緒傾向，偵測負面情緒關鍵詞（合約 9.3 條），觸發優先回應協議並通知真人管理員。合約驗收標準：負面情緒識別率 >= 90%。

### 規格 6-1: `analyze_sentiment`

**描述 (Description)**: 對消費者訊息進行情緒分析，返回情緒標籤、信心分數及是否觸發升級。

**函式簽名**:
```python
async def analyze_sentiment(
    self,
    message_text: str,
    conversation_id: UUID,
) -> SentimentResultDTO:
```

**契約式設計 (Design by Contract, DbC)**:

*   **前置條件 (Preconditions)**:
    1. `message_text` 為非空字串，`role = "user"` 的訊息。
    2. `conversation_id` 對應的對話記錄存在。

*   **後置條件 (Postconditions)**:
    1. 返回 `SentimentResultDTO` 包含 `sentiment_label`（positive / neutral / negative）、`confidence`（0.0 ~ 1.0）、`trigger_escalation`（bool）。
    2. 若 `sentiment_label = "negative"` 且 `confidence >= 0.85`：
       - `trigger_escalation = True`
       - 系統透過 LINE Push API 通知管理員（含對話摘要 + ProblemCard 連結）。
       - 對話切換為安撫語氣回覆模板。
       - ProblemCard 的 `sentiment_label` 欄位更新為 `"negative"`。
    3. 情緒分析結果記錄至 `audit_logs` 表。

*   **不變性 (Invariants)**:
    1. `confidence` 永遠在 `0.0` ~ `1.0` 之間。
    2. 情緒分析不得阻塞主對話流程（以 BackgroundTask 或 asyncio.create_task 執行）。
    3. 負面情緒識別率 >= 90%（以甲方提供之測試集驗證）。

**返回 DTO**:
```python
@dataclass
class SentimentResultDTO:
    sentiment_label: str       # "positive" | "neutral" | "negative"
    confidence: float          # 0.0 ~ 1.0
    trigger_escalation: bool   # True if negative + high confidence
    detected_keywords: list[str]  # matched negative keywords
```

**負面情緒關鍵詞清單**（基礎清單，可透過管理後台擴充）:
- 投訴類：「不能接受」「要求投訴」「找你們主管」「我要退費」「叫你們經理來」
- 情緒類：「太離譜」「什麼爛服務」「受夠了」「再也不會用」「垃圾」
- 威脅類：「要告你們」「消保官」「媒體」「律師」

---

### 規格 6-2: `notify_admin_escalation`

**描述 (Description)**: 當偵測到負面情緒時，透過 LINE Push API 通知管理員並記錄。

**函式簽名**:
```python
async def notify_admin_escalation(
    self,
    conversation_id: UUID,
    sentiment_result: SentimentResultDTO,
    problem_card_id: UUID | None,
) -> None:
```

**契約式設計**:

*   **前置條件**: `sentiment_result.trigger_escalation = True`。
*   **後置條件**:
    1. LINE Push 訊息已發送至管理員群組，包含：對話摘要、消費者原始訊息、ProblemCard 連結、情緒分析結果。
    2. `admin_notifications` 表新增一筆紀錄。
    3. 通知發送失敗時不中斷主流程，僅記錄錯誤日誌。

---

### 測試情境與案例 (SentimentTriageEngine)

<!-- TC-ID: IT-0141 | legacy: TC-STE-001 -->
#### 情境 1: 正常路徑 — 偵測明確負面情緒並通知管理員

*   **測試案例 ID**: `TC-STE-001`
*   **描述**: 消費者訊息包含「不能接受」，系統應識別為負面情緒並觸發管理員通知。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: 建立對話記錄，消費者發送 `"不能接受這種服務品質，等了三天都沒人來"`。
    2.  **Act**: 呼叫 `analyze_sentiment(message_text, conversation_id)`。
    3.  **Assert**:
        - 驗證 `sentiment_label = "negative"`。
        - 驗證 `confidence >= 0.90`。
        - 驗證 `trigger_escalation = True`。
        - 驗證 `detected_keywords` 包含 `"不能接受"`。
        - 驗證 LINE Push API 被呼叫（Mock 驗證）。
        - 驗證 ProblemCard `sentiment_label` 已更新為 `"negative"`。

<!-- TC-ID: IT-0142 | legacy: TC-STE-002 -->
#### 情境 2: 正常路徑 — 中性訊息不觸發升級

*   **測試案例 ID**: `TC-STE-002`
*   **描述**: 消費者發送一般技術問題，系統應識別為中性情緒，不觸發任何通知。
*   **測試步驟**:
    1.  **Arrange**: 消費者發送 `"請問 Samsung SHP-DP609 怎麼設定臨時密碼？"`。
    2.  **Act**: 呼叫 `analyze_sentiment(message_text, conversation_id)`。
    3.  **Assert**:
        - 驗證 `sentiment_label = "neutral"`。
        - 驗證 `trigger_escalation = False`。
        - 驗證 LINE Push API **未被呼叫**。

<!-- TC-ID: IT-0143 | legacy: TC-STE-003 -->
#### 情境 3: 邊界情況 — 隱含不滿但未使用關鍵詞

*   **測試案例 ID**: `TC-STE-003`
*   **描述**: 消費者表達隱含不滿（如「已經試了很多次了」），系統應正確識別。
*   **測試步驟**:
    1.  **Arrange**: 消費者發送 `"已經試了很多次了，真的很煩，你們到底行不行"`。
    2.  **Act**: 呼叫 `analyze_sentiment(message_text, conversation_id)`。
    3.  **Assert**:
        - 驗證 `sentiment_label = "negative"`。
        - 驗證 `confidence >= 0.85`。
        - 驗證系統切換為安撫語氣回覆。

<!-- TC-ID: IT-0144 | legacy: TC-STE-004 -->
#### 情境 4: 效能約束 — 情緒分析不阻塞對話

*   **測試案例 ID**: `TC-STE-004`
*   **描述**: 情緒分析應以 BackgroundTask 執行，不影響對話回應速度。
*   **測試步驟**:
    1.  **Arrange**: 設定 Mock LLM 情緒分析延遲 2 秒。
    2.  **Act**: 呼叫 `process_message()`（包含情緒分析）。
    3.  **Assert**:
        - 驗證 LINE Webhook 回應在 1 秒內返回 200。
        - 驗證情緒分析以 BackgroundTask 排入佇列。

<!-- TC-ID: IT-0145 -->
#### 情境 5: 異常 — LINE Push API 失敗不中斷主流程
*   **Arrange**: 偵測 negative，trigger_escalation=true；mock LINE Push API 回 500。
*   **Act**: notify_admin_escalation。
*   **Assert**: 主對話流程仍正常回覆消費者；admin_notifications 表新增 1 筆 status=failed；error_log 記錄但不 raise exception；retry queue 排程下次重試。

<!-- TC-ID: IT-0146 -->
#### 情境 6: 業務規則 — 負面情緒識別率 ≥ 90% (合約 9.3 條)
*   **Arrange**: 甲方測試集 100 條訊息 (50 negative + 50 neutral/positive)。
*   **Act**: 跑全部訊息過 analyze_sentiment。
*   **Assert**: True positive rate ≥ 90% (≥ 45/50 negative 被正確識別)；False positive rate ≤ 10% (≤ 5/50 neutral 誤判 negative)；audit_logs 含 batch_eval 摘要。

---

