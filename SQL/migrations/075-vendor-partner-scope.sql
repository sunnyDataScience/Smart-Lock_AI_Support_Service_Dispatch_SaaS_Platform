-- 075-vendor-partner-scope.sql
-- WHY（CR-0084 / TI-PORTAL-01）：Partner Portal 宣稱「品牌/經銷/建商只看自己」，但實際只有
--   tenant 級隔離 —— vendor 登入後可查整個 tenant 下所有品牌的 brand_b2b_statement（假綠：
--   list_statements 的 brand_partner_id 是 caller 自選 query param 而非由身分強制）。根因：
--   vendors 表無 brand_partner_id 連結，無法把登入身分綁到單一 partner scope。
-- WHAT：vendors +brand_partner_id（vendor↔品牌 partner 連結）+ partial index。
--   service 層 resolve_partner_scope 用此欄強制過濾（fail-closed）。純 ADD COLUMN 可重套。
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS brand_partner_id UUID;
CREATE INDEX IF NOT EXISTS idx_vendors_brand_partner ON vendors (brand_partner_id)
    WHERE brand_partner_id IS NOT NULL;
COMMENT ON COLUMN vendors.brand_partner_id IS
  'CR-0084/TI-PORTAL-01：vendor 綁定的品牌 partner（partner scope 隔離強制過濾來源）';
