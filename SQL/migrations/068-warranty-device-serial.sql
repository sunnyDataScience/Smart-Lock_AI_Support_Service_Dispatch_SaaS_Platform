-- 068-warranty-device-serial.sql
-- WHY（CR-0069 / TI-M02-05 / ADR-0053）：device serial 為 warranty/RMA 的唯一識別，但
--   warranty_claims 原僅以 customer + device_brand/model 識別，無法區分同型號不同實體鎖，
--   也無法做 serial 級 RMA 濫用偵測（同一顆鎖反覆送修）。
-- WHAT：warranty_claims +device_serial TEXT（optional —— 既有雙觸發流程不一定有 serial；
--   有則用於 serial 級 RMA 識別/abuse 偵測）。純 ADD COLUMN 可重套。
ALTER TABLE warranty_claims ADD COLUMN IF NOT EXISTS device_serial TEXT;
COMMENT ON COLUMN warranty_claims.device_serial IS
  'CR-0069/TI-M02-05/ADR-0053：裝置序號（warranty/RMA 唯一識別）；有則用於 serial 級 abuse 偵測';
CREATE INDEX IF NOT EXISTS idx_warranty_claims_device_serial
  ON warranty_claims (device_serial) WHERE device_serial IS NOT NULL;
