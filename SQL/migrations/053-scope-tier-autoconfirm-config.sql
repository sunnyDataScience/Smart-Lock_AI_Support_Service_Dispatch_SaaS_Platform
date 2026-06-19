-- 053-scope-tier-autoconfirm-config.sql
--
-- WHY（CR-0038 桶4）：兩個 P1 公單缺口的治理參數入 M18 config（不寫死 money/rule，CR-0036 紅線）：
--   - BR-M08-02：scope change「對任何金額一律 pending」→ 改金額分級閘（minor/standard/major）；
--     門檻必須 config 驅動（會議紅線）。
--   - Q063：客戶未回自動結案的時數，亦入 config 可調。
--
-- WHAT：兩個 namespace + 全域 active default（idempotent，仿 CR-0036/0039/0042/0043）。
-- 性質：config seed，ON CONFLICT/NOT EXISTS 可重套。code 讀 read_global_value 帶 fallback，
--   故即使本 migration 未套，行為仍以程式預設運作（_SCOPE_TIER_DEFAULTS / _AUTO_CONFIRM_DEFAULTS）。

-- 1. scope_change_policy（BR-M08-02 分級門檻）
INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('scope_change_policy',
   '現場範圍變更分級門檻（CR-0038 BR-M08-02；major 需主管核准）',
   '{"type":"object","properties":{"minor_max":{"type":"number"},"standard_max":{"type":"number"},"major_pct":{"type":"number"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'scope_change_policy', 'default',
  '{"minor_max":500,"standard_max":2000,"major_pct":0.5}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='scope_change_policy' AND key='default');

-- 2. auto_confirm_policy（Q063 自動結案時數）
INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('auto_confirm_policy',
   '客戶未回自動結案政策（CR-0038 Q063；排除 hold/異常單）',
   '{"type":"object","properties":{"enabled":{"type":"boolean"},"hours":{"type":"number"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'auto_confirm_policy', 'default',
  '{"enabled":true,"hours":48}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='auto_confirm_policy' AND key='default');
