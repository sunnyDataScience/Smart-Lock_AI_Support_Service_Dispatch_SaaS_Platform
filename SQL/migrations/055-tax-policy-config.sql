-- 055-tax-policy-config.sql
--
-- WHY（CR-0045 / esales Q-07）：發票稅原本 hardcode mock 0（invoice_service「待 esales Q-07」）。
--   翻 20260617 資料：ERP spec Q099 已定發票責任（B2C 平台開 / B2B 派工人），但稅率/含稅未明寫；
--   業主 2026-06-19 裁決：預設台灣 VAT 5% 含稅（可動態改）。稅屬 money rule → 入 M18 config 不寫死。
--
-- WHAT：tax_policy namespace + 全域 active default（rate=0.05 / mode=inclusive 含稅）。
-- 性質：config seed，idempotent（ON CONFLICT / NOT EXISTS 可重套）。code 讀 read_global_value 帶
--   fallback（0.05 / inclusive），故未套仍以預設運作。

INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('tax_policy',
   '發票稅務政策（CR-0045 / esales Q-07；台灣 VAT 5% 含稅預設，業主可動態改）',
   '{"type":"object","properties":{"rate":{"type":"number"},"mode":{"type":"string","enum":["inclusive","exclusive"]},"source":{"type":"string"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'tax_policy', 'default',
  '{"rate":0.05,"mode":"inclusive","source":"台灣 VAT 5% 含稅；esales Q-07 業主 2026-06-19 預設，可動態改"}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='tax_policy' AND key='default');
