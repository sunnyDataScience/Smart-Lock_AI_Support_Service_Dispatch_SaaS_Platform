-- ============================================================================
-- 027-brand-b2b-statements.sql — FR-0047 Phase II MVP: Brand B2B Settlement
-- ============================================================================
-- 目的：品牌 / 經銷 / 建商 B2B 月結（AR + AP 雙向）。
--
-- 與 FR-0045/0046 同狀態機 pattern 但金額多了 AR 收款方向。
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.brand_b2b_statement (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),

  -- B2B partner
  brand_partner_id    uuid        NOT NULL,    -- 品牌方 (users.id 或 partners table)
  brand_name          text        NOT NULL,
  contract_ref        text        NULL,         -- 合約編號（per ADR-0056 contract attachment）

  period_year         integer     NOT NULL,
  period_month        integer     NOT NULL CHECK (period_month BETWEEN 1 AND 12),

  -- 雙向：AR 品牌付服務費 / AP 平台付品牌 commission
  direction           text        NOT NULL CHECK (direction IN ('AR', 'AP', 'NET')),
  -- NET = 同月 AR/AP 相沖後最終一方向

  -- 服務量指標
  total_service_orders integer    NOT NULL DEFAULT 0,
  total_warranty_claims integer   NOT NULL DEFAULT 0,
  sla_breach_count    integer     NOT NULL DEFAULT 0,

  -- 金額拆解
  ar_service_fee      numeric(12,2) NOT NULL DEFAULT 0,   -- AR: 品牌付服務費
  ap_commission       numeric(12,2) NOT NULL DEFAULT 0,   -- AP: 平台付品牌 commission
  warranty_deduction  numeric(12,2) NOT NULL DEFAULT 0,   -- 保固扣款（從 AP 扣）
  sla_penalty         numeric(12,2) NOT NULL DEFAULT 0,   -- SLA breach 罰款
  net_amount          numeric(12,2) NOT NULL DEFAULT 0,   -- direction='NET' 時：> 0 = 品牌應收；< 0 = 品牌應付
  net_payable_to      text        NULL CHECK (net_payable_to IS NULL OR net_payable_to IN ('brand', 'platform')),

  -- 同 FR-0045 6 狀態機
  status              text        NOT NULL DEFAULT 'draft' CHECK (status IN (
    'draft', 'pending_review', 'disputed', 'approved', 'rejected', 'paid'
  )),
  dispute_window_ends_at timestamptz NULL,
  disputed_at         timestamptz NULL,
  dispute_reason      text        NULL,
  reviewed_by         uuid        NULL,
  reviewed_at         timestamptz NULL,
  paid_at             timestamptz NULL,
  notes               text        NULL,
  created_at          timestamptz NOT NULL DEFAULT NOW(),
  updated_at          timestamptz NOT NULL DEFAULT NOW(),

  -- 同 brand + period + direction 唯一
  UNIQUE(tenant_id, brand_partner_id, period_year, period_month, direction)
);

CREATE INDEX IF NOT EXISTS brand_b2b_tenant_period_idx
  ON saas.brand_b2b_statement(tenant_id, period_year DESC, period_month DESC);

CREATE INDEX IF NOT EXISTS brand_b2b_partner_idx
  ON saas.brand_b2b_statement(brand_partner_id, period_year DESC, period_month DESC);

CREATE INDEX IF NOT EXISTS brand_b2b_status_idx
  ON saas.brand_b2b_statement(tenant_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS brand_b2b_direction_idx
  ON saas.brand_b2b_statement(tenant_id, direction, status);

COMMENT ON TABLE saas.brand_b2b_statement IS
  'FR-0047 品牌 B2B Settlement — AR (品牌付服務費) + AP (平台付 commission) 雙向'
  '；NET direction 同月相沖；同 FR-0045/0046 狀態機 pattern + dispute window';
