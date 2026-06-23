-- 077-problem-card-per-issue.sql
-- CR-0096：修「同一 LINE 客人的不同問題擠進同一張問題卡」（業主 2026-06-23 實測回報）。
--
-- 根因：problem_cards.conversation_id 全唯一（Schema.sql:228）＋ LINE 同一用戶永遠同一
--       conversation（session_id = {tenant}:{user_id} 永久復用）→ 一個客人一輩子只有一張卡，
--       第二個問題只能 append 進舊卡（problem_card_service.draft_card_from_escalation:611-631）。
--
-- 決策（業主裁決方案 A）：舊卡「已轉工單 或 已結案」才開新卡；draft / 已確認但未派工 →
--       新訊息視為同問題補充併入。詳見 docs/4-exploration/CR-0096-problem-card-per-issue.md。
--
-- 做法：加 converted_at 標記「已轉工單」；conversation_id 全唯一改「部分唯一索引」——
--       同一 conversation 同時只允許一張「仍 active」的卡，已結案/已轉工單的歷史卡不受約束。

-- ── 1. 已轉工單標記（nullable；既有列 NULL 不回溯；轉工單時 work_order_service 設）──
ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS converted_at TIMESTAMPTZ;
COMMENT ON COLUMN problem_cards.converted_at IS
'轉工單時間戳（CR-0096）；非 NULL 表此卡已轉工單 → 不再 active，同 conversation 可開新卡';

-- ── 2. 拆掉全唯一約束（PostgreSQL 對 `col UNIQUE` 自動建的 constraint）──
ALTER TABLE problem_cards
    DROP CONSTRAINT IF EXISTS problem_cards_conversation_id_key;

-- ── 3. 改部分唯一：同一 conversation 同時只允許一張「仍 active」的卡 ──
--   active = 未結案（status NOT IN resolved/escalated）且 未轉工單（converted_at IS NULL）
--   已結案 / 已轉工單的歷史卡不在約束內 → 可累積多張 + 一張新 active
CREATE UNIQUE INDEX IF NOT EXISTS uniq_pc_conversation_active
    ON problem_cards (conversation_id)
    WHERE status NOT IN ('resolved', 'escalated') AND converted_at IS NULL;
COMMENT ON INDEX uniq_pc_conversation_active IS
'CR-0096：同一 conversation 同時只一張 active 問題卡（取代原全唯一）。已轉工單/結案不受限';
