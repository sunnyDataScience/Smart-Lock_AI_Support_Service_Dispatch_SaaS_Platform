-- 062-config-effective-date.sql
-- WHY（CR-0059 / BR-M18-02）：M18 config 變更原僅 activated_at 即時生效，無未來排程生效。
--   業主要「X 日 0 時起套用新費率」需排程。draft + 未來 effective_at = 排程；cron 到期自動 activate。
-- WHAT：saas.config_version +effective_at TIMESTAMPTZ。純 ADD COLUMN 可重套。
ALTER TABLE saas.config_version ADD COLUMN IF NOT EXISTS effective_at TIMESTAMP WITH TIME ZONE;
COMMENT ON COLUMN saas.config_version.effective_at IS 'CR-0059 排程生效日：draft + effective_at<=now → cron 自動 active（退役同 ns/key 舊 active）';
