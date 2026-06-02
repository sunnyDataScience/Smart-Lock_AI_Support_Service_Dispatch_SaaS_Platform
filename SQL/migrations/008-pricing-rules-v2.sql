-- ============================================================================
-- Migration 008 — Pricing Rules v2（Track B S4 / CR-0004 §8 C3 / ADR-0046）
-- ----------------------------------------------------------------------------
-- 路徑 C 混合過渡：saas.price_rule（tenant-scoped）
--   + saas.change_request_type_dim（canonical type registry）
--   + saas.change_request（governance 審計軌跡，每次 pricing mutation 並寫）
--
-- 設計決策：
--   - change_request.created_by 用 plain uuid NOT NULL，無 FK（saas.user_account 不存在）
--     比照 dispute.filed_by / reconciliation.reviewed_by 的 actor-from-auth 設計。
--   - change_request_approval 表本波次省略（approval workflow Phase II M18 收斂時補）。
--   - Phase II：pricing 納入 M18 staged rollout namespace（config_m18 governance）。
--
-- Backfill:
--   public.price_rules → saas.price_rule
--     float → numeric(12,2) CAST；ON CONFLICT (id) DO NOTHING
--
-- Assumptions:
--   - saas schema 已存在（migration 004 建立）
--   - saas.tenant 已存在（migration 004 建立；dev seed 00000000-…-0001 存在）
--   - public.price_rules 完全保留（dual-mount 過渡；不動 legacy）
--
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/008-pricing-rules-v2.sql
-- Idempotent: CREATE TABLE IF NOT EXISTS / indexes IF NOT EXISTS / ON CONFLICT DO NOTHING
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. saas.price_rule（mirror public.price_rules + numeric 型別對齊）
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.price_rule (
  id           uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid          NOT NULL REFERENCES saas.tenant(id),
  brand        text          NOT NULL,
  lock_type    text          NOT NULL,
  difficulty   text,
  base_price   numeric(12,2) NOT NULL DEFAULT 0,
  labor_cost   numeric(12,2) NOT NULL DEFAULT 0,
  parts_cost   numeric(12,2) NOT NULL DEFAULT 0,
  modifiers    jsonb,
  is_active    boolean       NOT NULL DEFAULT true,
  created_at   timestamptz   NOT NULL DEFAULT now(),
  updated_at   timestamptz   NOT NULL DEFAULT now()
);

-- 複合 index：tenant 過濾 + is_active + brand + lock_type 分頁/查詢
CREATE INDEX IF NOT EXISTS price_rule_tenant_active_brand_idx
  ON saas.price_rule(tenant_id, is_active, brand, lock_type);

COMMENT ON TABLE saas.price_rule IS
  'v2 tenant-scoped pricing rules（Track B S4 / CR-0004 §8 C3 / ADR-0046）; '
  'decimal 欄位 numeric(12,2) 對齊；mutation 需並寫 saas.change_request 審計軌跡; '
  'Phase II: 納入 M18 staged rollout namespace（config_m18 governance）。';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. saas.price_rule updated_at 自動更新 trigger
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION saas.price_rule_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'tg_price_rule_updated_at'
      AND tgrelid = 'saas.price_rule'::regclass
  ) THEN
    CREATE TRIGGER tg_price_rule_updated_at
      BEFORE UPDATE ON saas.price_rule
      FOR EACH ROW EXECUTE FUNCTION saas.price_rule_set_updated_at();
  END IF;
END;
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. saas.change_request_type_dim（canonical type registry，PK = code）
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.change_request_type_dim (
  code        text         PRIMARY KEY,
  category    text         NOT NULL,
  description text         NOT NULL
);

COMMENT ON TABLE saas.change_request_type_dim IS
  'Canonical change request type registry（ADR-0046）; '
  'PK = code；seed 六種標準類型；新類型 INSERT 前需 ADR 評審。';

-- Seed 六種 canonical type（冪等 ON CONFLICT (code) DO NOTHING）
INSERT INTO saas.change_request_type_dim (code, category, description) VALUES
  ('pricing_rule',          'pricing',      '計價規則異動（base_price / labor_cost / modifiers）'),
  ('rbac',                  'governance',   'RBAC 角色權限異動'),
  ('sla',                   'governance',   'SLA 服務水準協議異動'),
  ('template',              'operations',   '作業範本（SOP / 通知）異動'),
  ('contract_instance',     'legal',        '合約實例建立或終止'),
  ('cancellation_reason',   'operations',   '取消原因新增或停用')
ON CONFLICT (code) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. saas.change_request（governance 審計軌跡）
--
-- 注意：created_by 為 plain uuid NOT NULL，無 FK——saas.user_account 不存在於 live DB；
--   actor id 來自認證 header（X-Initiator），比照 dispute.filed_by / reconciliation.reviewed_by
--   的無 FK 設計（auth system 為外部邊界）。
--
-- Phase II：change_request_approval 表（approval workflow / dual-sign）
--   待 config-m18 M18 staged rollout namespace 收斂時補建。本波次省略以保持精簡。
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.change_request (
  id             uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid         NOT NULL REFERENCES saas.tenant(id),
  type_code      text         NOT NULL REFERENCES saas.change_request_type_dim(code),
  state          text         NOT NULL DEFAULT 'draft'
                              CHECK (state IN ('draft', 'pending_approval', 'approved',
                                               'rejected', 'effective', 'retired')),
  payload_diff   jsonb        NOT NULL,
  effective_date date,
  reason         text,
  -- created_by: plain uuid（無 FK）—— actor from auth（X-Initiator header）
  created_by     uuid         NOT NULL,
  created_at     timestamptz  NOT NULL DEFAULT now(),
  updated_at     timestamptz  NOT NULL DEFAULT now()
);

-- 複合 index：tenant + type + state 倒序分頁
CREATE INDEX IF NOT EXISTS change_request_tenant_type_state_idx
  ON saas.change_request(tenant_id, type_code, state, created_at DESC);

COMMENT ON TABLE saas.change_request IS
  'Governance 審計軌跡（ADR-0046）; '
  'pricing_rule mutation 每次並寫一筆；'
  'state: draft/pending_approval/approved/rejected/effective/retired; '
  'created_by: plain uuid（無 FK），actor from auth; '
  'Phase II：change_request_approval 表（dual-sign approval workflow）待 M18 收斂時補建。';

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Backfill: public.price_rules → saas.price_rule
--    已有 tenant_id 直接帶；float → numeric(12,2) CAST；ON CONFLICT (id) DO NOTHING
--    注意：live DB 目前 0 rows，backfill 為安全兜底
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO saas.price_rule (
  id,
  tenant_id,
  brand,
  lock_type,
  difficulty,
  base_price,
  labor_cost,
  parts_cost,
  modifiers,
  is_active,
  created_at,
  updated_at
)
SELECT
  pr.id,
  pr.tenant_id,
  pr.brand,
  pr.lock_type,
  pr.difficulty,
  CAST(pr.base_price AS numeric(12,2)),
  CAST(pr.labor_cost AS numeric(12,2)),
  CAST(COALESCE(pr.parts_cost, 0.0) AS numeric(12,2)),
  pr.modifiers,
  COALESCE(pr.is_active, true),
  COALESCE(pr.created_at, NOW()),
  COALESCE(pr.updated_at, NOW())
FROM public.price_rules pr
ON CONFLICT (id) DO NOTHING;
