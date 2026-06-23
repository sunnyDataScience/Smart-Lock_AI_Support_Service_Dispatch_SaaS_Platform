-- 078-media-completion-signature.sql
--
-- WHY（技師完工簽名上傳 422）：前端 my-orders/[id] 完工簽名上傳送
--   purpose='completion_signature'，但 purpose 白名單共 4 層（router v2 _PURPOSE /
--   router v1 _PURPOSE / media_service._ALLOWED_PURPOSES / 本 DB CHECK）皆未含此值，
--   使用者實測 422（前兩層回 FastAPI 驗證 422 → 前端顯示 UNKNOWN）。
--   router + service 三處已於同 CR 補上；本 migration 補最後一層 DB CHECK。
--
-- WHAT：media_files purpose CHECK 補 'completion_signature'。idempotent（DROP+ADD），
--   並與 router/service 對齊（含 migration 060 的 completion_during）。

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
    'completion_before', 'completion_during', 'completion_after', 'completion_signature',
    'dispute_evidence_customer', 'dispute_evidence_technician', 'other'
  ));
