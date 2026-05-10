---
id: MOD-V1-08
title: family-review-engine — V1.0 Core Module
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
legacy_id: V1-Module-8
extracted_from: _pending-split-v1-core-modules.md (lines 1287-1320)
---

# family-review-engine — V1.0 Core Module Contract

> 從 `_pending-split-v1-core-modules.md` (V1.0 5-9 module spec) 模組 8 抽出。
> 待重構為 VibeCoding `module-contract.template.md` 的 pre/post conditions 結構。

## 模組 8: FamilyReviewEngine (FamilyReviewUseCase) — 對應 BDD Feature: F-109（V1.0 後段）/ 流程 cross-cutting

**模組職責**: 實現甲方指定家族成員對 SOP 草稿的覆核機制。合約 4.4(d) 要求覆核率 100%，覆核紀錄不可刪除。

### 規格 8-1: `submit_family_review`

**描述**: 家族覆核員對已通過管理員初審的 SOP 草稿進行最終覆核（通過/退回）。

**函式簽名**:
```python
async def submit_family_review(
    self,
    sop_draft_id: UUID,
    reviewer_id: UUID,
    action: str,  # "approved" | "rejected"
    comment: str,
) -> FamilyReviewRecordDTO:
```

**契約式設計**:

*   **前置條件**:
    1. `sop_draft_id` 對應的 SOP 草稿 `status = "admin_approved"`。
    2. `reviewer_id` 對應使用者具有 `family_reviewer` 角色。
*   **後置條件**:
    1. `family_review_records` 表新增一筆不可刪除之紀錄（reviewer_id, action, comment, reviewed_at）。
    2. 若 `action = "approved"`：SOP 草稿 `status` 更新為 `"family_approved"`，可正式入庫。
    3. 若 `action = "rejected"`：SOP 草稿 `status` 更新為 `"family_rejected"`，通知原審管理員。
*   **不變性**:
    1. 覆核紀錄一經寫入不可修改或刪除（APPEND-ONLY）。
    2. 所有 SOP 入庫前必須經過家族覆核（覆核率 100%）。

---

