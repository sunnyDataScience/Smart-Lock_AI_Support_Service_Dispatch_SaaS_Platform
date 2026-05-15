---
id: MOD-V1-07
title: proactive-photo-guidance — V1.0 Core Module
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
legacy_id: V1-Module-7
extracted_from: _pending-split-v1-core-modules.md (lines 1235-1286)
---

# proactive-photo-guidance — V1.0 Core Module Contract

> 從 `_pending-split-v1-core-modules.md` (V1.0 5-9 module spec) 模組 7 抽出。
> 待重構為 VibeCoding `module-contract.template.md` 的 pre/post conditions 結構。

## 模組 7: ProactivePhotoGuidance (GuidePhotoUploadUseCase) — 對應 BDD Feature: F-108 / 流程 F-001 / F-006

**模組職責**: 當消費者描述模糊導致 ProblemCard 完整率不足合約要求的 85% 時，主動引導上傳特定部位照片。合約 9.3 條要求。圖片僅作為附件存儲，不進行 AI 影像辨識（SOW 2.1(4) 排除項）。

### 規格 7-1: `evaluate_and_guide_photo_upload`

**描述**: 評估 ProblemCard 完整度，若低於閾值且缺乏視覺診斷資訊，則發送 LINE Flex Message 引導上傳照片。

**函式簽名**:
```python
async def evaluate_and_guide_photo_upload(
    self,
    problem_card: ProblemCard,
    conversation_id: UUID,
) -> PhotoGuidanceResultDTO:
```

**契約式設計**:

*   **前置條件**: ProblemCard 已建立且 `completeness_score < 0.85`。
*   **後置條件**:
    1. 若觸發引導：LINE Flex Message 已發送，包含照片拍攝指引與示意圖。
    2. 若不觸發（completeness >= 0.85 或症狀描述已充分具體）：不發送引導訊息。
    3. 照片引導記錄至對話日誌。

**照片引導類型**:
- `lock_bolt_side`：鎖舌側面照（門側邊可看到鎖舌位置）
- `handle_front`：把手/面板正面照
- `error_code_screen`：錯誤代碼螢幕截圖
- `installation_overview`：安裝環境全景照

### 規格 7-2: `attach_photo_to_problem_card`

**描述**: 消費者上傳照片後，將照片 URL 附加至 ProblemCard。

**函式簽名**:
```python
async def attach_photo_to_problem_card(
    self,
    problem_card_id: UUID,
    image_url: str,
    photo_type: str | None = None,
) -> None:
```

**契約式設計**:

*   **前置條件**: `problem_card_id` 對應的 ProblemCard 存在。`image_url` 為有效 URL。
*   **後置條件**: ProblemCard `attachment_links` JSONB 陣列新增一筆 `{url, photo_type, uploaded_at}`。

---

## 測試情境與案例 (ProactivePhotoGuidance)

<!-- TC-ID: IT-0111 -->
#### 情境 1: 正常路徑 — 完整度 0.6 觸發 lock_bolt_side 引導
*   **Arrange**: ProblemCard pc-001 completeness_score=0.6（< 0.85），缺視覺診斷資訊。
*   **Act**: evaluate_and_guide_photo_upload(pc-001, conv-001)。
*   **Assert**: LINE Flex Message 已發送含 `lock_bolt_side` 拍攝指引 + 示意圖；conversation_logs 含 1 筆 photo_guidance；audit `photo.guidance_sent`。

<!-- TC-ID: IT-0112 -->
#### 情境 2: 正常路徑 — 上傳照片 attach 到 ProblemCard
*   **Arrange**: pc-001 attachment_links=[]；客戶上傳 LINE 照片。
*   **Act**: attach_photo_to_problem_card(pc-001, https://cdn/abc.jpg, photo_type=lock_bolt_side)。
*   **Assert**: attachment_links 新增 `{url, photo_type:lock_bolt_side, uploaded_at}`；不執行 AI 影像辨識（per SOW 2.1(4) 排除）。

<!-- TC-ID: IT-0113 -->
#### 情境 3: 邊界 — completeness=0.85 剛好不觸發
*   **Arrange**: pc-edge completeness=0.85 (=閾值)。
*   **Act**: evaluate_and_guide_photo_upload。
*   **Assert**: 不發送 Flex Message；不寫 photo_guidance；回傳 `{triggered: false, reason: "completeness_threshold_met"}`。

<!-- TC-ID: IT-0114 -->
#### 情境 4: 邊界 — 同 ProblemCard 已引導不重複發送
*   **Arrange**: pc-001 之前已有 photo_guidance log 24h 內。
*   **Act**: 再次 evaluate。
*   **Assert**: 不重複發 Flex；audit `photo.guidance_dedupe`。

<!-- TC-ID: IT-0115 -->
#### 情境 5: 異常 — image_url 不合法
*   **Arrange**: pc-001。
*   **Act**: attach_photo_to_problem_card(pc-001, "not-a-url")。
*   **Assert**: 回 422 `invalid_url`；attachment_links 不變。

<!-- TC-ID: IT-0116 -->
#### 情境 6: 業務規則 — 完整度 < 85% 是合約要求門檻
*   **Arrange**: 合約 9.3 條要求 completeness ≥ 85% 才能 dispatch。
*   **Act**: 派工前檢查 pc-001 completeness=0.7 (即使已引導照片但仍未上傳)。
*   **Assert**: dispatch_engine.assign() 回 422 `completeness_below_contract_threshold`；audit `dispatch.blocked.completeness`。
