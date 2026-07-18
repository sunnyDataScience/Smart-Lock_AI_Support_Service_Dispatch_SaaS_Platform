-- 107-reconciliation-reject.sql
--
-- WHY（UAT-0718 W1-2 / 第二輪代理 UAT P2-2）：
--   對帳（public.reconciliations）只有「核准」單一動作，無駁回/退回 transition，
--   「爭議中」篩選無任何產生入口＝死篩選。已釘契約：
--   POST /accounting/reconciliations/{id}:reject body {"reason":">=3字"}
--   → status='rejected' + 審計欄位；僅 pending 可駁；409 語意同 approve。
--
-- WHAT：reconciliations 加 3 個駁回審計欄（nullable）。status 欄為 VARCHAR(50)
--   無 CHECK constraint（Schema.sql 僅註解列舉），'rejected' 不需放行 constraint。
--   ADD COLUMN IF NOT EXISTS 可重套（idempotent）。

ALTER TABLE reconciliations
    ADD COLUMN IF NOT EXISTS rejected_by UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE reconciliations
    ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE reconciliations
    ADD COLUMN IF NOT EXISTS reject_reason TEXT;

COMMENT ON COLUMN reconciliations.rejected_by IS '駁回操作者（users.id）；UAT-0718 W1-2';
COMMENT ON COLUMN reconciliations.rejected_at IS '駁回時間；UAT-0718 W1-2';
COMMENT ON COLUMN reconciliations.reject_reason IS '駁回原因（≥3 字必填）；UAT-0718 W1-2';
