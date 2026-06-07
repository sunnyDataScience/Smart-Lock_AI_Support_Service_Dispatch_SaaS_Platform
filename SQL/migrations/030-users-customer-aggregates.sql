-- ============================================================================
-- 030-users-customer-aggregates.sql — users 表加客戶聚合欄位
-- ============================================================================
-- 目的: 支援 /admin/customers 4 filter (風險等級/設備品牌/保固狀態/偏好技師).
-- 各欄位實際資料由背景 worker / batch job 計算 (roadmap), 或 admin manual
-- 標記; 本 migration 只建欄位 + 索引讓 filter 可運作.
-- ============================================================================

BEGIN;

-- 風險等級 (NPS-based or admin manual)
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS risk_level text
    CHECK (risk_level IS NULL OR risk_level IN ('low', 'medium', 'high', 'critical'));

-- 主要設備品牌 (從歷史工單 aggregate, 或 device 主檔填入)
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS primary_device_brand text;

-- 保固狀態 (簡化: active/expired/none, 詳情走 warranty_claims 表)
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS warranty_status text
    CHECK (warranty_status IS NULL OR warranty_status IN ('active', 'expired', 'none'));

-- 偏好技師 (從歷史派工頻次 aggregate)
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS preferred_technician_id uuid;

-- partial indexes (only on customers / has values)
CREATE INDEX IF NOT EXISTS idx_users_risk_level
  ON users(risk_level)
  WHERE risk_level IS NOT NULL AND role = 'line_user';

CREATE INDEX IF NOT EXISTS idx_users_primary_device_brand
  ON users(primary_device_brand)
  WHERE primary_device_brand IS NOT NULL AND role = 'line_user';

CREATE INDEX IF NOT EXISTS idx_users_warranty_status
  ON users(warranty_status)
  WHERE warranty_status IS NOT NULL AND role = 'line_user';

CREATE INDEX IF NOT EXISTS idx_users_preferred_tech
  ON users(preferred_technician_id)
  WHERE preferred_technician_id IS NOT NULL AND role = 'line_user';

COMMIT;
