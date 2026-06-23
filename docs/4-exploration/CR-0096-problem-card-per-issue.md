# CR-0096 — 同一 LINE 客人的不同問題各自獨立成卡

> **狀態**: ✅ 已實作（業主 2026-06-23 裁決方案 A，同日實作）
> **分支**: `fix/problem-card-per-issue`（疊於 `feat/quote-wo-picker`）
> **觸發面向**: Domain model（問題卡生命週期）+ DB schema（約束變更）+ User flow（進線建卡）

## 1. 背景 / 問題

業主實測：透過 LINE 闡述新問題、成功生成「新問題卡」，但**內容跟第一次開的問題卡寫在一起**
（問題卡 `49c8e184-…`）。

## 2. 根因（code-grounded）

三連鎖：

1. **LINE 同一用戶永遠同一 conversation** —— `line_gateway` 的 `session_id = {tenant}:{user_id}`；
   `conversation_service.create_conversation` 以 `WHERE session_id = … LIMIT 1` 復用既有，不開新的。
2. **一個 conversation 只能掛一張問題卡** —— `problem_cards.conversation_id` 全唯一
   （`Schema.sql:228`，設計註解明寫「每個 Conversation 至多一張 ProblemCard 1:1」）。
3. **第二次進線 → 找到既有卡 → append 新症狀（不建新卡）** ——
   `problem_card_service.escalation_to_draft_pc` 的 `existing` 分支把新症狀併進舊卡 `symptoms`，
   回 `created: False`（API 回 200 但其實沒建新卡）。且**不看舊卡狀態**，連已轉工單的卡也照 append。

結果：**一個客人一輩子只有一張問題卡**，所有後續需求全擠進同一張，無法分單 / 分別派工 / 分別報價。

## 3. 決策（§8 業主裁決）

| 決策點 | 選項 | 裁決（2026-06-23） |
|---|---|---|
| 何時開「新問題卡」 vs 併入舊卡 | A=已轉工單/已結案才開新卡；B=已確認後就開新卡；C=每次轉真人都開新卡 | **A** —— 舊卡仍在 draft / 已確認但未派工 → 新訊息視為同問題補充併入；舊卡「已轉工單 或 已結案」→ 新訊息＝新需求 → 開新卡 |

技術方案（實作層自選，最小破壞）：加 `converted_at` 標記已轉工單；`conversation_id` 全唯一改
**部分唯一索引**（同 conversation 同時只允許一張「仍 active」的卡），不動 `status` 語意。
`active = status NOT IN (resolved/escalated) AND converted_at IS NULL`。

## 4. 影響盤點（所有碰 `problem_cards.conversation_id` 的點）

| 位置 | 原假設 1:1 | 處置 |
|---|---|---|
| `problem_card_service.escalation_to_draft_pc` idempotency 查詢 | 同鍵回既有 | 加 active 條件（已轉工單/結案不當 dedup 目標）|
| `problem_card_service.escalation_to_draft_pc` existing 查詢 | 回唯一既有 | 加 active 條件 + `ORDER BY created_at DESC LIMIT 1`（只併 active 卡）|
| `problem_card_service.create_card` 409 檢查 | 任何既有卡→409 | 改成只有 active 卡才 409 |
| `work_order_service.create_from_problem_card` | （無）| 轉工單成功後 set `converted_at = NOW()` |
| `sop_draft_service`（conversation→PC）| `LIMIT 1` 無排序 | 加 `ORDER BY created_at DESC`（1:N 後行為確定）|
| `conversation_service`（escalation reason）| 已有 `ORDER BY updated_at DESC LIMIT 1` | 無需改（本就 1:N 安全）|
| `problem_card_service.list_cards` by conversation_id | 列表 | 無需改（列表本可多筆）|

## 5. 實作

- **migration 077** `077-problem-card-per-issue.sql`：`+converted_at` + DROP 全唯一 +
  `CREATE UNIQUE INDEX uniq_pc_conversation_active … WHERE status NOT IN (resolved,escalated) AND converted_at IS NULL`
- service 改動 5 處（見 §4）

## 6. 測試

`test_cr_0096_problem_card_per_issue` 3/3：
- 舊卡 active → 第二問題 append 同卡
- 舊卡已轉工單（converted_at）→ 新問題開新卡（同 conversation）
- 舊卡已結案（resolved）→ 新問題開新卡

回歸：轉工單 / 工單 v2 / escalation / convert / create_card / sop_draft / ingest 共 64 passed 0 fail。

## 7. Follow-up（已知限制）

- **對話串顯示仍混在一起**：一個 conversation 多張卡共用同一對話訊息串，問題卡詳情頁的
  `LinkedConversationCard` 仍顯示整段對話。卡 / 工單已分開（核心痛點已解），但對話串要完全分需
  「每個新問題開新 conversation」——更大改動（影響 ingest / handover / 對話管理），列後續。
- prod 套用 migration 077 待部署流程。
