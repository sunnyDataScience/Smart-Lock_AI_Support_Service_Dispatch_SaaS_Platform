-- 060-media-completion-during.sql
--
-- WHY（CR-0054 / 派工單 PDF §四優化）：PDF 明列存證需「施工前全門外觀 / 施工中拓孔結構 /
--   施工後正反面完工照」三類，現 media_files purpose 只有 completion_before/after 兩類，缺施工中。
--
-- WHAT：media_files purpose CHECK 補 'completion_during'。idempotent（DROP+ADD）。

DO $$
DECLARE cname text;
BEGIN
  SELECT conname INTO cname FROM pg_constraint
   WHERE conrelid='media_files'::regclass AND contype='c'
     AND pg_get_constraintdef(oid) LIKE '%door_check_before%';
  IF cname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE media_files DROP CONSTRAINT %I', cname);
  END IF;
END $$;

ALTER TABLE media_files ADD CONSTRAINT media_files_purpose_check
  CHECK (purpose IN (
    'door_check_before', 'door_check_after',
    'completion_before', 'completion_during', 'completion_after',
    'dispute_evidence_customer', 'dispute_evidence_technician', 'other'
  ));
