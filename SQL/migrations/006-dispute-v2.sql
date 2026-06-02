-- ============================================================================
-- Migration 006 — Dispute v2 dual-sign 狀態機（Track B S2 / FR-0013 / CR-0004 §8）
-- ----------------------------------------------------------------------------
-- 1 table: saas.dispute
-- dual-sign flow: CSM review (step-1) → ops_manager co-sign (step-2) → resolved
-- status 狀態機: filed → in_review → (mediation) → resolved | escalated | closed_withdrawn
-- reopen lineage: parent_dispute_id 自參照
--
-- Assumptions:
--   - saas schema 已存在（migration 004 建立）
--   - saas.tenant 已存在（migration 004 建立；dev seed 00000000-…-0001 存在）
--   - public.disputes 完全保留（dual-mount 過渡；DROP legacy 延 P4）
--
-- Backfill:
--   public.disputes → saas.dispute
--   tenant_id 由 JOIN public.users ON filed_by = users.id 取得
--   status 映射：rejected→resolved, closed→resolved, under_review→in_review；其餘同名直帶
--   sla_deadline 缺則 filed_at + 60d
--   idempotent (ON CONFLICT (id) DO NOTHING)
--
-- SoD backstop at DB layer:
--   dispute_dual_sign_distinct CHECK: reviewed_by <> cosigned_by (兩者非 NULL 時)
--
-- HD-4 resolution_amount 負值 DGS cascade（ADR-0061/FR-0014）：
--   本波次僅記錄 resolution_amount 於 saas.dispute；
--   負值 → DGS/refund 5-tier cascade 標 follow-up，不實作（Phase II）。
--
-- 60d escalation cron（AC-03）：
--   Phase II Cloud Scheduler（不接 cron，helper 函式 _escalate_overdue_disputes() 已在 service 層留存）。
--
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/006-dispute-v2.sql
-- Idempotent: CREATE TABLE IF NOT EXISTS / indexes IF NOT EXISTS / ON CONFLICT DO NOTHING
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. saas.dispute
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.dispute (
  id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid        NOT NULL REFERENCES saas.tenant(id),
  work_order_id        uuid,
  invoice_id           uuid,
  filed_by             uuid        NOT NULL,
  -- dispute_type 5-enum（對齊 FR-0013 / legacy API enum）
  dispute_type         text        NOT NULL
                                   CHECK (dispute_type IN (
                                     'pricing','quality','warranty',
                                     'cancellation_fee','settlement'
                                   )),
  -- status 狀態機 canonical enum（HD-2）
  status               text        NOT NULL DEFAULT 'filed'
                                   CHECK (status IN (
                                     'filed','in_review','mediation',
                                     'resolved','escalated','closed_withdrawn'
                                   )),
  description          text,
  evidence             jsonb,
  -- step-1: CSM review 提案
  proposed_resolution  text,
  -- step-2: 最終結論
  resolution           text,
  resolution_amount    numeric(12,2),
  -- step-1: CSM reviewer（first signer）
  reviewed_by          uuid,
  reviewed_at          timestamptz,
  -- step-2: ops_manager co-signer（second signer）
  cosigned_by          uuid,
  cosigned_at          timestamptz,
  -- escalation
  escalated_to         text,
  escalated_at         timestamptz,
  -- reopen lineage（AC-05）
  parent_dispute_id    uuid        REFERENCES saas.dispute(id),
  filed_at             timestamptz NOT NULL DEFAULT now(),
  -- SLA deadline = filed_at + 60d（INSERT 時算，see trigger below）
  sla_deadline         timestamptz,
  resolved_at          timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  -- DB 層 SoD backstop：兩個 signer 非 NULL 時必須相異
  CONSTRAINT dispute_dual_sign_distinct
    CHECK (reviewed_by IS NULL OR cosigned_by IS NULL OR reviewed_by <> cosigned_by)
);

CREATE INDEX IF NOT EXISTS dispute_tenant_status_created_idx
  ON saas.dispute(tenant_id, status, created_at DESC);

COMMENT ON TABLE saas.dispute IS
  'v2 dual-sign 爭議表（FR-0013 / CR-0004 §8 HD-1）; '
  'step-1 reviewed_by(CSM) → step-2 cosigned_by(ops_manager) → status:resolved; '
  'HD-4: resolution_amount<0 負值 DGS cascade 留 follow-up（ADR-0061/FR-0014）Phase II; '
  'AC-03: 60d 自動 escalation cron = Phase II Cloud Scheduler.';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. updated_at 自動更新 trigger（仿 migration 001 格式）
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION saas.dispute_set_updated_at()
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
    WHERE tgname = 'tg_dispute_updated_at'
      AND tgrelid = 'saas.dispute'::regclass
  ) THEN
    CREATE TRIGGER tg_dispute_updated_at
      BEFORE UPDATE ON saas.dispute
      FOR EACH ROW EXECUTE FUNCTION saas.dispute_set_updated_at();
  END IF;
END;
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Backfill: public.disputes → saas.dispute
--    tenant_id 由 JOIN public.users ON filed_by = users.id 取得
--    status 映射：rejected→resolved, closed→resolved, under_review→in_review；其餘同名
--    sla_deadline 缺則 filed_at + 60d
--    idempotent via ON CONFLICT (id) DO NOTHING
--    注意：live DB 目前 0 rows（CR-0004 §8 HD-1 confirmed），backfill 為安全兜底
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO saas.dispute (
  id,
  tenant_id,
  work_order_id,
  invoice_id,
  filed_by,
  dispute_type,
  status,
  description,
  evidence,
  resolution,
  resolution_amount,
  filed_at,
  sla_deadline,
  created_at,
  updated_at
)
SELECT
  d.id,
  u.tenant_id,
  d.work_order_id,
  d.invoice_id,
  d.filed_by,
  -- dispute_type 直帶（enum 相同）
  COALESCE(d.dispute_type, 'quality'),
  -- status 映射：legacy 5 enum → canonical 6 enum
  CASE d.status
    WHEN 'rejected'    THEN 'resolved'
    WHEN 'closed'      THEN 'resolved'
    WHEN 'under_review' THEN 'in_review'
    ELSE COALESCE(d.status, 'filed')
  END,
  d.description,
  d.evidence,
  d.resolution,
  CAST(d.resolution_amount AS numeric(12,2)),
  COALESCE(d.filed_at, d.created_at, NOW()),
  -- sla_deadline: 原有值優先，缺則 filed_at + 60d
  COALESCE(d.sla_deadline,
           COALESCE(d.filed_at, d.created_at, NOW()) + INTERVAL '60 days'),
  COALESCE(d.created_at, NOW()),
  COALESCE(d.updated_at, NOW())
FROM public.disputes d
JOIN public.users u ON d.filed_by = u.id
ON CONFLICT (id) DO NOTHING;
