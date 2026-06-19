-- 051-problemcard-completeness-config.sql
-- CR-0042 Alpha Exit 收尾 #1：ProblemCard 完整度門檻入 M18 config（BR-M03，不寫死）。
--
-- WHY：spec 要 PC 完整度達標才可轉 WO（test-plan §46）；現況 confidence_score 永遠 None、
--   convert-to-WO 無完整度 gate。業主 2026-06-19 裁決 min_completeness=0.8 + 硬擋 + 主管 override。
--
-- WHAT：namespace problemcard_policy + 全域 active config（min_completeness / key_fields）。
-- 性質：config seed（idempotent），仿 CR-0036/0039。

INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('problemcard_policy',
   'ProblemCard 完整度門檻（CR-0042 BR-M03；業主裁決）',
   '{"type":"object","properties":{"min_completeness":{"type":"number"},"key_fields":{"type":"array","items":{"type":"string"}},"is_mock":{"type":"boolean"},"source":{"type":"string"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'problemcard_policy', 'default',
  '{"min_completeness":0.8,"key_fields":["brand","model","symptom","urgency","customer_address"],"is_mock":false,"source":"CR-0042 業主裁決 2026-06-19"}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='problemcard_policy' AND key='default');
