-- ============================================================================
-- 019-monthly-settlement.sql — CR-0012 Stage 1: Manual CSV 月結
-- ============================================================================
-- 業主決議 (CR-batch 2026-06-05):
--   HD-1=Manual CSV 階段化 (V1 純 manual export，無 bank API)
--   HD-2=Cloud Scheduler
--   HD-3=retry 後標 manual_payout
--   HD-4=admin UI 手動確認 + 上傳水單
--   HD-5=flag-driven dispute 排除
--   HD-6=不啟用 escrow
--
-- 本 migration：
--   1. saas.settlement 擴 status enum 加 'csv_exported' / 'manual_paid'
--   2. 加 settled_eligible 欄位 (HD-5 flag-driven dispute 排除)
--   3. 加 receipt_url / manual_paid_at / manual_paid_by audit
--   4. 加 retry_count / last_retry_at (HD-3)
--   5. 新表 saas.monthly_settlement_batch 月結批次審計（含 CSV 匯出記錄）
-- ============================================================================

-- 1. settlement 擴 status enum + audit + flag
ALTER TABLE saas.settlement
  DROP CONSTRAINT IF EXISTS settlement_status_check;

ALTER TABLE saas.settlement
  ADD CONSTRAINT settlement_status_check CHECK (status IN (
    'pending',         -- 月結建立但未撥
    'csv_exported',    -- 已匯出 CSV 給財務
    'paid',            -- bank API 回 paid（V2 才有）
    'manual_paid',     -- HD-4 admin UI 手動標記 + 水單 (HD-3 retry 後路徑)
    'failed'           -- bank API 失敗（V2）
  ));

ALTER TABLE saas.settlement
  ADD COLUMN IF NOT EXISTS settled_eligible boolean NOT NULL DEFAULT true;
  -- HD-5 flag-driven dispute 排除：work_orders.dispute open 時設 false

ALTER TABLE saas.settlement
  ADD COLUMN IF NOT EXISTS receipt_url text NULL;
  -- HD-4 水單 URL（admin UI 上傳到 GCS / 對應 media_files）

ALTER TABLE saas.settlement
  ADD COLUMN IF NOT EXISTS manual_paid_at timestamptz NULL;

ALTER TABLE saas.settlement
  ADD COLUMN IF NOT EXISTS manual_paid_by uuid NULL;
  -- 標 manual_paid 的 admin user_id

ALTER TABLE saas.settlement
  ADD COLUMN IF NOT EXISTS retry_count integer NOT NULL DEFAULT 0;

ALTER TABLE saas.settlement
  ADD COLUMN IF NOT EXISTS last_retry_at timestamptz NULL;
  -- HD-3 retry 後路徑紀錄；MVP 用 0 retry 後直接 manual_paid

-- 2. monthly batch 審計表（HD-2 Cron tick 一次 = 一個 batch）
CREATE TABLE IF NOT EXISTS saas.monthly_settlement_batch (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),
  period_year         integer     NOT NULL,
  period_month        integer     NOT NULL CHECK (period_month BETWEEN 1 AND 12),
  triggered_at        timestamptz NOT NULL DEFAULT NOW(),
  triggered_by        text        NOT NULL,           -- 'cron' / 'manual'
  total_settlements   integer     NOT NULL DEFAULT 0,
  total_amount        numeric(12,2) NOT NULL DEFAULT 0,
  csv_exported_at     timestamptz NULL,
  csv_url             text        NULL,                -- GCS object url
  notes               text        NULL,
  created_at          timestamptz NOT NULL DEFAULT NOW(),
  UNIQUE(tenant_id, period_year, period_month)
);

CREATE INDEX IF NOT EXISTS msb_tenant_period_idx
  ON saas.monthly_settlement_batch(tenant_id, period_year DESC, period_month DESC);

-- 3. settlement 加 batch reference（一個 settlement 隸屬一個 monthly batch）
ALTER TABLE saas.settlement
  ADD COLUMN IF NOT EXISTS monthly_batch_id uuid NULL REFERENCES saas.monthly_settlement_batch(id);

CREATE INDEX IF NOT EXISTS settlement_batch_idx
  ON saas.settlement(monthly_batch_id) WHERE monthly_batch_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS settlement_status_eligible_idx
  ON saas.settlement(tenant_id, status) WHERE settled_eligible = true;

COMMENT ON TABLE saas.monthly_settlement_batch IS
  'CR-0012 Stage 1 月結批次審計：'
  'cron 每月跑一次 → 產 batch row + N 個 settlement → CSV 匯出 → admin 手標 paid';

COMMENT ON COLUMN saas.settlement.settled_eligible IS
  'CR-0012 HD-5 flag-driven dispute 排除：'
  'work_orders.dispute open 時設 false，月結 cron 不納入；'
  'reconciliation_v2 co-sign 時計算';

COMMENT ON COLUMN saas.settlement.status IS
  'pending: 月結 INSERT 但未匯 CSV；'
  'csv_exported: CSV 已給財務；'
  'manual_paid: admin UI 確認財務已撥款 + 上傳水單；'
  'paid/failed: bank API 路徑 (V2 才用)';
