-- 066-media-legal-hold.sql
-- WHY（CR-0067 / TI-M09-03 / ADR-0051）：Evidence retention 清理 cron 原僅看 retention_until
--   過期就軟刪，無法處理「法務保留（legal hold）」——訴訟/爭議調查中的證據即使保存期過期
--   也不可刪。legal_hold 與 retention 衝突時 legal_hold wins。
-- WHAT：media_files +legal_hold BOOLEAN NOT NULL DEFAULT false。soft_delete_expired_media
--   WHERE 補 AND legal_hold IS NOT TRUE。純 ADD COLUMN 可重套。
ALTER TABLE media_files ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT false;
COMMENT ON COLUMN media_files.legal_hold IS
  'CR-0067/TI-M09-03：法務保留旗標；true 時即使 retention_until 過期也不軟刪（legal_hold wins）';
