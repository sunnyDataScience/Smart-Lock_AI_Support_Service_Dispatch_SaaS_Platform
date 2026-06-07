-- ============================================================================
-- 029-scheduled-reports.sql — scheduled_report 表
-- ============================================================================
-- 目的: 支援 admin 排程定期報表 (週/月報, KPI/Revenue/技師排名), 解
-- /admin/reports/* + /accounting/revenue 排程按鈕 disabled.
--
-- cron 執行留 backend roadmap; 本 migration 只建 schedule registry,
-- listing API 可即時讀取已排程項目, POST 寫入即時 enabled.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS saas.scheduled_report (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid        NOT NULL REFERENCES saas.tenant(id),

  report_type   text        NOT NULL CHECK (report_type IN (
    'kpi', 'revenue', 'technician_ranking', 'settlements'
  )),
  cadence       text        NOT NULL CHECK (cadence IN (
    'weekly', 'monthly', 'quarterly'
  )),

  recipients    jsonb       NOT NULL DEFAULT '[]'::jsonb,  -- 接收 email list
  format        text        NOT NULL DEFAULT 'csv' CHECK (format IN ('csv', 'xlsx', 'pdf')),

  filters       jsonb       NULL,   -- 報表 filter (granularity / period 等)
  next_run_at   timestamptz NULL,
  last_run_at   timestamptz NULL,

  is_active     boolean     NOT NULL DEFAULT true,
  created_by    uuid        NULL,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS scheduled_report_tenant_active_idx
  ON saas.scheduled_report(tenant_id, report_type)
  WHERE is_active = true;

COMMENT ON TABLE saas.scheduled_report IS
  'Admin-managed scheduled report registry. Cron runner (roadmap) reads is_active=true rows.';

COMMIT;
