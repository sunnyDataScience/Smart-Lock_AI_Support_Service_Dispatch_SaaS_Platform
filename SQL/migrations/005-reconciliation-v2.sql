-- ============================================================================
-- Migration 005 — Reconciliation v2 dual-sign（Track B S2 / FR-0013 / CR-0004 §8）
-- ----------------------------------------------------------------------------
-- 2 tables: saas.reconciliation + saas.settlement
-- dual-sign flow: CSM review (step-1) → ops_manager co-sign (step-2) → settlement INSERT
--
-- Assumptions:
--   - saas schema 已存在（migration 004 建立）
--   - saas.tenant 已存在（migration 004 建立；dev seed 00000000-…-0001 存在）
--   - public.reconciliations / public.settlements 完全保留（dual-mount 過渡）
--
-- Backfill:
--   public.reconciliations → saas.reconciliation（tenant_id 由 JOIN public.technicians 取得）
--   public.settlements → saas.settlement
--   idempotent (ON CONFLICT (id) DO NOTHING)
--
-- SoD backstop at DB layer:
--   recon_dual_sign_distinct CHECK: reviewed_by <> approved_by (兩者非 NULL 時)
--
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/005-reconciliation-v2.sql
-- Idempotent: CREATE TABLE IF NOT EXISTS / indexes IF NOT EXISTS / ON CONFLICT DO NOTHING
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. saas.reconciliation
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.reconciliation (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),
  technician_id       uuid        NOT NULL,
  period_start        timestamptz,
  period_end          timestamptz,
  total_orders        int         NOT NULL DEFAULT 0,
  total_revenue       numeric(12,2) NOT NULL DEFAULT 0,
  platform_fee        numeric(12,2) NOT NULL DEFAULT 0,
  technician_payout   numeric(12,2) NOT NULL DEFAULT 0,
  status              text        NOT NULL DEFAULT 'pending'
                                  CHECK (status IN ('pending','in_review','approved','disputed')),
  -- step-1: CSM review
  reviewed_by         uuid,
  reviewed_at         timestamptz,
  -- step-2: ops_manager co-sign
  approved_by         uuid,
  approved_at         timestamptz,
  note                text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  -- DB 層 SoD backstop：兩個 signer 非 NULL 時必須相異
  CONSTRAINT recon_dual_sign_distinct
    CHECK (reviewed_by IS NULL OR approved_by IS NULL OR reviewed_by <> approved_by)
);

CREATE INDEX IF NOT EXISTS recon_tenant_status_created_idx
  ON saas.reconciliation(tenant_id, status, created_at DESC);

COMMENT ON TABLE saas.reconciliation IS
  'v2 dual-sign 對帳表（FR-0013 / CR-0004 §8 HD-1）; '
  'step-1 reviewed_by(CSM) → step-2 approved_by(ops_manager) → settlement INSERT';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. saas.settlement
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.settlement (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),
  reconciliation_id   uuid        NOT NULL REFERENCES saas.reconciliation(id),
  technician_id       uuid        NOT NULL,
  amount              numeric(12,2) NOT NULL,
  currency            text        NOT NULL DEFAULT 'TWD',
  status              text        NOT NULL DEFAULT 'pending'
                                  CHECK (status IN ('pending','paid','failed')),
  payment_method      text,
  paid_at             timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS settlement_tenant_recon_idx
  ON saas.settlement(tenant_id, reconciliation_id);

COMMENT ON TABLE saas.settlement IS
  'v2 settlement 表（dual-sign co-sign 完成才 INSERT）';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Backfill: public.reconciliations → saas.reconciliation
--    tenant_id 由 JOIN public.technicians ON technician_id 取得
--    status 映射：pending/disputed 直接帶；approved → approved_by 帶入，reviewed_by NULL（legacy 單簽歷史）
--    idempotent via ON CONFLICT (id) DO NOTHING
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO saas.reconciliation (
  id,
  tenant_id,
  technician_id,
  period_start,
  period_end,
  total_orders,
  total_revenue,
  platform_fee,
  technician_payout,
  status,
  reviewed_by,
  reviewed_at,
  approved_by,
  approved_at,
  note,
  created_at
)
SELECT
  r.id,
  t.tenant_id,
  r.technician_id,
  r.period_start,
  r.period_end,
  r.total_orders,
  CAST(r.total_revenue AS numeric(12,2)),
  CAST(r.platform_fee AS numeric(12,2)),
  CAST(r.technician_payout AS numeric(12,2)),
  -- status 映射：legacy 只有 pending/approved/disputed，v2 新增 in_review
  -- legacy approved 直接映射 approved（保留歷史），pending/disputed 直接帶
  r.status,
  -- reviewed_by: legacy 單簽無此欄，保留 NULL 表示 legacy 歷史
  NULL,
  NULL,
  -- approved_by: legacy approved 帶入（單簽歷史）；其他狀態 NULL
  CASE WHEN r.status = 'approved' THEN r.approved_by ELSE NULL END,
  r.approved_at,
  NULL,
  r.created_at
FROM public.reconciliations r
JOIN public.technicians t ON r.technician_id = t.id
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Backfill: public.settlements → saas.settlement
--    tenant_id 由 JOIN saas.reconciliation（剛 backfill 完）取得
--    idempotent via ON CONFLICT (id) DO NOTHING
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO saas.settlement (
  id,
  tenant_id,
  reconciliation_id,
  technician_id,
  amount,
  currency,
  status,
  payment_method,
  paid_at,
  created_at
)
SELECT
  s.id,
  sr.tenant_id,
  s.reconciliation_id,
  s.technician_id,
  CAST(s.amount AS numeric(12,2)),
  COALESCE(s.currency, 'TWD'),
  COALESCE(s.status, 'pending'),
  s.payment_method,
  s.paid_at,
  s.created_at
FROM public.settlements s
JOIN saas.reconciliation sr ON s.reconciliation_id = sr.id
ON CONFLICT (id) DO NOTHING;
