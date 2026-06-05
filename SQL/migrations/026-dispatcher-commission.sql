-- ============================================================================
-- 026-dispatcher-commission.sql — FR-0046 Phase II MVP: Dispatcher Commission
-- ============================================================================
-- 目的：派工人 commission 月結（per new spec P0「分表」原則）。
--
-- 與 FR-0045 technician_statement 同模式但對象不同（dispatcher_user_id），
-- commission 計算依派工數 / 完工率 / 客戶滿意度（M18 config 公式）。
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.dispatcher_commission_statement (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),
  dispatcher_user_id  uuid        NOT NULL,

  period_year         integer     NOT NULL,
  period_month        integer     NOT NULL CHECK (period_month BETWEEN 1 AND 12),

  -- 派工指標
  total_dispatched_orders    integer NOT NULL DEFAULT 0,
  total_completed_orders     integer NOT NULL DEFAULT 0,
  completion_rate_pct        numeric(5,2) NOT NULL DEFAULT 0,    -- 0..100
  avg_customer_satisfaction  numeric(3,1) NULL,                  -- 1.0..5.0

  -- 抽成計算
  base_commission     numeric(12,2) NOT NULL DEFAULT 0,
  performance_bonus   numeric(12,2) NOT NULL DEFAULT 0,
  penalty             numeric(12,2) NOT NULL DEFAULT 0,    -- e.g. 完工率低於 70% 罰款
  net_commission      numeric(12,2) NOT NULL DEFAULT 0,

  -- 狀態機 (同 FR-0045 technician_statement)
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

  UNIQUE(tenant_id, dispatcher_user_id, period_year, period_month)
);

CREATE INDEX IF NOT EXISTS disp_comm_tenant_period_idx
  ON saas.dispatcher_commission_statement(tenant_id, period_year DESC, period_month DESC);

CREATE INDEX IF NOT EXISTS disp_comm_user_idx
  ON saas.dispatcher_commission_statement(dispatcher_user_id, period_year DESC, period_month DESC);

CREATE INDEX IF NOT EXISTS disp_comm_status_idx
  ON saas.dispatcher_commission_statement(tenant_id, status, created_at DESC);

COMMENT ON TABLE saas.dispatcher_commission_statement IS
  'FR-0046 派工人 Commission Statement — base + performance_bonus - penalty = net'
  '；狀態機與 FR-0045 同模式';
