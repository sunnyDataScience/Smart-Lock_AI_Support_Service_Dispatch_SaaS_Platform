-- 047-completion-policy-config.sql
-- CR-0039 完工硬閘（BR-M08-03）：把完工驗證門檻入 M18 config 治理，不寫死 code（會議紅線）。
--
-- WHY：work_order_service.complete_order 原本只檢查狀態機，師傅可無照片/無簽名/無序號完工
--   （Beta 測試計畫 §46 驗收項 + 客訴/帳務爭議源頭）。業主 2026-06-19 裁決 §8 全採建議預設。
--
-- WHAT：namespace completion_policy + 全域 active config：
--   min_photos=3（test-plan §46）/ require_signature=true / serial_required_categories=["install"]
--   （只安裝案強制序號，BR-M10-03）/ allow_supervisor_override=true（admin/dispatcher :complete 為 override 路徑）。
--
-- 性質：config seed（idempotent：namespace ON CONFLICT DO NOTHING；config_version NOT EXISTS）。
--   仿 migration 044（CR-0036）。值為業主裁決定案 → is_mock:false。改門檻走 M18 改版流程，非改 migration。

INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('completion_policy',
   '完工硬閘門檻（CR-0039 BR-M08-03；業主 2026-06-19 裁決）',
   '{"type":"object","properties":{"min_photos":{"type":"integer"},"require_signature":{"type":"boolean"},"serial_required_categories":{"type":"array","items":{"type":"string"}},"allow_supervisor_override":{"type":"boolean"},"is_mock":{"type":"boolean"},"source":{"type":"string"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'completion_policy', 'default',
  '{"min_photos":3,"require_signature":true,"serial_required_categories":["install"],"allow_supervisor_override":true,"is_mock":false,"source":"CR-0039 test-plan-§46 + 業主裁決 2026-06-19"}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='completion_policy' AND key='default');
