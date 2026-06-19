-- 048-media-evidence-governance.sql
-- CR-0040 Evidence 治理（BR-M09-03 保存期）：media_files 加保存期 + 軟刪欄位。
--
-- WHY：media_files 原只有 created_at，無保存期/清除機制（Q027：一般 1 年、保固/客訴 2 年）。
--   角色可見性（BR-M09-02）走 service 端規則式過濾（HD-1），不加欄位 → 本 migration 只處理保存期。
--
-- WHAT：retention_until（建立時依 purpose/案件類型算）+ deleted_at（軟刪 HD-4）+ backfill 既有 +
--   清除用 partial index。
--
-- 性質：純 ADD COLUMN + backfill，idempotent 可重套。

ALTER TABLE media_files ADD COLUMN IF NOT EXISTS retention_until TIMESTAMPTZ;
ALTER TABLE media_files ADD COLUMN IF NOT EXISTS deleted_at      TIMESTAMPTZ;

-- backfill 既有 media：客訴(dispute) 2 年、其餘 1 年（從 created_at 起算）
UPDATE media_files
SET retention_until = created_at + (
        CASE WHEN purpose LIKE 'dispute_evidence%' THEN INTERVAL '2 years'
             ELSE INTERVAL '1 year' END)
WHERE retention_until IS NULL;

-- 清除 cron 掃描用（只掃未軟刪）
CREATE INDEX IF NOT EXISTS idx_media_files_retention
    ON media_files (retention_until)
    WHERE deleted_at IS NULL;

COMMENT ON COLUMN media_files.retention_until IS
    'CR-0040 保存期到期日（一般 1 年、客訴/保固 2 年，Q027）；過期由清除 cron 軟刪';
COMMENT ON COLUMN media_files.deleted_at IS
    'CR-0040 軟刪時間（HD-4；過期或人工標記，畫面不顯示但可復原 + audit）';
