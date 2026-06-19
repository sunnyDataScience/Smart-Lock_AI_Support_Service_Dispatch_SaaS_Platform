-- 061-completion-materials-payment.sql
-- WHY（CR-0058 / 審計 #8 / BR-M08-03 完工套件）：完工套件 spec 列 photos+materials used+
--   payment status+sign-off+teaching 五件，CR-0039/0050 做了照片/簽名/序號/教學，補用料+付款證明。
--   付款核銷子系統屬 P2；本 migration 只補完工套件「欄位」+ 選用閘（config 預設 off，避免擋無料檢測單）。
-- WHAT：work_orders 補 materials_used / payment_proof TEXT（nullable）；completion_policy config
--   merge require_materials / require_payment_proof（預設 false）。純 ADD COLUMN + config merge，可重套。

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS materials_used TEXT;
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS payment_proof  TEXT;
COMMENT ON COLUMN work_orders.materials_used IS 'CR-0058 完工套件：現場用料紀錄（自由文字/JSON）';
COMMENT ON COLUMN work_orders.payment_proof  IS 'CR-0058 完工套件：付款證明（現金末五碼/轉帳截圖ref/收款人）；正式核銷 P2';

UPDATE saas.config_version
SET value = value || '{"require_materials": false, "require_payment_proof": false}'::jsonb
WHERE tenant_id IS NULL AND namespace='completion_policy' AND key='default' AND state='active'
  AND NOT (value ? 'require_materials');
