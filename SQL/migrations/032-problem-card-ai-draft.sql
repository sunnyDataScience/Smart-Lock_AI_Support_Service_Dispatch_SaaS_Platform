-- 032-problem-card-ai-draft.sql
-- CR-0022 / ADR-0112：AI 草擬問題卡（HITL）。LINE agent 轉真人（escalation）→ 在 API 建
-- 一張「AI 草擬」問題卡（DB status='incomplete' = API 'draft'），客服在既有問題卡頁補全 →
-- 既有 confirm → 既有 convert-to-work-order。AI 永不自轉（ADR-0028/0031）。
--
-- 設計（見 ADR-0112）：
--   - 不新增 DB status（incomplete 已映射 API draft，零狀態機變更）。
--   - 新增 source 區分 AI 草擬 vs 客服手建（後台佇列以此篩選）。
--   - 新增 ai_missing_fields 記「待客服補」欄位清單當 hint（不做信心分數，CR-0022 §8 #5 延後）。
--   - 兩欄皆 nullable / 有預設 → 反相容；既有 row 視為 'human'。
--   - problem_cards 無 created_by 欄位，source='ai_line' 即 AI 來源標記（CR-0022 §8 #7）。

-- ── 1. source：問題卡來源 ─────────────────────────────────────────────────
ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'human';
    -- 'human'   : 客服 / 系統手建（既有行為，預設）
    -- 'ai_line' : LINE agent 轉真人後 AI 草擬

COMMENT ON COLUMN problem_cards.source IS
    'CR-0022/ADR-0112 問題卡來源：human（手建，預設）/ ai_line（LINE agent AI 草擬）';

-- ── 2. ai_missing_fields：AI 草擬時尚缺、待客服補的欄位清單（hint）───────────
ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS ai_missing_fields JSONB NULL;

COMMENT ON COLUMN problem_cards.ai_missing_fields IS
    'CR-0022/ADR-0112 AI 草擬卡尚缺欄位清單（如 ["brand","model","location"]），供客服佇列 hint';

-- ── 3. 佇列查詢索引：後台依 source + status 篩 AI 草擬待處理卡 ─────────────────
CREATE INDEX IF NOT EXISTS idx_problem_cards_source_status
    ON problem_cards (source, status, created_at DESC)
    WHERE source = 'ai_line';
