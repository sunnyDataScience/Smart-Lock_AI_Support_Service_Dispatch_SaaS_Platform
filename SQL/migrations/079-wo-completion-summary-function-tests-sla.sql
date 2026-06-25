-- 079-wo-completion-summary-function-tests-sla.sql
--
-- WHY（CR-0100 工單詳情頁 B 類後端欄位）：盤點報告（wo-detail-hardcoded-audit-20260625）
--   發現 admin 工單詳情頁「完工報告功能測試」「SLA 倒數」為寫死假資料，且後端無對應欄位。
--   業主 2026-06-25 裁決：完工摘要 + 功能測試逐項結果（預設 6 項）+ SLA 三級政策全做。
--
-- WHAT：
--   1. work_orders + completion_summary（B0：技師完工 notes 抽出乾淨欄，service_report 稽核串不動）
--   2. work_orders + function_tests jsonb（B1：[{key,result}]，result∈pass/fail/na；預設 []）
--   3. config namespace sla_policy（B2：三級時數 high=8h/medium=24h/low=48h；emergency 4h 留未來）
--      —— sla_deadline 不落欄，service 以 created_at + 政策 computed（免 backfill、政策可調即生效）
--
-- 性質：全 additive（nullable / 預設值 / config seed），idempotent（IF NOT EXISTS / ON CONFLICT）。
--   功能測試非完工硬閘（選填，與 CR-0039 三閘脫鉤）。SLA 計時起點＝created_at（業主預設）。

-- 1. work_orders 完工摘要 + 功能測試（B0 / B1）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS completion_summary text;
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS function_tests jsonb NOT NULL DEFAULT '[]'::jsonb;

-- 2. SLA 政策 config（B2，M18 治理，不寫死；比照 047 completion_policy）
INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('sla_policy',
   '工單 SLA 時效政策（CR-0100；業主 2026-06-25 裁決三級）',
   '{"type":"object","properties":{"hours_by_urgency":{"type":"object"},"clock_start":{"type":"string"},"is_mock":{"type":"boolean"},"source":{"type":"string"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'sla_policy', 'default',
  '{"hours_by_urgency":{"high":8,"medium":24,"low":48},"clock_start":"created_at","is_mock":false,"source":"CR-0100 業主裁決 2026-06-25（三級對齊；emergency 4h 留未來）"}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='sla_policy' AND key='default');
