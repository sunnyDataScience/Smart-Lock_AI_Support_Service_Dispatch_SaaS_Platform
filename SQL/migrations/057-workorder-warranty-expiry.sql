-- 057-workorder-warranty-expiry.sql
--
-- WHY（CR-0047 / 派工單 PDF §四 優化建議「保固期動態計算」）：work_orders 有 serial_number/
--   purchase_date/install_date/brand，但 warranty_status 為「本輪人工填」（migration 036:31），
--   且無到期日落地欄。warranty_service 已有 5-mode 起算 + brand override + compute_warranty_end
--   引擎，但未接 work_order。本 migration 補到期日欄，service 接引擎自動算保內/保外。
--
-- WHAT：work_orders 補 warranty_expiry_date DATE（nullable，向後相容）。
-- 性質：純 ADD COLUMN，idempotent 可重套。

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS warranty_expiry_date DATE;

COMMENT ON COLUMN work_orders.warranty_expiry_date IS
  'CR-0047 保固到期日（warranty_service 由 purchase/install date + brand 期間自動算）；warranty_status 隨之自動回填';
