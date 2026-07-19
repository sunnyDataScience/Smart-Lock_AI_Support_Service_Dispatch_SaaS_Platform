-- 110-idempotency-reserve-first.sql
--
-- WHY（UAT R3-6 / 已釘契約「Idempotency 先佔」）：
--   idempotency_keys 原為 check-then-act（先 SELECT 再 handler 跑完後 INSERT），
--   同 key 併發 2 發都撈不到快取 → 雙雙執行 handler → 同一張問題卡兩張工單＋
--   發票錯亂（雙擊送單即可命中）。改 reserve-first：handler 執行前先 INSERT
--   佔位（status='in_progress'），ON CONFLICT 撞既有列時依 status 回放或 409。
--
-- WHAT：
--   1. idempotency_keys 加 status 欄（'in_progress' / 'completed'；存量列全為
--      已完成回應 → DEFAULT 'completed' 回填）；response_status / response_body
--      改 nullable（佔位列尚無回應）。
--   2. work_orders 對 problem_card_id 加 partial UNIQUE 兜底（DB 層擋
--      「一卡雙原始工單」的最後防線）。範圍限定「原始 convert 單」：
--      parent_work_order_id IS NULL AND rework_of_id IS NULL——
--      reopen（CR-0043 返修子單複製 problem_card_id）與 rework 屬合法同卡多單，
--      必須排除，否則返修功能整條壞死。
--
-- ⚠️ 套用前置檢查（有重複列＝先人工裁決，不硬上）：
--   SELECT problem_card_id, COUNT(*) FROM work_orders
--   WHERE problem_card_id IS NOT NULL
--     AND parent_work_order_id IS NULL AND rework_of_id IS NULL
--   GROUP BY 1 HAVING COUNT(*) > 1;
--   （scratch 5490 已驗證 0 列；本機/prod 套用前務必重跑）
--
-- 性質：forward-only、idempotent（ADD COLUMN / CREATE INDEX IF NOT EXISTS、
--   DROP NOT NULL 可重套）。

-- [1] idempotency_keys — reserve-first 欄位
ALTER TABLE idempotency_keys
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'completed';

ALTER TABLE idempotency_keys DROP CONSTRAINT IF EXISTS idempotency_keys_status_check;
ALTER TABLE idempotency_keys
    ADD CONSTRAINT idempotency_keys_status_check
    CHECK (status IN ('in_progress', 'completed'));

ALTER TABLE idempotency_keys ALTER COLUMN response_status DROP NOT NULL;
ALTER TABLE idempotency_keys ALTER COLUMN response_body DROP NOT NULL;

COMMENT ON COLUMN idempotency_keys.status IS
    'reserve-first 先佔狀態（UAT R3-6）：in_progress=handler 執行中（同 key 併發 409 IDEMPOTENCY_IN_PROGRESS）；completed=已存回應可回放';

-- [2] work_orders — 一卡一原始工單 partial UNIQUE（併發 convert DB 兜底）
CREATE UNIQUE INDEX IF NOT EXISTS uq_work_orders_problem_card
    ON work_orders (problem_card_id)
    WHERE problem_card_id IS NOT NULL
      AND parent_work_order_id IS NULL
      AND rework_of_id IS NULL;

COMMENT ON INDEX uq_work_orders_problem_card IS
    '一張問題卡至多一張「原始」工單（UAT R3-6 併發 convert 兜底）；reopen 子單/rework 排除在外';
