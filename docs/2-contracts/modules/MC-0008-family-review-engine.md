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

## 測試情境與案例 (FamilyReviewEngine)

<!-- TC-ID: IT-0063 -->
#### 情境 1: 正常路徑 — 家族成員 approve 後 SOP 變 family_approved

*   **描述**: SOP draft 已 admin_approved，家族覆核員 approve 後 status 應變 family_approved 並可入庫。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - SOP draft `sop-001` status=admin_approved。
        - User `u-fam-001` 角色 family_reviewer。
    2.  **Act**: submit_family_review(sop_draft_id="sop-001", reviewer_id="u-fam-001", action="approved", comment="OK")。
    3.  **Assert**:
        - SOP `status` = `family_approved`。
        - `family_review_records` 新增 1 筆 (sop-001, u-fam-001, approved, "OK", reviewed_at)。
        - 回傳 DTO 含 record_id。
        - knowledge_base 入庫流程 trigger（assert: KB 新增該 SOP）。

<!-- TC-ID: IT-0064 -->
#### 情境 2: 正常路徑 — 家族成員 reject 後 SOP 變 family_rejected + 通知原審員

*   **描述**: 家族 reject SOP，狀態變 family_rejected 並 push 通知給原審 admin。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - SOP `sop-002` status=admin_approved，admin_reviewer_id=u-admin-001。
        - Family reviewer u-fam-001。
    2.  **Act**: submit_family_review(sop-002, u-fam-001, "rejected", "步驟順序錯誤")。
    3.  **Assert**:
        - SOP status=family_rejected。
        - notifications 新增 1 筆 target=u-admin-001, type=`sop.family_rejected`。
        - 覆核紀錄含 comment 完整文字（不裁切）。

<!-- TC-ID: IT-0065 -->
#### 情境 3: 邊界情況 — 同一 SOP 重複覆核（冪等性）

*   **描述**: 同一 SOP 第二次提交 review 應 409 Conflict（一次覆核即終態）。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: SOP `sop-003` 已被 u-fam-001 approve，status=family_approved。
    2.  **Act**: 再呼叫 submit_family_review(sop-003, u-fam-001, "rejected", "改主意")。
    3.  **Assert**:
        - 回 409 `terminal_state`。
        - `family_review_records` 仍只有 1 筆。
        - SOP status 不變（family_approved）。

<!-- TC-ID: IT-0066 -->
#### 情境 4: 邊界情況 — 覆核紀錄 APPEND-ONLY 不可改寫

*   **描述**: 攻擊面 — 嘗試 DELETE/UPDATE family_review_records 應被 DB-level RLS 或 trigger 阻擋（合約 4.4(d) 要求）。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: family_review_records 已有 1 筆 `rec-001`。
    2.  **Act**:
        - `DELETE FROM family_review_records WHERE id='rec-001'` (即使是 super_admin)。
        - `UPDATE family_review_records SET action='approved' WHERE id='rec-001'`。
    3.  **Assert**:
        - 兩個 SQL 都 raise `DatabaseError: append_only_violation`（DB trigger 阻擋）。
        - 紀錄保持原樣。
        - audit_logs 含 `family_review.tamper_attempt` 事件，含 actor=super_admin。

<!-- TC-ID: IT-0067 -->
#### 情境 5: 無效輸入 — 對未通過 admin_approved 的 SOP submit family_review

*   **描述**: 違反前置條件 1（SOP 必須先 admin_approved），應 422 reject。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: SOP `sop-005` status=draft（未 admin 審）。
    2.  **Act**: submit_family_review(sop-005, u-fam-001, "approved", "ok")。
    3.  **Assert**:
        - 回 422 `precondition_failed`，detail=`sop_not_admin_approved`。
        - `family_review_records` 不新增。

<!-- TC-ID: IT-0068 -->
#### 情境 6: 業務規則 — 覆核率 100% 強制檢查 — SOP 未經 family_review 不可入庫

*   **描述**: 不變性 2 — knowledge_base 拒絕 status != family_approved 的 SOP 入庫。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**: SOP `sop-006` status=admin_approved（未經 family review）。
    2.  **Act**: 直接呼叫 `knowledge_base.publish(sop_id="sop-006")` 嘗試繞過。
    3.  **Assert**:
        - 回 403 `family_review_required`。
        - SOP 不入庫，KB 查詢結果不含此 SOP。
        - audit_logs 含 `kb.publish.rejected.family_review_missing` 事件。

