-- migrate-targets: brand
-- ============================================================================
-- 117-problem-card-dismissed.sql — 問題卡作廢終態（CR-0185）
-- ============================================================================
--
-- WHY：ProblemCardStatus 只有 draft/confirmed/resolved，LINE agent 誤判自動建的
--      草擬卡沒有乾淨的關閉途徑 —— 標「已解決」會污染解決率**且會被 refinery
--      汲取成知識**（intake.py 只吃 status='resolved' AND knowledge_ready=TRUE），
--      留 draft 則永遠佔住待確認佇列。
--
-- 本檔做兩件事：
--   1. 新增 dismissed_at / dismiss_reason 欄（沿用 invoice `voided` 的欄位慣例）
--   2. **重建 partial unique index** —— 這是最容易漏的一步：
--      原 predicate 為 `status NOT IN ('resolved','escalated')`，dismissed 不在其中，
--      作廢卡會**永遠佔住該對話的唯一 active 名額**，導致同一對話再也開不了新卡。
--
-- status 欄本身是 VARCHAR(50) 無 CHECK 約束（見 SQL/Schema.sql），故新增值不需 DDL。
-- 全 idempotent，可重複執行。
-- ============================================================================

-- ── 1. 作廢軌跡欄位 ──────────────────────────────────────────────────────
ALTER TABLE problem_cards ADD COLUMN IF NOT EXISTS dismissed_at TIMESTAMPTZ;
ALTER TABLE problem_cards ADD COLUMN IF NOT EXISTS dismiss_reason TEXT;

COMMENT ON COLUMN problem_cards.dismissed_at IS
'CR-0185：作廢時間；status=''dismissed'' 時必填。沿用 invoices.voided_at 慣例';
COMMENT ON COLUMN problem_cards.dismiss_reason IS
'CR-0185：作廢理由（客服填，供稽核）。沿用 invoices.void_reason 慣例';

-- ── 2. 重建 active 部分唯一索引，把 dismissed 排除在 active 之外 ──────────
--   active = 未結案（resolved/escalated）、**未作廢（dismissed）**、且未轉工單。
--   不重建的話：作廢卡仍算 active → uniq 約束擋掉同對話的新卡（本修復自我廢除）。
DROP INDEX IF EXISTS uniq_pc_conversation_active;
CREATE UNIQUE INDEX IF NOT EXISTS uniq_pc_conversation_active
    ON problem_cards (conversation_id)
    WHERE status NOT IN ('resolved', 'escalated', 'dismissed') AND converted_at IS NULL;
COMMENT ON INDEX uniq_pc_conversation_active IS
'CR-0096＋CR-0185：同一 conversation 同時只一張 active 問題卡；已轉工單/結案/作廢不受限';

-- ── 3. 欄位註解同步（status 值域說明）────────────────────────────────────
COMMENT ON COLUMN problem_cards.status IS
'incomplete（草擬）/ confirmed（客服確認）/ resolved（結案）/ escalated（已升級）/ dismissed（作廢，CR-0185）';
