-- 065-pc-idempotency-key.sql
-- WHY（CR-0065 / TI-M03-06 / A06 / Sync-M03）：ProblemCard 建卡原僅以 conversation_id
--   UNIQUE 去重，無法抵抗 DLQ/outbox retry 造成的重複建卡（同對話多次 escalation 已擋，
--   但跨 retry 的同一邏輯 turn 缺穩定 idempotency key）。spec 要 sha256(conv_id +
--   first_unresolved_symptom + brand) 作冪等鍵 + 24h dedup 視窗。
-- WHAT：problem_cards +idempotency_key TEXT（app 層計算 sha256；非 DB UNIQUE，dedup 視窗
--   邏輯在 service 控以保留 24h 語意）。純 ADD COLUMN，可重套。
ALTER TABLE problem_cards ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
COMMENT ON COLUMN problem_cards.idempotency_key IS
  'CR-0065/TI-M03-06：sha256(conv_id+first_unresolved_symptom+brand) 冪等鍵；24h dedup 視窗由 service 控';
CREATE INDEX IF NOT EXISTS idx_problem_cards_idempotency_key
  ON problem_cards (idempotency_key) WHERE idempotency_key IS NOT NULL;
