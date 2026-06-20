-- 072-settlement-config-versioning.sql
-- WHY（CR-0073 / TI-FIN-SETTLE-04）：結算金額所套用的費率 config 版本原無釘選 —— 事後改費率
--   無法回溯「此筆 settlement 當初套哪版」。合規/稽核（P2-UAT-005 鎖定後可稽核）要求每筆
--   settlement 記錄建立當下的 config rule_version + effective_date，且版本釘選後不隨後續變更漂移。
-- WHAT：saas.settlement +applied_config_version_id（FK→saas.config_version）+rate_effective_date。
--   純 ADD COLUMN nullable（舊列 NULL，best-effort 不阻斷結算）。M18 versioning infra（CR-0059
--   effective_at + get_active_version）已就緒，本批只做釘選 wiring，不遷移 80/20 計算來源。
ALTER TABLE saas.settlement ADD COLUMN IF NOT EXISTS applied_config_version_id UUID
    REFERENCES saas.config_version(id);
ALTER TABLE saas.settlement ADD COLUMN IF NOT EXISTS rate_effective_date TIMESTAMPTZ;
COMMENT ON COLUMN saas.settlement.applied_config_version_id IS
  'CR-0073/TI-FIN-SETTLE-04：建立當下套用的結算費率 config active 版本（釘選，可回溯）';
