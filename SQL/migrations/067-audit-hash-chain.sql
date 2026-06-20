-- 067-audit-hash-chain.sql
-- WHY（CR-0068 / TI-AUDIT-03 / 合規紅線）：audit_events 原為 append-only，但無
--   篡改偵測 —— 任何人改了 payload/action 也看不出來。合規要求 sha256 hash chain：
--   每列 entry_hash = sha256(prev_hash + 內容)，prev_hash 接前一列 entry_hash；
--   竄改任一列內容會使其 entry_hash 對不上，往後整條鏈斷裂可被 verify 偵測。
-- WHAT：audit_events +prev_hash TEXT +entry_hash TEXT（NULL 容許 —— migration 前的
--   歷史列不回填，verify 只驗有 entry_hash 的鏈段）。純 ADD COLUMN 可重套。
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS prev_hash TEXT;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS entry_hash TEXT;
COMMENT ON COLUMN audit_events.entry_hash IS
  'CR-0068/TI-AUDIT-03：sha256(prev_hash + 正規化內容)；篡改偵測用';
COMMENT ON COLUMN audit_events.prev_hash IS
  'CR-0068/TI-AUDIT-03：鏈接前一列 entry_hash（genesis = "GENESIS"）';
CREATE INDEX IF NOT EXISTS idx_audit_events_entry_hash
  ON audit_events (created_at, id) WHERE entry_hash IS NOT NULL;
