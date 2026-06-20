-- 074-family-review-ledger.sql
-- WHY（CR-0079 / TI-A10-02 / 合約 4.4(d)）：高風險 SOP 雙審（Knowledge Owner + domain
--   expert）+ 家族覆核不可篡改 ledger 是合約紅線（違反=合約終止，RC 前必補）。family_reviews
--   原無 (1) 雙審 distinct 強制（家族覆核者須異於初審 admin）(2) 不可篡改保證（無 hash chain，
--   改了 action/comment 看不出來）。
-- WHAT：family_reviews +prev_hash +entry_hash（hash chain 篡改偵測，複用 audit_events 067 機制）。
--   雙審 distinct 在 service 層強制（admin reviewed_by ≠ family reviewer_id）。
ALTER TABLE family_reviews ADD COLUMN IF NOT EXISTS prev_hash TEXT;
ALTER TABLE family_reviews ADD COLUMN IF NOT EXISTS entry_hash TEXT;
COMMENT ON COLUMN family_reviews.entry_hash IS
  'CR-0079/TI-A10-02：sha256(prev_hash + 正規化內容)；家族覆核 ledger 不可篡改偵測（合約 4.4d）';
CREATE INDEX IF NOT EXISTS idx_family_reviews_entry_hash
  ON family_reviews (created_at, id) WHERE entry_hash IS NOT NULL;
