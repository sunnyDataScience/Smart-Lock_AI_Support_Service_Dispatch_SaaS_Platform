-- ============================================================================
-- Migration 004 — M18 Runtime Config Governance (ADR-0067 Phase 0 / CR-0004 §8)
-- ----------------------------------------------------------------------------
-- 4 tables: config_namespace / config_version / config_rollout / config_audit
-- Seed 6 namespaces (per canonical ddl-migration-001-init.sql §9).
-- No pricing namespace — HD-04 Phase II.
--
-- Strategy: saas schema 在 live DB 不存在（僅 public schema），本 migration：
--   1. CREATE SCHEMA IF NOT EXISTS saas（新建 saas schema）
--   2. 建 saas.tg_block_mutation function（append-only trigger 用）
--   3. 建最小 saas.tenant（config_version.tenant_id FK target；nullable FK →
--      若 saas.tenant 記錄不存在，config_version 仍可建 tenant_id=NULL 的
--      global config）
--   4. 建 4 個 M18 config 表 + index + trigger + seed
--
-- NOTE — saas.tenant 為最小骨架表（id, name, created_at），不含完整 canonical
-- schema（locale/tenant_status/updated_at + trigger）。原因：完整 saas.* 需
-- C5 schema 命名遷移裁決（CR-0004 §1 D-C5）後統一補齊；本波次僅需 FK target
-- 存在即可。後續 C5 migration 補齊所有欄位（ADD COLUMN IF NOT EXISTS）。
--
-- dual-mount note (HD-03)：public.system_config 完全保留（不動）。
-- 本 migration 僅建新 saas.* 表，現行 config_service.py 路徑不受影響。
--
-- Idempotent (CREATE … IF NOT EXISTS / DO $$ pg_constraint check $$ style)。
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/004-config-m18.sql
-- ============================================================================

-- 1. saas schema
CREATE SCHEMA IF NOT EXISTS saas;

-- 2. append-only trigger function（saas.config_audit 使用）
CREATE OR REPLACE FUNCTION saas.tg_block_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'append-only table — mutation blocked (% on %)', TG_OP, TG_TABLE_NAME;
END;
$$;

-- 3. 最小 saas.tenant（config_version.tenant_id FK target）
--    只建必要欄位；C5 migration 補齊完整 canonical schema。
CREATE TABLE IF NOT EXISTS saas.tenant (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 3b. Seed dev/test default tenant (00000000-…-0001) — FK target for test runs.
--     Production tenants are created via onboarding; this is dev seed only.
INSERT INTO saas.tenant (id, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'demo-tenant')
ON CONFLICT (id) DO NOTHING;

-- 4a. config_namespace
CREATE TABLE IF NOT EXISTS saas.config_namespace (
  code             text PRIMARY KEY,
  description      text,
  json_schema      jsonb NOT NULL,
  owner_role_codes text[] NOT NULL DEFAULT '{}'
);

-- 4b. config_version
CREATE TABLE IF NOT EXISTS saas.config_version (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid REFERENCES saas.tenant(id),      -- nullable = global config
  namespace         text NOT NULL REFERENCES saas.config_namespace(code),
  key               text NOT NULL,
  value             jsonb NOT NULL,
  state             text NOT NULL DEFAULT 'draft'
                        CHECK (state IN ('draft','rolling_out','active','retired','rolled_back')),
  parent_version_id uuid REFERENCES saas.config_version(id),
  created_by        uuid NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  activated_at      timestamptz
);

-- At most one active version per (tenant, namespace, key)
-- NOTE: partial unique index on nullable column — two NULLs are distinct in PG
--       so (NULL, ns, key) never conflicts; tenant_id=NULL = global config.
CREATE UNIQUE INDEX IF NOT EXISTS config_one_active
  ON saas.config_version(tenant_id, namespace, key)
  WHERE state = 'active';

CREATE INDEX IF NOT EXISTS config_lookup_idx
  ON saas.config_version(tenant_id, namespace, key, state)
  INCLUDE (value);

-- 4c. config_rollout
CREATE TABLE IF NOT EXISTS saas.config_rollout (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  config_version_id  uuid NOT NULL REFERENCES saas.config_version(id),
  strategy           text NOT NULL CHECK (strategy IN ('canary_5_50_100','instant')),
  current_stage      text NOT NULL CHECK (current_stage IN ('5%','50%','100%','rolled_back')),
  stage_started_at   timestamptz NOT NULL DEFAULT now(),
  next_stage_eta     timestamptz,
  initiator_user_id  uuid NOT NULL,
  approver_user_id   uuid NOT NULL,
  CHECK (initiator_user_id <> approver_user_id)
);

-- 4d. config_audit (append-only)
CREATE TABLE IF NOT EXISTS saas.config_audit (
  id                bigserial PRIMARY KEY,
  tenant_id         uuid,
  config_version_id uuid NOT NULL REFERENCES saas.config_version(id),
  actor_user_id     uuid NOT NULL,
  action            text NOT NULL CHECK (action IN
                        ('draft_created','rollout_started','stage_advanced',
                         'rolled_back','activated','retired')),
  diff              jsonb,
  ts                timestamptz NOT NULL DEFAULT now()
);

-- Append-only triggers (drop first for idempotency)
DROP TRIGGER IF EXISTS config_audit_no_update ON saas.config_audit;
CREATE TRIGGER config_audit_no_update
  BEFORE UPDATE ON saas.config_audit
  FOR EACH ROW EXECUTE FUNCTION saas.tg_block_mutation();

DROP TRIGGER IF EXISTS config_audit_no_delete ON saas.config_audit;
CREATE TRIGGER config_audit_no_delete
  BEFORE DELETE ON saas.config_audit
  FOR EACH ROW EXECUTE FUNCTION saas.tg_block_mutation();

-- ----------------------------------------------------------------------------
-- 5. Seed 6 config namespaces (per canonical §9)
-- NOT seeding 'pricing' namespace — HD-04, Phase II.
-- ----------------------------------------------------------------------------
INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('cancellation_reason_codes',
   '取消費 reason code 字典 (ADR-0102)',
   '{"type":"object","required":["code","label_zh","applies_to"],"properties":{"code":{"type":"string"},"label_zh":{"type":"string"},"applies_to":{"type":"array","items":{"type":"string","enum":["customer","customer_service","technician","system_auto"]}}}}'::jsonb),
  ('cancellation_fee_tiers',
   '取消費 6 階段金額表 (S1/S1_5/S2/S3/S4/S5)',
   '{"type":"object"}'::jsonb),
  ('refund_tier_thresholds',
   '退款 5 tier 金額門檻 (ADR-0040 v2)',
   '{"type":"object","properties":{"L1_max":{"type":"number"},"L2_max":{"type":"number"},"L3_max":{"type":"number"},"L4_max":{"type":"number"}}}'::jsonb),
  ('sla_dispatch',
   '接單 SLA (一般 10 分 / 急件 5 分)',
   '{"type":"object","properties":{"normal_min":{"type":"integer"},"urgent_min":{"type":"integer"}}}'::jsonb),
  ('travel_fee_distance_tiers',
   '車馬費距離級距 (ADR-0041)',
   '{"type":"object"}'::jsonb),
  ('technician_suspension_reasons',
   '師傅停權 reason 字典',
   '{"type":"object"}'::jsonb)
ON CONFLICT (code) DO NOTHING;

COMMENT ON TABLE saas.config_namespace IS 'M18 config namespace registry (ADR-0067 Phase 0)';
COMMENT ON TABLE saas.config_version IS 'M18 versioned config values; state machine: draft→rolling_out|active→retired|rolled_back';
COMMENT ON TABLE saas.config_rollout IS 'M18 rollout records; canary_5_50_100 auto-advance deferred to Phase II (needs scheduler)';
COMMENT ON TABLE saas.config_audit IS 'M18 append-only audit log (ADR-VCH-002 ≥7y retention)';
