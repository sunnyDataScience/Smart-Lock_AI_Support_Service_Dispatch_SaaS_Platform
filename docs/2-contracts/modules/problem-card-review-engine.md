---
id: MOD-V1-09
title: problem-card-review-engine — V1.0 Core Module
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
legacy_id: V1-Module-9
extracted_from: _pending-split-v1-core-modules.md (lines 1321-1401)
---

# problem-card-review-engine — V1.0 Core Module Contract

> 從 `_pending-split-v1-core-modules.md` (V1.0 5-9 module spec) 模組 9 抽出。
> 待重構為 VibeCoding `module-contract.template.md` 的 pre/post conditions 結構。

## 模組 9: ProblemCardReviewEngine (ReviewProblemCardUseCase) — 對應 BDD Feature: F-105 / 流程 F-002

**模組職責**: 客服收到 ConversationManager 產出的 `confirmed` ProblemCard 後，執行人工審核（核可 / 退回 / 補資訊），並在核可時觸發 WorkOrder 建立。本模組是 V1.0 後台首次干預 AI 自動流程的閘門，亦是 V2.0 派工流程（F-003 / F-004）的入口。

**對應 API 端點**:
- `POST /api/v1/problem-cards/{id}/confirm`（operationId: `confirmProblemCard`）— 規格 9-1 的薄包裝
- 內部觸發：`create_work_order_from_problem_card`（規格 9-2，無公開 endpoint，由 review approve 後 server-side 啟動）

### 規格 9-1: `review_problem_card`

**描述 (Description)**: 客服對狀態為 `confirmed` 的 ProblemCard 執行最終審核決策，決定是否進入派工流程。

**函式簽名**:
```python
async def review_problem_card(
    self,
    problem_card_id: UUID,
    reviewer_id: UUID,
    action: str,  # "approved" | "rejected" | "needs_info"
    comment: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> ProblemCardReviewResultDTO:
```

**契約式設計**:

*   **前置條件**:
    1. `problem_card_id` 對應的 PC 存在且 `status = "confirmed"`。
    2. `reviewer_id` 對應使用者具備 `customer_service` 或以上角色（依 RBAC，F-019 / 模組 14）。
    3. `action` 必為 `"approved" / "rejected" / "needs_info"` 之一。
    4. 若 `action = "rejected"` 或 `"needs_info"`，`comment` 必填。
*   **後置條件**:
    1. `audit_logs` 寫入一筆 review action（`reviewer_id`, `problem_card_id`, `action`, `comment`, `decided_at`），APPEND-ONLY。
    2. 若 `action = "approved"`：呼叫 `create_work_order_from_problem_card`（規格 9-2），PC 維持 `confirmed`（後續由 WorkOrder lifecycle 接管）。
    3. 若 `action = "rejected"`：PC.status 設為 `"closed_by_review"`，附 `comment` 為 reason。
    4. 若 `action = "needs_info"`：PC.status 回退為 `"draft"`，重新觸發 ConversationManager 收集流程（模組 1）。
*   **不變性**:
    1. 同一 PC 不可重複核可（透過 `idempotency_key` 阻擋；對應 `Idempotency-Key` HTTP header）。
    2. 審核紀錄寫入 audit_logs 後不可修改或刪除。
    3. tenant 隔離：reviewer 的 tenant_id 必須等於 PC 的 tenant_id（multi-tenant 邊界）。

### 規格 9-2: `create_work_order_from_problem_card`

**描述 (Description)**: 從核可的 ProblemCard 建立對應的 WorkOrder，繼承 PC 上下文（地址、緊急度、品牌、症狀），初始 status = `"created"`，並觸發派工媒合（F-003 / F-202）。

**函式簽名**:
```python
async def create_work_order_from_problem_card(
    self,
    problem_card_id: UUID,
    created_by: UUID,
) -> WorkOrderDTO:
```

**契約式設計**:

*   **前置條件**:
    1. PC.status = `"confirmed"` 且最近一次 review action = `"approved"`（規格 9-1 後置條件 2 觸發）。
    2. PC 必填欄位齊全：`brand`, `model`, `address`, `urgency`, `symptoms`（completeness_score >= 0.85）。
    3. PC 尚未綁定既有 WorkOrder（一張 PC 對一張 WO）。
*   **後置條件**:
    1. `work_orders` 表新增一筆 row：`status = "created"`、`problem_card_id` 反向引用、`tenant_id` 繼承自 PC、`urgency` 從 PC 複製。
    2. 觸發 `TechnicianMatcher`（模組 7）執行派工媒合演算法（dispatch §2 / F-202）。
    3. `audit_logs` 記錄 WO 建立來源（`source = "pc_review_approved"`, `pc_id`, `created_by`）。
*   **不變性**:
    1. 一張 PC 至多對應一張 WO（多次核可仍視為同一 WO，靠規格 9-1 idempotency 防重複）。
    2. WO.tenant_id 必須等於 PC.tenant_id（multi-tenant 邊界）。
    3. WO 建立失敗時 PC 狀態不得變更（transactional：要嘛兩者都成功，要嘛回滾）。

### 測試情境與案例 (ProblemCardReviewEngine)

> 本模組詳細測試案例（TC-PCR-NNN）待 V1.0 admin BDD F-105 細化後補充於 `附錄 A`。涵蓋情境包含：

- **Happy Path**: 客服核可 confirmed PC → WO 自動建立 + 派工觸發
- **Edge Case**: 客服重複核可同一 PC（idempotency 阻擋）
- **Edge Case**: 客服退回 PC（needs_info）→ 對話續寫 → 再次 confirmed → 二度送審
- **Invalid Input**: 對非 confirmed 狀態的 PC 執行 review（前置條件違反 → 409）
- **Business Rule**: 跨 tenant 審核被 RBAC 阻擋（前置條件 3 違反 → 403）

---

