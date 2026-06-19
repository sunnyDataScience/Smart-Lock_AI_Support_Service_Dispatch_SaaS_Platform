-- 044-finance-config.sql
--
-- WHY（CR-0036 / 業主指正）：
--   esales PhaseII FinanceSettlement sheet 24「Finance Config」已有訂金/佣金/月結時程草稿值，
--   CR-0035 卻 punt 成「待裁決 Phase II」。sheet 24 標題明寫「所有規則版本化，不可寫死」，
--   專案已有 M18 config governance（migration 004）但「No pricing namespace — Phase II」留空。
--   本 migration 依決議 5 把 sheet 24 值當 mock seed 進 config 治理（非寫死 code）。
--
-- WHAT：
--   1) config_namespace 加 deposit_policy / dispatch_commission / monthly_close_schedule
--   2) config_version seed 三筆 global(tenant_id NULL) active config（value 含 is_mock/esales_status/source）
--   3) invoices 加 deposit_required（CR-0036 從 deposit_policy config 算）
--
-- 性質：DB schema + config seed（idempotent：namespace ON CONFLICT DO NOTHING；
--   config_version 用 NOT EXISTS 防重；ADD COLUMN IF NOT EXISTS）。mock-first：值為 esales
--   sheet 24 草稿，正式值待業主確認（§8；走 M18 改版流程，非改 migration）。
--   退款 tier（CFG-REFUND-L1~L3）已在 refund_service ADR-0040 + namespace refund_tier_thresholds，不重做。

-- 1) namespaces
-- json_schema 含 esales_status / source 中繼欄（seed value 帶之；additionalProperties 預設允許，
-- 仍明列以利日後經 config_m18_service 改版時 schema 驗證通過）
INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('deposit_policy',
   '訂金政策（esales sheet24 CFG-DEPOSIT-*；CR-0036 mock）',
   '{"type":"object","properties":{"rate":{"type":"number"},"min_twd":{"type":"number"},"material_prepay_rate":{"type":"number"},"is_mock":{"type":"boolean"},"esales_status":{"type":"string"},"source":{"type":"string"}}}'::jsonb),
  ('dispatch_commission',
   '派工佣金率（esales sheet24 CFG-DISPATCH-COMM；CR-0036 mock）',
   '{"type":"object","properties":{"rate":{"type":"number"},"min_rate":{"type":"number"},"max_rate":{"type":"number"},"is_mock":{"type":"boolean"},"esales_status":{"type":"string"},"source":{"type":"string"}}}'::jsonb),
  ('monthly_close_schedule',
   '月結時程工作日（esales sheet24 CFG-CLOSE-*；esales 標 Accepted default → is_mock:false）',
   '{"type":"object","properties":{"prelim_workday":{"type":"integer"},"review_workday":{"type":"integer"},"pay_workday":{"type":"integer"},"is_mock":{"type":"boolean"},"esales_status":{"type":"string"},"source":{"type":"string"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

-- 2) seed global active config（created_by = 系統 seed uuid；NOT NULL 無 FK）
--    value 內含 is_mock + esales_status + source，自我標示 mock 待覆核
INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'deposit_policy', 'default',
  '{"rate":0.3,"min_twd":1000,"material_prepay_rate":1.0,"is_mock":true,"esales_status":"draft","source":"esales-PhaseII-FinanceConfig-sheet24"}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='deposit_policy' AND key='default');

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'dispatch_commission', 'default',
  '{"rate":0.08,"min_rate":0.05,"max_rate":0.10,"is_mock":true,"esales_status":"draft","source":"esales-PhaseII-FinanceConfig-sheet24"}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='dispatch_commission' AND key='default');

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'monthly_close_schedule', 'default',
  '{"prelim_workday":3,"review_workday":5,"pay_workday":10,"is_mock":false,"esales_status":"accepted","source":"esales-PhaseII-FinanceConfig-sheet24"}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='monthly_close_schedule' AND key='default');

-- 3) invoices 加 deposit_required（CR-0036 從 deposit_policy config 算）
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS deposit_required NUMERIC(12,2);
COMMENT ON COLUMN invoices.deposit_required IS '應收訂金（CR-0036；公式 round(min(total, max(total×rate, min_twd)),2) = rate/min 取高但不超過 total）；mock 規則待 esales Q-08（訂金門檻）';
