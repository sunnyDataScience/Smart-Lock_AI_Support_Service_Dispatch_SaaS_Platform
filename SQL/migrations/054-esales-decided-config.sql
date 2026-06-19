-- 054-esales-decided-config.sql
--
-- WHY（CR-0044 / 業主 2026-06-19 裁決）：盤點 20260617 esales 報價資料庫後發現「已決定值」
--   （已知規格 / Accepted default）部分仍寫死，且取消費 code 值與 esales 決定的規格衝突。
--   業主裁決：取消費採 esales（較新 2026-06-03，標 ADR-0102）500/800；已決定值 de-hardcode 入 config
--   （會議「不可寫死 money rules」紅線）。註：區域加價已在 surcharge_rule 表、佣金 0.08 已在
--   dispatch_commission config，本 migration 只處理「仍寫死」的取消費 + 有效期。
--
-- WHAT：
--   1. 取消費 S3/S4：system_config.cancellation.fees 覆寫 300/300 → 500/800（與 esales CNL-S3/S4 對齊）。
--   2. 報價有效期：BR-M04-05 已知規格 14/3 入 M18 config quote_validity_policy（de-hardcode）。
-- 性質：UPDATE + config seed，idempotent（值已正確則不重覆寫；ON CONFLICT/NOT EXISTS 可重套）。

-- ============================================================
-- 1. 取消費 S3/S4 校正（system_config.cancellation.fees）
-- ============================================================
UPDATE system_config
SET config = jsonb_set(
        jsonb_set(config, '{cancellation,fees,s3_cancellation_fee}', '500'::jsonb, false),
        '{cancellation,fees,s4_cancellation_fee}', '800'::jsonb, false),
    version = COALESCE(version, 0) + 1,
    updated_at = now()
WHERE config ? 'cancellation'
  AND COALESCE(config->'cancellation'->'fees'->>'s3_cancellation_fee', '') <> '500';

-- ============================================================
-- 2. 報價有效期入 M18 config（BR-M04-05；de-hardcode quote_engine_service）
-- ============================================================
INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('quote_validity_policy',
   '報價有效期天數（CR-0044；esales BR-M04-05 已知規格 一般14/急件3）',
   '{"type":"object","properties":{"normal_days":{"type":"number"},"urgent_days":{"type":"number"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'quote_validity_policy', 'default',
  '{"normal_days":14,"urgent_days":3}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='quote_validity_policy' AND key='default');
