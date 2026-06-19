-- 052-workorder-fields-phase2.sql
--
-- WHY（CR-0043 / 2026-06-19 對抗式逐欄查證）：
--   CR-0026 補了公單欄位骨架，但對齊 20260617 派工單規格（PDF §三 6 模組 24 欄）後，
--   逐欄查證發現仍缺：購買地點/經銷商(M2.3)、安裝日期獨立欄(M2.4)、安裝環境遮雨三段(M2.5)、
--   特殊門型加價確認(M4.1)、付款方式(M5.5)。本 migration 補這 5 欄 + 計費費目 seed + 治理 config。
--
-- WHAT：
--   1. work_orders 補 5 欄（全 nullable、向後相容、idempotent）：dealer / install_date /
--      rain_exposure / special_door_surcharge / payment_method。
--   2. service_catalog 補 dispatch（出勤費）/ destruction（破壞費）/ removal（拆除費）SVC code seed，
--      讓 M5 結構化費目語意有 catalog 依據（數值 is_mock，待財務覆核）。
--   3. M18 config 治理（不寫死 money/rule，CR-0036 紅線）：
--      - completion_policy.require_consents（完工前是否強制三段免責，預設 false 避免回歸破壞）
--      - quote_policy.apply_surcharge（單筆 quote 是否計入出勤加成，預設 false；費率讀 surcharge_rule）
--
-- 影響：純 ADD COLUMN + seed + config，不改既有欄、不刪資料。列舉值由 app 層驗證（DB 不加 CHECK 保彈性）。

-- ============================================================
-- 1. work_orders 補 5 欄（CR-0043 Phase 2）
-- ============================================================
-- 購買地點/經銷商（M2.3：釐清原廠直營/電商/特定鎖行通路）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS dealer                VARCHAR(150);
-- 安裝日期（M2.4：回溯裝機日精準判保固剩餘；與 purchase_date 區分）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS install_date          DATE;
-- 安裝環境與遮雨（M2.5 三段：indoor/outdoor_covered/outdoor_exposed；is_interior_door 二分不足）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS rain_exposure         VARCHAR(20);
-- 特殊門型加價確認（M4.1：3cm白鐵門/敵銳門等特殊工時耗材加價簽認旗標）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS special_door_surcharge BOOLEAN;
-- 付款方式（M5.5 總計金額：cash/bank_transfer/credit_card/line_pay；工單層留存，invoices 另計）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS payment_method        VARCHAR(20);

COMMENT ON COLUMN work_orders.dealer                IS 'CR-0043 M2.3 購買地點/經銷商（原廠/電商/鎖行通路）';
COMMENT ON COLUMN work_orders.install_date          IS 'CR-0043 M2.4 安裝日期（回溯判保固；與 purchase_date 區分）';
COMMENT ON COLUMN work_orders.rain_exposure         IS 'CR-0043 M2.5 indoor/outdoor_covered/outdoor_exposed — app 驗證';
COMMENT ON COLUMN work_orders.special_door_surcharge IS 'CR-0043 M4.1 特殊門型加價確認旗標';
COMMENT ON COLUMN work_orders.payment_method        IS 'CR-0043 M5.5 cash/bank_transfer/credit_card/line_pay — app 驗證';

-- ============================================================
-- 2. service_catalog 補 M5 結構化費目（dispatch/destruction/removal）— seed，is_mock 待財務覆核
-- ============================================================
INSERT INTO service_catalog
  (service_code, category, service_name, service_type, material_class, unit,
   needs_dispatch, cross_zone, internal_note, internal_base_cost, suggested_customer_price, decision_status)
VALUES
  ('SVC-FEE-DISPATCH','計費費目','出勤費用','dispatch','一般','次','是','否','非保固維修收取；白天/夜間加成由 surcharge_rule 計',300,500,'待填價'),
  ('SVC-FEE-DESTRUCT','計費費目','主鎖/輔助鎖破壞費','destruction','一般','次','否','否','需破壞鎖解鎖時計價；非產品故障由客戶自負',0,800,'待填價'),
  ('SVC-FEE-REMOVAL','計費費目','舊鎖拆除費','removal','一般','次','否','否','舊鎖拆除工時',0,500,'待填價')
ON CONFLICT (service_code) DO NOTHING;

-- ============================================================
-- 3. M18 config 治理（不寫死；code 讀 read_global_value 帶 fallback）
-- ============================================================
-- 3a. completion_policy.require_consents — 在既有 default value 上 merge（idempotent；預設 false）
UPDATE saas.config_version
SET value = value || '{"require_consents": false}'::jsonb
WHERE tenant_id IS NULL AND namespace = 'completion_policy' AND key = 'default' AND state = 'active'
  AND NOT (value ? 'require_consents');

-- 3b. quote_policy.apply_surcharge — 新 namespace（預設 false；on 時費率讀 surcharge_rule）
INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('quote_policy',
   '報價政策（CR-0043；出勤加成是否計入單筆 quote total）',
   '{"type":"object","properties":{"apply_surcharge":{"type":"boolean"},"surcharge_source":{"type":"string"},"is_mock":{"type":"boolean"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'quote_policy', 'default',
  '{"apply_surcharge":false,"surcharge_source":"surcharge_rule","is_mock":true}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace = 'quote_policy' AND key = 'default');
