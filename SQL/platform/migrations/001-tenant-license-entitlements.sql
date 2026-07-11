-- 001-tenant-license-entitlements.sql（平台庫）
--
-- WHY（CR-0166 R3 / ADR-002 / ADR-018）：
--   License 訂閱＝開通閘門，控 ①per-brand bundle 部署權 ②附加模組集
--   （refinery/studio/compiler）。原 tenant.plan 單一 VARCHAR「MVP 未用」，無
--   entitlement enforcement／到期日／模組集資料結構。本 migration 補齊資料面。
--
-- WHAT：tenant 加 plan_tier（free/standard/pro/enterprise）＋entitled_modules
--   JSONB（開通模組字串陣列，預設 ["core"]）＋license_expires_at（NULL=無期限）。
--   idempotent（ADD COLUMN IF NOT EXISTS）。

ALTER TABLE tenant ADD COLUMN IF NOT EXISTS plan_tier VARCHAR(30) NOT NULL DEFAULT 'standard';
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS entitled_modules JSONB NOT NULL DEFAULT '["core"]'::jsonb;
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS license_expires_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN tenant.plan_tier IS 'CR-0166 R3：訂閱級距（free/standard/pro/enterprise）';
COMMENT ON COLUMN tenant.entitled_modules IS 'CR-0166 R3：已開通附加模組字串陣列（core 恆有；refinery/studio/compiler 等）';
COMMENT ON COLUMN tenant.license_expires_at IS 'CR-0166 R3：License 到期時間（NULL=無期限）；過期＝僅 core 可用';

-- 創始品牌 locksmart 開全模組（平台自營，enterprise 級）
UPDATE tenant
SET plan_tier = 'enterprise',
    entitled_modules = '["core","refinery","studio","compiler"]'::jsonb
WHERE slug = 'locksmart' AND entitled_modules = '["core"]'::jsonb;
