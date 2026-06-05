-- ============================================================================
-- 025-tech-ap-statements.sql — FR-0045 Phase II MVP: Technician AP Statement
-- ============================================================================
-- 目的：師傅月結 statement（per tech per month）— self-service 查詢 + dispute window。
--
-- 與 CR-0012 saas.settlement / monthly_settlement_batch 互補：
--   - settlement = 個別 reconciliation 的撥款記錄
--   - technician_statement = 該技師月度匯總（gross / 扣除 / net）給技師看
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.technician_statement (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),
  technician_id       uuid        NOT NULL,

  -- 期間
  period_year         integer     NOT NULL,
  period_month        integer     NOT NULL CHECK (period_month BETWEEN 1 AND 12),

  -- 金額拆解（依 §1 Scope）
  total_completed_orders integer  NOT NULL DEFAULT 0,
  gross_amount        numeric(12,2) NOT NULL DEFAULT 0,    -- 完工 WO 累計
  travel_fee_deduction numeric(12,2) NOT NULL DEFAULT 0,   -- 車馬費扣除 (ADR-0041)
  cash_collection_deduction numeric(12,2) NOT NULL DEFAULT 0,  -- 代收抵扣
  dispute_hold_amount numeric(12,2) NOT NULL DEFAULT 0,    -- 暫扣爭議金額
  other_deductions    numeric(12,2) NOT NULL DEFAULT 0,
  net_amount          numeric(12,2) NOT NULL DEFAULT 0,    -- = gross - 各扣除

  -- 狀態機
  status              text        NOT NULL DEFAULT 'draft' CHECK (status IN (
    'draft',            -- 系統產生未送
    'pending_review',   -- 待主管核准
    'disputed',         -- 技師舉報異議 (dispute window 內)
    'approved',         -- 主管核准
    'paid',             -- 匯款執行
    'rejected'          -- 主管拒絕（退回 draft 修）
  )),

  -- dispute window
  dispute_window_ends_at timestamptz NULL,    -- 通常 statement 送達後 7 天
  disputed_at         timestamptz NULL,
  dispute_reason      text        NULL,

  -- 雙簽 audit
  reviewed_by         uuid        NULL,
  reviewed_at         timestamptz NULL,
  paid_at             timestamptz NULL,

  notes               text        NULL,
  created_at          timestamptz NOT NULL DEFAULT NOW(),
  updated_at          timestamptz NOT NULL DEFAULT NOW(),

  -- 同技師同月唯一
  UNIQUE(tenant_id, technician_id, period_year, period_month)
);

CREATE INDEX IF NOT EXISTS tech_stmt_tenant_period_idx
  ON saas.technician_statement(tenant_id, period_year DESC, period_month DESC);

CREATE INDEX IF NOT EXISTS tech_stmt_tech_idx
  ON saas.technician_statement(technician_id, period_year DESC, period_month DESC);

CREATE INDEX IF NOT EXISTS tech_stmt_status_idx
  ON saas.technician_statement(tenant_id, status, created_at DESC);

COMMENT ON TABLE saas.technician_statement IS
  'FR-0045 Technician AP Statement：師傅月結匯總（gross/deductions/net）+ '
  '狀態機 (draft→pending_review→disputed|approved→paid) + dispute window。'
  '與 CR-0012 settlement 互補（statement=匯總視角；settlement=個別撥款記錄）';
