---
id: CR-0028
title: "Change Impact Analysis — LINE 公單派出→派工→報價回傳斷鏈修復"
status: built
tier: 4-exploration
owner: HYBRID
created: 2026-06-18
target-release: TBD（Lite 版 / Beta 前）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0028: LINE 公單回傳斷鏈修復

> **Tier**: 4-exploration → Change Impact Analysis（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 User/Business flow + External integration）
> **Generated**: 手動（依 CIA-0000 模板，比照 CR-0025）
> **驅動來源**: 2026-06-17 lock-AI 會議 Action #6 +「§1.2 公單可以開但 LINE 收不到公單回傳（轉真人→派工→報價回 LINE 斷在後台）」+ 決議 4（客戶端走 LINE）
> **依賴**: 複用 CR-0017 outbox 基礎建設（已 BUILD）

---

## 1. Change Statement

**As-is**：工單狀態轉換時**客戶收不到 LINE 通知**。`assign_order`（派工）/ `accept_order`（接單）皆不推 LINE；`scope_change_service.respond_public`（客戶報價決議後）不回推確認。**且** outbox worker 的 reference resolver 對 `work_orders` / `scope_changes` 路徑用了不存在的欄 `work_orders.tenant_id` → 查詢丟例外 → 反查 LINE uid 靜默失敗（既有 `scope_change_proposal` 提案 push 實際也送不出）。

**To-be**：派工、接單、報價決議三個關鍵節點主動推 LINE 給客戶（複用 CR-0017 outbox + Flex builder）；修復 resolver bug 讓 `work_orders` / `scope_changes` 路徑能正確反查客戶 LINE uid。

**Driver**：會議當場實測發現「公單派出→回傳 LINE 斷在後台」（最痛、最具體的工單問題）。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF`（工單派工通知） | Modified | 派工完成 → 推 LINE「已為您安排技師」 |
| `BF`（工單接單通知） | Modified | 技師接單 → 推 LINE「技師已接單」 |
| `BF`（Flow 3 範圍變更） | Modified | 客戶決議後 → 回推 LINE 確認（補 CR-0017 提案 push 之後的回程） |

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `NFR`（送達可靠性） | Unchanged | 沿用 outbox best-effort + retry/backoff，push 失敗不阻斷主業務 |

## 4. Affected API

無新端點。改動在 service 層（`assign_order` / `accept_order` / `respond_public` 內部加 enqueue）。

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `line_push_outbox` | Unchanged | `push_kind VARCHAR(40)` 無 CHECK 約束 → 新增 `work_order_assigned` / `work_order_accepted` / `scope_change_result` **不需 migration** |

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `test_cr_0028_wo_push.py` | New | 三 builder render 合法 Flex / text fallback；accept vs reject 文案不同；`build_messages` dispatch 三新 kind；PushKind Literal 含三新值 |
| `test_cr_0017_*` | Regression | outbox worker + builder 既有測試保持綠燈 |

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| External integration（LINE push） | 擴充 | 複用 CR-0017 outbox→worker→Flex builder，加 3 個 push_kind + builder |
| Bug fix | resolver | `line_push_outbox_worker._resolve_line_uid`：`work_orders`/`scope_changes` 路徑 `wo.tenant_id` → `u.tenant_id`（work_orders 無 tenant_id 欄，租戶過濾走 users，與 `_WO_JOIN` 一致）|
| 新 ADR？ | No | 沿用 CR-0017 架構決策，無新架構邊界 |

## 8. Human Decisions Required

✅ **本階段無阻塞**（會議已授權修此鏈路；推播文案用合理預設，業主日後可調）。

| # | Question | Owner | Status | Decision |
|---|---|---|---|---|
| 1 | 推播文案內容（assign/accept/結果通知）| 業主 | ✅ 預設 | 用合理客服語氣預設（見 builders.py），業主日後微調 |
| 2 | accept push 觸發點（技師接單 vs 客戶確認 vs 施工開始）| 業主 | ✅ 預設 | 暫定**技師接單（accept_order）**時推「技師已接單」；若要改在 in_progress 另議 |

## 9. Suggested Implementation Order（已實作）

1. ✅ builders.py 加 `render_work_order_assigned` / `render_work_order_accepted` / `render_scope_change_result` + 註冊 `BUILDERS`
2. ✅ `line_push_outbox_service.PushKind` 加三新值
3. ✅ `line_push_outbox_worker._resolve_line_uid` 修 `wo.tenant_id`→`u.tenant_id`（2 路徑）
4. ✅ `work_order_service.assign_order` / `accept_order` 加 best-effort enqueue
5. ✅ `scope_change_service.respond_public` 加 best-effort enqueue（從 work_order join 推導 tenant_id）
6. ✅ `test_cr_0028_wo_push.py`（6 案 pass）+ CR-0017 回歸（17 案 pass）
7. ✅ 補正 CR-0017 文件 status → built
8. ⏳ Docs sync：CHANGELOG / system-completion-status（commit 時）

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| resolver 改動波及既有 reschedule/scope push | Low | Medium | `saas.reschedule_proposal` 路徑（用 `rp.tenant_id`，真有此欄）不動；回歸跑 CR-0017 測試（17 pass）|
| push 失敗阻斷主業務 | Low | High | 全部 best-effort try/except，沿用既有 pattern；push 失敗只 log |
| 客戶端 LINE 顯示 raw UUID | Low | Low | builder 不顯示 raw UUID，只顯示 document_number（有則顯示）|

**Rollback plan**：push 為純新增 best-effort 路徑，移除 enqueue 呼叫即回原狀；resolver 修復為純 bug fix（原本就送不出，改後才會送）。

## 11. Out of Scope

- 公單欄位補洞 → CR-0026
- 報價成本明細 + 客戶端電子工單 PDF → CR-0027
- 客服回訊自動推 LINE（CR-0024 Phase 2 範疇）

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主）| Sunny | 2026-06-17 | ✅（會議授權修此鏈）|

## 13. 實作進度

- ✅ 全部 §9 步驟完成（builders / PushKind / resolver fix / 3 enqueue / 測試）
- ✅ `test_cr_0028_wo_push.py` 6 pass、CR-0017 回歸 17 pass、5 檔 py_compile pass
- ⏳ 整合驗證：本機起 stack 派工一張工單 → 確認 outbox 出現 row（LINE 真送需整合環境 + LINE_CHANNEL_ACCESS_TOKEN）
- 分支：`feat/cr-0028-line-wo-pushback`（從整合線 feat/self-service-password-reset 切，因 main 落後 1138 commit 無 outbox code）
