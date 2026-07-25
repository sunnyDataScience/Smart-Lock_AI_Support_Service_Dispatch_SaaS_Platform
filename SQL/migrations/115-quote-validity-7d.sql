-- 115-quote-validity-7d.sql
-- CR-0181：報價有效期一般/急件統一 7 天（0723 會議決議＋業主 0725 裁決「都改七天、expire 保留」）
--
-- 落庫：品牌庫（lock-ai-db；saas.* schema）
--
-- 背景：054 把 BR-M04-05 的 14/3 種進 saas.config_version 全域 active row——
--   quote_engine_service._validity_days() 先讀此值，DB 有值時 code fallback（本輪已改 7/7）
--   完全被覆蓋。只改 code 不動 DB = 已套 054 的環境（本機/雲端）行為不變。
--
-- 作法：namespace 防呆 upsert（未套 054 的庫單檔定向套用不炸 FK；089/090 有前例）→
--   retire 舊值的 active row → 補插 7/7 active row。與 054 同途徑直寫（繞過 M18
--   draft→rollout 治理），留痕靠本檔＋schema_migrations 登錄。冪等：value 已為
--   7/7 時 UPDATE 不中、INSERT 因 active row 存在而跳過。
--
-- 生效：_validity_days 走 read_global_value 直查 DB（不經 cache），套用後即時生效，
--   不需重佈。（confirm_token TTL 上限 48h→7d 是 code 常數，仍需重佈 api 才生效。）

INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('quote_validity_policy',
   '報價有效期天數（CR-0181 業主裁決：一般/急件統一 7；原 CR-0044/BR-M04-05 為 14/3）',
   '{"type":"object","properties":{"normal_days":{"type":"number"},"urgent_days":{"type":"number"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

UPDATE saas.config_version
   SET state = 'retired'
 WHERE tenant_id IS NULL AND namespace = 'quote_validity_policy' AND key = 'default'
   AND state = 'active'
   AND value <> '{"normal_days":7,"urgent_days":7}'::jsonb;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'quote_validity_policy', 'default',
       '{"normal_days":7,"urgent_days":7}'::jsonb,
       'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version
   WHERE tenant_id IS NULL AND namespace = 'quote_validity_policy' AND key = 'default'
     AND state = 'active');

UPDATE saas.config_namespace
   SET description = '報價有效期天數（CR-0181 業主裁決：一般/急件統一 7；原 CR-0044/BR-M04-05 為 14/3）'
 WHERE code = 'quote_validity_policy';
